"""
Сервис для генерации статей с использованием шаблонов промптов и GigaChat API
"""
import logging
import time
import re
import base64
from typing import Dict, Any, Optional
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image
import io
import requests
from bs4 import BeautifulSoup

from .models import PromptTemplate, AISchedule, AIGeneratedArticle, TokenUsage, NewsSource
from .ai_service import AIService, GigaChatAPIService
from .token_utils import count_tokens_approx, estimate_prompt_tokens, check_token_limit
from .news_parser import NewsParserService
from .category_rotator import CategoryRotator
from .seo_integration import SEOArticleService
from .search_engines_submitter import SearchEnginesSubmitter
from Blog.models import Post, Category

User = get_user_model()
logger = logging.getLogger(__name__)


def safe_log_text(text: str) -> str:
    """
    Безопасное преобразование текста для логирования в Windows cp1251
    Убирает эмодзи и небезопасные Unicode символы
    """
    if not text:
        return ''
    try:
        # Простой способ: убираем все символы, которые нельзя закодировать в cp1251
        # Сохраняем кириллицу и ASCII
        safe_text = text.encode('cp1251', errors='ignore').decode('cp1251', errors='ignore')
        return safe_text
    except Exception:
        # Если не получилось - возвращаем только ASCII
        try:
            return text.encode('ascii', 'ignore').decode('ascii')
        except Exception:
            return str(text)[:100]  # Ограничиваем длину на случай проблем

