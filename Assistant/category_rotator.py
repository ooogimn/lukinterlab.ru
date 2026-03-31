"""
Сервис для умной ротации категорий при автогенерации статей
"""
import logging
from typing import Optional
from django.utils import timezone
from django.db.models import Q, F
from datetime import timedelta

from .models import CategoryStats
from Blog.models import Category

logger = logging.getLogger(__name__)


class CategoryRotator:
    """Сервис для умной ротации категорий"""
    
    def __init__(self):
        """Инициализация ротатора"""
        pass
    
    def get_next_category(self, exclude_categories: list = None) -> Optional[Category]:
        """
        Выбор следующей категории для публикации
        
        Логика:
        - Начало: по дате последней публикации (наименее используемая)
        - Со временем: популярные категории (с высокими просмотрами) публикуются в 2 раза чаще
        
        Args:
            exclude_categories: Список ID категорий для исключения
            
        Returns:
            Выбранная категория или None
        """
        try:
            # Получаем все активные категории
            categories = Category.objects.filter(activ=True)
            
            if exclude_categories:
                categories = categories.exclude(id__in=exclude_categories)
            
            if not categories.exists():
                logger.warning("Нет активных категорий для ротации")
                return None
            
            # Получаем или создаем статистику для всех категорий
            category_stats = []
            for category in categories:
                stats, created = CategoryStats.objects.get_or_create(
                    category=category,
                    defaults={
                        'total_views': 0,
                        'articles_count': 0,
                        'priority': 1.0,
                    }
                )
                category_stats.append((category, stats))
            
            # Сортируем по приоритету и дате последней публикации
            # Популярные категории (priority=2.0) будут выбираться в 2 раза чаще
            # Если приоритет одинаковый, выбираем категорию с более старой публикацией
            
            # Разделяем на группы по приоритету
            high_priority = [(cat, stats) for cat, stats in category_stats if stats.priority >= 2.0]
            medium_priority = [(cat, stats) for cat, stats in category_stats if 1.0 <= stats.priority < 2.0]
            low_priority = [(cat, stats) for cat, stats in category_stats if stats.priority < 1.0]
            
            # Выбираем категорию
            selected_category = None
            
            # 70% вероятность выбрать из высокоприоритетных (популярных)
            import random
            if high_priority and random.random() < 0.7:
                # Сортируем по дате последней публикации (старые первыми)
                high_priority.sort(
                    key=lambda x: x[1].last_publication or timezone.now() - timedelta(days=365),
                    reverse=False
                )
                selected_category = high_priority[0][0]
                logger.info(f"[OK] Выбрана популярная категория: {selected_category.title} (приоритет: {high_priority[0][1].priority:.2f})")
            
            # 25% вероятность выбрать из средних
            elif medium_priority and not selected_category:
                if random.random() < 0.25 or not high_priority:
                    medium_priority.sort(
                        key=lambda x: x[1].last_publication or timezone.now() - timedelta(days=365),
                        reverse=False
                    )
                    selected_category = medium_priority[0][0]
                    logger.info(f"[OK] Выбрана категория среднего приоритета: {selected_category.title}")
            
            # 5% вероятность выбрать из низких (или если других нет)
            if not selected_category and low_priority:
                low_priority.sort(
                    key=lambda x: x[1].last_publication or timezone.now() - timedelta(days=365),
                    reverse=False
                )
                selected_category = low_priority[0][0]
                logger.info(f"[OK] Выбрана категория низкого приоритета: {selected_category.title}")
            
            # Если все еще не выбрана, берем любую с самой старой публикацией
            if not selected_category:
                all_sorted = sorted(
                    category_stats,
                    key=lambda x: x[1].last_publication or timezone.now() - timedelta(days=365),
                    reverse=False
                )
                selected_category = all_sorted[0][0]
                logger.info(f"[OK] Выбрана категория по дате: {selected_category.title}")
            
            return selected_category
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка выбора категории: {str(e)}", exc_info=True)
            # Fallback: берем первую активную категорию
            try:
                return Category.objects.filter(activ=True).first()
            except:
                return None
    
    def track_category_views(self, category: Category, views: int = 0):
        """
        Отслеживание просмотров категории
        
        Args:
            category: Категория
            views: Количество просмотров
        """
        try:
            stats, created = CategoryStats.objects.get_or_create(
                category=category,
                defaults={
                    'total_views': views,
                    'articles_count': 0,
                    'priority': 1.0,
                }
            )
            
            if not created:
                stats.total_views += views
                stats.update_priority()
            
            logger.debug(f"[STATS] Обновлена статистика категории {category.title}: просмотры={stats.total_views}")
            
        except Exception as e:
            logger.error(f"Ошибка отслеживания просмотров категории: {str(e)}")
    
    def calculate_category_priority(self, category: Category) -> float:
        """
        Расчет приоритета категории
        
        Args:
            category: Категория
            
        Returns:
            Приоритет категории (0.5 - 2.0)
        """
        try:
            stats = CategoryStats.objects.filter(category=category).first()
            if stats:
                stats.update_priority()
                return stats.priority
            return 1.0
        except Exception as e:
            logger.error(f"Ошибка расчета приоритета: {str(e)}")
            return 1.0
    
    def record_publication(self, category: Category, views: int = 0):
        """
        Записать публикацию статьи в категории
        
        Args:
            category: Категория
            views: Начальное количество просмотров (обычно 0)
        """
        try:
            stats, created = CategoryStats.objects.get_or_create(
                category=category,
                defaults={
                    'total_views': views,
                    'articles_count': 1,
                    'last_publication': timezone.now(),
                    'priority': 1.0,
                }
            )
            
            if not created:
                stats.record_publication(views)
            
            logger.info(f"[PUBLISH] Записана публикация в категории {category.title}: статей={stats.articles_count}, просмотры={stats.total_views}")
            
        except Exception as e:
            logger.error(f"Ошибка записи публикации: {str(e)}")
