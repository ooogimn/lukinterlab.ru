"""
Сервис для SEO оптимизации статей
"""
import logging
import json
import re
from typing import Dict, Any, Optional
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from Blog.models import Post, Category

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


class SEOArticleService:
    """Сервис для генерации SEO метатегов и structured data"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')
    
    def generate_seo_meta(self, post: Post) -> Dict[str, str]:
        """
        Генерация SEO метатегов для статьи
        
        Args:
            post: Статья Post
            
        Returns:
            Словарь с метатегами
        """
        # Meta title
        meta_title = post.meta_title or post.title
        if len(meta_title) > 60:
            meta_title = meta_title[:57] + '...'
        
        # Meta description
        meta_description = post.meta_description
        if not meta_description:
            if post.description:
                meta_description = post.description
            else:
                # Берем первые слова из контента
                text_content = self._extract_text_from_html(post.content)
                words = text_content.split()[:25]
                meta_description = ' '.join(words)
        
        if len(meta_description) > 160:
            meta_description = meta_description[:157] + '...'
        
        # Meta keywords
        meta_keywords = post.meta_keywords
        if not meta_keywords:
            # Генерируем из тегов и контента
            keywords = []
            if post.tags.exists():
                keywords.extend([tag.name for tag in post.tags.all()])
            
            # Добавляем ключевые слова из контента
            text_content = self._extract_text_from_html(post.content)
            content_keywords = self._extract_keywords_from_text(text_content, max_keywords=5)
            keywords.extend(content_keywords)
            
            meta_keywords = ', '.join(keywords[:10])
        
        # Focus keyword
        focus_keyword = post.focus_keyword
        if not focus_keyword and post.tags.exists():
            focus_keyword = post.tags.first().name
        
        return {
            'meta_title': meta_title,
            'meta_description': meta_description,
            'meta_keywords': meta_keywords,
            'focus_keyword': focus_keyword,
        }
    
    def generate_structured_data(self, post: Post, faq_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Генерация JSON-LD structured data для статьи
        
        Args:
            post: Статья Post
            faq_data: FAQ данные в формате [{"question": "...", "answer": "..."}]
            
        Returns:
            Словарь с structured data
        """
        article_url = f"{self.site_url}{post.get_absolute_url()}"
        
        # Article schema
        article_schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": post.title,
            "description": post.meta_description or post.description or "",
            "image": self._get_image_url(post),
            "datePublished": post.created.isoformat() if post.created else timezone.now().isoformat(),
            "dateModified": post.updated.isoformat() if post.updated else timezone.now().isoformat(),
            "author": {
                "@type": "Person",
                "name": post.author.get_full_name() or post.author.username,
            },
            "publisher": {
                "@type": "Organization",
                "name": "LukInterLab",
                "logo": {
                    "@type": "ImageObject",
                    "url": f"{self.site_url}/static/images/logo.png"
                }
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": article_url
            }
        }
        
        # BreadcrumbList
        breadcrumb_schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Главная",
                    "item": self.site_url
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": "Блог",
                    "item": f"{self.site_url}/blog/"
                }
            ]
        }
        
        # Добавляем категорию в breadcrumb
        if post.category:
            breadcrumb_schema["itemListElement"].append({
                "@type": "ListItem",
                "position": 3,
                "name": post.category.title,
                "item": f"{self.site_url}{post.category.get_absolute_url()}"
            })
        
        breadcrumb_schema["itemListElement"].append({
            "@type": "ListItem",
            "position": len(breadcrumb_schema["itemListElement"]) + 1,
            "name": post.title,
            "item": article_url
        })
        
        structured_data = {
            'article': article_schema,
            'breadcrumb': breadcrumb_schema,
        }
        
        # FAQPage schema (если есть FAQ)
        if faq_data and isinstance(faq_data, list) and len(faq_data) > 0:
            faq_schema = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": []
            }
            
            for item in faq_data:
                if isinstance(item, dict) and 'question' in item and 'answer' in item:
                    faq_schema["mainEntity"].append({
                        "@type": "Question",
                        "name": item['question'],
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": item['answer']
                        }
                    })
            
            if faq_schema["mainEntity"]:
                structured_data['faq'] = faq_schema
        
        return structured_data
    
    def apply_seo_to_post(self, post: Post) -> Post:
        """
        Применение SEO оптимизации к статье
        
        Args:
            post: Статья Post
            
        Returns:
            Обновленная статья
        """
        # Генерируем метатеги
        meta = self.generate_seo_meta(post)
        
        # Обновляем поля статьи
        if not post.meta_title:
            post.meta_title = meta['meta_title']
        if not post.meta_description:
            post.meta_description = meta['meta_description']
        if not post.meta_keywords:
            post.meta_keywords = meta['meta_keywords']
        if not post.focus_keyword:
            post.focus_keyword = meta['focus_keyword']
        
        post.save(update_fields=['meta_title', 'meta_description', 'meta_keywords', 'focus_keyword'])
        
        # Генерируем structured data (можно использовать в шаблонах)
        # FAQ данные берутся из post.faq_data
        structured_data = self.generate_structured_data(post, post.faq_data)
        # Сохраняем в кэш или можно добавить поле для хранения
        # Пока просто логируем
        safe_title = safe_log_text(post.title) if post.title else ''
        logger.debug(f"Structured data сгенерирована для статьи: {safe_title}")
        
        logger.info(f"[OK] SEO оптимизация применена к статье: {safe_title}")
        
        return post
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """Извлечение текста из HTML"""
        if not html_content:
            return ""
        
        # Простая очистка HTML тегов
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_keywords_from_text(self, text: str, max_keywords: int = 10) -> list:
        """Извлечение ключевых слов из текста"""
        # Слова длиннее 4 символов
        words = re.findall(r'\b[а-яА-ЯёЁa-zA-Z]{4,}\b', text.lower())
        
        # Подсчет частоты
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Сортируем по частоте
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:max_keywords]]
    
    def _get_image_url(self, post: Post) -> str:
        """Получить URL изображения для structured data"""
        if post.og_image:
            return f"{self.site_url}{post.og_image.url}"
        elif post.kartinka:
            return f"{self.site_url}{post.kartinka.url}"
        else:
            return f"{self.site_url}/static/images/default-article.jpg"