"""Класс для генерации статей через GigaChat API с использованием шаблонов промптов"""
class ArticleGeneratorService:
    """Сервис для генерации статей через GigaChat API с использованием шаблонов промптов"""
    
    """Генерация статьи"""
    def __init__(self, schedule: AISchedule = None, prompt_template: PromptTemplate = None):
        """
        Инициализация сервиса генерации
        
        Args:
            schedule: Расписание генерации статей (опционально для тестирования)
            prompt_template: Шаблон промпта (используется если schedule не указан)
        """
        if schedule:
            self.schedule = schedule
            self.prompt_template = schedule.prompt_template
        elif prompt_template:
            self.schedule = None
            self.prompt_template = prompt_template
        else:
            raise ValueError("Необходимо указать либо schedule, либо prompt_template")
        
        # Получаем настройки AI
        from .models import AssistantSettings
        self.assistant_settings = AssistantSettings.objects.first()
        if not self.assistant_settings:
            raise ValueError("Настройки AI не найдены. Создайте AssistantSettings в админ-панели.")
        
        # Инициализируем сервисы
        self.ai_service = AIService(self.assistant_settings)
        self.gigachat_service = GigaChatAPIService(self.assistant_settings)
        self.news_parser = NewsParserService()
        self.category_rotator = CategoryRotator()
        self.seo_service = SEOArticleService()
        self.search_submitter = SearchEnginesSubmitter()
        
        # Получаем или создаем AI пользователя
        self.ai_user = self._get_or_create_ai_user()
        
        # Callback для прогресса генерации
        self.progress_callback = None
        
        # Статистика генерации
        self._generation_stats = {}
        self._tokens_used = {}
        self._usage_data = {}
    
    """Получить или создать пользователя для AI статей"""
    def _get_or_create_ai_user(self):
        """Получить или создать пользователя для AI статей"""
        username = 'ai_assistant'
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            logger.info(f"Создание пользователя {username} для AI статей")
            return User.objects.create_user(
                username=username,
                email='ai@lukinterlab.ru',
                first_name='AI',
                last_name='Ассистент'
            )
    
    """Генерация статьи"""
    def generate_article(self, context_data: Optional[Dict[str, Any]] = None) -> Optional[Post]:
        """
        Генерация одной статьи на основе шаблона промпта
        
        Args:
            context_data: Дополнительные данные для контекста промптов
            
        Returns:
            Созданная статья Post или None в случае ошибки
        """
        start_time = time.time()
        
        try:
            # 0. Ротация категории (умная выборка) или использование переданной
            test_category = context_data.get('category') if context_data else None
            test_category_obj = context_data.get('_category_obj') if context_data else None  # Объект Category (если передан)
            test_keywords = context_data.get('keywords', '') if context_data else ''
            
            # Флаг: использовать ли категорию в контексте промпта
            use_category_in_context = True
            category_for_publication = None
            
            if test_category_obj:
                # Если передан объект Category напрямую
                category_for_publication = test_category_obj
                logger.info(f"[TEST] Используется объект категории из параметров: {category_for_publication.title}")
            elif test_category:
                # Если категория передана как строка - пытаемся найти объект Category
                if isinstance(test_category, str):
                    try:
                        category_for_publication = Category.objects.get(title=test_category)
                        logger.info(f"[TEST] Найдена категория по названию '{test_category}': {category_for_publication.title}")
                    except Category.DoesNotExist:
                        try:
                            # Пробуем найти по slug
                            category_for_publication = Category.objects.get(slug=test_category.lower().replace(' ', '-'))
                            logger.info(f"[TEST] Найдена категория по slug '{test_category}': {category_for_publication.title}")
                        except Category.DoesNotExist:
                            logger.warning(f"[WARNING] Категория '{test_category}' не найдена. Используется fallback.")
                            category_for_publication = None
                elif hasattr(test_category, 'title'):
                    # Если передан объект Category
                    category_for_publication = test_category
                    logger.info(f"[TEST] Используется категория из параметров: {category_for_publication.title}")
            elif self.schedule:
                # Для расписаний - используем ротацию или категорию из расписания
                logger.info("[ROTATE] Выбор категории...")
                category_for_publication = self._rotate_category()
                if not category_for_publication:
                    logger.error("[ERROR] Не удалось выбрать категорию")
                    return None
                logger.info(f"[OK] Выбрана категория: {category_for_publication.title}")
            else:
                # Тестовый режим без категории - используем fallback категорию для публикации, но НЕ в контексте
                logger.info("[TEST] Категория не выбрана, используем fallback категорию для публикации (не в контексте)")
                try:
                    category_for_publication = Category.objects.get(slug='vysoko-intellektualnye-novosti')
                    use_category_in_context = False
                    logger.info(f"[OK] Fallback категория для публикации: {category_for_publication.title}")
                except Category.DoesNotExist:
                    logger.error("[ERROR] Fallback категория 'vysoko-intellektualnye-novosti' не найдена")
                    return None
            
            # Сохраняем выбранную категорию для использования в контексте (только если нужно)
            if use_category_in_context:
                self._selected_category = category_for_publication
            else:
                self._selected_category = None
            
            # Сохраняем категорию для публикации (нужна для режимов парсинга)
            self._category_for_publication = category_for_publication
            
            # 0.1. НОВАЯ СХЕМА: Поиск и парсинг новостей ВСЕГДА если генерируется контент (200-300 слов)
            # Новости парсятся сначала, затем используется для генерации контента, потом из контента генерируется заголовок
            parsed_news = None
            parsed_image_data = None  # Для режима search_and_parse изображений
            
            if self.prompt_template.generate_content:
                # НОВАЯ ЛОГИКА: Всегда парсим новости для генерации контента (200-300 слов)
                logger.info("[SEARCH] Поиск и парсинг новостей (200-300 слов) для генерации контента...")
                
                # Определяем, нужно ли также парсить изображения для режима search_and_parse
                need_image_parsing = (
                    self.prompt_template.generate_image and 
                    self.prompt_template.image_generation_mode == 'search_and_parse'
                )
                
                # Парсим новости (200-300 слов, по умолчанию 250)
                target_words = 250
                parsed_news = self._search_and_parse_news(category_for_publication, test_keywords, target_words=target_words)
                
                # Если режим изображения - search_and_parse, парсим изображения одновременно с новостями
                if need_image_parsing and parsed_news and parsed_news.get('image_url'):
                    try:
                        logger.info(f"[IMAGE] Одновременный поиск изображения из новостей: {parsed_news['image_url']}")
                        img_response = requests.get(parsed_news['image_url'], timeout=10, headers=self.news_parser.headers)
                        if img_response.status_code == 200:
                            content_type = img_response.headers.get('content-type', '')
                            if content_type.startswith('image/'):
                                parsed_image_data = ContentFile(img_response.content)
                                parsed_image_data.name = f"parsed_image_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                logger.info("[OK] Изображение спарсено вместе с новостями")
                    except Exception as e:
                        logger.warning(f"[WARNING] Ошибка парсинга изображения вместе с новостями: {str(e)}")
                
                if parsed_news:
                    word_count = len(parsed_news.get('parsed_text', '').split())
                    logger.info(f"[OK] Найдены новости: {parsed_news.get('title', '')[:50]}... ({word_count} слов)")
                else:
                    logger.warning("[WARNING] Новости не найдены, продолжаем без них")
            else:
                logger.info("[INFO] Поиск новостей не требуется (генерация контента отключена)")
            
            # Подготовка контекста для промптов (с учетом новостей, если они есть)
            # Передаем категорию в контекст только если use_category_in_context=True
            context_category_for_prompt = category_for_publication if use_category_in_context else None
            article_index = context_data.pop('_article_index', 1) if context_data else 1
            context = self._prepare_context(context_data, parsed_news, test_category=context_category_for_prompt, test_keywords=test_keywords, article_index=article_index)
            
            # Сохраняем parsed_image_data для использования в генерации изображений
            if parsed_image_data:
                self._parsed_image_data = parsed_image_data
            else:
                self._parsed_image_data = None
            
            if self.schedule:
                logger.info(f"[START] Начало генерации статьи по расписанию: {self.schedule.name}")
            else:
                logger.info(f"[START] Начало тестовой генерации статьи")
            logger.info(f"[TEMPLATE] Используется шаблон: {self.prompt_template.name}")
            
            # Проверка настроек GigaChat перед генерацией
            # Проверяем наличие хотя бы одного способа авторизации
            has_auth_key = bool(self.assistant_settings.get_gigachat_authorization_key())
            has_old_creds = bool(self.assistant_settings.gigachat_client_id and self.assistant_settings.get_gigachat_client_secret())
            
            if not has_auth_key and not has_old_creds:
                error_msg = "GigaChat не настроен! Настройте AssistantSettings в админ-панели Django."
                logger.error(f"[ERROR] {error_msg}")
                logger.error("[ERROR] Необходимо заполнить одно из:")
                logger.error("[ERROR] 1. gigachat_authorization_key (новый способ авторизации)")
                logger.error("[ERROR] ИЛИ")
                logger.error("[ERROR] 2. gigachat_client_id и gigachat_client_secret (старый способ)")
                raise ValueError(error_msg)
            
            # НОВАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ:
            # 1. Сначала генерируем контент на основе parsed_news
            # 2. Потом генерируем заголовок на основе первых 100 слов контента
            
            # 1. Генерация основного контента (если включено) - ПЕРВЫМ ШАГОМ
            content = None
            title = None  # Заголовок пока неизвестен, будет сгенерирован после контента
            
            if self.prompt_template.generate_content:
                if self.progress_callback:
                    self.progress_callback('content', 'Генерация основного контента...', 20)
                logger.info("[CONTENT] Генерация основного контента на основе parsed_news...")
                content_start = time.time()
                # Передаем временный заголовок (пустой или дефолтный) для генерации контента
                # Заголовок будет сгенерирован позже на основе контента
                content = self._generate_content_by_mode(context, title=None)
                content_time = time.time() - content_start
                self._generation_stats['content'] = {'time': round(content_time, 2)}
                if not content:
                    logger.error("[ERROR] Не удалось сгенерировать контент")
                    return None
            else:
                logger.info("[CONTENT] Генерация контента отключена в шаблоне - элемент исключен из работы")
                # Контент не генерируется, оставляем пустым
                content = ''
            
            # Валидация объема текста (800-1300 слов) - применяется только если контент был сгенерирован
            if self.prompt_template.generate_content:
                word_count = self._count_words(content)
                logger.info(f"[INFO] Контент сгенерирован: {word_count} слов ({len(content)} символов)")
                
                if word_count < 800:
                    logger.warning(f"[WARNING] Контент слишком короткий ({word_count} слов, требуется 800-1300). Перегенерирую...")
                    # Перегенерируем с дополнительным промптом (только для режима AI генерации)
                    if self.prompt_template.content_generation_mode == 'generate':
                        context['min_words'] = 800
                        context['max_words'] = 1300
                        # title еще не сгенерирован, передаем None
                        content = self._generate_content_by_mode(context, title=None, retry=True)
                    else:
                        logger.warning(f"[WARNING] Режим {self.prompt_template.content_generation_mode} не поддерживает перегенерацию. Продолжаем с текущим контентом.")
                    if content:
                        word_count = self._count_words(content)
                        logger.info(f"[INFO] Контент перегенерирован: {word_count} слов")
                    else:
                        logger.error("[ERROR] Не удалось перегенерировать контент")
                        return None
                
                if word_count > 1300:
                    logger.warning(f"[WARNING] Контент слишком длинный ({word_count} слов, требуется 800-1300). Обрезаю до 1300 слов...")
                    content = self._truncate_to_words(content, 1300)
                    word_count = self._count_words(content)
                    logger.info(f"[INFO] Контент обрезан до {word_count} слов")
                
                if word_count < 800 or word_count > 1300:
                    logger.warning(f"[WARNING] Контент не соответствует требованиям: {word_count} слов (требуется 800-1300), но продолжаем...")
            
            # 2. Генерация заголовка на основе первых 100 слов контента (НОВАЯ СХЕМА)
            # Заголовок генерируется ПОСЛЕ контента, используя первые 100 слов
            if self.prompt_template.generate_title:
                if content:
                    # Извлекаем первые 100 слов контента
                    content_first_100_words = self._extract_content_fragment(content, 'first_100_words')
                    
                    # Обновляем контекст для генерации заголовка
                    title_context = {**context, 'content_first_100_words': content_first_100_words}
                    
                    if self.progress_callback:
                        self.progress_callback('title', 'Генерация заголовка из контента...', 45)
                    logger.info("[TITLE] Генерация заголовка на основе первых 100 слов контента...")
                    title_start = time.time()
                    title = self._generate_title_from_content(content_first_100_words, title_context)
                    title_time = time.time() - title_start
                    self._generation_stats['title'] = {'time': round(title_time, 2)}
                    if not title:
                        # Получаем последнюю ошибку для более детального сообщения
                        error_details = getattr(self, '_last_generation_error', None)
                        if error_details and 'credentials not configured' in str(error_details).lower():
                            error_msg = "GigaChat не настроен! Настройте AssistantSettings в админ-панели: заполните gigachat_authorization_key ИЛИ (gigachat_client_id и gigachat_client_secret)"
                        else:
                            error_msg = f"Не удалось сгенерировать заголовок. {error_details if error_details else 'Проверьте логи для деталей.'}"
                        logger.error(f"[ERROR] {error_msg}")
                        raise ValueError(error_msg)
                    logger.info(f"[OK] Заголовок: {title[:50]}...")
                else:
                    logger.warning("[WARNING] Контент отсутствует - заголовок не может быть сгенерирован из контента")
                    # Fallback: генерация заголовка без контента (используя старый метод)
                    if self.progress_callback:
                        self.progress_callback('title', 'Генерация заголовка...', 45)
                    logger.info("[TITLE] Fallback: генерация заголовка без контента...")
                    title = self._generate_title(context)
                    if not title:
                        title = 'Статья без заголовка'
            else:
                logger.info("[TITLE] Генерация заголовка отключена в шаблоне - элемент исключен из работы")
                # Для создания статьи нужен title, используем минимальный дефолт только для сохранения
                title = 'Статья без заголовка'
            
            # 3. Генерация описания для Telegram (автоматически из первых 200 слов контента)
            # Описание генерируется только если есть контент
            description = ''
            if content:
                if self.progress_callback:
                    self.progress_callback('description', 'Генерация описания...', 50)
                logger.info("[DESC] Генерация описания для Telegram (первые 200 слов контента)...")
                desc_start = time.time()
                description = self._generate_description(context, title, content)
                desc_time = time.time() - desc_start
                self._generation_stats['description'] = {'time': round(desc_time, 2)}
            else:
                logger.info("[DESC] Контент отсутствует - описание не генерируется")
            
            # 4. Генерация или загрузка изображения (если включено)
            image_file = None
            image_prompt_used = ""
            if self.prompt_template.generate_image:
                if self.progress_callback:
                    self.progress_callback('image', 'Генерация/поиск изображения...', 70)
                logger.info("[IMAGE] Обработка изображения...")
                image_start = time.time()
                
                # НОВАЯ СХЕМА: Для режима search_and_parse используем уже спарсенное изображение
                if (self.prompt_template.image_generation_mode == 'search_and_parse' and 
                    hasattr(self, '_parsed_image_data') and self._parsed_image_data):
                    logger.info("[IMAGE] Используется уже спарсенное изображение из новостей")
                    image_file = self._parsed_image_data
                    image_prompt_used = f"Изображение из источника: {parsed_news.get('source_name', 'Unknown') if parsed_news else 'Unknown'}"
                else:
                    # Для режима generate или если изображение не было спарсено - используем стандартный метод
                    # Передаем первые 100 слов контента для генерации изображения
                    content_first_100_words = self._extract_content_fragment(content, 'first_100_words') if content else ''
                    image_context = {**context, 'content_first_100_words': content_first_100_words}
                    image_file, image_prompt_used = self._generate_image_by_mode(image_context, title, parsed_news)
                
                image_time = time.time() - image_start
                self._generation_stats['image'] = {'time': round(image_time, 2)}
            else:
                logger.info("[IMAGE] Генерация изображения отключена в шаблоне - элемент исключен из работы")
            
            # 5. Генерация дополнительной секции (если включено и промпт заполнен)
            if self.prompt_template.generate_additional_section and self.prompt_template.additional_section_prompt and self.prompt_template.generate_content and content:
                if self.progress_callback:
                    self.progress_callback('additional', 'Генерация дополнительной секции...', 85)
                logger.info("[ADDITIONAL] Генерация дополнительной секции...")
                additional_start = time.time()
                additional_section = self._generate_additional_section(context, title, content)
                additional_time = time.time() - additional_start
                self._generation_stats['additional_section'] = {'time': round(additional_time, 2)}
                if additional_section:
                    logger.info("[OK] Дополнительная секция сгенерирована")
                    # Сохраняем дополнительную секцию отдельно для отображения
                    if not hasattr(self, '_additional_section'):
                        self._additional_section = {}
                    self._additional_section['html'] = additional_section
                    # Добавляем в конец контента
                    content = content + '\n\n' + additional_section
                else:
                    logger.warning("[WARNING] Не удалось сгенерировать дополнительную секцию")
            elif self.prompt_template.generate_additional_section:
                if not self.prompt_template.additional_section_prompt:
                    logger.info("[ADDITIONAL] Промпт для дополнительной секции не заполнен - пропускаем")
                elif not self.prompt_template.generate_content or not content:
                    logger.info("[ADDITIONAL] Контент не был сгенерирован - дополнительная секция не генерируется")
            
            # 6. Генерация тегов по смыслу (автоматически, если есть контент)
            generated_tags = None
            if content:
                if self.progress_callback:
                    self.progress_callback('tags', 'Генерация тегов...', 90)
                logger.info("[TAGS] Генерация тегов...")
                tags_start = time.time()
                generated_tags = self._generate_tags(context, title, content)
                tags_time = time.time() - tags_start
                self._generation_stats['tags'] = {'time': round(tags_time, 2)}
            
            # 7. Проверка на дубликаты статей
            logger.info("[CHECK] Проверка на дубликаты статей...")
            duplicate_post = Post.objects.filter(title=title, status='published').first()
            if duplicate_post:
                logger.warning(f"[WARNING] Найдена статья с таким же заголовком (ID: {duplicate_post.id}). Добавляю суффикс...")
                # Добавляем суффикс к заголовку
                counter = 1
                new_title = f"{title} ({counter})"
                while Post.objects.filter(title=new_title, status='published').exists():
                    counter += 1
                    new_title = f"{title} ({counter})"
                title = new_title
                logger.info(f"[INFO] Заголовок изменен на: {title}")
            
            # 8. Создание статьи
            if self.progress_callback:
                self.progress_callback('save', 'Сохранение статьи...', 95)
            logger.info("[SAVE] Сохранение статьи...")
            # Для тестирования создаем как черновик, для расписаний - опубликовано
            article_status = 'draft' if not self.schedule else 'published'
            post = Post.objects.create(
                title=title,
                category=category_for_publication,
                content=content,
                description=description,
                author=self.ai_user,
                status=article_status,
                kartinka=image_file,
                faq_data=None,  # FAQ теперь генерируется через дополнительную секцию
                news_source_url=parsed_news.get('link') if parsed_news else None,
                parsed_content=parsed_news.get('parsed_text') if parsed_news else None,
            )
            
            # Добавление тегов
            tags = (self.schedule.tags if self.schedule else '') or self.prompt_template.default_tags or (context_data.get('tags', '') if context_data else '')
            if tags:
                tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                post.tags.add(*tag_list)
            
            # Добавляем сгенерированные теги
            if generated_tags:
                post.tags.add(*generated_tags)
            
            # 9. Применение SEO оптимизации
            logger.info("[SEO] Применение SEO оптимизации...")
            self.seo_service.apply_seo_to_post(post)
            
            # 10. Запись статистики категории
            self.category_rotator.record_publication(category_for_publication, views=0)
            
            # 11. Запись статистики источника новостей
            if parsed_news and parsed_news.get('source_name'):
                self._track_news_source(parsed_news['source_name'], parsed_news.get('link', ''), views=0)
            
            # 12. Сохранение истории генерации
            generation_time = time.time() - start_time
            
            # Получаем ответы AI (если были сохранены)
            ai_responses = getattr(self, '_ai_responses', {})
            
            # Собираем информацию о токенах из всех ответов
            tokens_used = getattr(self, '_tokens_used', {})
            usage_data_dict = getattr(self, '_usage_data', {})
            total_tokens = sum(tokens_used.values())
            
            # Собираем детальную информацию о токенах из usage
            prompt_tokens_total = 0
            completion_tokens_total = 0
            
            # Суммируем токены из всех ответов
            for response_key in ['title', 'description', 'content']:
                if response_key in usage_data_dict:
                    usage = usage_data_dict[response_key]
                    prompt_tokens_total += usage.get('prompt_tokens', 0)
                    completion_tokens_total += usage.get('completion_tokens', 0)
            
            # Записываем использование токенов для мониторинга
            if total_tokens > 0:
                try:
                    usage_data = {
                        'total_tokens': total_tokens,
                        'prompt_tokens': prompt_tokens_total,
                        'completion_tokens': completion_tokens_total if completion_tokens_total > 0 else total_tokens,
                    }
                    text_model = self.schedule.text_model if self.schedule else 'GigaChat-2-Lite'
                    TokenUsage.record_usage(text_model, usage_data)
                except Exception as e:
                    logger.warning(f"Не удалось записать использование токенов: {str(e)}")
            
            # Создаем запись о генерации (сохраняем всегда, даже для тестовых статей)
            try:
                # КРИТИЧНО: Валидация контекста перед сохранением в JSONField
                # Преобразуем все объекты Django в примитивы для предотвращения ошибок JSON сериализации
                sanitized_context = self._sanitize_context_for_json(context)
                
                ai_article = AIGeneratedArticle.objects.create(
                    schedule=self.schedule,  # Может быть None для тестовых статей
                    prompt_template=self.prompt_template,
                    post=post,
                    generated_title=title,
                    generated_description=description,
                    generated_content=content,
                    generated_image_prompt=image_prompt_used,
                    title_prompt_used=self.prompt_template.format_prompt(
                        self.prompt_template.title_prompt, context
                    ) if self.prompt_template.title_prompt else '',
                    description_prompt_used="Автоматически: первые 200 слов из контента",  # Описание генерируется автоматически
                    content_prompt_used=self.prompt_template.format_prompt(
                        self.prompt_template.content_prompt, {**context, 'title': title}
                    ) if self.prompt_template.content_prompt else '',
                    image_prompt_used=image_prompt_used,
                    ai_title_response=ai_responses.get('title', ''),
                    ai_description_response=ai_responses.get('description', ''),
                    ai_content_response=ai_responses.get('content', ''),
                    ai_image_response='',  # Будет заполнено при генерации изображения
                    context_data=sanitized_context,  # Используем очищенный контекст
                    generation_time=generation_time,
                    tokens_used=total_tokens  # Сохраняем общее количество токенов
                )
                logger.info(f"[HISTORY] История генерации сохранена: ID={ai_article.pk}")
            except Exception as e:
                logger.error(f"[ERROR] Не удалось сохранить историю генерации: {str(e)}", exc_info=True)
            
            if self.progress_callback:
                self.progress_callback('completed', 'Генерация завершена', 100)
            
            # Сохраняем общее время генерации
            self._generation_stats['total'] = {'time': round(generation_time, 2)}
            
            # Безопасное логирование заголовка (убираем эмодзи для Windows cp1251)
            safe_title = safe_log_text(post.title) if post.title else ''
            logger.info(f"[OK] Статья успешно создана: {safe_title}")
            logger.info(f"[TIME] Время генерации: {generation_time:.2f} сек")
            
            # 13. Отправка в поисковые системы (только для расписаний, не для тестов)
            if self.schedule:
                logger.info("[SUBMIT] Отправка в поисковые системы...")
                try:
                    self.search_submitter.submit_all(post)
                except Exception as e:
                    logger.warning(f"[WARNING] Ошибка отправки в поисковые системы: {str(e)}")
                
                # Обновление статистики расписания
                self.schedule.total_generated += 1
                self.schedule.last_run = timezone.now()
                self.schedule.save(update_fields=['total_generated', 'last_run'])
            
            safe_title = safe_log_text(post.title) if post.title else ''
            logger.info(f"[OK] Статья полностью готова: {safe_title}")
            return post
            
        except ValueError as ve:
            # ValueError пробрасываем дальше (для конфигурационных ошибок)
            logger.error(f"[ERROR] Ошибка конфигурации: {str(ve)}")
            raise  # Пробрасываем ValueError дальше
        except Exception as e:
            # Все остальные исключения логируем и возвращаем None
            logger.error(f"[ERROR] Ошибка генерации статьи: {str(e)}", exc_info=True)
            return None
    

    """Подготовка контекста для промптов"""
    def _prepare_context(self, additional_context: Optional[Dict[str, Any]] = None, parsed_news: Optional[Dict] = None, test_category=None, test_keywords='', article_index: int = 1) -> Dict[str, Any]:
        """
        Подготовка контекста для промптов
        """
        # Инициализируем пустой контекст
        context = {}
        
        # 2. Получаем категорию (уже выбрана через ротатор или передана для тестирования)
        # Если test_category=None явно передан и _selected_category тоже None,
        # значит категорию НЕ нужно включать в контекст промпта
        selected_cat = getattr(self, '_selected_category', None)
        
        # Если test_category=None и _selected_category=None, категория не в контексте
        if test_category is None and selected_cat is None:
            category_for_context = None
        else:
            # Используем обычную логику: test_category -> _selected_category -> schedule -> template
            category_for_context = test_category or selected_cat or (self.schedule.category if self.schedule else None) or self.prompt_template.default_category
        
        # 3. Базовый контекст с системными переменными
        context.update({
            'category': str(category_for_context.title if category_for_context else ''),
            'keywords': test_keywords or (self.schedule.keywords if self.schedule else '') or '',
            'topic': (self.schedule.context_data.get('topic', '') if self.schedule and self.schedule.context_data else '') or (additional_context.get('topic', '') if additional_context else ''),
            'tone': (self.schedule.context_data.get('tone', 'дружелюбный и экспертный') if self.schedule and self.schedule.context_data else 'дружелюбный и экспертный') or (additional_context.get('tone', 'дружелюбный и экспертный') if additional_context else 'дружелюбный и экспертный'),
        })
        
        # Добавляем спарсенный контент новостей
        # Все источники настроены на русский язык, работаем только с русским
        if parsed_news:
            news_text = parsed_news.get('parsed_text', '')
            news_title = parsed_news.get('title', '')
            
            context['parsed_news_content'] = news_text
            context['news_title'] = news_title
            
            context['news_url'] = parsed_news.get('link', '')
            context['news_source'] = parsed_news.get('source_name', 'Unknown')
            context['news_source_type'] = parsed_news.get('source_type', 'unknown')
            # Статистика по всем источникам
            if 'sources_statistics' in parsed_news:
                context['sources_statistics'] = parsed_news.get('sources_statistics', {})
            if 'total_news_found' in parsed_news:
                context['total_news_found'] = parsed_news.get('total_news_found', 0)
        
        # Добавляем дополнительные данные из расписания (могут быть переопределены)
        if self.schedule and self.schedule.context_data:
            context.update(self.schedule.context_data)
        
        # Добавляем переданные дополнительные данные (ПОСЛЕДНИМИ - переопределяют все предыдущие значения)
        # Это позволяет переопределить системные переменные (topic, category, keywords) из полей формы тестирования
        if additional_context:
            # КРИТИЧНО: Преобразуем объекты Django в примитивы перед добавлением в контекст
            # Это предотвращает ошибки JSON сериализации при сохранении в AIGeneratedArticle.context_data
            sanitized_context = {}
            for key, value in additional_context.items():
                if hasattr(value, '__class__'):
                    # Проверяем, является ли объект моделью Django
                    if hasattr(value, '_meta'):
                        # Модель Django - преобразуем в строку или ID
                        if hasattr(value, 'title'):
                            sanitized_context[key] = str(value.title)
                        elif hasattr(value, 'name'):
                            sanitized_context[key] = str(value.name)
                        elif hasattr(value, 'pk'):
                            sanitized_context[key] = value.pk
                        else:
                            sanitized_context[key] = str(value)
                    else:
                        # Другой объект - преобразуем в строку или оставляем как есть
                        try:
                            import json
                            json.dumps(value)  # Проверяем, можно ли сериализовать
                            sanitized_context[key] = value
                        except (TypeError, ValueError):
                            sanitized_context[key] = str(value)
                else:
                    # Примитивный тип - оставляем как есть
                    sanitized_context[key] = value
            
            context.update(sanitized_context)
            logger.info(f"[CONTEXT] Переопределены значения из формы тестирования: {list(sanitized_context.keys())}")
        
        return context
    
    """Ротация категории (умная выборка)"""
    def _rotate_category(self) -> Optional[Category]:
        """Ротация категории (умная выборка)"""
        return self.category_rotator.get_next_category()
    
    """Поиск и парсинг новостей по категории (НОВАЯ ЛОГИКА: веб-скрапинг, немедленный парсинг первой статьи)"""
    def _search_and_parse_news(self, category: Category, keywords: str = '', target_words: int = 200) -> Optional[Dict]:
        """
        НОВАЯ ЛОГИКА: Поиск и немедленный парсинг первой найденной статьи
        
        Алгоритм:
        1. Поиск статей через веб-скрапинг (источники в рандомном порядке)
        2. Для каждой найденной статьи:
           - Проверка: не была ли уже спарсена в последние 24 часа
           - Немедленный парсинг текста и изображения
           - Если успешно - возвращаем результат и помечаем как спарсенную
           - Если нет - переходим к следующей статье
        3. Цикл продолжается пока не будет успешный парсинг
        
        Args:
            category: Категория для поиска
            keywords: Ключевые слова для поиска
            target_words: Целевое количество слов для парсинга (по умолчанию 200)
        """
        try:
            # Используем русские запросы напрямую без перевода
            search_keywords = keywords or (self.schedule.keywords if self.schedule else '') or category.title
            search_category = category.title
            
            logger.info(f"[SEARCH] Поиск и немедленный парсинг статей: category='{search_category}', keywords='{search_keywords}'")
            
            # Поиск новостей на русском языке (streaming - возвращает результаты как только нашли 5+ статей)
            # Не ждем все источники - начинаем парсить сразу при наличии достаточного количества статей
            # Передаем category_id для фильтрации источников по категории блога
            news_items = self.news_parser.search_news_streaming(
                search_category, 
                search_keywords, 
                min_articles=5, 
                limit=20,
                category_id=category.id if category else None
            )
            
            if not news_items:
                logger.warning("[WARNING] Новости не найдены")
                return None
            
            logger.info(f"[INFO] Найдено {len(news_items)} статей. Начинаю немедленный парсинг первой доступной статьи...")
            
            # Получаем статистику по источникам ДО парсинга
            sources_statistics = self.news_parser.get_source_statistics(news_items)
            
            # НОВАЯ ЛОГИКА: Итерация по статьям с немедленным парсингом (кэш противодублирования отключен)
            parsed_count = 0
            
            for news_item in news_items:
                url = news_item.get('link', '')
                if not url:
                    continue
                
                # КЭШ ПРОТИВОДУБЛИРОВАНИЯ ОТКЛЮЧЕН - парсим все статьи
                
                parsed_count += 1
                logger.info(f"[PARSE #{parsed_count}] Немедленный парсинг статьи: {url[:80]}...")
                
                try:
                    # Немедленный парсинг текста и изображения
                    parsed_text, image_url = self.news_parser.parse_article_content(url, target_words=target_words)
                    
                    # Проверка успешности парсинга
                    if parsed_text and len(parsed_text.strip()) > 100:  # Минимум 100 символов текста
                        word_count = len(parsed_text.split())
                        logger.info(f"[SUCCESS] Статья успешно спарсена: {word_count} слов из {url[:80]}...")
                        
                        # КЭШ ПРОТИВОДУБЛИРОВАНИЯ ОТКЛЮЧЕН - не помечаем URL
                        
                        # Формируем результат
                        result = {
                            'title': news_item.get('title', ''),
                            'link': url,
                            'description': news_item.get('description', ''),
                            'parsed_text': parsed_text,
                            'image_url': image_url or news_item.get('image_url'),
                            'source_name': news_item.get('source_name', 'Unknown'),
                            'source_type': news_item.get('source_type', 'unknown'),
                            'published': news_item.get('published'),
                            # Статистика по всем источникам
                            'sources_statistics': sources_statistics,
                            'total_news_found': len(news_items),
                            'parsed_attempts': parsed_count,
                        }
                        
                        return result
                    else:
                        logger.warning(f"[FAIL] Парсинг не удался: недостаточно текста ({len(parsed_text) if parsed_text else 0} символов)")
                        # Продолжаем поиск следующей статьи
                        continue
                        
                except Exception as e:
                    logger.warning(f"[FAIL] Ошибка парсинга статьи {url[:80]}...: {str(e)}")
                    # Продолжаем поиск следующей статьи
                    continue
            
            # Если все статьи не удалось спарсить
            logger.error(f"[ERROR] Не удалось спарсить ни одну статью из {len(news_items)} найденных")
            logger.error(f"[ERROR] Попыток парсинга: {parsed_count}")
            return None
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка поиска и парсинга новостей: {str(e)}", exc_info=True)
            return None
    
    """Генерация дополнительной секции через GigaChat на основе кастомного промпта"""
    def _generate_additional_section(self, context: Dict[str, Any], title: str, content: str) -> Optional[str]:
        """
        Генерация дополнительной секции через GigaChat на основе кастомного промпта
        
        Args:
            context: Контекст для промптов
            title: Заголовок статьи
            content: Основной контент статьи
            
        Returns:
            HTML строка с дополнительной секцией или None
        """
        try:
            # ПРОВЕРКА: Если промпт пустой - возвращаем None
            if not self.prompt_template.additional_section_prompt or not self.prompt_template.additional_section_prompt.strip():
                logger.warning("[WARNING] Промпт для дополнительной секции не заполнен")
                return None
            
            # Форматируем промпт с переменными
            context_with_content = {**context, 'title': title, 'content': content}
            prompt = self.prompt_template.format_prompt(
                self.prompt_template.additional_section_prompt,
                context_with_content
            )
            
            # Проверяем, что промпт не стал пустым после форматирования
            if not prompt or not prompt.strip():
                logger.error("[ERROR] Промпт для дополнительной секции стал пустым после форматирования")
                return None
            
            logger.info(f"[ADDITIONAL] Промпт: {prompt[:200]}...")
            logger.info(f"[ADDITIONAL] Контекст содержит переменные: {list(context_with_content.keys())}")
            
            # Временно меняем модель
            original_model = self.ai_service.model
            text_model = self.schedule.text_model if self.schedule else 'GigaChat'
            self.ai_service.model = text_model
            
            # Генерируем дополнительную секцию БЕЗ системного промпта чат-бота
            response = self.ai_service.generate_response(prompt, use_system_prompt=False)
            additional_html = response.get('content', '').strip()
            
            # Сохраняем токены
            if 'tokens_used' not in response:
                response['tokens_used'] = response.get('usage', {}).get('total_tokens', 0) if isinstance(response.get('usage'), dict) else 0
            
            if not hasattr(self, '_tokens_used'):
                self._tokens_used = {}
            if not hasattr(self, '_usage_data'):
                self._usage_data = {}
            self._tokens_used['additional_section'] = response.get('tokens_used', 0)
            if 'usage' in response:
                self._usage_data['additional_section'] = response['usage']
            
            # Восстанавливаем модель
            self.ai_service.model = original_model
            
            if additional_html:
                # Очищаем от markdown оберток, если есть
                import re
                # Убираем markdown code blocks
                additional_html = re.sub(r'```html\s*', '', additional_html)
                additional_html = re.sub(r'```\s*', '', additional_html)
                additional_html = additional_html.strip()
                
                logger.info(f"[OK] Дополнительная секция сгенерирована ({len(additional_html)} символов)")
                return additional_html
            else:
                logger.warning("[WARNING] Пустой ответ от AI для дополнительной секции")
                return None
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка генерации дополнительной секции: {str(e)}", exc_info=True)
            return None
    
    """Генерация тегов по смыслу для перелинковки"""
    def _generate_tags(self, context: Dict[str, Any], title: str, content: str) -> list:
        """Генерация тегов по смыслу для перелинковки (3-4 тега)"""
        try:
            # Используем GigaChat для генерации тегов
            tags_prompt = f"""На основе статьи "{title}" и контента создай список из 3-4 самых релевантных тегов.
                Теги должны:
                - Соответствовать теме статьи
                - Быть полезными для перелинковки с другими статьями
                - Включать самые важные и специфические термины
                - Формат: список тегов через запятую (ровно 3-4 тега)
                Только теги, без дополнительного текста."""
            
            # Временно меняем модель
            original_model = self.ai_service.model
            text_model = self.schedule.text_model if self.schedule else 'GigaChat'
            self.ai_service.model = text_model
            
            # Генерируем теги БЕЗ системного промпта чат-бота
            response = self.ai_service.generate_response(tags_prompt, use_system_prompt=False)
            tags_text = response.get('content', '').strip()
            
            # Сохраняем токены
            if 'tokens_used' not in response:
                response['tokens_used'] = response.get('usage', {}).get('total_tokens', 0) if isinstance(response.get('usage'), dict) else 0
            
            if not hasattr(self, '_tokens_used'):
                self._tokens_used = {}
            if not hasattr(self, '_usage_data'):
                self._usage_data = {}
            self._tokens_used['tags'] = response.get('tokens_used', 0)
            if 'usage' in response:
                self._usage_data['tags'] = response['usage']
            
            # Восстанавливаем модель
            self.ai_service.model = original_model
            
            # Парсим теги
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            # Ограничиваем до 4 тегов (3-4 по требованию)
            tags = tags[:4]
            
            logger.info(f"[OK] Сгенерировано тегов: {len(tags)}")
            return tags
            
        except Exception as e:
            logger.error(f"Ошибка генерации тегов: {str(e)}")
            return []
    
    """Отслеживание использования источника новостей"""
    def _track_news_source(self, source_name: str, source_url: str, views: int = 0):
        """Отслеживание использования источника новостей"""
        try:
            source, created = NewsSource.objects.get_or_create(
                source_name=source_name,
                source_url=source_url,
                defaults={
                    'total_views': views,
                    'articles_count': 1,
                    'last_used': timezone.now(),
                    'rating': 0.0,
                }
            )
            
            if not created:
                source.record_usage(views)
            
        except Exception as e:
            logger.error(f"Ошибка отслеживания источника: {str(e)}")
    
    """Извлечение фрагментов контента для использования в промптах"""
    def _extract_content_fragment(self, content: str, fragment_type: str) -> str:
        """
        Универсальное извлечение фрагментов контента
        
        Args:
            content: Полный контент статьи
            fragment_type: 'first_100_words', 'first_200_words', 'first_paragraph'
        
        Returns:
            Извлеченный фрагмент
        """
        if not content:
            return ''
        
        # Убираем HTML теги для извлечения чистого текста
        clean_content = re.sub(r'<[^>]+>', '', content)
        
        if fragment_type == 'first_100_words':
            words = clean_content.split()[:100]
            return ' '.join(words)
        elif fragment_type == 'first_200_words':
            words = clean_content.split()[:200]
            return ' '.join(words)
        elif fragment_type == 'first_paragraph':
            # Первый полный абзац (до точки)
            sentences = re.split(r'[.!?]\s+', clean_content)
            if sentences:
                return sentences[0] + '.' if not sentences[0].endswith('.') else sentences[0]
            return clean_content[:200]
        
        return clean_content[:200]  # Fallback
    
    """Генерация заголовка на основе первых 100 слов контента"""
    def _generate_title_from_content(self, content_first_100_words: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Генерация заголовка на основе первых 100 слов контента (НОВАЯ СХЕМА)
        
        Args:
            content_first_100_words: Первые 100 слов контента
            context: Контекст для промптов
        
        Returns:
            Сгенерированный заголовок или None
        """
        try:
            # ПРОВЕРКА: Если промпт пустой - возвращаем None
            if not self.prompt_template.title_prompt or not self.prompt_template.title_prompt.strip():
                logger.error("[ERROR] Промпт для заголовка пустой, но generate_title=True. Отредактируйте шаблон.")
                return None
            
            # Обновляем контекст: добавляем первые 100 слов контента вместо category/keywords
            title_context = {**context, 'content_first_100_words': content_first_100_words}
            
            # Форматируем промпт с обновленным контекстом
            prompt = self.prompt_template.format_prompt(
                self.prompt_template.title_prompt,
                title_context
            )
            
            # Проверяем, что промпт не стал пустым после форматирования
            if not prompt or not prompt.strip():
                logger.error("[ERROR] Промпт стал пустым после форматирования")
                return None
            
            logger.info(f"[TITLE] Промпт для генерации из контента: {prompt[:200]}...")
            logger.info(f"[TITLE] Используются первые 100 слов контента: {content_first_100_words[:100]}...")
            
            # Проверяем лимит токенов перед отправкой
            text_model = self.schedule.text_model if self.schedule else 'GigaChat'
            estimated_tokens = count_tokens_approx(prompt) + 100  # +100 для ответа
            limit_check = check_token_limit(text_model, estimated_tokens)
            
            if limit_check['will_exceed']:
                logger.warning(
                    f"[WARNING] Превышение лимита токенов для {text_model}. "
                    f"Осталось: {limit_check['remaining']}, требуется: {estimated_tokens}"
                )
            
            # Временно меняем модель на указанную в расписании
            original_model = self.ai_service.model
            self.ai_service.model = text_model
            
            # Генерируем заголовок БЕЗ системного промпта чат-бота
            response = self.ai_service.generate_response(prompt, use_system_prompt=False)
            title = response.get('content', '').strip()
            
            # Проверяем на ошибки
            if response.get('error') or not title:
                error_msg = response.get('error', 'Неизвестная ошибка')
                logger.error(f"[ERROR] Ошибка генерации заголовка: {error_msg}")
                
                # Сохраняем ошибку для передачи наверх
                self._last_generation_error = error_msg
                
                return None
            
            # Сохраняем токены из ответа
            if 'tokens_used' not in response:
                response['tokens_used'] = response.get('usage', {}).get('total_tokens', 0) if isinstance(response.get('usage'), dict) else 0
            
            # Восстанавливаем модель
            self.ai_service.model = original_model
            
            # Очистка заголовка (убираем лишние символы, кавычки и т.д.)
            title = self._clean_text(title)
            
            # Сохраняем ответ AI для истории
            if not hasattr(self, '_ai_responses'):
                self._ai_responses = {}
            self._ai_responses['title'] = response.get('content', '')
            
            # Сохраняем токены для мониторинга
            if not hasattr(self, '_tokens_used'):
                self._tokens_used = {}
            if not hasattr(self, '_usage_data'):
                self._usage_data = {}
            self._tokens_used['title'] = response.get('tokens_used', 0)
            if 'usage' in response:
                self._usage_data['title'] = response['usage']
            
            return title if title else None
            
        except Exception as e:
            logger.error(f"Ошибка генерации заголовка из контента: {str(e)}")
            return None
    
    """Генерация заголовка статьи (старый метод, используется как fallback)"""
    def _generate_title(self, context: Dict[str, Any]) -> Optional[str]:
        """Генерация заголовка статьи (fallback метод)"""
        try:
            # ПРОВЕРКА: Если промпт пустой - возвращаем None
            # Эта проверка нужна, т.к. метод вызывается только если generate_title=True
            if not self.prompt_template.title_prompt or not self.prompt_template.title_prompt.strip():
                logger.error("[ERROR] Промпт для заголовка пустой, но generate_title=True. Отредактируйте шаблон.")
                return None
            
            # Форматируем промпт с контекстом
            prompt = self.prompt_template.format_prompt(
                self.prompt_template.title_prompt,
                context
            )
            
            # Проверяем, что промпт не стал пустым после форматирования
            if not prompt or not prompt.strip():
                logger.error("[ERROR] Промпт стал пустым после форматирования")
                return None
            
            logger.info(f"[TITLE] Промпт для генерации: {prompt[:200]}...")
            logger.info(f"[TITLE] Контекст содержит переменные: {list(context.keys())}")
            
            # Проверяем лимит токенов перед отправкой
            text_model = self.schedule.text_model if self.schedule else 'GigaChat'
            estimated_tokens = count_tokens_approx(prompt) + 100  # +100 для ответа
            limit_check = check_token_limit(text_model, estimated_tokens)
            
            if limit_check['will_exceed']:
                logger.warning(
                    f"[WARNING] Превышение лимита токенов для {text_model}. "
                    f"Осталось: {limit_check['remaining']}, требуется: {estimated_tokens}"
                )
            
            # Временно меняем модель на указанную в расписании
            original_model = self.ai_service.model
            text_model = self.schedule.text_model if self.schedule else 'GigaChat'
            self.ai_service.model = text_model
            
            # Генерируем заголовок БЕЗ системного промпта чат-бота
            # use_system_prompt=False - чтобы использовать только промпт из шаблона
            response = self.ai_service.generate_response(prompt, use_system_prompt=False)
            title = response.get('content', '').strip()
            
            # Проверяем на ошибки
            if response.get('error') or not title:
                error_msg = response.get('error', 'Неизвестная ошибка')
                logger.error(f"[ERROR] Ошибка генерации заголовка: {error_msg}")
                logger.error(f"[ERROR] Ответ AI: {response}")
                
                # Сохраняем ошибку для передачи наверх
                self._last_generation_error = error_msg
                
                # Проверяем, что это ошибка конфигурации GigaChat
                if 'credentials not configured' in error_msg.lower() or 'not configured' in error_msg.lower():
                    logger.error("[ERROR] GigaChat не настроен! Настройте AssistantSettings в админ-панели:")
                    logger.error("[ERROR] 1. Зайдите в админ-панель Django")
                    logger.error("[ERROR] 2. Откройте AssistantSettings")
                    logger.error("[ERROR] 3. Заполните поля: gigachat_authorization_key ИЛИ gigachat_client_id и gigachat_client_secret")
                
                return None
            # Сохраняем токены из ответа
            if 'tokens_used' not in response:
                # Если токены не вернулись, пытаемся получить из usage
                response['tokens_used'] = response.get('usage', {}).get('total_tokens', 0) if isinstance(response.get('usage'), dict) else 0
            
            # Восстанавливаем модель
            self.ai_service.model = original_model
            
            # Очистка заголовка (убираем лишние символы, кавычки и т.д.)
            title = self._clean_text(title)
            
            # Сохраняем ответ AI для истории (будет сохранено в generate_article)
            # Временно сохраняем в контексте
            if not hasattr(self, '_ai_responses'):
                self._ai_responses = {}
            self._ai_responses['title'] = response.get('content', '')
            # Сохраняем токены для мониторинга
            if not hasattr(self, '_tokens_used'):
                self._tokens_used = {}
            if not hasattr(self, '_usage_data'):
                self._usage_data = {}
            self._tokens_used['title'] = response.get('tokens_used', 0)
            # Сохраняем детальную информацию об использовании
            if 'usage' in response:
                self._usage_data['title'] = response['usage']
            
            return title if title else None
            
        except Exception as e:
            logger.error(f"Ошибка генерации заголовка: {str(e)}")
            return None
    
    """Роутер для генерации контента в зависимости от режима шаблона"""
    def _generate_content_by_mode(self, context: Dict[str, Any], title: Optional[str] = None, retry: bool = False) -> Optional[str]:
        """
        Роутер для генерации контента в зависимости от режима шаблона
        
        Args:
            context: Контекст для промптов
            title: Заголовок статьи (опционально, может быть None в новой схеме)
            retry: Флаг повторной попытки (только для режима AI генерации)
            
        Returns:
            Сгенерированный контент или None
        """
        mode = self.prompt_template.content_generation_mode
        
        logger.info(f"[MODE] Режим генерации контента: {mode}")
        
        if mode == 'generate':
            return self._generate_content_ai(context, title, retry)
        elif mode == 'parse_and_generate':
            return self._generate_content_parse_and_generate(context, title)
        elif mode == 'full_parse':
            return self._generate_content_full_parse(context, title)
        else:
            logger.warning(f"[WARNING] Неизвестный режим генерации: {mode}. Используется режим по умолчанию (generate)")
            return self._generate_content_ai(context, title, retry)
    
    """Генерация основного контента статьи через AI (режим 1: generate)"""
    def _generate_content_ai(self, context: Dict[str, Any], title: Optional[str] = None, retry: bool = False) -> Optional[str]:
        """Генерация основного контента статьи через AI (режим 1: generate)"""
        try:
            # ПРОВЕРКА: Если промпт пустой - возвращаем None
            # Эта проверка нужна, т.к. метод вызывается только если generate_content=True
            if not self.prompt_template.content_prompt or not self.prompt_template.content_prompt.strip():
                logger.error("[ERROR] Промпт для контента пустой, но generate_content=True. Отредактируйте шаблон.")
                return None
            
            # Добавляем заголовок в контекст (если он есть, иначе используем пустую строку)
            context_with_title = {**context, 'title': title or ''}
            
            # Если это повторная попытка, добавляем более строгие требования
            if retry:
                additional_prompt = "\n\nВАЖНО: Статья должна содержать минимум 800 слов и максимум 1300 слов. Убедись, что контент достаточно подробный и информативный."
                context_with_title['additional_requirements'] = additional_prompt
            
            # Форматируем промпт
            prompt = self.prompt_template.format_prompt(
                self.prompt_template.content_prompt,
                context_with_title
            )
            
            # Проверяем, что промпт не стал пустым после форматирования
            if not prompt or not prompt.strip():
                logger.error("[ERROR] Промпт стал пустым после форматирования")
                return None
            
            logger.info(f"[CONTENT] Промпт для генерации: {prompt[:300]}...")
            logger.info(f"[CONTENT] Контекст содержит переменные: {list(context_with_title.keys())}")
            
            # Если это повторная попытка, добавляем требование к объему в промпт
            if retry:
                prompt += "\n\nВАЖНО: Статья должна содержать минимум 800 слов и максимум 1300 слов. Убедись, что контент достаточно подробный и информативный."
            
            # Временно меняем модель
            original_model = self.ai_service.model
            text_model = self.schedule.text_model if self.schedule else 'GigaChat'
            self.ai_service.model = text_model
            
            # Генерируем контент БЕЗ системного промпта чат-бота
            # use_system_prompt=False - чтобы использовать только промпт из шаблона
            response = self.ai_service.generate_response(prompt, use_system_prompt=False)
            content = response.get('content', '').strip()
            
            # Проверяем на ошибки
            if response.get('error') or not content:
                error_msg = response.get('error', 'Неизвестная ошибка')
                logger.error(f"[ERROR] Ошибка генерации контента: {error_msg}")
                logger.error(f"[ERROR] Ответ AI: {response}")
                
                # Сохраняем ошибку для передачи наверх
                self._last_generation_error = error_msg
                
                # Проверяем, что это ошибка конфигурации GigaChat
                if 'credentials not configured' in error_msg.lower() or 'not configured' in error_msg.lower():
                    logger.error("[ERROR] GigaChat не настроен! Настройте AssistantSettings в админ-панели")
                
                return None
            # Сохраняем токены из ответа
            if 'tokens_used' not in response:
                response['tokens_used'] = response.get('usage', {}).get('total_tokens', 0) if isinstance(response.get('usage'), dict) else 0
            
            # КРИТИЧНО: Детальное логирование токенов для отладки
            tokens_count = response.get('tokens_used', 0)
            usage_info = response.get('usage', {})
            logger.info(f"[TOKENS] Контент: использовано {tokens_count} токенов")
            if usage_info:
                prompt_tokens = usage_info.get('prompt_tokens', 0)
                completion_tokens = usage_info.get('completion_tokens', 0)
                logger.info(f"[TOKENS] Контент (детали): prompt={prompt_tokens}, completion={completion_tokens}, total={tokens_count}")
            
            # Восстанавливаем модель
            self.ai_service.model = original_model
            
            # Очистка контента
            content = self._clean_text(content)
            
            # Сохраняем ответ AI
            if not hasattr(self, '_ai_responses'):
                self._ai_responses = {}
            self._ai_responses['content'] = response.get('content', '')
            # Сохраняем токены
            if not hasattr(self, '_tokens_used'):
                self._tokens_used = {}
            if not hasattr(self, '_usage_data'):
                self._usage_data = {}
            self._tokens_used['content'] = tokens_count
            # Сохраняем детальную информацию об использовании
            if 'usage' in response:
                self._usage_data['content'] = response['usage']
            
            # ПРОВЕРКА: Если токены не были получены, логируем предупреждение
            if tokens_count == 0:
                logger.warning("[WARNING] Токены для контента не были получены из ответа AI! Проверьте формат ответа.")
                logger.warning(f"[WARNING] Полный ответ AI: {response}")
            
            return content if content else None
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка генерации контента: {str(e)}")
            return None
    
    """Генерация контента через парсинг 200 слов + генерация на основе этих данных (режим 2: parse_and_generate)"""
    def _generate_content_parse_and_generate(self, context: Dict[str, Any], title: Optional[str] = None) -> Optional[str]:
        """
        Генерация контента через парсинг 200 слов + генерация на основе этих данных (режим 2: parse_and_generate)
        
        Алгоритм:
        1. Парсим 200 слов из интернета по категории и ключевым словам
        2. Добавляем спарсенные данные в контекст как parsed_content_200_words
        3. Генерируем полный текст (800-1300 слов) через AI на основе спарсенных данных и промпта
        """
        logger.info("[MODE] Режим: parse_and_generate (парсинг 200 слов + генерация)")
        
        try:
            # Получаем категорию для поиска
            # Используем category_for_publication, которая была сохранена в generate_article
            category_for_search = getattr(self, '_category_for_publication', None)
            if not category_for_search:
                # Если категория не была сохранена, пытаемся получить из контекста или шаблона
                from Blog.models import Category
                category_name = context.get('category', '')
                if category_name:
                    try:
                        category_for_search = Category.objects.get(title=category_name)
                    except Category.DoesNotExist:
                        pass
                
                if not category_for_search:
                    category_for_search = self.prompt_template.default_category
                    if not category_for_search:
                        # Fallback категория
                        try:
                            category_for_search = Category.objects.get(slug='vysoko-intellektualnye-novosti')
                        except Category.DoesNotExist:
                            logger.error("[ERROR] Не удалось определить категорию для поиска")
                            return None
            
            # Получаем ключевые слова из контекста
            keywords = context.get('keywords', '')
            
            # ОПТИМИЗАЦИЯ: Используем уже спарсенные новости из context (устраняет дублирование парсинга)
            parsed_text_200_words = None
            parsed_source = 'Unknown'
            parsed_url = ''
            
            if 'parsed_news_content' in context and context.get('parsed_news_content'):
                # Используем уже спарсенные новости (берем первые 200 слов из 250)
                news_text = context['parsed_news_content']
                words = news_text.split()[:200]
                parsed_text_200_words = ' '.join(words)
                parsed_source = context.get('news_source', 'Unknown')
                parsed_url = context.get('news_url', '')
                logger.info(f"[REUSE] Используются уже спарсенные новости из context: {len(parsed_text_200_words.split())} слов из источника: {parsed_source}")
            else:
                # Fallback: Парсим только если не были спарсены ранее
                logger.info(f"[PARSE] Парсинг 200 слов для категории: {category_for_search.title}, keywords: {keywords}")
                parsed_news = self._search_and_parse_news(category_for_search, keywords, target_words=200)
                
                if not parsed_news or not parsed_news.get('parsed_text'):
                    logger.warning("[WARNING] Не удалось спарсить 200 слов. Используется режим generate без парсинга.")
                    return self._generate_content_ai(context, title, retry=False)
                
                parsed_text_200_words = parsed_news.get('parsed_text', '')
                parsed_source = parsed_news.get('source_name', 'Unknown')
                parsed_url = parsed_news.get('link', '')
                logger.info(f"[OK] Спарсено {len(parsed_text_200_words.split())} слов из источника: {parsed_source}")
            
            # Добавляем спарсенные данные в контекст
            context_with_parsed = {**context}
            context_with_parsed['parsed_content_200_words'] = parsed_text_200_words
            context_with_parsed['parsed_source'] = parsed_source
            context_with_parsed['parsed_url'] = parsed_url
            
            # Генерируем полный текст через AI на основе спарсенных данных
            logger.info("[GENERATE] Генерация полного текста на основе спарсенных 200 слов...")
            return self._generate_content_ai(context_with_parsed, title or None, retry=False)
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка в режиме parse_and_generate: {str(e)}", exc_info=True)
            # Fallback на обычную генерацию
            logger.warning("[WARNING] Ошибка парсинга. Используется режим generate без парсинга.")
            return self._generate_content_ai(context, title or None, retry=False)
    
    """Полный парсинг контента статьи без изменений (режим 3: full_parse)"""
    def _generate_content_full_parse(self, context: Dict[str, Any], title: Optional[str] = None) -> Optional[str]:
        """
        Полный парсинг контента статьи без изменений (режим 3: full_parse)
        
        Алгоритм:
        1. Парсит content_prompt на наличие URL (http/https)
        2. Если URL найдены - обходит их и ищет статью для парсинга
        3. Если URL нет - использует content_prompt как критерий поиска для веб-поиска
        4. Парсит полный текст статьи (без ограничения по словам)
        5. Если не получается - пробует другие источники/запросы до успеха
        """
        logger.info("[MODE] Режим: full_parse (полный парсинг)")
        
        import re
        from urllib.parse import urlparse
        
        try:
            content_prompt = self.prompt_template.content_prompt or ''
            
            # 1. Ищем URL в content_prompt
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, content_prompt)
            
            if urls:
                # 2. Обходим найденные URL и пытаемся спарсить статью
                logger.info(f"[PARSE] Найдено {len(urls)} URL в content_prompt. Начинаю обход...")
                for url in urls:
                    try:
                        # Проверяем, что это валидный URL
                        parsed = urlparse(url)
                        if not parsed.scheme or not parsed.netloc:
                            continue
                        
                        logger.info(f"[PARSE] Парсинг статьи из источника: {url}")
                        full_text, image_url = self.news_parser.parse_full_article_content(url)
                        
                        if full_text and len(full_text.strip()) > 100:  # Минимум 100 символов
                            word_count = len(full_text.split())
                            logger.info(f"[OK] Успешно спарсено {word_count} слов из {url}")
                            
                            # Применяем валидацию 800-1300 слов
                            if word_count < 800:
                                logger.warning(f"[WARNING] Спарсенный текст слишком короткий ({word_count} слов, требуется 800-1300)")
                                # Пробуем следующий источник
                                continue
                            
                            if word_count > 1300:
                                logger.info(f"[INFO] Спарсенный текст длинный ({word_count} слов). Обрезаю до 1300 слов...")
                                full_text = self._truncate_to_words(full_text, 1300)
                                word_count = len(full_text.split())
                                logger.info(f"[INFO] Текст обрезан до {word_count} слов")
                            
                            return full_text
                        else:
                            logger.warning(f"[WARNING] Не удалось спарсить достаточный контент из {url}")
                            continue
                            
                    except Exception as e:
                        logger.warning(f"[WARNING] Ошибка парсинга {url}: {str(e)}")
                        continue
                
                logger.warning("[WARNING] Не удалось спарсить ни один из указанных URL")
            
            # 3. Если URL не найдены или не удалось спарсить - используем веб-поиск
            logger.info("[SEARCH] URL не найдены или парсинг не удался. Использую веб-поиск...")
            
            # Получаем категорию для поиска
            category_for_search = getattr(self, '_category_for_publication', None)
            if not category_for_search:
                from Blog.models import Category
                category_name = context.get('category', '')
                if category_name:
                    try:
                        category_for_search = Category.objects.get(title=category_name)
                    except Category.DoesNotExist:
                        pass
                
                if not category_for_search:
                    category_for_search = self.prompt_template.default_category
                    if not category_for_search:
                        try:
                            category_for_search = Category.objects.get(slug='vysoko-intellektualnye-novosti')
                        except Category.DoesNotExist:
                            logger.error("[ERROR] Не удалось определить категорию для поиска")
                            return None
            
            # Используем content_prompt как критерий поиска (или keywords из контекста)
            search_query = content_prompt.strip() or context.get('keywords', '') or category_for_search.title
            logger.info(f"[SEARCH] Поиск статей по запросу (на русском): {search_query[:100]}...")
            
            # Ищем новости на русском языке (без перевода)
            news_items = self.news_parser.search_news(category_for_search.title, search_query, limit=20)
            
            if not news_items:
                logger.error("[ERROR] Не найдено статей для парсинга")
                return None
            
            # Пробуем спарсить каждую найденную статью
            logger.info(f"[PARSE] Найдено {len(news_items)} статей. Начинаю парсинг...")
            for news_item in news_items:
                try:
                    url = news_item.get('link')
                    if not url:
                        continue
                    
                    logger.info(f"[PARSE] Парсинг статьи: {url}")
                    full_text, image_url = self.news_parser.parse_full_article_content(url)
                    
                    if full_text and len(full_text.strip()) > 100:
                        word_count = len(full_text.split())
                        logger.info(f"[OK] Успешно спарсено {word_count} слов из {url}")
                        
                        # Применяем валидацию 800-1300 слов
                        if word_count < 800:
                            logger.warning(f"[WARNING] Спарсенный текст слишком короткий ({word_count} слов, требуется 800-1300). Пробую следующую статью...")
                            continue
                        
                        if word_count > 1300:
                            logger.info(f"[INFO] Спарсенный текст длинный ({word_count} слов). Обрезаю до 1300 слов...")
                            full_text = self._truncate_to_words(full_text, 1300)
                            word_count = len(full_text.split())
                            logger.info(f"[INFO] Текст обрезан до {word_count} слов")
                        
                        return full_text
                    else:
                        logger.warning(f"[WARNING] Не удалось спарсить достаточный контент из {url}")
                        continue
                        
                except Exception as e:
                    logger.warning(f"[WARNING] Ошибка парсинга {url}: {str(e)}")
                    continue
            
            logger.error("[ERROR] Не удалось спарсить ни одну статью из найденных")
            return None
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка в режиме full_parse: {str(e)}", exc_info=True)
            return None
    
    """Подсчет количества слов в тексте (учитывая HTML)"""
    def _count_words(self, text: str) -> int:
        """Подсчет количества слов в тексте (учитывая HTML)"""
        import re
        # Удаляем HTML теги для подсчета слов
        clean_text = re.sub(r'<[^>]+>', ' ', text)
        # Разбиваем на слова
        words = clean_text.split()
        return len(words)
    
    """Обрезка текста до указанного количества слов с сохранением HTML структуры"""
    def _truncate_to_words(self, text: str, max_words: int) -> str:
        """Обрезка текста до указанного количества слов с сохранением HTML структуры"""
        import re
        from bs4 import BeautifulSoup
        
        try:
            # Парсим HTML
            soup = BeautifulSoup(text, 'html.parser')
            # Получаем весь текст
            all_text = soup.get_text()
            words = all_text.split()
            
            if len(words) <= max_words:
                return text
            
            # Обрезаем до нужного количества слов
            truncated_words = words[:max_words]
            truncated_text = ' '.join(truncated_words)
            
            # Пытаемся сохранить структуру HTML - берем первые N символов из оригинального HTML
            # и обрезаем на границе тега
            html_length = len(text)
            target_length = int(html_length * (max_words / len(words)))
            
            # Находим ближайший закрывающий тег
            truncated_html = text[:target_length]
            # Ищем последний закрытый тег
            last_tag_end = truncated_html.rfind('>')
            if last_tag_end > 0:
                truncated_html = truncated_html[:last_tag_end + 1]
            
            # Закрываем незакрытые теги
            try:
                soup_truncated = BeautifulSoup(truncated_html, 'html.parser')
                return str(soup_truncated)
            except:
                # Если не получилось, просто возвращаем обрезанный текст
                return truncated_text + "..."
                
        except Exception as e:
            logger.warning(f"[WARNING] Ошибка при обрезке HTML: {str(e)}, используем простую обрезку")
            # Простая обрезка без HTML
            words = text.split()
            if len(words) <= max_words:
                return text
            return ' '.join(words[:max_words]) + "..."
    
    """Генерация описания для Telegram"""
    def _generate_description(self, context: Dict[str, Any], title: str, content: str) -> str:
        """
        Генерация описания для Telegram
        
        Автоматически берет первые 200 слов из основного контента статьи.
        Это описание используется только для отправки в Telegram и не публикуется на сайте.
        """
        try:
            # Убираем HTML теги из контента для получения чистого текста
            import re
            # Простая очистка HTML (можно улучшить, используя BeautifulSoup)
            clean_content = re.sub(r'<[^>]+>', '', content)
            
            # Берем первые 200 слов
            words = clean_content.split()[:200]
            description = ' '.join(words)
            
            # Если описание заканчивается не на точку, добавляем многоточие
            if description and not description.endswith(('.', '!', '?')):
                description = description.rstrip(',;:') + '...'
            
            logger.info(f"[OK] Описание для Telegram сгенерировано: {len(description)} символов")
            
            return description if description else ""
            
        except Exception as e:
            logger.error(f"Ошибка генерации описания: {str(e)}")
            # Fallback на первые 200 слов контента
            if content:
                words = content.split()[:200]
                return ' '.join(words)
            return ""
    
    """Роутер для генерации изображения в зависимости от режима шаблона"""
    def _generate_image_by_mode(self, context: Dict[str, Any], title: str, parsed_news: Optional[Dict] = None):
        """
        Роутер для генерации изображения в зависимости от режима шаблона
        
        Args:
            context: Контекст для промптов
            title: Заголовок статьи
            parsed_news: Спарсенные новости (если есть)
            
        Returns:
            Tuple (ContentFile с изображением, использованный промпт)
        """
        mode = self.prompt_template.image_generation_mode
        
        logger.info(f"[IMAGE_MODE] Режим генерации изображения: {mode}")
        
        if mode == 'generate':
            return self._generate_image_ai(context, title)
        elif mode == 'search_and_parse':
            return self._search_and_parse_image(context, title, parsed_news)
        else:
            logger.warning(f"[WARNING] Неизвестный режим генерации изображения: {mode}. Используется режим по умолчанию (generate)")
            return self._generate_image_ai(context, title)
    
    """Генерация изображения через GigaChat-Pro через /chat/completions с function_call="auto"""
    def _generate_image_ai(self, context: Dict[str, Any], title: str):
        """
        Генерация изображения через GigaChat-Pro через /chat/completions с function_call="auto"
        GigaChat автоматически определяет необходимость вызова функции text2image
        
        Returns:
            Tuple (ContentFile с изображением, использованный промпт)
        """
        try:
            # ПРОВЕРКА: Если промпт пустой - возвращаем None
            if not self.prompt_template.image_prompt or not self.prompt_template.image_prompt.strip():
                logger.warning("[WARNING] Промпт для изображения пустой")
                return None, ""
            
            # НОВАЯ СХЕМА: Добавляем title и первые 100 слов контента в контекст
            # content_first_100_words уже должен быть в context, но проверяем
            image_context = {**context, 'title': title or ''}
            if 'content_first_100_words' not in image_context:
                logger.warning("[WARNING] content_first_100_words не найден в контексте для генерации изображения")
            
            # Форматируем промпт для изображения
            image_prompt = self.prompt_template.format_prompt(
                self.prompt_template.image_prompt,
                image_context
            )
            
            # Проверяем, что промпт не стал пустым после форматирования
            if not image_prompt or not image_prompt.strip():
                logger.error("[ERROR] Промпт для изображения стал пустым после форматирования")
                return None, ""
            
            logger.info(f"[IMAGE] Генерация изображения с промптом: {image_prompt[:100]}...")
            logger.info(f"[IMAGE] Контекст содержит переменные: {list(image_context.keys())}")
            if 'content_first_100_words' in image_context:
                logger.info(f"[IMAGE] Используются первые 100 слов контента: {image_context['content_first_100_words'][:100]}...")
            
            # Формируем запрос для генерации изображения
            # GigaChat автоматически определит, что нужно вызвать text2image
            image_request = f"Нарисуй изображение по следующему описанию: {image_prompt}"
            
            # Генерируем через chat/completions с function_call="auto"
            # Используем прямой вызов API через requests, так как нужно передать function_call
            access_token = self.gigachat_service._get_access_token()
            if not access_token:
                logger.error("[ERROR] Не удалось получить токен доступа для генерации изображения")
                return None, image_prompt
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Используем модель для изображений из расписания или по умолчанию GigaChat-2-Pro
            image_model = self.schedule.image_model if self.schedule else 'GigaChat-2-Pro'
            # Проверяем, что модель поддерживает генерацию изображений (Pro или Max)
            if 'Lite' in image_model:
                # Lite не поддерживает генерацию изображений, используем Pro
                image_model = 'GigaChat-2-Pro'
                logger.warning(f"[WARNING] Модель Lite не поддерживает генерацию изображений, используется Pro")
            
            payload = {
                'model': image_model,
                'messages': [
                    {
                        'role': 'user',
                        'content': image_request
                    }
                ],
                'function_call': 'auto',  # Автоматический вызов функции text2image
                'temperature': 0.7,
                'max_tokens': 500
            }
            
            logger.info("[IMAGE] Отправка запроса на генерацию изображения через /chat/completions...")
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                verify=self.assistant_settings.get_gigachat_verify_ssl(),
                timeout=120  # Увеличенный таймаут для генерации изображений
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                if content:
                    logger.info(f"[IMAGE] Ответ от GigaChat: {content[:200]}...")
                    
                    # Извлекаем file_id из <img src="file_id" fuse="true"/>
                    file_id_match = re.search(r'<img\s+src=["\']([^"\']+)["\']', content)
                    
                    if file_id_match:
                        file_id = file_id_match.group(1)
                        logger.info(f"[IMAGE] Найден file_id изображения: {file_id}")
                        
                        # Скачиваем изображение через GET /files/{file_id}/content
                        download_url = f'https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content'
                        download_response = requests.get(
                            download_url,
                            headers={
                                'Authorization': f'Bearer {access_token}',
                                'Accept': 'application/json'
                            },
                            verify=self.assistant_settings.get_gigachat_verify_ssl(),
                            timeout=60
                        )
                        
                        if download_response.status_code == 200:
                            # Изображение может быть в base64 (JSON) или в бинарном виде
                            content_type = download_response.headers.get('Content-Type', '')
                            
                            if 'application/json' in content_type:
                                # JSON с base64 закодированным изображением
                                try:
                                    download_data = download_response.json()
                                    if isinstance(download_data, dict) and 'content' in download_data:
                                        image_content = base64.b64decode(download_data['content'])
                                    else:
                                        # Если структура другая, пробуем бинарные данные
                                        image_content = download_response.content
                                except (ValueError, KeyError):
                                    # Если не JSON, берем бинарные данные
                                    image_content = download_response.content
                            else:
                                # Бинарные данные напрямую
                                image_content = download_response.content
                            
                            # Создаем ContentFile
                            image_file = ContentFile(image_content)
                            image_file.name = f"ai_generated_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            
                            logger.info("[OK] Изображение успешно сгенерировано и скачано")
                            return image_file, image_prompt
                        else:
                            logger.error(f"[ERROR] Не удалось скачать изображение: HTTP {download_response.status_code}")
                            logger.error(f"[ERROR] Ответ: {download_response.text[:200]}")
                    else:
                        logger.warning("[WARNING] В ответе GigaChat не найден <img> тег с file_id")
                        logger.warning(f"[WARNING] Полный ответ: {content[:500]}")
            else:
                logger.error(f"[ERROR] Не удалось сгенерировать изображение: HTTP {response.status_code}")
                logger.error(f"[ERROR] Ответ: {response.text[:500]}")
            
            return None, image_prompt
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка генерации изображения: {str(e)}", exc_info=True)
            return None, image_prompt if 'image_prompt' in locals() else ""
    
    """Поиск и парсинг изображения на основании запроса (режим 2: search_and_parse)"""
    def _search_and_parse_image(self, context: Dict[str, Any], title: str, parsed_news: Optional[Dict] = None):
        """
        Поиск и парсинг изображения на основании запроса (режим 2: search_and_parse)
        
        Алгоритм:
        1. Сначала пытается найти изображение в спарсенных новостях (если они есть)
        2. Если не найдено - использует image_search_criteria для поиска через веб-поиск
        3. Загружает найденное изображение
        
        Returns:
            Tuple (ContentFile с изображением, использованный критерий поиска)
        """
        logger.info("[IMAGE_MODE] Режим: search_and_parse (поиск и парсинг изображения)")
        
        try:
            # 1. Сначала пытаемся найти изображение в спарсенных новостях
            if parsed_news and parsed_news.get('image_url'):
                try:
                    logger.info(f"[IMAGE] Попытка загрузить изображение из новости: {parsed_news['image_url']}")
                    img_response = requests.get(parsed_news['image_url'], timeout=10, headers=self.news_parser.headers)
                    if img_response.status_code == 200:
                        # Проверяем, что это действительно изображение
                        content_type = img_response.headers.get('content-type', '')
                        if content_type.startswith('image/'):
                            image_file = ContentFile(img_response.content)
                            image_file.name = f"parsed_image_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            logger.info("[OK] Изображение загружено из новости")
                            return image_file, f"Изображение из источника: {parsed_news.get('source_name', 'Unknown')}"
                        else:
                            logger.warning(f"[WARNING] URL не является изображением: {content_type}")
                except Exception as e:
                    logger.warning(f"[WARNING] Не удалось загрузить изображение из новости: {str(e)}")
            
            # 2. Если не найдено в новостях - используем image_search_criteria для поиска
            search_criteria = self.prompt_template.image_search_criteria
            if not search_criteria or not search_criteria.strip():
                logger.warning("[WARNING] Критерий поиска изображения не указан в шаблоне")
                return None, ""
            
            logger.info(f"[IMAGE] Поиск изображения по критерию: {search_criteria[:100]}...")
            
            # Получаем категорию для поиска
            category_for_search = getattr(self, '_category_for_publication', None)
            if not category_for_search:
                from Blog.models import Category
                category_name = context.get('category', '')
                if category_name:
                    try:
                        category_for_search = Category.objects.get(title=category_name)
                    except Category.DoesNotExist:
                        pass
                
                if not category_for_search:
                    category_for_search = self.prompt_template.default_category
            
            # Ищем новости на русском языке (без перевода)
            search_query = f"{category_for_search.title if category_for_search else ''} {search_criteria}".strip()
            logger.info(f"[IMAGE] Поиск статей с изображениями (на русском): {search_query}")
            
            news_items = self.news_parser.search_news(category_for_search.title if category_for_search else "новости", search_criteria, limit=10)
            
            if not news_items:
                logger.warning("[WARNING] Не найдено статей для поиска изображений")
                return None, search_criteria
            
            # Пробуем найти изображение в найденных статьях
            for news_item in news_items:
                try:
                    url = news_item.get('link')
                    if not url:
                        continue
                    
                    # Парсим статью для поиска изображения
                    _, image_url = self.news_parser.parse_article_content(url, target_words=50)  # Минимум слов, нам нужна только картинка
                    
                    if image_url:
                        logger.info(f"[IMAGE] Найдено изображение в статье: {url}")
                        img_response = requests.get(image_url, timeout=10, headers=self.news_parser.headers)
                        if img_response.status_code == 200:
                            content_type = img_response.headers.get('content-type', '')
                            if content_type.startswith('image/'):
                                image_file = ContentFile(img_response.content)
                                image_file.name = f"searched_image_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                logger.info("[OK] Изображение найдено и загружено")
                                return image_file, search_criteria
                except Exception as e:
                    logger.warning(f"[WARNING] Ошибка поиска изображения в {url}: {str(e)}")
                    continue
            
            logger.warning("[WARNING] Не удалось найти изображение по критерию поиска")
            return None, search_criteria
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка в режиме search_and_parse изображения: {str(e)}", exc_info=True)
            return None, ""
    
    """Очистка текста от лишних символов"""
    def _clean_text(self, text: str) -> str:
        """Очистка текста от лишних символов"""
        if not text:
            return ""
        
        # Убираем лишние пробелы
        text = ' '.join(text.split())
        
        # Убираем кавычки в начале и конце, если они есть
        text = text.strip('"\'«»')
        
        return text.strip()
    
    """Очистка контекста для JSON сериализации"""
    def _sanitize_context_for_json(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Очистка контекста от несериализуемых объектов для сохранения в JSONField
        Преобразует объекты Django (Category, User и т.д.) в примитивные типы
        
        Args:
            context: Исходный контекст с возможными объектами Django
            
        Returns:
            Очищенный контекст, пригодный для JSON сериализации
        """
        import json
        from datetime import datetime, date
        from django.utils import timezone
        
        sanitized = {}
        
        for key, value in context.items():
            try:
                # Пробуем сериализовать значение
                json.dumps(value)
                sanitized[key] = value
            except (TypeError, ValueError):
                # Если не получается - преобразуем в примитивный тип
                if hasattr(value, '__class__'):
                    # Проверяем, является ли объект моделью Django
                    if hasattr(value, '_meta'):
                        # Модель Django - преобразуем в строку или ID
                        if hasattr(value, 'title'):
                            sanitized[key] = str(value.title)
                        elif hasattr(value, 'name'):
                            sanitized[key] = str(value.name)
                        elif hasattr(value, 'pk'):
                            sanitized[key] = value.pk
                        elif hasattr(value, 'id'):
                            sanitized[key] = value.id
                        else:
                            sanitized[key] = str(value)
                    # Проверяем datetime/date
                    elif isinstance(value, (datetime, date)):
                        sanitized[key] = value.isoformat()
                    # Проверяем timezone-aware datetime
                    elif hasattr(value, 'isoformat'):
                        sanitized[key] = value.isoformat()
                    else:
                        # Другой объект - преобразуем в строку
                        sanitized[key] = str(value)
                else:
                    # Неизвестный тип - преобразуем в строку
                    sanitized[key] = str(value) if value is not None else None
        
        return sanitized
    
    """Генерация нескольких статей"""
    def generate_batch(self, count: Optional[int] = None) -> list[Post]:
        """
        Генерация нескольких статей
        
        Args:
            count: Количество статей для генерации (по умолчанию из расписания)
            
        Returns:
            Список созданных статей
        """
        if not self.schedule:
            raise ValueError("generate_batch требует наличие расписания")
        count = count or self.schedule.articles_per_run
        generated_posts = []
        
        logger.info(f"[BATCH] Начало пакетной генерации: {count} статей")
        
        for i in range(count):
            logger.info(f"[BATCH] Генерация статьи {i+1}/{count}...")
            context_data = {'_article_index': i + 1}
            post = self.generate_article(context_data)
            if post:
                generated_posts.append(post)
            else:
                logger.warning(f"[WARNING] Не удалось сгенерировать статью {i+1}")
        
        logger.info(f"[OK] Пакетная генерация завершена: {len(generated_posts)}/{count} статей создано")
        
        return generated_posts
    
    """Генерация тестовой статьи без расписания"""
    def generate_test_article(self, category, keywords='', context_data: Optional[Dict[str, Any]] = None, use_image_generation=False) -> Optional[Post]:
        """
        Генерация тестовой статьи без расписания
        
        Args:
            category: Категория для статьи (объект Category или None - тогда используется fallback)
            keywords: Ключевые слова для генерации
            context_data: Дополнительные данные для контекста
            use_image_generation: Использовать генерацию изображений
            
        Returns:
            Созданная статья Post или None в случае ошибки
        """
        # Добавляем параметры в context_data
        if context_data is None:
            context_data = {}
        
        # КРИТИЧНО: Сохраняем объект Category отдельно для использования в generate_article
        # Объект Category всегда сохраняется в _category_obj (если передан объект)
        # Строка 'category' в context_data используется ТОЛЬКО для контекста промпта
        if category is not None:
            # Сохраняем объект Category напрямую (для использования в generate_article)
            if hasattr(category, 'title'):
                # Это объект Category - ВСЕГДА сохраняем в _category_obj
                context_data['_category_obj'] = category  # Объект Category для публикации
                # Строка для контекста промпта устанавливается только если её нет
                # (чтобы не перезаписать значение из формы или additional_context)
                if 'category' not in context_data:
                    context_data['category'] = str(category.title)  # Строка для контекста промпта
                logger.info(f"[TEST] Объект Category сохранён в _category_obj: {category.title}")
            elif hasattr(category, 'name'):
                # Это объект с name атрибутом
                context_data['_category_obj'] = category  # Объект Category для публикации
                if 'category' not in context_data:
                    context_data['category'] = str(category.name)  # Строка для контекста промпта
                logger.info(f"[TEST] Объект Category сохранён в _category_obj: {category.name}")
            elif isinstance(category, str):
                # Если передана строка - сохраняем как строку (объект будет найден в generate_article)
                context_data['category'] = category
                logger.info(f"[TEST] Категория передана как строка: {category}")
        
        context_data['keywords'] = keywords
        context_data['use_image_generation'] = use_image_generation
        context_data['_article_index'] = 1  # Для тестовой статьи всегда индекс 1
        
        # Генерируем статью
        return self.generate_article(context_data)

