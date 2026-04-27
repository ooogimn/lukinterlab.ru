from django.conf import settings
from django.urls import reverse
from .models import Post
from taggit.models import Tag
from urllib.parse import urlparse
import re
import json
import logging

logger = logging.getLogger(__name__)


def effective_post_meta_description(post, max_length=160):
    """
    Непустое описание для meta description, og:twitter и JSON-LD.
    Совпадает по смыслу с pre_save в Blog/signals (generate_seo_meta_tags), но работает
    для старых постов без повторного save и при пустых полях в БД.
    """
    from home.seo_utils import SEOUtils

    md = (getattr(post, 'meta_description', None) or '').strip()
    if md:
        return SEOUtils.generate_meta_description(md, max_length)

    desc = (getattr(post, 'description', None) or '').strip()
    if desc:
        return SEOUtils.generate_meta_description(desc, max_length)

    content = getattr(post, 'content', None) or ''
    if content:
        plain = SEOUtils.plain_text_for_meta(content)
        snippet = ' '.join(plain.split()[:40])
        gen = SEOUtils.generate_meta_description(snippet, max_length)
        if gen:
            return gen

    title = (getattr(post, 'title', None) or '').strip()
    if title:
        fallback = f'{title} — статья в блоге LukInterLab.'
        return SEOUtils.generate_meta_description(fallback, max_length)

    return SEOUtils.generate_meta_description(
        'Блог LukInterLab — IT, разработка и технологии.', max_length
    )


def safe_log_text(text: str) -> str:
    """Заголовки с emoji для Windows-консоли (cp1251): безопасная строка для logger."""
    if not text:
        return ''
    try:
        return text.encode('cp1251', errors='ignore').decode('cp1251', errors='ignore')
    except Exception:
        try:
            return text.encode('ascii', errors='ignore').decode('ascii')
        except Exception:
            return str(text)[:100]


def get_related_posts(post, limit=5):
    """
    Получение похожих статей для внутренней перелинковки
    
    Приоритеты:
    1. Статьи с общими тегами
    2. Статьи из той же категории
    3. Статьи с похожими ключевыми словами в заголовке
    """
    related_posts = []
    
    try:
        # Приоритет 1: Статьи с общими тегами
        if post.pk and post.tags.exists():
            post_tags = post.tags.all()
            related_by_tags = Post.objects.filter(
                status='published',
                tags__in=post_tags
            ).exclude(pk=post.pk).distinct()[:limit]
            
            related_posts.extend(related_by_tags)
        
        # Если недостаточно статей, добавляем из той же категории
        if len(related_posts) < limit:
            related_by_category = Post.objects.filter(
                status='published',
                category=post.category
            ).exclude(pk=post.pk).exclude(pk__in=[p.pk for p in related_posts])[:limit - len(related_posts)]
            
            related_posts.extend(related_by_category)
        
        # Если все еще недостаточно, ищем по ключевым словам в заголовке
        if len(related_posts) < limit and post.title:
            # Извлекаем ключевые слова из заголовка
            title_words = re.findall(r'\b\w{4,}\b', post.title.lower())
            if title_words:
                related_by_keywords = Post.objects.filter(
                    status='published',
                    title__icontains=title_words[0]
                ).exclude(pk=post.pk).exclude(pk__in=[p.pk for p in related_posts])[:limit - len(related_posts)]
                
                related_posts.extend(related_by_keywords)
        
        # Ограничиваем результат
        return related_posts[:limit]
        
    except Exception as e:
        logger.error(f"[SEO] Ошибка при получении похожих статей: {str(e)}", exc_info=True)
        return []


