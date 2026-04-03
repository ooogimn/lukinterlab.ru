from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import models
from .models import ChatMessage, ChatSession, AISchedule
from .ai_service import AnalyticsService
from .tasks import setup_schedules, remove_schedule
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ChatMessage)
def update_analytics_on_message(sender, instance, created, **kwargs):
    """Обновить аналитику при создании нового сообщения"""
    if created and instance.message_type == 'assistant':
        try:
            # Обновляем ежедневную аналитику
            AnalyticsService.update_daily_analytics()
        except Exception as e:
            logger.error(f"Error updating analytics: {str(e)}")


@receiver(post_save, sender=ChatSession)
def create_welcome_message(sender, instance, created, **kwargs):
    """Создать приветственное сообщение для новой сессии"""
    if created:
        try:
            from .models import AssistantSettings, ChatMessage
            
            settings = AssistantSettings.objects.first()
            if settings and settings.is_enabled:
                ChatMessage.objects.create(
                    session=instance,
                    message_type='assistant',
                    content=settings.welcome_message
                )
        except Exception as e:
            logger.error(f"Error creating welcome message: {str(e)}")


@receiver(post_save, sender=AISchedule)
def setup_ai_schedule(sender, instance, created, **kwargs):
    """Настроить расписание Django-Q при создании/обновлении AISchedule"""
    if kwargs.get('raw'):
        return
    if instance.is_active:
        try:
            setup_schedules()
            logger.info(f"[OK] Расписание Django-Q настроено для: {instance.name}")
        except Exception as e:
            logger.error(f"Ошибка настройки расписания Django-Q: {str(e)}")


@receiver(post_delete, sender=AISchedule)
def remove_ai_schedule(sender, instance, **kwargs):
    """Удалить расписание Django-Q при удалении AISchedule"""
    if kwargs.get('raw'):
        return
    try:
        remove_schedule(instance.id)
        logger.info(f"[OK] Расписание Django-Q удалено для: {instance.name}")
    except Exception as e:
        logger.error(f"Ошибка удаления расписания Django-Q: {str(e)}")
