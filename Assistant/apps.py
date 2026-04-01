from django.apps import AppConfig


class AssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Assistant'
    verbose_name = 'AI Ассистент'
    
    def ready(self):
        """Инициализация при запуске приложения — регистрация сигналов."""
        try:
            import Assistant.signals  # noqa: F401
        except ImportError:
            pass