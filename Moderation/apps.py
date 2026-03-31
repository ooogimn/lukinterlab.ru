from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class ModerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Moderation'
    verbose_name = 'Модерация'
    
    def ready(self):
        import Moderation.signals  # Регистрация сигналов
        # Дополнительная регистрация сигналов для комментариев к отзывам и заказам
        try:
            from Moderation.signals import register_comment_signals
            register_comment_signals()
            logger.info("[MODERATION_APP] Все сигналы модерации успешно зарегистрированы")
        except Exception as e:
            logger.error(f"[MODERATION_APP] Ошибка при регистрации сигналов: {str(e)}", exc_info=True)
