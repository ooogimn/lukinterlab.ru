from django.apps import AppConfig


class AssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Assistant'
    verbose_name = 'AI Ассистент'
    
    def ready(self):
        """Инициализация при запуске приложения"""
        import Assistant.signals  # Регистрируем сигналы
    
    def ready(self):
        """Инициализация приложения"""
        # Импортируем сигналы
        try:
            import Assistant.signals
        except ImportError:
            pass