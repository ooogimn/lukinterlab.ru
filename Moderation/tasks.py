"""
Фоновые задачи для модерации (Django-Q)
"""
import logging
from django.utils import timezone
from Blog.models import Post, Comment
from .models import (
    ArticleModeration, CommentModeration,
    ModerationCriteria, CommentModerationCriteria
)
from .services import (
    ArticleModerationService,
    CommentModerationService,
    SEOService,
    NotificationService,
    StatisticsService
)

logger = logging.getLogger(__name__)


def moderate_articles_task():
    """Задача автоматической модерации статей"""
    try:
        service = ArticleModerationService()
        notification_service = NotificationService()
        
        # Получаем статьи, ожидающие модерации
        pending_moderations = ArticleModeration.objects.filter(
            status='pending'
        ).select_related('post', 'criteria_used')
        
        # Получаем активные критерии
        criteria = ModerationCriteria.objects.filter(is_active=True).first()
        
        if not criteria:
            logger.warning("Нет активных критериев модерации")
            return {'success': False, 'error': 'Нет активных критериев'}
        
        moderated_count = 0
        for moderation in pending_moderations:
            try:
                result = service.moderate_article(moderation.post, criteria)
                if result.get('moderation'):
                    moderated_count += 1
                    # Отправляем уведомление если статус изменился
                    if result.get('status') != 'pending':
                        notification_service.notify_article_pending(result['moderation'])
                    logger.info(f"Статья {moderation.post.id} промодерирована: {result.get('status')}")
            except Exception as e:
                logger.error(f"Ошибка модерации статьи {moderation.post.id}: {str(e)}")
        
        logger.info(f"Автоматическая модерация завершена: обработано {moderated_count} статей")
        return {
            'success': True,
            'moderated_count': moderated_count,
        }
    except Exception as e:
        logger.error(f"Ошибка в задаче модерации статей: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


def moderate_comments_task():
    """Задача автоматической модерации комментариев"""
    try:
        service = CommentModerationService()
        
        # Получаем комментарии без действия (не промодерированные)
        # Примечание: 'comment' - это GenericForeignKey, его нельзя использовать в select_related
        pending_moderations = CommentModeration.objects.filter(
            action__isnull=True
        ).select_related('content_type', 'criteria_used')
        
        # Получаем активные критерии
        criteria = CommentModerationCriteria.objects.filter(is_active=True).first()
        
        if not criteria:
            logger.warning("Нет активных критериев модерации комментариев")
            return {'success': False, 'error': 'Нет активных критериев'}
        
        moderated_count = 0
        for moderation in pending_moderations:
            try:
                result = service.moderate_comment(moderation.comment, criteria)
                if result.get('moderation'):
                    moderated_count += 1
                    logger.info(f"Комментарий {moderation.comment.id} промодерирован: {result.get('action')}")
            except Exception as e:
                logger.error(f"Ошибка модерации комментария {moderation.comment.id}: {str(e)}")
        
        logger.info(f"Автоматическая модерация комментариев завершена: обработано {moderated_count} комментариев")
        return {
            'success': True,
            'moderated_count': moderated_count,
        }
    except Exception as e:
        logger.error(f"Ошибка в задаче модерации комментариев: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


def analyze_seo_task():
    """Задача SEO анализа статей"""
    try:
        service = SEOService()
        notification_service = NotificationService()
        
        # Получаем опубликованные статьи без SEO анализа или с устаревшим анализом
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=30)
        
        posts = Post.objects.filter(
            status='published'
        ).exclude(
            seo_analysis__updated_at__gte=cutoff_date
        )[:50]  # Ограничиваем количество за раз
        
        analyzed_count = 0
        for post in posts:
            try:
                result = service.analyze_post(post)
                if result.get('analysis'):
                    analyzed_count += 1
                    # Отправляем уведомление если низкий score
                    if result.get('score', 0) < 50:
                        notification_service.notify_seo_low_score(result['analysis'])
                    logger.info(f"SEO анализ статьи {post.id} завершен: score={result.get('score')}")
            except Exception as e:
                logger.error(f"Ошибка SEO анализа статьи {post.id}: {str(e)}")
        
        logger.info(f"SEO анализ завершен: обработано {analyzed_count} статей")
        return {
            'success': True,
            'analyzed_count': analyzed_count,
        }
    except Exception as e:
        logger.error(f"Ошибка в задаче SEO анализа: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


def update_statistics_task():
    """Задача обновления статистики модерации"""
    try:
        stats_service = StatisticsService()
        
        # Обновляем статистику за сегодня
        stats = stats_service.update_daily_statistics()
        
        logger.info(f"Статистика обновлена за {stats.date}")
        return {
            'success': True,
            'date': str(stats.date),
        }
    except Exception as e:
        logger.error(f"Ошибка в задаче обновления статистики: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}


def submit_sitemap_task():
    """Регулярная отправка sitemap в поисковые системы"""
    try:
        from Assistant.search_engines_submitter import SearchEnginesSubmitter
        from django.conf import settings
        
        submitter = SearchEnginesSubmitter()
        sitemap_url = f"{submitter.site_url}/sitemap.xml"
        
        results = {
            'google': submitter.submit_to_google(sitemap_url),
            'yandex': submitter.submit_to_yandex(sitemap_url),
            'bing': submitter.submit_to_bing(sitemap_url),
        }
        
        success_count = sum(1 for r in results.values() if r.get('success', False))
        logger.info(f"[SUBMIT] Sitemap отправлен в поисковые системы: {success_count}/3 успешно")
        
        return {
            'success': True,
            'results': results,
            'success_count': success_count,
        }
    except ImportError:
        logger.warning("[SUBMIT] Модуль SearchEnginesSubmitter не найден, пропускаем отправку sitemap")
        return {'success': False, 'error': 'Модуль не найден'}
    except Exception as e:
        logger.error(f"[SUBMIT] Ошибка отправки sitemap: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}
