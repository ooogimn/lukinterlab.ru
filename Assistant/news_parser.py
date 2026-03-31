"""
Сервис для поиска и парсинга новостей из различных источников
НОВАЯ АРХИТЕКТУРА: Прямой HTML-скрапинг без RSS

ЛОГИКА РАБОТЫ:
1. RSS ПОЛНОСТЬЮ ОТМЕНЕН - используется прямой HTML-скрапинг для поиска статей
2. HTML-скрапинг страниц новостей для извлечения ссылок на статьи
3. Сами статьи парсятся через универсальный HTML-парсер (_parse_html_universal)
4. HTML-парсер использует расширенный набор селекторов для работы с любыми сайтами
5. Fallback на newspaper4k только если HTML-парсинг не справился
6. Немедленный парсинг первой найденной статьи, отслеживание спарсенных URL (24 часа)
"""
import logging
import re
import json
import requests
import time
import hashlib
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Попытка импортировать newspaper4k, если не доступен - используем fallback
try:
    from newspaper import Article, Config
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    logger.warning("[WARNING] newspaper4k не установлен. Используется fallback парсинг через BeautifulSoup.")

# Попытка импортировать dateutil для парсинга дат
try:
    from dateutil import parser as date_parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False


"""Сервис для поиска и парсинга новостей из различных источников"""
class NewsParserService:
    """Инициализация сервиса"""
    def __init__(self):
        self.sources = [
            {
                'name': 'VC.ru',
                'type': 'html',
                'base_url': 'https://vc.ru',
                'search_url': 'https://vc.ru/search',
                'article_selector': 'a.content-link',
                'title_selector': '.content-title',
                'enabled': False,  # Отключен - 404 ошибка при поиске
                'language': 'ru'
            },
            {
                'name': 'Hi-Tech Mail.ru',
                'type': 'html',
                'base_url': 'https://hi-tech.mail.ru',
                'search_url': 'https://hi-tech.mail.ru/news/',
                'article_selector': 'a.news-item__link, a.news-item__title, article a',
                'title_selector': '.news-item__title, h2, h3',
                'enabled': True,
                'language': 'ru'
            },
            {
                'name': 'Lifehacker',
                'type': 'html',
                'base_url': 'https://lifehacker.ru',
                'search_url': 'https://lifehacker.ru',
                'article_selector': 'a.post-card__title, article a, .post a',
                'title_selector': '.post-card__title, h2.post-title',
                'enabled': True,
                'language': 'ru'
            },
            {
                'name': 'IXBT.com',
                'type': 'html',
                'base_url': 'https://www.ixbt.com',
                'search_url': 'https://www.ixbt.com/news/',
                'article_selector': 'a.item-news__title, .news-list a',
                'title_selector': '.item-news__title, h2',
                'enabled': False,  # Отключен - не находит статьи (0 результатов)
                'language': 'ru'
            },
        ]
        
        # User-Agent для веб-скрапинга
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # Настройка newspaper4k если доступен
        if NEWSPAPER_AVAILABLE:
            self.newspaper_config = Config()
            self.newspaper_config.browser_user_agent = self.headers['User-Agent']
            self.newspaper_config.request_timeout = 10
            self.newspaper_config.memoize_articles = False  # Отключаем кэширование newspaper (используем Django cache)
    
        # Индекс для циклического перебора источников в рандомном порядке
        self._source_rotation_index = {}
    
    """Проверка и пометка URL как спарсенного (на 24 часа) - ОТКЛЮЧЕНО"""
    def _is_url_parsed_recently(self, url: str) -> bool:
        """
        ОТКЛЮЧЕНО: Механизм противодублирования на 24 часа отключен
        Теперь всегда возвращает False - можно парсить любые статьи
        
        Args:
            url: URL статьи
            
        Returns:
            False (механизм отключен)
        """
        # Механизм противодублирования отключен - всегда разрешаем парсинг
        return False
    
    """Помечает URL как спарсенный (на 24 часа) - ОТКЛЮЧЕНО"""
    def _mark_url_as_parsed(self, url: str):
        """
        ОТКЛЮЧЕНО: Механизм противодублирования на 24 часа отключен
        Метод оставлен для совместимости, но ничего не делает
        
        Args:
            url: URL статьи
        """
        # Механизм противодублирования отключен - ничего не делаем
        pass
    
    """Получение источников в рандомном порядке с циклической ротацией"""
    def _get_shuffled_sources(self) -> List[Dict]:
        """
        Возвращает источники в рандомном порядке с циклической ротацией
        Каждый раз порядок будет другой, но используется ротационный индекс
        для равномерного использования всех источников
        
        Returns:
            Список источников в рандомном порядке
        """
        enabled_sources = [s.copy() for s in self.sources if s.get('enabled', True)]
        
        # Получаем текущий индекс ротации для этой категории источников
        sources_hash = hash(tuple(sorted(s['name'] for s in enabled_sources)))
        rotation_index = self._source_rotation_index.get(sources_hash, 0)
        
        # Перемешиваем источники - каждый раз порядок будет другой
        # Используем комбинацию времени и ротационного индекса для seed
        current_time = int(time.time() * 1000)  # миллисекунды для более уникального seed
        random.seed(current_time + rotation_index)
        shuffled = enabled_sources.copy()
        random.shuffle(shuffled)  # Перемешиваем на месте
        
        # Обновляем индекс ротации для следующего раза
        self._source_rotation_index[sources_hash] = (rotation_index + 1) % max(len(enabled_sources), 1)
        
        logger.info(f"[ROTATION] Источники перемешаны в рандомном порядке (индекс ротации: {rotation_index}):")
        for idx, source in enumerate(shuffled, 1):
            logger.info(f"  {idx}. {source['name']} ({source.get('type', 'unknown')})")
        
        return shuffled
    
    """Поиск новостей с немедленной отдачей результатов (для ускоренного парсинга)"""
    def search_news_streaming(self, category: str, keywords: str = '', min_articles: int = 5, limit: int = 10, category_id: Optional[int] = None) -> List[Dict]:
        """
        Поиск новостей с немедленной отдачей результатов по мере поступления
        НОВАЯ ЛОГИКА: возвращает результаты как только нашли достаточно статей (min_articles)
        
        Args:
            category: Название категории блога
            keywords: Ключевые слова для поиска
            min_articles: Минимальное количество статей для начала парсинга (по умолчанию 5)
            limit: Максимальное количество новостей из каждого источника
            category_id: ID категории блога (для фильтрации источников по категории)
            
        Returns:
            Список новостей с информацией об источнике (как только нашли min_articles)
        """
        query = f"{category} {keywords}".strip()
        
        logger.info(f"[SEARCH] Поиск новостей (streaming): категория='{category}', keywords='{keywords}', category_id={category_id}, min_articles={min_articles}")
        
        # Получаем источники в рандомном порядке
        enabled_sources = self._get_shuffled_sources()
        
        # Фильтруем источники по категории блога, если указана
        if category_id:
            # Оставляем только источники, привязанные к этой категории, или общие источники (без привязки)
            filtered_sources = []
            for source in enabled_sources:
                source_category_id = source.get('category_id')
                if source_category_id is None or source_category_id == category_id:
                    filtered_sources.append(source)
            enabled_sources = filtered_sources
            logger.info(f"[SEARCH] Отфильтровано источников по категории {category_id}: {len(enabled_sources)} источников")
        
        all_news = []
        
        if len(enabled_sources) > 1:
            # Параллельный поиск для нескольких источников
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=min(len(enabled_sources), 4)) as executor:
                future_to_source = {
                    executor.submit(self._search_source, source, query, category, limit): source
                    for source in enabled_sources
                }
                
                completion_count = 0
                for future in as_completed(future_to_source):
                    source = future_to_source[future]
                    source_start = time.time()
                    try:
                        news_items = future.result()
                        elapsed = time.time() - source_start
                        all_news.extend(news_items)
                        completion_count += 1
                        
                        logger.info(f"[OK #{completion_count}] {source['name']}: найдено {len(news_items)} новостей (время: {elapsed:.2f}с)")
                        
                        # КРИТИЧНО: Если нашли достаточно статей - сразу возвращаем результаты
                        # Не ждем остальные источники
                        if len(all_news) >= min_articles:
                            total_time = time.time() - start_time
                            logger.info(f"[FAST] Найдено достаточно статей ({len(all_news)} >= {min_articles}). Прерываю поиск для немедленного парсинга (время: {total_time:.2f}с)")
                            # Отменяем оставшиеся задачи (опционально)
                            # Но уже начатые задачи продолжат выполняться в фоне
                            break
                            
                    except Exception as e:
                        elapsed = time.time() - source_start
                        completion_count += 1
                        logger.error(f"[ERROR #{completion_count}] Ошибка в {source['name']}: {str(e)} (время: {elapsed:.2f}с)")
                        # Продолжаем даже при ошибке, может другие источники уже вернули результаты
                        if len(all_news) >= min_articles:
                            break
        else:
            # Последовательный поиск для одного источника
            for idx, source in enumerate(enabled_sources, 1):
                source_start = time.time()
                try:
                    news_items = self._search_source(source, query, category, limit)
                    elapsed = time.time() - source_start
                    all_news.extend(news_items)
                    logger.info(f"[OK #{idx}] {source['name']}: найдено {len(news_items)} новостей (время: {elapsed:.2f}с)")
                    if len(all_news) >= min_articles:
                        break
                except Exception as e:
                    elapsed = time.time() - source_start
                    logger.error(f"[ERROR #{idx}] Ошибка при поиске в {source['name']}: {str(e)} (время: {elapsed:.2f}с)")
                    continue
        
        # Сортируем по дате (новые первыми)
        all_news.sort(key=lambda x: x.get('published', datetime.min), reverse=True)
        
        logger.info(f"[INFO] Найдено {len(all_news)} статей (достаточно для начала парсинга)")
        
        return all_news
    
    """Поиск новостей по категории и ключевым словам через все источники (НОВАЯ ЛОГИКА)"""
    def search_news(self, category: str, keywords: str = '', limit: int = 10) -> List[Dict]:
        """
        Поиск новостей по категории и ключевым словам через все источники
        НОВАЯ ЛОГИКА: использует streaming-версию для ускорения (возвращает результаты сразу при нахождении достаточного количества)
        
        Args:
            category: Название категории
            keywords: Ключевые слова для поиска
            limit: Максимальное количество новостей из каждого источника (используется для поиска, не для парсинга)
            
        Returns:
            Список новостей с информацией об источнике
        """
        # Используем streaming-версию для ускорения
        # Возвращаем результаты как только нашли 5+ статей
        return self.search_news_streaming(category, keywords, min_articles=5, limit=limit)
    
    """Вспомогательный метод для поиска в одном источнике (для параллелизации)"""
    def _search_source(self, source: Dict, query: str, category: str, limit: int) -> List[Dict]:
        try:
            # Работаем только с HTML источниками
            if source['type'] == 'html':
                news_items = self._search_html(source, query, category, limit)
            else:
                logger.warning(f"[WARNING] Неподдерживаемый тип источника: {source.get('type', 'unknown')} для {source.get('name', 'Unknown')}")
                news_items = []
            
            # Добавляем информацию об источнике
            for item in news_items:
                item['source_name'] = source['name']
                item['source_type'] = source['type']
            
            return news_items
        except Exception as e:
            logger.error(f"[ERROR] Ошибка при поиске в {source['name']}: {str(e)}")
            return []
    
    """Поиск новостей через HTML-скрапинг (ОСНОВНОЙ МЕТОД вместо RSS)"""
    def _search_html(self, source: Dict, query: str, category: str, limit: int) -> List[Dict]:
        """
        Поиск ссылок на статьи через прямой HTML-скрапинг страниц сайтов
        НОВАЯ ЛОГИКА: Полностью заменяет RSS-парсинг на HTML-скрапинг
        
        Args:
            source: Конфигурация источника с типом 'html'
            query: Поисковый запрос
            category: Категория новостей
            limit: Максимальное количество статей
            
        Returns:
            Список статей с информацией (title, link, description, published)
        """
        try:
            # Формируем URL для поиска
            search_url = source.get('search_url', source.get('base_url', ''))
            base_url = source.get('base_url', '')
            
            if not search_url:
                logger.warning(f"[WARNING] URL поиска не найден для источника {source['name']}")
                return []
            
            # Подставляем запрос и категорию в URL если есть плейсхолдеры
            if '{query}' in search_url:
                encoded_query = quote(query, safe='')
                search_url = search_url.format(query=encoded_query, category=category.lower() if category else '')
            elif '{category}' in search_url:
                # Если есть плейсхолдер для категории, используем её
                encoded_category = quote(category.lower() if category else '', safe='')
                search_url = search_url.format(category=encoded_category, query=query if query else '')
            
            logger.info(f"[HTML] Поиск статей на {source['name']}: {search_url}")
            
            # Загружаем HTML страницу (таймаут уменьшен до 5 секунд для ускорения)
            response = requests.get(search_url, headers=self.headers, timeout=5)
            response.raise_for_status()
            
            # Определяем кодировку
            response.encoding = response.apparent_encoding or 'utf-8'
            
            # Парсим HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Получаем селекторы для поиска статей
            article_selector = source.get('article_selector', 'article a, a[href*="/"]')
            title_selector = source.get('title_selector', 'h2, h3, .title')
            
            # Ищем ссылки на статьи
            news_items = []
            seen_links = set()  # Для избежания дубликатов
            
            # Метод 1: Ищем по селектору ссылок
            article_links = soup.select(article_selector)
            
            for link in article_links[:limit * 2]:  # Берем больше, чтобы отфильтровать
                try:
                    # Извлекаем URL
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # Нормализуем URL (относительный -> абсолютный)
                    if href.startswith('/'):
                        href = urljoin(base_url, href)
                    elif not href.startswith('http'):
                        href = urljoin(search_url, href)
                    
                    # Пропускаем дубликаты и нестатейные ссылки
                    if href in seen_links:
                        continue
                    
                    # Фильтруем нестатейные ссылки (главная, контакты, и т.д.)
                    excluded_patterns = ['#', 'javascript:', 'mailto:', '/tag/', '/category/', '/author/', '/page/']
                    if any(pattern in href.lower() for pattern in excluded_patterns):
                        continue
                    
                    # Проверяем, что это похоже на ссылку на статью
                    if not any(indicator in href.lower() for indicator in ['/news/', '/article/', '/post/', '/story/', '/', source['name'].lower().replace(' ', '').replace('.', '').lower()]):
                        continue
                    
                    seen_links.add(href)
                    
                    # Извлекаем заголовок
                    title = ''
                    if title_selector:
                        title_elem = link.find(title_selector) or link.find('h2') or link.find('h3')
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                    
                    if not title:
                        title = link.get_text(strip=True)
                    
                    if not title or len(title) < 10:  # Минимум 10 символов
                        continue
                    
                    # Извлекаем описание (если есть)
                    description = ''
                    parent = link.parent
                    if parent:
                        desc_elem = parent.find(['p', '.description', '.excerpt', '.summary'])
                        if desc_elem:
                            description = desc_elem.get_text(strip=True)[:200]
                    
                    # Извлекаем дату публикации
                        published = timezone.now()
                    date_elem = link.find_parent(['article', 'div', 'li'])
                    if date_elem:
                        date_text = date_elem.get_text()
                        # Простая попытка найти дату в тексте
                        date_pattern = r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})'
                        date_match = re.search(date_pattern, date_text)
                        if date_match:
                            try:
                                from dateutil import parser as date_parser
                                published = date_parser.parse(date_match.group(1))
                            except:
                                pass
                    
                    # Извлекаем изображение
                    image_url = None
                    img = link.find('img') or (link.parent and link.parent.find('img'))
                    if img:
                        img_src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                        if img_src:
                            image_url = self._normalize_image_url(base_url, img_src)
                    
                    news_item = {
                        'title': title[:200],  # Ограничиваем длину
                        'link': href,
                        'description': description,
                        'published': published,
                        'author': '',
                    }
                    
                    if image_url:
                        news_item['image_url'] = image_url
                    
                    news_items.append(news_item)
                    
                    if len(news_items) >= limit:
                        break
                    
                except Exception as e:
                    logger.debug(f"[DEBUG] Ошибка обработки ссылки в {source['name']}: {str(e)}")
                    continue
            
            # Метод 2 (fallback): Если не нашли достаточно - ищем по заголовкам
            if len(news_items) < limit:
                title_elements = soup.select(title_selector)
                for title_elem in title_elements:
                    if len(news_items) >= limit:
                        break
                    
                    link = title_elem.find('a')
                    if not link:
                        link = title_elem.parent.find('a')
                    
                    if link:
                        href = link.get('href', '')
                        if href and href not in seen_links:
                            href = urljoin(base_url, href) if href.startswith('/') else urljoin(search_url, href)
                            if href not in seen_links and 'http' in href:
                                seen_links.add(href)
                                title = title_elem.get_text(strip=True)
                                if title and len(title) > 10:
                                    news_items.append({
                                        'title': title[:200],
                                        'link': href,
                                        'description': '',
                                        'published': timezone.now(),
                                        'author': '',
                                    })
            
            logger.info(f"[OK] HTML-скрапинг {source['name']}: найдено {len(news_items)} статей")
            return news_items[:limit]
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка HTML-скрапинга {source['name']}: {str(e)}")
            return []
    
    """Извлечение изображения из RSS entry с приоритетами"""
    def _extract_image_from_rss_entry(self, entry) -> Optional[str]:
        # Приоритет 1: media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    return media.get('url', '')
        
        # Приоритет 2: links с типом image
        if hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('type', '').startswith('image/'):
                    return link.get('href', '')
        
        # Приоритет 3: enclosure
        if hasattr(entry, 'enclosures'):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    return enclosure.get('href', '')
        
        return None
    
    """Автоматическое определение селекторов через GigaChat"""
    def _auto_detect_selectors_with_gigachat(self, url: str, source_name: str) -> Optional[Dict[str, str]]:
        """
        Автоматически определяет CSS селекторы для поиска статей на сайте через GigaChat
        
        Args:
            url: URL страницы со списком статей (например, https://vc.ru или https://www.ixbt.com/news/)
            source_name: Название источника
            
        Returns:
            Словарь с селекторами: {
                'article_selector': '...',
                'title_selector': '...',
                'search_url': '...',
                'base_url': '...'
            } или None при ошибке
        """
        try:
            from .ai_service import AIService
            from .models import AssistantSettings
            
            # Получаем настройки GigaChat
            settings_obj = AssistantSettings.objects.first()
            if not settings_obj:
                logger.warning("[WARNING] GigaChat настройки не найдены для автоопределения селекторов")
                return None
            
            ai_service = AIService(settings_obj)
            
            # Загружаем HTML страницы
            logger.info(f"[AUTO-DETECT] Загрузка HTML для определения селекторов: {url}")
            html_content = self._fetch_html_with_cloudscraper(url)
            if not html_content:
                logger.warning(f"[WARNING] Не удалось загрузить HTML для {url}")
                return None
            
            # Ограничиваем размер HTML (GigaChat ограничение)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Удаляем ненужные элементы для экономии токенов
            for tag in soup.find_all(['script', 'style', 'noscript', 'iframe', 'svg']):
                tag.decompose()
            
            # Берем только основную часть страницы (первые 15000 символов)
            html_for_ai = str(soup)[:15000]
            
            # Формируем промпт для GigaChat
            prompt = f"""Проанализируй HTML код страницы новостного сайта и определи CSS селекторы для поиска статей.

ТРЕБОВАНИЯ:
1. Найди CSS селектор для ссылок на статьи (article_selector) - должен находить все ссылки на новости/статьи
2. Найди CSS селектор для заголовков статей (title_selector) - должен находить заголовки новостей
3. Определи базовый URL сайта (base_url)
4. Определи URL страницы со списком новостей (search_url) - может быть такой же как base_url

ВАЖНО:
- article_selector должен находить элементы <a> со ссылками на статьи
- title_selector должен находить элементы с заголовками (h1, h2, h3, .title и т.д.)
- Игнорируй ссылки на: меню, навигацию, рекламу, футер, шапку, теги, категории
- Селекторы должны быть максимально специфичными, но не слишком сложными

HTML КОД:
{html_for_ai}

ВЕРНИ ТОЛЬКО JSON в следующем формате (без дополнительных комментариев):
{{
    "article_selector": "CSS селектор для ссылок на статьи",
    "title_selector": "CSS селектор для заголовков",
    "base_url": "https://example.com",
    "search_url": "https://example.com/news/"
}}"""

            # Вызываем GigaChat API
            logger.info(f"[AUTO-DETECT] Отправка запроса в GigaChat для определения селекторов: {source_name}")
            response = ai_service.generate_response(prompt, use_system_prompt=False)
            
            if response.get('error') or not response.get('content'):
                error_msg = response.get('error', 'Unknown error')
                logger.warning(f"[WARNING] GigaChat не смог определить селекторы: {error_msg}")
                return None
            
            # Парсим ответ GigaChat (может быть JSON или текст с JSON)
            content = response.get('content', '').strip()
            
            # Извлекаем JSON из ответа (может быть обернут в markdown или текст)
            json_match = re.search(r'\{[^{}]*"article_selector"[^{}]*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Пробуем найти JSON в обратных кавычках
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = content
            
            # Парсим JSON
            try:
                selectors = json.loads(json_str)
                
                # Валидация результата
                required_keys = ['article_selector', 'title_selector', 'base_url']
                if all(key in selectors for key in required_keys):
                    # Если search_url не указан, используем base_url
                    if 'search_url' not in selectors:
                        selectors['search_url'] = selectors.get('base_url', url)
                    
                    logger.info(f"[OK] GigaChat определил селекторы для {source_name}:")
                    logger.info(f"  - article_selector: {selectors['article_selector']}")
                    logger.info(f"  - title_selector: {selectors['title_selector']}")
                    logger.info(f"  - base_url: {selectors['base_url']}")
                    logger.info(f"  - search_url: {selectors['search_url']}")
                    
                    return selectors
                else:
                    logger.warning(f"[WARNING] GigaChat вернул неполные селекторы: {selectors}")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.warning(f"[WARNING] Не удалось распарсить JSON от GigaChat: {str(e)}")
                logger.debug(f"[DEBUG] Ответ GigaChat: {content[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] Ошибка автоопределения селекторов для {source_name}: {str(e)}", exc_info=True)
            return None
    
    """Автоматическое обновление конфигурации источника"""
    def auto_update_source_config(self, source_name: str, url: str = None) -> bool:
        """
        Автоматически обновляет конфигурацию источника через GigaChat
        
        Args:
            source_name: Название источника (например, 'VC.ru' или 'IXBT.com')
            url: URL для анализа (если None - используется search_url из конфигурации)
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            # Находим источник в списке
            source = None
            for s in self.sources:
                if s['name'] == source_name:
                    source = s
                    break
            
            if not source:
                logger.error(f"[ERROR] Источник '{source_name}' не найден в списке")
                return False
            
            # Определяем URL для анализа
            if not url:
                url = source.get('search_url') or source.get('base_url')
            
            if not url:
                logger.error(f"[ERROR] URL не указан для источника '{source_name}'")
                return False
            
            # Автоматически определяем селекторы
            selectors = self._auto_detect_selectors_with_gigachat(url, source_name)
            
            if not selectors:
                logger.error(f"[ERROR] Не удалось определить селекторы для {source_name}")
                return False
            
            # Обновляем конфигурацию источника
            source['article_selector'] = selectors['article_selector']
            source['title_selector'] = selectors['title_selector']
            source['base_url'] = selectors['base_url']
            source['search_url'] = selectors.get('search_url', selectors['base_url'])
            
            logger.info(f"[OK] Конфигурация источника '{source_name}' успешно обновлена")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка обновления конфигурации источника '{source_name}': {str(e)}")
            return False
    
    """Автоматический поиск новых источников через GigaChat для категории блога"""
    def auto_discover_news_sources(self, category_title: str = None, category_id: int = None, language: str = "ru") -> List[Dict]:
        """
        Автоматически находит новые источники новостей через GigaChat для конкретной категории блога
        
        Args:
            category_title: Название категории блога (например, "КРИПТА", "Майнинг ALEO", "DJANGO")
            category_id: ID категории блога (альтернатива category_title)
            language: Язык источников ('ru', 'en' и т.д.)
            
        Returns:
            Список найденных источников с конфигурацией, привязанных к категории
        """
        try:
            from Blog.models import Category
            from .ai_service import AIService
            from .models import AssistantSettings
            
            # Получаем категорию блога
            category = None
            if category_id:
                try:
                    category = Category.objects.get(pk=category_id, activ=True)
                except Category.DoesNotExist:
                    logger.warning(f"[WARNING] Категория с ID {category_id} не найдена")
                    return []
            elif category_title:
                try:
                    category = Category.objects.get(title=category_title, activ=True)
                except Category.DoesNotExist:
                    logger.warning(f"[WARNING] Категория '{category_title}' не найдена")
                    return []
            else:
                logger.error("[ERROR] Не указана категория (category_title или category_id)")
                return []
            
            # Получаем настройки GigaChat
            settings_obj = AssistantSettings.objects.first()
            if not settings_obj:
                logger.warning("[WARNING] GigaChat настройки не найдены для поиска источников")
                return []
            
            ai_service = AIService(settings_obj)
            
            # Формируем промпт для GigaChat с учетом категории блога
            prompt = f"""Найди популярные русскоязычные новостные сайты, которые публикуют статьи по теме категории блога: "{category.title}".

ВАЖНО:
- Ищи источники, которые публикуют контент именно по теме "{category.title}"
- Источники должны быть доступны без авторизации
- Источники должны иметь открытый доступ к новостям
- Приоритет: крупные медиа, специализированные порталы, авторитетные издания
- Для каждой категории нужны источники, которые публикуют контент именно по этой теме

ТРЕБОВАНИЯ:
1. Найди 5-10 популярных русскоязычных новостных сайтов по теме "{category.title}"
2. Для каждого сайта укажи:
   - Название сайта
   - Базовый URL (base_url)
   - URL страницы со списком новостей по теме "{category.title}" (search_url)
   - Пример URL статьи для тестирования

ВЕРНИ ТОЛЬКО JSON в следующем формате (без дополнительных комментариев):
{{
    "sources": [
        {{
            "name": "Название сайта",
            "base_url": "https://example.com",
            "search_url": "https://example.com/news/category-name/",
            "test_article_url": "https://example.com/news/article-123"
        }}
    ]
}}"""

            # Вызываем GigaChat API
            logger.info(f"[AUTO-DISCOVER] Поиск новых источников для категории '{category.title}' через GigaChat")
            response = ai_service.generate_response(prompt, use_system_prompt=False)
            
            if response.get('error') or not response.get('content'):
                error_msg = response.get('error', 'Unknown error')
                logger.warning(f"[WARNING] GigaChat не смог найти источники: {error_msg}")
                return []
            
            # Парсим ответ GigaChat
            content = response.get('content', '').strip()
            json_match = re.search(r'\{[^{}]*"sources"[^{}]*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = content
            
            try:
                result = json.loads(json_str)
                sources = result.get('sources', [])
                
                # Для каждого источника определяем селекторы
                discovered_sources = []
                for source_info in sources:
                    name = source_info.get('name', '')
                    test_url = source_info.get('test_article_url') or source_info.get('search_url') or source_info.get('base_url')
                    
                    if not test_url:
                        continue
                    
                    logger.info(f"[AUTO-DISCOVER] Определение селекторов для {name}...")
                    selectors = self._auto_detect_selectors_with_gigachat(test_url, name)
                    
                    if selectors:
                        new_source = {
                            'name': name,
                            'type': 'html',
                            'base_url': selectors['base_url'],
                            'search_url': selectors.get('search_url', selectors['base_url']),
                            'article_selector': selectors['article_selector'],
                            'title_selector': selectors['title_selector'],
                            'enabled': False,  # По умолчанию отключен для тестирования
                            'language': language,
                            'category_id': category.id,  # Привязка к категории блога
                            'category_title': category.title,  # Название категории для удобства
                            'category_slug': category.slug,  # Slug категории
                        }
                        discovered_sources.append(new_source)
                        logger.info(f"[OK] Найден новый источник для категории '{category.title}': {name}")
                    else:
                        logger.warning(f"[WARNING] Не удалось определить селекторы для {name}")
                
                logger.info(f"[OK] Найдено {len(discovered_sources)} новых источников для категории '{category.title}'")
                return discovered_sources
                
            except json.JSONDecodeError as e:
                logger.warning(f"[WARNING] Не удалось распарсить JSON от GigaChat: {str(e)}")
                logger.debug(f"[DEBUG] Ответ GigaChat: {content[:500]}")
                return []
                
        except Exception as e:
            logger.error(f"[ERROR] Ошибка поиска новых источников: {str(e)}", exc_info=True)
            return []
    
    """Выбор источника с максимальными просмотрами/рейтингом"""
    def get_best_source(self, news_items: List[Dict]) -> Optional[Dict]:
        """
        Выбор источника с максимальными просмотрами/рейтингом
        
        Args:
            news_items: Список новостей с информацией об источниках
            
        Returns:
            Лучшая новость с информацией об источнике
        """
        if not news_items:
            return None
        
        # Получаем статистику источников из базы данных
        from .models import NewsSource
        
        source_ratings = {}
        for news in news_items:
            source_name = news.get('source_name', 'Unknown')
            source_url = news.get('link', '')
            
            if source_name not in source_ratings:
                try:
                    news_source = NewsSource.objects.filter(
                        source_name=source_name
                    ).first()
                    
                    if news_source:
                        rating = news_source.rating
                    else:
                        news_source = NewsSource.objects.create(
                            source_url=source_url,
                            source_name=source_name,
                            source_type=news.get('source_type', 'rss'),
                            rating=1.0
                        )
                        rating = 1.0
                    
                    source_ratings[source_name] = rating
                except Exception as e:
                    logger.warning(f"[WARNING] Ошибка получения статистики источника {source_name}: {str(e)}")
                    source_ratings[source_name] = 1.0
        
        # Сортируем новости по рейтингу источника (приоритет) и дате публикации
        def sort_key(news_item):
            source_name = news_item.get('source_name', 'Unknown')
            rating = source_ratings.get(source_name, 1.0)
            published = news_item.get('published', datetime.min)
            return (-rating, -published.timestamp() if isinstance(published, datetime) else 0)
        
        sorted_news = sorted(news_items, key=sort_key, reverse=True)
        
        best_news = sorted_news[0]
        source_name = best_news.get('source_name', 'Unknown')
        rating = source_ratings.get(source_name, 1.0)
        
        logger.info(f"[BEST] Выбрана лучшая новость: {best_news.get('title', '')[:50]}... из {source_name} (рейтинг: {rating:.2f})")
        
        return best_news
    
    """Парсинг контента статьи (100-200 слов) с retry механизмом БЕЗ кэширования"""
    def parse_article_content(self, url: str, target_words: int = 150, max_retries: int = 3, use_cache: bool = False) -> Tuple[str, Optional[str]]:
        """
        Парсинг контента статьи (100-200 слов) с retry механизмом
        КЭШИРОВАНИЕ ОТКЛЮЧЕНО для предотвращения дубликатов - всегда парсим свежие данные
        
        Args:
            url: URL статьи
            target_words: Целевое количество слов (100-200)
            max_retries: Максимальное количество попыток (по умолчанию 3)
            use_cache: Использовать кэширование (по умолчанию False - отключено)
            
        Returns:
            Tuple (текст статьи, изображение URL)
        """
        # КЭШИРОВАНИЕ ОТКЛЮЧЕНО - всегда парсим свежие данные
        # Это предотвращает дубликаты из-за кэша и обеспечивает актуальность данных
        
        # Используем универсальный метод парсинга (БЕЗ кэша)
        result = self._parse_article(url, target_words=target_words, max_retries=max_retries)
        
        return result
    
    """Полный парсинг контента статьи без ограничения по словам БЕЗ кэширования"""
    def parse_full_article_content(self, url: str, max_retries: int = 3, use_cache: bool = False) -> Tuple[str, Optional[str]]:
        """
        Полный парсинг контента статьи без ограничения по словам
        КЭШИРОВАНИЕ ОТКЛЮЧЕНО для предотвращения дубликатов - всегда парсим свежие данные
        
        Args:
            url: URL статьи
            max_retries: Максимальное количество попыток (по умолчанию 3)
            use_cache: Использовать кэширование (по умолчанию False - отключено)
            
        Returns:
            Tuple (полный текст статьи, изображение URL)
        """
        # КЭШИРОВАНИЕ ОТКЛЮЧЕНО - всегда парсим свежие данные
        # Это предотвращает дубликаты из-за кэша и обеспечивает актуальность данных
        
        # Используем универсальный метод парсинга без ограничения слов (БЕЗ кэша)
        result = self._parse_article(url, target_words=None, max_retries=max_retries)
        
        return result
    
    """Универсальный метод парсинга статьи (ОСНОВНОЙ - с цепочкой fallback)"""
    def _parse_article(self, url: str, target_words: Optional[int] = None, max_retries: int = 3) -> Tuple[str, Optional[str]]:
        """
        УНИВЕРСАЛЬНЫЙ МЕТОД ПАРСИНГА С ЦЕПОЧКОЙ FALLBACK
        
        Приоритет методов:
        1. GigaChat API (интеллектуальный парсинг) - самый точный
        2. Trafilatura (readability алгоритм) - быстрый и качественный
        3. BeautifulSoup (текущий метод) - надежный fallback
        4. Newspaper4k (старый fallback) - на крайний случай
        
        Args:
            url: URL статьи
            target_words: Целевое количество слов (None для полного текста)
            max_retries: Максимальное количество попыток
            
        Returns:
            Tuple (текст статьи, изображение URL)
        """
        for attempt in range(1, max_retries + 1):
            try:
                # ШАГ 1: Загружаем HTML с обходом защиты (Cloudflare)
                html_content = self._fetch_html_with_cloudscraper(url)
                if not html_content:
                    logger.warning(f"[WARNING] Не удалось загрузить HTML для {url}")
                    if attempt < max_retries:
                        time.sleep(attempt * 2)
                        continue
                    return "", None
                
                # ШАГ 2: Пробуем GigaChat API парсинг (самый умный)
                use_gigachat = getattr(settings, 'USE_GIGACHAT_PARSING', True)
                gigachat_fallback = getattr(settings, 'GIGACHAT_PARSING_FALLBACK', True)
                
                if use_gigachat:
                    try:
                        text, image_url = self._parse_with_gigachat_ai(url, html_content, target_words)
                        if text and len(text.split()) >= 30:  # Минимум 30 слов
                            logger.info(f"[OK] GigaChat успешно извлек {len(text.split())} слов из {url[:50]}...")
                            return text, image_url
                    except Exception as e:
                        if not gigachat_fallback:
                            logger.warning(f"[WARNING] GigaChat парсинг обязателен и не удался: {str(e)}")
                            if attempt < max_retries:
                                time.sleep(attempt * 2)
                                continue
                        else:
                            logger.debug(f"[DEBUG] GigaChat парсинг не удался, пробуем fallback: {str(e)}")
                
                # ШАГ 3: Fallback на Trafilatura (readability алгоритм)
                use_trafilatura = getattr(settings, 'USE_TRAFILATURA', True)
                if use_trafilatura:
                    try:
                        text, image_url = self._parse_with_trafilatura(url, html_content, target_words)
                        if text and len(text.split()) >= 30:  # Минимум 30 слов
                            logger.info(f"[OK] Trafilatura успешно извлек {len(text.split())} слов из {url[:50]}...")
                            return text, image_url
                    except Exception as e:
                        logger.debug(f"[DEBUG] Trafilatura парсинг не удался: {str(e)}")
                
                # ШАГ 4: Fallback на текущий метод (BeautifulSoup через _parse_html_universal)
                logger.debug("[FALLBACK] Используется BeautifulSoup парсинг")
                text, image_url = self._parse_html_universal(url, target_words)
                if text and len(text.split()) >= 30:
                    return text, image_url
                
                # ШАГ 5: Последний fallback на newspaper4k
                if NEWSPAPER_AVAILABLE:
                    logger.debug("[FALLBACK] Используется newspaper4k парсинг")
                    try:
                        text, image_url = self._parse_with_newspaper(url, target_words)
                        if text and len(text.split()) >= 30:
                            return text, image_url
                    except Exception as e:
                        logger.debug(f"[DEBUG] Newspaper4k парсинг не удался: {str(e)}")
                
                # Если все методы не сработали, пробуем еще раз
                if attempt < max_retries:
                    wait_time = attempt * 2
                    logger.warning(f"[RETRY #{attempt}] Не удалось извлечь достаточно текста из {url}. Повтор через {wait_time}с...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[ERROR] Не удалось спарсить {url} после {max_retries} попыток всеми методами")
                    return "", None
                
            except Exception as e:
                if attempt < max_retries:
                    wait_time = attempt * 2
                    logger.warning(f"[RETRY #{attempt}] Ошибка парсинга {url}: {str(e)}. Повтор через {wait_time}с...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[ERROR] Не удалось спарсить {url} после {max_retries} попыток: {str(e)}")
                    return "", None
        
        return "", None
    
    """Парсинг статьи через newspaper4k"""
    def _parse_with_newspaper(self, url: str, target_words: Optional[int] = None) -> Tuple[str, Optional[str]]:
        """Парсинг статьи через newspaper4k"""
        try:
            article = Article(url, config=self.newspaper_config)
            article.download()
            article.parse()
            
            text = article.text.strip()
            
            # Обрезаем до нужного количества слов если указано
            if target_words and text:
                words = text.split()
                if len(words) > target_words:
                    words = words[:target_words]
                    text = ' '.join(words)
                    
                    # Находим последнее полное предложение
                    sentence_endings = re.finditer(r'[.!?]\s+', text)
                    last_sentence_end = None
                    for match in sentence_endings:
                        if match.end() <= len(text):
                            last_sentence_end = match.end()
                    
                    if last_sentence_end:
                        text = text[:last_sentence_end].rstrip()
                    else:
                        text = text.rstrip(',;:') + '...'
            
            # Извлекаем изображение (newspaper предоставляет top_image)
            image_url = article.top_image if hasattr(article, 'top_image') and article.top_image else None
            
            # Если не нашли изображение, используем улучшенный метод
            if not image_url:
                image_url = self._extract_image_improved(url, article.html if hasattr(article, 'html') else None)
            
            return text, image_url
            
        except Exception as e:
            logger.warning(f"[WARNING] Ошибка парсинга через newspaper4k: {str(e)}")
            raise
    
    """Загрузка HTML с обходом Cloudflare через cloudscraper"""
    def _fetch_html_with_cloudscraper(self, url: str) -> Optional[str]:
        """
        Загрузка HTML с обходом Cloudflare и защиты от ботов через cloudscraper
        
        Преимущества:
        - Автоматический обход Cloudflare
        - Эмуляция браузера
        - Поддержка cookies и session
        - Обход защиты от ботов
        
        Args:
            url: URL для загрузки
            
        Returns:
            HTML содержимое страницы или None при ошибке
        """
        use_cloudscraper = getattr(settings, 'USE_CLOUDSCRAPER', True)
        
        if use_cloudscraper:
            try:
                import cloudscraper
                
                # Создаем cloudscraper сессию (автоматически обходит Cloudflare)
                scraper = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True
                    }
                )
                
                logger.debug(f"[CLOUDSCRAPER] Загрузка через cloudscraper: {url[:80]}...")
                response = scraper.get(url, timeout=10, headers=self.headers)
                response.raise_for_status()
                
                response.encoding = response.apparent_encoding or 'utf-8'
                return response.text
                
            except ImportError:
                logger.warning("[WARNING] cloudscraper не установлен, используем requests")
            except Exception as e:
                logger.warning(f"[WARNING] Ошибка cloudscraper для {url}: {str(e)}, используем requests")
        
        # Fallback на обычный requests
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            return response.text
        except Exception as e:
            logger.error(f"[ERROR] Ошибка загрузки {url}: {str(e)}")
            return None
    
    """Интеллектуальный парсинг с GigaChat API"""
    def _parse_with_gigachat_ai(self, url: str, html_content: str, target_words: Optional[int] = None) -> Tuple[str, Optional[str]]:
        """
        ИНТЕЛЛЕКТУАЛЬНЫЙ ПАРСИНГ С GIGACHAT API
        
        Использует LLM для понимания структуры страницы и извлечения основного контента.
        Преимущества:
        - Понимает структуру любой страницы без селекторов
        - Извлекает только релевантный контент (игнорирует рекламу, меню и т.д.)
        - Работает с неструктурированным HTML
        - Поддерживает любые сайты без настройки селекторов
        
        Args:
            url: URL статьи
            html_content: HTML содержимое страницы
            target_words: Целевое количество слов (None для полного текста)
            
        Returns:
            Tuple (текст статьи, изображение URL)
        """
        use_gigachat = getattr(settings, 'USE_GIGACHAT_PARSING', True)
        
        if not use_gigachat:
            return None, None
        
        try:
            from .ai_service import AIService
            from Assistant.models import AssistantSettings
            
            # Получаем настройки GigaChat
            settings_obj = AssistantSettings.objects.first()
            if not settings_obj:
                logger.debug("[DEBUG] GigaChat настройки не найдены, пропускаем GigaChat парсинг")
                return None, None
            
            ai_service = AIService(settings_obj)
            
            # Ограничиваем размер HTML для промпта (GigaChat ограничение ~32k токенов)
            # Оставляем только релевантные части: body, article, main
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Удаляем явно ненужные элементы ДО отправки в GigaChat
            unwanted_tags = ["script", "style", "nav", "header", "footer", "aside", 
                            "iframe", "noscript", "svg", "form", "button", "input", 
                            "select", "textarea", "link", "meta"]
            for tag in unwanted_tags:
                for element in soup.find_all(tag):
                    element.decompose()
            
            # Пробуем найти основной контент для ограничения размера
            main_content = soup.find('article') or soup.find('main') or soup.find('body')
            if main_content:
                html_for_ai = str(main_content)[:40000]  # Максимум 40k символов (безопасное ограничение)
            else:
                html_for_ai = str(soup.body)[:40000] if soup.body else html_content[:40000]
            
            # Формируем промпт для GigaChat
            target_text = f" (извлеки ровно {target_words} слов)" if target_words else ""
            
            prompt = f"""Извлеки основной текст статьи из следующего HTML кода.

ТРЕБОВАНИЯ:
1. Извлеки ТОЛЬКО основной текст статьи (заголовок, абзацы, списки)
2. ИГНОРИРУЙ: меню, навигацию, рекламу, комментарии, футер, шапку
3. Сохрани структуру (параграфы, заголовки)
4. Верни ТОЛЬКО текст статьи без HTML тегов
5. Если текст слишком длинный - верни первые {target_words or 500} слов{target_text}

HTML КОД:
{html_for_ai[:35000]}

ВЕРНИ ТОЛЬКО ТЕКСТ СТАТЬИ БЕЗ ДОПОЛНИТЕЛЬНЫХ КОММЕНТАРИЕВ:"""
            
            # Вызываем GigaChat API
            logger.info(f"[GIGACHAT] Интеллектуальный парсинг через GigaChat: {url[:80]}...")
            response = ai_service.generate_response(prompt, use_system_prompt=False)
            
            if response.get('error') or not response.get('content'):
                error_msg = response.get('error', 'Unknown error')
                logger.debug(f"[DEBUG] GigaChat не смог распарсить: {error_msg}")
                return None, None
            
            extracted_text = response.get('content', '').strip()
            
            # Очистка текста от возможных артефактов GigaChat
            # Убираем возможные префиксы типа "Вот текст статьи:" и т.д.
            extracted_text = re.sub(r'^.*?(?=^[А-ЯЁA-Z])', '', extracted_text, flags=re.MULTILINE | re.DOTALL)
            extracted_text = re.sub(r'\s+', ' ', extracted_text)
            extracted_text = extracted_text.strip()
            
            # Проверяем минимальную длину
            if not extracted_text or len(extracted_text.split()) < 30:
                logger.debug(f"[DEBUG] GigaChat вернул слишком короткий текст: {len(extracted_text.split())} слов")
                return None, None
            
            # Обрезка до нужного количества слов
            if target_words and extracted_text:
                words = extracted_text.split()
                if len(words) > target_words:
                    words = words[:target_words]
                    extracted_text = ' '.join(words)
                    
                    # Обрезаем до последнего предложения
                    sentence_endings = list(re.finditer(r'[.!?]\s+', extracted_text))
                    if sentence_endings:
                        last_sentence_end = sentence_endings[-1].end()
                        extracted_text = extracted_text[:last_sentence_end].rstrip()
            
            # Извлекаем изображение
            image_url = self._extract_image_improved(url, html_content)
            
            logger.info(f"[OK] GigaChat извлек {len(extracted_text.split())} слов из {url[:50]}...")
            
            return extracted_text, image_url
            
        except ImportError as e:
            logger.debug(f"[DEBUG] Ошибка импорта для GigaChat парсинга: {str(e)}")
            return None, None
        except Exception as e:
            logger.warning(f"[WARNING] Ошибка GigaChat парсинга {url}: {str(e)}")
            return None, None
    
    """Парсинг через Trafilatura (readability алгоритм)"""
    def _parse_with_trafilatura(self, url: str, html_content: str, target_words: Optional[int] = None) -> Tuple[str, Optional[str]]:
        """
        Парсинг через Trafilatura (readability алгоритм)
        
        Преимущества:
        - Высокое качество извлечения контента
        - Автоматическое удаление рекламы и навигации
        - Быстрая работа
        - Поддержка множества сайтов
        
        Args:
            url: URL статьи
            html_content: HTML содержимое страницы
            target_words: Целевое количество слов (None для полного текста)
            
        Returns:
            Tuple (текст статьи, изображение URL)
        """
        use_trafilatura = getattr(settings, 'USE_TRAFILATURA', True)
        
        if not use_trafilatura:
            return None, None
        
        try:
            import trafilatura
            
            logger.debug(f"[TRAFILATURA] Парсинг через trafilatura: {url[:80]}...")
            
            # Извлекаем текст через trafilatura
            text = trafilatura.extract(
                html_content, 
                include_comments=False, 
                include_tables=False,
                include_links=False,
                output_format='plaintext'
            )
            
            if not text or len(text.strip()) < 100:
                logger.debug(f"[DEBUG] Trafilatura вернул слишком короткий текст: {len(text) if text else 0} символов")
                return None, None
            
            # Очистка текста
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            # Обрезаем до нужного количества слов
            if target_words:
                words = text.split()
                if len(words) > target_words:
                    words = words[:target_words]
                    text = ' '.join(words)
                    
                    # Обрезаем до последнего предложения
                    sentence_endings = list(re.finditer(r'[.!?]\s+', text))
                    if sentence_endings:
                        last_sentence_end = sentence_endings[-1].end()
                        text = text[:last_sentence_end].rstrip()
            
            # Извлекаем изображение
            image_url = self._extract_image_improved(url, html_content)
            
            logger.info(f"[OK] Trafilatura извлек {len(text.split())} слов из {url[:50]}...")
            
            return text, image_url
            
        except ImportError:
            logger.debug("[DEBUG] trafilatura не установлен, пропускаем")
            return None, None
        except Exception as e:
            logger.debug(f"[DEBUG] Ошибка trafilatura парсинга {url}: {str(e)}")
            return None, None
    
    """Универсальный HTML-парсинг статей (FALLBACK МЕТОД)"""
    def _parse_html_universal_fallback(self, html_content: str, target_words: Optional[int] = None) -> Tuple[str, Optional[str]]:
        """
        Fallback парсинг через BeautifulSoup (используется когда GigaChat/Trafilatura не справились)
        
        Args:
            html_content: HTML содержимое страницы
            target_words: Целевое количество слов (None для полного текста)
            
        Returns:
            Tuple (текст статьи, изображение URL)
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Удаляем ненужные элементы
            unwanted_tags = ["script", "style", "nav", "header", "footer", "aside", "iframe", 
                           "noscript", "svg", "form", "button", "input", "select", "textarea"]
            for tag in unwanted_tags:
                for element in soup.find_all(tag):
                    element.decompose()
            
            # Расширенный набор селекторов для поиска основного контента
            content_selectors = [
                'article .article-content',
                'article .post-content',
                'article .entry-content',
                'article .article-body',
                '[itemprop="articleBody"]',
                'article',
                '[role="article"]',
                'main',
            ]
            
            content = None
            for selector in content_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        text_preview = element.get_text(strip=True)[:500]
                        if len(text_preview) > 200:
                            content = element
                            break
                except:
                    continue
            
            if not content:
                content = soup.find('body')
            
            if not content:
                return "", None
            
            # Извлекаем текст
            paragraphs = []
            for p in content.find_all(['p', 'div', 'h1', 'h2', 'h3']):
                text_p = p.get_text(strip=True)
                if text_p and len(text_p) > 20:
                    paragraphs.append(text_p)
            
            if not paragraphs:
                text = content.get_text(separator=' ', strip=True)
            else:
                text = ' '.join(paragraphs)
            
            # Очистка текста
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            # Обрезка до нужного количества слов
            if target_words and text:
                words = text.split()
                if len(words) > target_words:
                    words = words[:target_words]
                    text = ' '.join(words)
                    
                    sentence_endings = list(re.finditer(r'[.!?]\s+', text))
                    if sentence_endings:
                        last_sentence_end = sentence_endings[-1].end()
                        text = text[:last_sentence_end].rstrip()
            
            return text, None
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка fallback парсинга: {str(e)}")
            return "", None
    
    """Универсальный HTML-парсинг статей (ОСНОВНОЙ МЕТОД)"""
    def _parse_html_universal(self, url: str, target_words: Optional[int] = None) -> Tuple[str, Optional[str]]:
        """
        Универсальный HTML-парсинг статей через BeautifulSoup
        Использует расширенный набор селекторов для извлечения контента с различных сайтов
        
        Args:
            url: URL статьи
            target_words: Целевое количество слов (None для полного текста)
            
        Returns:
            Tuple (текст статьи, изображение URL)
        """
        try:
            # Таймаут уменьшен до 8 секунд для ускорения парсинга
            response = requests.get(url, headers=self.headers, timeout=8)
            response.raise_for_status()
            
            # Определяем кодировку
            response.encoding = response.apparent_encoding or 'utf-8'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Удаляем ненужные элементы
            unwanted_tags = ["script", "style", "nav", "header", "footer", "aside", "iframe", 
                           "noscript", "svg", "form", "button", "input", "select", "textarea"]
            for tag in unwanted_tags:
                for element in soup.find_all(tag):
                    element.decompose()
            
            # Расширенный набор селекторов для поиска основного контента
            # Приоритетные селекторы (от самых специфичных к общим)
            content_selectors = [
                # Специфичные для популярных CMS и сайтов
                'article .article-content',
                'article .post-content',
                'article .entry-content',
                'article .article-body',
                'article .post-body',
                'article .content-wrapper',
                'article .text-content',
                '[itemprop="articleBody"]',  # Schema.org
                '[role="article"] .content',
                'main article',
                '.article article',
                '.post article',
                
                # Общие селекторы статьи
                'article',
                '[role="article"]',
                
                # Специфичные классы контента
                '.article-content',
                '.post-content',
                '.entry-content',
                '.article-body',
                '.post-body',
                '.content-body',
                '.text-content',
                '.post-text',
                '.article-text',
                '.story-body',
                '.story-content',
                '.news-content',
                '.news-body',
                
                # Основные области
                'main',
                '[role="main"]',
                '.main-content',
                '.main',
                
                # Общие классы контента
                '.content',
                '.body-content',
                '.entry',
                '.post',
            ]
            
            content = None
            selected_selector = None
            
            # Пробуем найти контент по селекторам
            for selector in content_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        # Проверяем, что элемент содержит достаточно текста (минимум 200 символов)
                        text_preview = element.get_text(strip=True)[:500]
                        if len(text_preview) > 200:
                            content = element
                            selected_selector = selector
                            logger.debug(f"[SELECTOR] Найден контент по селектору: {selector}")
                            break
                except Exception as e:
                    logger.debug(f"[DEBUG] Ошибка селектора {selector}: {str(e)}")
                    continue
            
            # Если контент не найден - используем body, но очищаем от мусора
            if not content:
                logger.warning(f"[WARNING] Контент не найден по селекторам для {url}, использую body")
                content = soup.find('body')
                if content:
                    # Удаляем явно ненужные блоки из body
                    unwanted_in_body = content.find_all(['nav', 'header', 'footer', 'aside', 
                                                         'form', 'div', 'section'], 
                                                        class_=re.compile(r'(menu|sidebar|footer|header|nav|ad|advertisement|promo|social)', re.I))
                    for element in unwanted_in_body:
                        element.decompose()
            
            if not content:
                logger.error(f"[ERROR] Не удалось найти контент на странице {url}")
                return "", None
            
            # Дополнительная очистка контента от рекламы и навигации
            # Удаляем элементы с классами, содержащими рекламу, меню и т.д.
            unwanted_patterns = [
                re.compile(r'(ad|advertisement|banner|promo|sponsor|social-share|share-buttons|related|similar|comments|author-box)', re.I),
                re.compile(r'(menu|nav|sidebar|footer|header)', re.I),
            ]
            
            for element in content.find_all(['div', 'section', 'aside']):
                classes = ' '.join(element.get('class', []))
                if any(pattern.search(classes) for pattern in unwanted_patterns):
                    element.decompose()
            
            # Извлекаем текст с сохранением структуры (параграфы)
            paragraphs = []
            for p in content.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text_p = p.get_text(strip=True)
                if text_p and len(text_p) > 20:  # Минимум 20 символов в параграфе
                    paragraphs.append(text_p)
            
            # Если параграфы не найдены - используем весь текст
            if not paragraphs:
                text = content.get_text(separator=' ', strip=True)
            else:
                text = ' '.join(paragraphs)
            
            # Очистка текста
            text = re.sub(r'\s+', ' ', text)  # Множественные пробелы в один
            text = re.sub(r'\n\s*\n', '\n', text)  # Множественные переносы строк
            text = text.strip()
            
            # Обрезаем до нужного количества слов если указано
            if target_words and text:
                words = text.split()
                if len(words) > target_words:
                    words = words[:target_words]
                    text = ' '.join(words)
                    
                    # Находим последнее полное предложение
                    sentence_endings = list(re.finditer(r'[.!?]\s+', text))
                    if sentence_endings:
                        last_sentence_end = sentence_endings[-1].end()
                        text = text[:last_sentence_end].rstrip()
                    else:
                        text = text.rstrip(',;:') + '...'
            
            # Извлекаем изображение универсальным методом
            image_url = self._extract_image_improved(url, str(soup))
            
            if selected_selector:
                logger.debug(f"[HTML] Контент извлечен через селектор '{selected_selector}': {len(text)} символов")
            
            return text, image_url
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[ERROR] Ошибка HTTP при парсинге {url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[ERROR] Ошибка HTML-парсинга {url}: {str(e)}", exc_info=True)
            raise
    
    """Парсинг статьи через BeautifulSoup (fallback для обратной совместимости)"""
    def _parse_with_beautifulsoup(self, url: str, target_words: Optional[int] = None) -> Tuple[str, Optional[str]]:
        """Парсинг статьи через BeautifulSoup (fallback - вызывает универсальный метод)"""
        return self._parse_html_universal(url, target_words)
    
    """Улучшенное извлечение изображения с приоритетами"""
    def _extract_image_improved(self, url: str, html: Optional[str] = None) -> Optional[str]:
        """
        Улучшенное извлечение изображения с приоритетами:
        1. Open Graph og:image
        2. Twitter Card twitter:image
        3. Первое изображение из статьи
        4. Первое изображение на странице
        """
        if not html:
            return None
        
        try:
            soup = BeautifulSoup(html, 'html.parser') if isinstance(html, str) else html
            
            # Приоритет 1: Open Graph og:image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']
                return self._normalize_image_url(url, image_url)
            
            # Приоритет 2: Twitter Card twitter:image
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                image_url = twitter_image['content']
                return self._normalize_image_url(url, image_url)
            
            # Приоритет 3: Первое изображение из статьи
            article = soup.find('article') or soup.find('main')
            if article:
                img = article.find('img')
                if img:
                    image_url = img.get('src') or img.get('data-src')
                    if image_url:
                        return self._normalize_image_url(url, image_url)
            
            # Приоритет 4: Первое изображение на странице
            img = soup.find('img')
            if img:
                image_url = img.get('src') or img.get('data-src')
                if image_url:
                    return self._normalize_image_url(url, image_url)
            
            return None
            
        except Exception as e:
            logger.warning(f"[WARNING] Ошибка извлечения изображения: {str(e)}")
            return None
    
    """Нормализация URL изображения (относительный -> абсолютный)"""
    def _normalize_image_url(self, base_url: str, image_url: str) -> str:
        """Нормализация URL изображения (относительный -> абсолютный)"""
        if not image_url:
            return None
        
        # Убираем пробелы и переносы строк
        image_url = image_url.strip()
        
        # Если уже абсолютный URL
        if image_url.startswith('http://') or image_url.startswith('https://'):
            return image_url
        
        # Если относительный URL
        if image_url.startswith('/'):
            parsed_url = urlparse(base_url)
            return f"{parsed_url.scheme}://{parsed_url.netloc}{image_url}"
        
        # Иначе - относительный путь
        return urljoin(base_url, image_url)
    
    """Скачивание изображения с retry механизмом"""
    def download_image(self, image_url: str, max_retries: int = 3, timeout: int = 10) -> Optional[bytes]:
        """
        Скачивание изображения с retry механизмом
        
        Args:
            image_url: URL изображения
            max_retries: Максимальное количество попыток
            timeout: Таймаут запроса в секундах
            
        Returns:
            Байты изображения или None
        """
        for attempt in range(max_retries):
            try:
                response = requests.get(image_url, headers=self.headers, timeout=timeout, stream=True)
                response.raise_for_status()
                
                # Проверяем Content-Type
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    logger.warning(f"[WARNING] URL не является изображением: {content_type}")
                    return None
                
                # Проверяем размер (макс 10MB)
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > 10 * 1024 * 1024:
                    logger.warning(f"[WARNING] Изображение слишком большое: {content_length} байт")
                    return None
                
                # Скачиваем изображение
                image_data = response.content
                
                # Проверяем минимальный размер (хотя бы 100 байт)
                if len(image_data) < 100:
                    logger.warning(f"[WARNING] Изображение слишком маленькое: {len(image_data)} байт")
                    return None
                
                logger.info(f"[OK] Изображение скачано: {len(image_data)} байт из {image_url}")
                return image_data
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"[WARNING] Ошибка скачивания изображения {image_url} (попытка {attempt + 1}/{max_retries}): {str(e)}. Повтор через {wait_time} сек...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[ERROR] Ошибка скачивания изображения {image_url} после {max_retries} попыток: {str(e)}")
        
        return None
    
    """Группировка новостей по источникам"""
    def get_news_by_source(self, news_items: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Группировка новостей по источникам
        
        Args:
            news_items: Список новостей с информацией об источниках
            
        Returns:
            Словарь {название_источника: [список_новостей]}
        """
        grouped = {}
        for item in news_items:
            source_name = item.get('source_name', 'Unknown')
            if source_name not in grouped:
                grouped[source_name] = []
            grouped[source_name].append(item)
        return grouped
    
    """Получение статистики по источникам"""
    def get_source_statistics(self, news_items: List[Dict]) -> Dict[str, Dict]:
        """
        Получение статистики по источникам
        
        Args:
            news_items: Список новостей с информацией об источниках
            
        Returns:
            Словарь {название_источника: {'count': количество, 'percentage': процент}}
        """
        stats = {}
        total = len(news_items)
        
        for item in news_items:
            source_name = item.get('source_name', 'Unknown')
            source_type = item.get('source_type', 'unknown')
            
            if source_name not in stats:
                stats[source_name] = {
                    'count': 0,
                    'type': source_type,
                    'percentage': 0.0
                }
            stats[source_name]['count'] += 1
        
        # Рассчитываем проценты
        for source_name in stats:
            stats[source_name]['percentage'] = (stats[source_name]['count'] / total * 100) if total > 0 else 0.0
        
        # Сортируем по количеству (по убыванию)
        return dict(sorted(stats.items(), key=lambda x: x[1]['count'], reverse=True))
    
    """Вывод информации об источниках в консоль (для отладки)"""
    def print_source_info(self, news_items: List[Dict]) -> None:
        """
        Вывод информации об источниках в консоль (для отладки)
        
        Args:
            news_items: Список новостей с информацией об источниках
        """
        stats = self.get_source_statistics(news_items)
        
        logger.info("[SOURCE INFO] Статистика по источникам:")
        logger.info(f"  Всего новостей: {len(news_items)}")
        for source_name, data in stats.items():
            logger.info(f"  - {source_name} ({data['type']}): {data['count']} новостей ({data['percentage']:.1f}%)")
    
    """Извлечение ключевых слов из контента"""
    def extract_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """
        Извлечение ключевых слов из контента
        
        Args:
            content: Текст контента
            max_keywords: Максимальное количество ключевых слов
            
        Returns:
            Список ключевых слов
        """
        # Простое извлечение: слова длиннее 4 символов, встречающиеся чаще всего
        words = re.findall(r'\b[а-яА-ЯёЁa-zA-Z]{4,}\b', content.lower())
        
        # Подсчет частоты
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Сортируем по частоте и берем топ
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, freq in sorted_words[:max_keywords]]
        
        return keywords
    
    """Отслеживание производительности источника"""
    def track_source_performance(self, source_name: str, views: int = 0):
        """
        Отслеживание производительности источника
        
        Args:
            source_name: Название источника
            views: Количество просмотров статьи из этого источника
        """
        try:
            from .models import NewsSource
            
            source = NewsSource.objects.filter(source_name=source_name).first()
            if source:
                source.record_usage(views)
                logger.debug(f"[STATS] Источник {source_name}: просмотры={views}, рейтинг={source.rating:.2f}")
            else:
                logger.debug(f"[STATS] Источник {source_name} не найден в БД")
        except Exception as e:
            logger.warning(f"[WARNING] Ошибка отслеживания производительности источника {source_name}: {str(e)}")
