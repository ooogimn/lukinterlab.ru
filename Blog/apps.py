from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Blog'
    verbose_name ="Журнал"
    
    def ready(self):
        import Blog.signals  # Регистрация сигналов