def generate_article_structured_data(post, request=None):
    """
    Генерация structured data (JSON-LD) для статьи
    
    Включает:
    - Article schema
    - BreadcrumbList
    - Author Person/Organization
    - Publisher Organization
    - ImageObject
    - AggregateRating (если есть лайки/комментарии)
    """
    site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
    
    # Базовый URL статьи
    article_url = f"{site_url}{post.get_absolute_url()}"
    
    # Изображение статьи
    image_url = None
    if post.og_image:
        image_url = f"{site_url}{post.og_image.url}"
    elif post.kartinka:
        image_url = f"{site_url}{post.kartinka.url}"
    else:
        dm = post.get_display_media()
        tu = dm.get("thumbnail_url") or dm.get("url")
        if tu and dm.get("type") in (
            "external_video",
            "external_image",
            "image",
        ):
            if tu.startswith("http"):
                image_url = tu
            else:
                image_url = f"{site_url}{tu}" if str(tu).startswith("/") else f"{site_url}/{tu}"
    
    # Описание для схемы — как на странице (непустое)
    article_desc = effective_post_meta_description(post, max_length=320)
    
    # Structured data для Article
    article_data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.meta_title or post.title,
        "description": article_desc,
        "image": image_url,
        "datePublished": post.created.isoformat() if post.created else None,
        "dateModified": post.updated.isoformat() if post.updated else None,
        "author": {
            "@type": "Person",
            "name": post.author.get_full_name() or post.author.username if post.author else "LukInterLab"
        },
        "publisher": {
            "@type": "Organization",
            "name": "LukInterLab",
            "logo": {
                "@type": "ImageObject",
                "url": f"{site_url}/static/img/favicon.svg"
            }
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": article_url
        }
    }
    
    # Добавляем категорию как articleSection
    if post.category:
        article_data["articleSection"] = post.category.title
    
    # Добавляем теги как keywords
    if post.tags.exists():
        keywords = [tag.name for tag in post.tags.all()[:5]]
        article_data["keywords"] = ", ".join(keywords)
    
    # Добавляем AggregateRating если есть лайки или комментарии
    if post.likes_count > 0 or post.comments.filter(active=True).count() > 0:
        comments_count = post.comments.filter(active=True).count()
        # Простая оценка на основе лайков и комментариев
        rating_value = min(5.0, max(1.0, (post.likes_count * 0.5 + comments_count * 0.3) / 2))
        
        article_data["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": round(rating_value, 1),
            "reviewCount": comments_count,
            "bestRating": 5,
            "worstRating": 1
        }
    
    # BreadcrumbList
    breadcrumb_items = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Главная",
            "item": site_url
        },
        {
            "@type": "ListItem",
            "position": 2,
            "name": "Блог",
            "item": f"{site_url}/blog/"
        }
    ]
    
    if post.category:
        breadcrumb_items.append({
            "@type": "ListItem",
            "position": 3,
            "name": post.category.title,
            "item": f"{site_url}{post.category.get_absolute_url()}"
        })
    
    breadcrumb_items.append({
        "@type": "ListItem",
        "position": len(breadcrumb_items) + 1,
        "name": post.title,
        "item": article_url
    })
    
    breadcrumb_data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": breadcrumb_items
    }
    
    # Сериализуем в JSON строки для использования в шаблоне
    return {
        'article_json': json.dumps(article_data, ensure_ascii=False),
        'breadcrumb_json': json.dumps(breadcrumb_data, ensure_ascii=False)
    }


def generate_faq_structured_data(post):
    """
    Генерация FAQ structured data для статьи
    
    Использует модель PostFAQ для создания FAQPage schema
    """
    try:
        faqs = post.faqs.all()
        if not faqs.exists():
            return None
        
        site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
        article_url = f"{site_url}{post.get_absolute_url()}"
        
        faq_items = []
        for faq in faqs:
            faq_items.append({
                "@type": "Question",
                "name": faq.question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq.answer
                }
            })
        
        faq_data = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_items
        }
        
        return faq_data
    except Exception as e:
        logger.error(f"[SEO] Ошибка при генерации FAQ structured data: {str(e)}", exc_info=True)
        return None


def generate_howto_structured_data(post):
    """
    Генерация HowTo structured data для статей с инструкциями
    
    Определяет наличие инструкций по ключевым словам в контенте
    """
    if not post.content:
        return None
    
    # Проверяем наличие инструкций по ключевым словам
    howto_keywords = ['шаг', 'инструкция', 'как сделать', 'пошагово', 'руководство', 'гайд']
    content_lower = post.content.lower()
    
    has_howto = any(keyword in content_lower for keyword in howto_keywords)
    
    if not has_howto:
        return None
    
    # Простая структура HowTo (можно расширить)
    site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
    
    howto_data = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": post.title,
        "description": effective_post_meta_description(post, max_length=320),
        "image": f"{site_url}{post.kartinka.url}" if post.kartinka else None,
        "totalTime": "PT30M",  # Примерное время, можно сделать динамическим
        "step": []  # Шаги можно извлечь из контента, но это сложнее
    }
    
    return howto_data


