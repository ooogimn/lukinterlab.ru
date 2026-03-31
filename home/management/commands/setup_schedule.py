"""
Management команда для настройки расписания задач django-Q
"""
from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    help = 'Настройка расписания задач django-Q'

    def handle(self, *args, **options):
        self.stdout.write('Настройка расписания задач...')
        
        # Очистка старых корзин (каждый день в 3:00)
        schedule, created = Schedule.objects.update_or_create(
            func='home.tasks.cleanup_old_sessions',
            name='cleanup_old_sessions',
            defaults={
                'schedule_type': Schedule.CRON,
                'cron': '0 3 * * *',
            }
        )
        action = 'создано' if created else 'обновлено'
        self.stdout.write(f'✓ Расписание cleanup_old_sessions {action}')
        
        # Обновление аналитики (каждый час)
        schedule, created = Schedule.objects.update_or_create(
            func='Assistant.ai_service.AnalyticsService.update_daily_analytics',
            name='update_analytics',
            defaults={
                'schedule_type': Schedule.CRON,
                'cron': '0 * * * *',
            }
        )
        action = 'создано' if created else 'обновлено'
        self.stdout.write(f'✓ Расписание update_analytics {action}')
        
        # SEO оптимизация для AI/ИИ (ежедневно в 2:00)
        schedule, created = Schedule.objects.update_or_create(
            func='home.tasks.optimize_seo_task',
            name='optimize_seo_ai',
            defaults={
                'schedule_type': Schedule.CRON,
                'cron': '0 2 * * *',
            }
        )
        action = 'создано' if created else 'обновлено'
        self.stdout.write(f'✓ Расписание optimize_seo_ai {action}')
        
        # Обновление базы знаний AI-ассистента (ежедневно в 3:00)
        schedule, created = Schedule.objects.update_or_create(
            func='home.tasks.update_knowledge_base_task',
            name='update_ai_knowledge_base',
            defaults={
                'schedule_type': Schedule.CRON,
                'cron': '0 3 * * *',
            }
        )
        action = 'создано' if created else 'обновлено'
        self.stdout.write(f'✓ Расписание update_ai_knowledge_base {action}')
        
        # Отправка уведомлений поисковикам об обновлении sitemap (ежедневно в 4:00)
        schedule, created = Schedule.objects.update_or_create(
            func='home.tasks.ping_search_engines',
            name='ping_search_engines',
            defaults={
                'schedule_type': Schedule.CRON,
                'cron': '0 4 * * *',
            }
        )
        action = 'создано' if created else 'обновлено'
        self.stdout.write(f'✓ Расписание ping_search_engines {action}')
        
        self.stdout.write(self.style.SUCCESS('\nРасписание успешно настроено!'))
        self.stdout.write('\nДоступные задачи:')
        self.stdout.write('  - cleanup_old_sessions: Очистка старых корзин (каждый день в 3:00)')
        self.stdout.write('  - update_analytics: Обновление аналитики (каждый час)')
        self.stdout.write('  - optimize_seo_ai: SEO оптимизация для AI/ИИ (каждый день в 2:00)')
        self.stdout.write('  - update_ai_knowledge_base: Обновление базы знаний (каждый день в 3:00)')
        self.stdout.write('  - ping_search_engines: Уведомление поисковиков (каждый день в 4:00)')
        self.stdout.write('\nДля запуска воркера django-Q выполните:')
        self.stdout.write('  python manage.py qcluster')

