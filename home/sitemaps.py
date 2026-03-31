from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.conf import settings
from Blog.models import Post, Category
from home.models import Otziv, Rabota
from django.utils import timezone


class StaticViewSitemap(Sitemap):
    """Sitemap для статических страниц"""
    changefreq = 'weekly'
    priority = 0.9
    
    def items(self):
        return [
            'home:home',
            'home:otzivs',
            'home:otziv-create',
        ]
    
    def location(self, obj):
        """Преобразует имя URL в путь"""
        return reverse(obj)
    
    def lastmod(self, obj):
        return timezone.now()


class BlogPostSitemap(Sitemap):
    """Sitemap для постов блога с изображениями"""
    changefreq = 'weekly'
    priority = 0.8
    
    def items(self):
        return Post.objects.filter(status='published').select_related('category', 'author')
    
    def lastmod(self, obj):
        """Возвращает дату обновления или дату создания"""
        if obj.updated:
            return obj.updated
        elif obj.created:
            return obj.created
        return timezone.now()
    
    def location(self, obj):
        return obj.get_absolute_url()
    
    def priority(self, obj):
        """Приоритет на основе даты обновления и популярности"""
        # Базовый приоритет
        base_priority = 0.8
        
        # Увеличиваем приоритет для свежих статей (менее 30 дней)
        from datetime import timedelta
        if obj.updated and (timezone.now() - obj.updated) < timedelta(days=30):
            base_priority = 0.9
        
        # Увеличиваем приоритет для популярных статей
        if obj.views > 1000:
            base_priority = min(1.0, base_priority + 0.1)
        
        return base_priority
    
    def changefreq(self, obj):
        """Частота обновления на основе даты обновления"""
        if not obj.updated:
            return 'monthly'
        
        from datetime import timedelta
        days_since_update = (timezone.now() - obj.updated).days
        
        if days_since_update < 7:
            return 'daily'
        elif days_since_update < 30:
            return 'weekly'
        elif days_since_update < 90:
            return 'monthly'
        else:
            return 'yearly'
    


class BlogCategorySitemap(Sitemap):
    """Sitemap для категорий блога"""
    changefreq = 'monthly'
    priority = 0.6
    
    def items(self):
        return Category.objects.all()
    
    def lastmod(self, obj):
        """Возвращает дату создания или дату последнего обновления поста в категории"""
        if obj.created:
            # Пытаемся получить дату последнего обновления поста в категории
            try:
                latest_post = obj.posts.filter(status='published').latest('updated')
                if latest_post and latest_post.updated:
                    return latest_post.updated
            except (Post.DoesNotExist, AttributeError):
                pass
            return obj.created
        return timezone.now()
    
    def location(self, obj):
        return obj.get_absolute_url()


class OtzivSitemap(Sitemap):
    """Sitemap для отзывов"""
    changefreq = 'monthly'
    priority = 0.7
    
    def items(self):
        return Otziv.objects.filter(active=True)
    
    def lastmod(self, obj):
        """Возвращает дату создания или текущую дату"""
        if obj.created:
            return obj.created
        return timezone.now()
    
    def location(self, obj):
        # Возвращаем URL конкретного отзыва
        return reverse('home:otziv-detail', args=[obj.pk])


class RabotaSitemap(Sitemap):
    """Sitemap для работ"""
    changefreq = 'monthly'
    priority = 0.7
    
    def items(self):
        return Rabota.objects.filter(status='completed')
    
    def lastmod(self, obj):
        """Возвращает дату обновления или дату создания"""
        if obj.updated:
            return obj.updated
        elif obj.created:
            return obj.created
        return timezone.now()
    
    def location(self, obj):
        return obj.get_absolute_url() 