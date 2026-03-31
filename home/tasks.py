"""
Задачи для автоматизации SEO и других процессов
"""
import logging
from django.core.management import call_command
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from home.models import SEOModel
from Assistant.models import AssistantKnowledge

logger = logging.getLogger(__name__)


def optimize_seo_task():
    """Автоматическая SEO оптимизация для AI/ИИ запросов"""
    try:
        logger.info("[SEO] Запуск автоматической SEO оптимизации...")
        call_command('optimize_seo_for_ai', verbosity=0)
        logger.info("[SEO] SEO оптимизация завершена успешно")
        return True
    except Exception as e:
        logger.error(f"[SEO] Ошибка при SEO оптимизации: {str(e)}", exc_info=True)
        return False


def update_knowledge_base_task():
    """Обновление базы знаний для AI-ассистента"""
    try:
        logger.info("[AI] Запуск обновления базы знаний...")
        call_command('create_ai_knowledge_base', verbosity=0)
        logger.info("[AI] База знаний обновлена успешно")
        return True
    except Exception as e:
        logger.error(f"[AI] Ошибка при обновлении базы знаний: {str(e)}", exc_info=True)
        return False


def ping_search_engines():
    """Отправка уведомлений поисковым системам об обновлении sitemap"""
    try:
        from django.conf import settings
        import requests
        
        sitemap_url = f"{getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')}/sitemap.xml"
        
        # Google
        try:
            google_ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
            response = requests.get(google_ping_url, timeout=10)
            if response.status_code == 200:
                logger.info("[SEO] Google уведомлен об обновлении sitemap")
        except Exception as e:
            logger.warning(f"[SEO] Ошибка уведомления Google: {str(e)}")
        
        # Yandex
        try:
            yandex_ping_url = f"https://webmaster.yandex.ru/ping?sitemap={sitemap_url}"
            response = requests.get(yandex_ping_url, timeout=10)
            if response.status_code == 200:
                logger.info("[SEO] Yandex уведомлен об обновлении sitemap")
        except Exception as e:
            logger.warning(f"[SEO] Ошибка уведомления Yandex: {str(e)}")
        
        # Bing
        try:
            bing_ping_url = f"https://www.bing.com/ping?sitemap={sitemap_url}"
            response = requests.get(bing_ping_url, timeout=10)
            if response.status_code == 200:
                logger.info("[SEO] Bing уведомлен об обновлении sitemap")
        except Exception as e:
            logger.warning(f"[SEO] Ошибка уведомления Bing: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"[SEO] Ошибка при отправке уведомлений поисковикам: {str(e)}", exc_info=True)
        return False


def cleanup_old_sessions():
    """Очистка старых сессий корзины"""
    try:
        from home.models import Cart
        from django.utils import timezone
        from datetime import timedelta
        
        # Удаляем корзины старше 30 дней
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = Cart.objects.filter(updated__lt=cutoff_date).delete()[0]
        
        logger.info(f"[CLEANUP] Удалено {deleted_count} старых корзин")
        return deleted_count
    except Exception as e:
        logger.error(f"[CLEANUP] Ошибка при очистке корзин: {str(e)}", exc_info=True)
        return 0