def generate_blog_list_structured_data(posts, request=None, title="Все статьи"):
    """
    Генерация ItemList structured data для списка статей блога
    """
    site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
    
    # Получаем URL текущей страницы
    if request:
        current_url = f"{site_url}{request.path}"
    else:
        current_url = f"{site_url}/blog/"
    
    # Формируем список элементов
    item_list = []
    for post in posts[:20]:  # Ограничиваем до 20 для производительности
        post_url = f"{site_url}{post.get_absolute_url()}"
        item_list.append({
            "@type": "ListItem",
            "position": len(item_list) + 1,
            "item": {
                "@type": "Article",
                "headline": post.meta_title or post.title,
                "url": post_url,
                "datePublished": post.created.isoformat() if post.created else None,
                "dateModified": post.updated.isoformat() if post.updated else None,
                "author": {
                    "@type": "Person",
                    "name": post.author.get_full_name() or post.author.username if post.author else "LukInterLab"
                }
            }
        })
    
    if not item_list:
        return None
    
    list_data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": title,
        "description": f"Список статей: {title}",
        "url": current_url,
        "numberOfItems": len(item_list),
        "itemListElement": item_list
    }
    
    return json.dumps(list_data, ensure_ascii=False)


def add_nofollow_to_external_links(html_content, site_domain=None):
    """
    Автоматически добавляет rel="nofollow" ко всем внешним ссылкам в HTML контенте
    
    Args:
        html_content: HTML контент со ссылками
        site_domain: Домен сайта (например, 'lukinterlab.ru')
    
    Returns:
        HTML контент с добавленными rel="nofollow" для внешних ссылок
    """
    if not html_content:
        return html_content
    
    if not site_domain:
        site_domain = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
        # Извлекаем домен из URL
        parsed = urlparse(site_domain)
        site_domain = parsed.netloc or parsed.path.replace('https://', '').replace('http://', '').split('/')[0]
    
    # Паттерн для поиска всех ссылок <a href="...">
    link_pattern = r'<a\s+([^>]*href=["\']([^"\']+)["\'][^>]*)>'
    
    def process_link(match):
        full_attrs = match.group(1)
        url = match.group(2)
        
        # Пропускаем якорные ссылки (#)
        if url.startswith('#'):
            return match.group(0)
        
        # Пропускаем mailto: и tel: ссылки
        if url.startswith(('mailto:', 'tel:', 'javascript:')):
            return match.group(0)
        
        # Определяем, является ли ссылка внешней
        is_external = False
        try:
            parsed_url = urlparse(url)
            link_domain = parsed_url.netloc or parsed_url.path.split('/')[0] if parsed_url.path else None
            
            # Если это относительная ссылка (без домена), считаем внутренней
            if not parsed_url.netloc:
                is_external = False
            # Если домен отличается от нашего
            elif link_domain and link_domain.lower() != site_domain.lower():
                is_external = True
        except:
            # В случае ошибки парсинга, считаем внешней для безопасности
            is_external = True
        
        # Если ссылка внешняя, добавляем rel="nofollow"
        if is_external:
            # Проверяем, есть ли уже rel атрибут
            if 'rel=' in full_attrs:
                # Если есть rel, добавляем nofollow к существующим значениям
                full_attrs = re.sub(
                    r'rel=["\']([^"\']*)["\']',
                    lambda m: f'rel="{m.group(1)} nofollow"'.replace('  ', ' '),
                    full_attrs
                )
            else:
                # Если rel нет, добавляем новый
                full_attrs = f'{full_attrs} rel="nofollow"'
        
        return f'<a {full_attrs}>'
    
    # Обрабатываем все ссылки
    processed_content = re.sub(link_pattern, process_link, html_content)
    
    return processed_content


