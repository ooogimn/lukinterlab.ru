from django.apps import AppConfig


class HomeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'home'
    verbose_name = 'Главная'

    def ready(self):
        """Регистрация сигналов. Тяжёлые задачи не запускаются здесь — только через django-q."""
        import home.signals  # noqa: F401
