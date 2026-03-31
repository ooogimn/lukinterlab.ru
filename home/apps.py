from django.apps import AppConfig


class HomeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'home'
    verbose_name = 'Главная'
    
    def ready(self):
        """Инициализация при запуске приложения"""
        import home.signals  # Регистрируем сигналы
        
        # Автоматический запуск SEO оптимизации и базы знаний при старте
        # Используем отложенное выполнение через django.db.transaction.on_commit
        # чтобы избежать предупреждения о доступе к БД во время инициализации
        try:
            from django.db import transaction
            from django.core.management import call_command
            from django.core.cache import cache
            from django.utils import timezone
            import logging
            
            logger = logging.getLogger(__name__)
            
            def run_initialization_tasks():
                """Отложенное выполнение задач инициализации"""
                try:
                    # Проверяем кэш для SEO оптимизации
                    seo_cache_key = 'seo_optimization_last_run'
                    last_seo_run = cache.get(seo_cache_key)
                    if not last_seo_run or (timezone.now() - last_seo_run).days >= 1:
                        try:
                            call_command('optimize_seo_for_ai', verbosity=0)
                            cache.set(seo_cache_key, timezone.now(), 86400)  # Кэш на 24 часа
                        except Exception as e:
                            logger.warning(f"Не удалось запустить SEO оптимизацию при старте: {e}")
                    
                    # Проверяем кэш для базы знаний
                    knowledge_cache_key = 'ai_knowledge_base_last_run'
                    last_knowledge_run = cache.get(knowledge_cache_key)
                    if not last_knowledge_run or (timezone.now() - last_knowledge_run).days >= 1:
                        try:
                            call_command('create_ai_knowledge_base', verbosity=0)
                            cache.set(knowledge_cache_key, timezone.now(), 86400)  # Кэш на 24 часа
                        except Exception as e:
                            logger.warning(f"Не удалось запустить обновление базы знаний при старте: {e}")
                except Exception as e:
                    logger.warning(f"Ошибка при выполнении задач инициализации: {e}")
            
            # Откладываем выполнение до первой транзакции
            transaction.on_commit(run_initialization_tasks)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Ошибка при инициализации приложения home: {e}")