def add_internal_links_to_content(post, html_content, max_links=5):
    """
    Автоматически добавляет внутренние ссылки на похожие статьи в контент
    
    Находит ключевые слова в тексте и заменяет их на ссылки на релевантные статьи.
    Ограничение: не более max_links ссылок на статью.
    
    Args:
        post: Объект Post (текущая статья)
        html_content: HTML контент статьи
        max_links: Максимальное количество ссылок для добавления
    
    Returns:
        HTML контент с добавленными внутренними ссылками
    """
    if not html_content or not post.pk:
        return html_content
    
    try:
        from django.conf import settings
        from urllib.parse import urlparse
        
        # Извлекаем текст из HTML для поиска ключевых слов
        text_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Получаем список похожих статей
        related_posts = get_related_posts(post, limit=max_links * 2)  # Берем больше для выбора
        
        if not related_posts:
            return html_content
        
        # Создаем словарь: ключевое слово -> статья
        # Используем теги и ключевые слова из заголовков похожих статей
        keyword_to_post = {}
        used_posts = set()
        
        # Приоритет 1: Используем теги текущей статьи
        if post.tags.exists():
            post_tags = post.tags.all()
            for tag in post_tags:
                if len(keyword_to_post) >= max_links:
                    break
                tag_name = tag.name.lower()
                # Ищем статью с таким же тегом
                for related_post in related_posts:
                    if related_post.pk not in used_posts and related_post.tags.filter(name=tag.name).exists():
                        keyword_to_post[tag_name] = related_post
                        used_posts.add(related_post.pk)
                        break
        
        # Приоритет 2: Используем ключевые слова из заголовков похожих статей
        if len(keyword_to_post) < max_links:
            for related_post in related_posts:
                if len(keyword_to_post) >= max_links:
                    break
                if related_post.pk in used_posts:
                    continue
                
                # Извлекаем ключевые слова из заголовка
                title_words = re.findall(r'\b\w{4,}\b', related_post.title.lower())
                for word in title_words:
                    if len(keyword_to_post) >= max_links:
                        break
                    # Проверяем, что слово есть в контенте и не является стоп-словом
                    stop_words = {'как', 'что', 'для', 'при', 'без', 'под', 'над', 'из', 'от', 'до', 
                                 'по', 'со', 'во', 'это', 'этот', 'эта', 'эти', 'этот', 'этих'}
                    if word not in stop_words and word in text_content.lower():
                        if word not in keyword_to_post:
                            keyword_to_post[word] = related_post
                            used_posts.add(related_post.pk)
                            break
        
        if not keyword_to_post:
            return html_content
        
        # Сортируем ключевые слова по длине (длинные сначала) для более точного совпадения
        sorted_keywords = sorted(keyword_to_post.keys(), key=len, reverse=True)
        
        # Заменяем ключевые слова на ссылки в HTML контенте
        processed_content = html_content
        links_added = 0
        
        # Разбиваем контент на части: текст и HTML теги
        # Используем более простой подход - ищем слова в тексте между тегами
        for keyword in sorted_keywords:
            if links_added >= max_links:
                break
            
            related_post = keyword_to_post[keyword]
            post_url = related_post.get_absolute_url()
            site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
            full_url = f"{site_url}{post_url}"
            
            # Проверяем, нет ли уже ссылки на эту статью
            if f'href="{full_url}"' in processed_content or f"href='{full_url}'" in processed_content:
                continue
            
            # Ищем первое вхождение ключевого слова в тексте (не в тегах)
            # ВАЖНО: В Python 3.13 ужесточены требования к look-behind в регулярных выражениях
            # Используем простой паттерн без look-behind и \b для избежания ошибок
            try:
                # Экранируем ключевое слово
                escaped_keyword = re.escape(keyword)
                # Используем простой паттерн без look-behind и word boundaries
                # Проверку границ слов сделаем вручную после поиска
                pattern = r'(?i)' + escaped_keyword
                
                # Находим все совпадения
                matches = list(re.finditer(pattern, processed_content))
                
                # Фильтруем совпадения: оставляем только те, что на границах слов
                filtered_matches = []
                for match in matches:
                    start, end = match.span()
                    # Проверяем границы слов вручную
                    # Перед совпадением должен быть не буквенно-цифровой символ или начало строки
                    char_before = processed_content[start - 1] if start > 0 else ''
                    # После совпадения должен быть не буквенно-цифровой символ или конец строки
                    char_after = processed_content[end] if end < len(processed_content) else ''
                    
                    # Проверяем, что это граница слова
                    is_word_boundary = (
                        (not char_before or not char_before.isalnum()) and
                        (not char_after or not char_after.isalnum())
                    )
                    
                    if is_word_boundary:
                        filtered_matches.append(match)
                
                matches = filtered_matches
            except re.error as e:
                # Если паттерн не компилируется, пропускаем это ключевое слово
                logger.error(f"[SEO] Ошибка компиляции паттерна для '{keyword}': {str(e)}. Пропускаем это ключевое слово.")
                continue
            except Exception as e:
                # Обработка любых других ошибок
                logger.error(f"[SEO] Неожиданная ошибка при поиске '{keyword}': {str(e)}. Пропускаем это ключевое слово.")
                continue
            if not matches:
                continue
            
            # Берем первое совпадение, которое не внутри ссылки
            for match in matches:
                start, end = match.span()
                # Проверяем, что это не внутри <a> тега
                before_match = processed_content[:start]
                # Ищем последний открывающий <a> тег перед совпадением
                last_a_open = before_match.rfind('<a')
                if last_a_open != -1:
                    # Проверяем, закрыт ли тег <a> до нашего совпадения
                    after_a_open = before_match[last_a_open:].find('>')
                    if after_a_open != -1:
                        # Проверяем, есть ли закрывающий </a> между открывающим тегом и нашим совпадением
                        if before_match[last_a_open + after_a_open:].find('</a>') == -1:
                            # Мы внутри открытого <a> тега, пропускаем
                            continue
                
                # Заменяем это совпадение
                matched_text = processed_content[start:end]
                link_html = f'<a href="{full_url}" title="{related_post.title}">{matched_text}</a>'
                processed_content = processed_content[:start] + link_html + processed_content[end:]
                links_added += 1
                break  # Добавляем только одну ссылку на ключевое слово
        
        logger.info(
            '[SEO] Добавлено %s внутренних ссылок в статью: %s',
            links_added,
            safe_log_text(post.title) if getattr(post, 'title', None) else '',
        )
        return processed_content
        
    except Exception as e:
        logger.error(f"[SEO] Ошибка при добавлении внутренних ссылок: {str(e)}", exc_info=True)
        return html_content


