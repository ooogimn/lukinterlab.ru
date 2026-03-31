"""
Management команда для настройки автоматических задач модерации в Django-Q
"""
from django.core.management.base import BaseCommand
from django_q.models import Schedule
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Настройка автоматических задач модерации в Django-Q'

    def handle(self, *args, **options):
        self.stdout.write('Настройка задач модерации...')
        
        # Задача модерации статей (каждый час)
        schedule_articles, created = Schedule.objects.update_or_create(
            name='moderate_articles_hourly',
            defaults={
                'func': 'Moderation.tasks.moderate_articles_task',
                'schedule_type': Schedule.HOURLY,
                'repeats': -1,  # Бесконечно
            }
        )
        action = 'создана' if created else 'обновлена'
        self.stdout.write(self.style.SUCCESS(f'[OK] Задача модерации статей {action}'))
        
        # Задача модерации комментариев (каждый час)
        schedule_comments, created = Schedule.objects.update_or_create(
            name='moderate_comments_hourly',
            defaults={
                'func': 'Moderation.tasks.moderate_comments_task',
                'schedule_type': Schedule.HOURLY,
                'repeats': -1,
            }
        )
        action = 'создана' if created else 'обновлена'
        self.stdout.write(self.style.SUCCESS(f'[OK] Задача модерации комментариев {action}'))
        
        # Задача SEO анализа (ежедневно)
        schedule_seo, created = Schedule.objects.update_or_create(
            name='analyze_seo_daily',
            defaults={
                'func': 'Moderation.tasks.analyze_seo_task',
                'schedule_type': Schedule.DAILY,
                'repeats': -1,
            }
        )
        action = 'создана' if created else 'обновлена'
        self.stdout.write(self.style.SUCCESS(f'[OK] Задача SEO анализа {action}'))
        
        # Задача обновления статистики (ежедневно)
        schedule_stats, created = Schedule.objects.update_or_create(
            name='update_statistics_daily',
            defaults={
                'func': 'Moderation.tasks.update_statistics_task',
                'schedule_type': Schedule.DAILY,
                'repeats': -1,
            }
        )
        action = 'создана' if created else 'обновлена'
        self.stdout.write(self.style.SUCCESS(f'[OK] Задача обновления статистики {action}'))
        
        # Задача отправки sitemap в поисковые системы (еженедельно)
        schedule_sitemap, created = Schedule.objects.update_or_create(
            name='submit_sitemap_weekly',
            defaults={
                'func': 'Moderation.tasks.submit_sitemap_task',
                'schedule_type': Schedule.WEEKLY,
                'repeats': -1,
            }
        )
        action = 'создана' if created else 'обновлена'
        self.stdout.write(self.style.SUCCESS(f'[OK] Задача отправки sitemap {action}'))
        
        self.stdout.write(self.style.SUCCESS('\nВсе задачи успешно настроены!'))
        self.stdout.write(self.style.WARNING('\nНе забудьте запустить Django-Q worker:'))
        self.stdout.write(self.style.WARNING('python manage.py qcluster'))

