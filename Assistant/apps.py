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
        # После autodiscover django-q: своя админка Schedule с колонкой AISchedule.name
        try:
            from Assistant.dq_schedule_admin import register_assistant_django_q_schedule_admin

            register_assistant_django_q_schedule_admin()
        except ImportError:
            pass