def generate_table_of_contents(html_content, min_headings=3):
    """
    Генерирует таблицу содержания (TOC) для статьи на основе заголовков H2 и H3
    
    Args:
        html_content: HTML контент статьи
        min_headings: Минимальное количество заголовков для генерации TOC
    
    Returns:
        tuple: (toc_html, processed_content) - HTML таблицы содержания и контент с якорными ссылками
    """
    if not html_content:
        return None, html_content
    
    try:
        import hashlib
        
        # Находим все заголовки H2 и H3
        heading_pattern = r'<h([23])[^>]*>(.*?)</h[23]>'
        headings = re.findall(heading_pattern, html_content, re.IGNORECASE | re.DOTALL)
        
        if len(headings) < min_headings:
            return None, html_content
        
        # Генерируем TOC
        toc_items = []
        processed_content = html_content
        heading_count = 0
        skip_faq_subheads = False
        _faq_title_re = re.compile(
            r'(?:частые вопросы|часто задаваемые|❓\s*часты|\bfaq\b|html[-\s]*блок\s*faq)',
            re.IGNORECASE,
        )

        for level, heading_text in headings:
            heading_count += 1
            # Очищаем текст заголовка от HTML
            clean_text = re.sub(r'<[^>]+>', '', heading_text).strip()
            if not clean_text:
                continue
            lv = int(level)
            if lv == 2:
                if _faq_title_re.search(clean_text):
                    skip_faq_subheads = True
                    continue
                skip_faq_subheads = False
            elif lv == 3 and skip_faq_subheads:
                continue

            # Генерируем уникальный ID для якоря
            # Используем первые слова заголовка + номер для уникальности
            anchor_id = f"heading-{heading_count}-{hashlib.md5(clean_text.encode()).hexdigest()[:8]}"
            
            # Добавляем в TOC
            toc_items.append({
                'level': int(level),
                'text': clean_text,
                'anchor': anchor_id
            })
            
            # Добавляем ID к заголовку в контенте (только первое вхождение)
            heading_with_id = f'<h{level} id="{anchor_id}">{heading_text}</h{level}>'
            # Заменяем только первое вхождение этого заголовка
            pattern = re.escape(f'<h{level}') + r'[^>]*>' + re.escape(heading_text) + f'</h{level}>'
            if re.search(pattern, processed_content, re.IGNORECASE | re.DOTALL):
                processed_content = re.sub(
                    pattern,
                    heading_with_id,
                    processed_content,
                    count=1,
                    flags=re.IGNORECASE | re.DOTALL
                )
        
        if not toc_items:
            return None, html_content
        
        # Генерируем HTML для TOC
        toc_html = '<div class="table-of-contents bg-gray-50 dark:bg-gray-800 rounded-lg p-6 mb-8 border border-gray-200 dark:border-gray-700">\n'
        toc_html += '<h3 class="text-xl font-bold text-gray-900 dark:text-white mb-4">Содержание статьи</h3>\n'
        toc_html += '<nav class="toc-nav">\n'
        toc_html += '<ul class="space-y-2">\n'
        
        for item in toc_items:
            indent_class = 'ml-4' if item['level'] == 3 else ''
            toc_html += f'<li class="{indent_class}">\n'
            toc_html += f'<a href="#{item["anchor"]}" class="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline transition-colors">{item["text"]}</a>\n'
            toc_html += '</li>\n'
        
        toc_html += '</ul>\n'
        toc_html += '</nav>\n'
        toc_html += '</div>\n'
        
        logger.info(f"[SEO] Сгенерирована таблица содержания с {len(toc_items)} пунктами")
        return toc_html, processed_content
        
    except Exception as e:
        logger.error(f"[SEO] Ошибка при генерации таблицы содержания: {str(e)}", exc_info=True)
        return None, html_content


