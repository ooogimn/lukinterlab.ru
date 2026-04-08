from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed
from .models import Post
from .utils import effective_post_meta_description
from django.conf import settings


class LatestPostsFeed(Feed):
    """RSS feed для последних опубликованных статей блога"""
    
    title = "LukInterLab.ru - Блог о красоте и стиле"
    link = "/blog/"
    description = "Последние статьи о красоте, моде, стиле и уходе за собой"
    feed_type = Atom1Feed  # Используем Atom формат (более современный)
    
    def items(self):
        """Получаем последние 20 опубликованных статей"""
        return Post.objects.filter(status='published').order_by('-created')[:20]
    
    def item_title(self, item):
        """Заголовок статьи"""
        return item.meta_title or item.title
    
    def item_description(self, item):
        """Описание статьи для RSS (та же логика, что и meta description на сайте)."""
        return effective_post_meta_description(item, max_length=300)
    
    def item_link(self, item):
        """Ссылка на статью"""
        return settings.SITE_URL + item.get_absolute_url()
    
    def item_author_name(self, item):
        """Имя автора"""
        return item.author.get_full_name() or item.author.username
    
    def item_author_email(self, item):
        """Email автора (если доступен)"""
        return item.author.email if item.author.email else None
    
    def item_pubdate(self, item):
        """Дата публикации"""
        return item.created
    
    def item_updateddate(self, item):
        """Дата обновления"""
        return item.updated
    
    def item_categories(self, item):
        """Категории и теги статьи"""
        categories = [item.category.title]
        # Добавляем теги
        tags = item.tags.all()
        categories.extend([tag.name for tag in tags])
        return categories
    
    def item_enclosure_url(self, item):
        """URL изображения для RSS"""
        if item.kartinka:
            return settings.SITE_URL + item.kartinka.url
        return None
    
    def item_enclosure_length(self, item):
        """Размер изображения (если доступен)"""
        if item.kartinka:
            try:
                return item.kartinka.size
            except:
                return None
        return None
    
    def item_enclosure_mime_type(self, item):
        """MIME тип изображения"""
        if item.kartinka:
            # Определяем тип по расширению
            ext = item.kartinka.name.split('.')[-1].lower()
            mime_types = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'webp': 'image/webp',
                'gif': 'image/gif',
            }
            return mime_types.get(ext, 'image/jpeg')
        return None


class LatestPostsRSSFeed(LatestPostsFeed):
    """RSS 2.0 feed (классический формат)"""
    feed_type = None  # По умолчанию RSS 2.0