def generate_category_structured_data(category, posts, request=None):
    """
    Генерация CollectionPage structured data для страницы категории
    
    Args:
        category: Объект Category
        posts: QuerySet опубликованных статей в категории
        request: HttpRequest объект
    
    Returns:
        JSON строка с structured data
    """
    try:
        site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
        category_url = f"{site_url}{category.get_absolute_url()}"
        
        # Формируем список статей
        item_list = []
        for post in posts[:20]:  # Ограничиваем до 20
            post_url = f"{site_url}{post.get_absolute_url()}"
            item_list.append({
                "@type": "ListItem",
                "position": len(item_list) + 1,
                "item": {
                    "@type": "Article",
                    "headline": post.meta_title or post.title,
                    "url": post_url,
                    "datePublished": post.created.isoformat() if post.created else None,
                }
            })
        
        collection_data = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": category.title,
            "description": f"Статьи в категории: {category.title}",
            "url": category_url,
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": posts.count(),
                "itemListElement": item_list
            }
        }
        
        # Добавляем breadcrumb
        breadcrumb_items = [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Главная",
                "item": site_url
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Блог",
                "item": f"{site_url}/blog/"
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": category.title,
                "item": category_url
            }
        ]
        
        breadcrumb_data = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": breadcrumb_items
        }
        
        return {
            'collection': json.dumps(collection_data, ensure_ascii=False),
            'breadcrumb': json.dumps(breadcrumb_data, ensure_ascii=False)
        }
        
    except Exception as e:
        logger.error(f"[SEO] Ошибка при генерации structured data для категории: {str(e)}", exc_info=True)
        return None


def generate_author_structured_data(author, posts, request=None):
    """
    Генерация Person structured data для страницы автора
    
    Args:
        author: Объект User (автор)
        posts: QuerySet опубликованных статей автора
        request: HttpRequest объект
    
    Returns:
        JSON строка с structured data
    """
    try:
        site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
        author_url = f"{site_url}/blog/?author={author.id}"
        
        # Формируем список статей автора
        item_list = []
        for post in posts[:20]:  # Ограничиваем до 20
            post_url = f"{site_url}{post.get_absolute_url()}"
            item_list.append({
                "@type": "ListItem",
                "position": len(item_list) + 1,
                "item": {
                    "@type": "Article",
                    "headline": post.meta_title or post.title,
                    "url": post_url,
                    "datePublished": post.created.isoformat() if post.created else None,
                }
            })
        
        person_data = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": author.get_full_name() or author.username,
            "url": author_url,
            "description": f"Автор статей на LukInterLab.ru. Всего статей: {posts.count()}",
        }
        
        if author.email:
            person_data["email"] = author.email
        
        # Добавляем список публикаций
        if item_list:
            person_data["mainEntity"] = {
                "@type": "ItemList",
                "numberOfItems": posts.count(),
                "itemListElement": item_list
            }
        
        return json.dumps(person_data, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"[SEO] Ошибка при генерации structured data для автора: {str(e)}", exc_info=True)
        return None

