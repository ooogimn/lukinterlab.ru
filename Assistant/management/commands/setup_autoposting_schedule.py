"""
Management-команда: одно AISchedule с интервальными запусками + минутный тик Django-Q.
Ранее создавались отдельные CRON на каждый слот — заменено на interval_hours/minutes.
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from Assistant.models import AISchedule, PromptTemplate
from Assistant.tasks import setup_schedules
from Blog.models import Category

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Создаёт/обновляет одно AISchedule: ~N запусков в день в окне start-hour–end-hour '
        '(средний интервал в минутах между запусками), затем синхронизирует django-q (минутный тик).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-hour',
            type=int,
            default=8,
            help='Час начала первого запуска сегодня или завтра (по умолчанию 8)',
        )
        parser.add_argument(
            '--end-hour',
            type=int,
            default=22,
            help='Не используется в расчёте интервала напрямую — см. total-articles',
        )
        parser.add_argument(
            '--total-articles',
            type=int,
            default=10,
            help='Целевое число запусков в сутки (для расчёта среднего интервала в минутах)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Настройка расписания автопостинга (интервальная модель)...')

        start_hour = options.get('start_hour', 8)
        end_hour = options.get('end_hour', 22)
        total_articles = max(1, options.get('total_articles', 10))

        prompt_template = PromptTemplate.objects.filter(is_active=True).first()
        if not prompt_template:
            self.stdout.write(self.style.WARNING(
                '[WARNING] Не найден активный шаблон промпта. Создайте его в админ-панели сначала.'
            ))
            return

        categories = Category.objects.filter(activ=True)
        if not categories.exists():
            self.stdout.write(self.style.WARNING(
                '[WARNING] Не найдено активных категорий. Создайте их в админ-панели сначала.'
            ))
            return

        total_hours = max(0.5, float(end_hour - start_hour))
        total_minutes_window = int(total_hours * 60)
        interval_minutes = max(1, total_minutes_window // total_articles)
        interval_hours = interval_minutes // 60
        interval_mins_only = interval_minutes % 60
        if interval_hours == 0 and interval_mins_only == 0:
            interval_mins_only = max(1, interval_minutes)

        now = timezone.now()
        local = timezone.localtime(now)
        start_today = local.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        if local >= start_today:
            first_run = start_today + timedelta(days=1)
        else:
            first_run = start_today
        first_run_at = timezone.make_aware(
            datetime.combine(first_run.date(), first_run.time()),
            timezone.get_current_timezone(),
        )

        schedule_name = (
            f'Автопостинг статей (~{total_articles} запуск./день, каждые ~{interval_minutes} мин)'
        )
        schedule, created = AISchedule.objects.get_or_create(
            name=schedule_name,
            defaults={
                'prompt_template': prompt_template,
                'first_run_at': first_run_at,
                'interval_hours': interval_hours,
                'interval_minutes': interval_mins_only,
                'articles_per_run': 1,
                'is_active': True,
                'max_schedule_runs': None,
            },
        )

        if not created:
            schedule.prompt_template = prompt_template
            schedule.first_run_at = first_run_at
            schedule.interval_hours = interval_hours
            schedule.interval_minutes = interval_mins_only
            schedule.articles_per_run = 1
            schedule.is_active = True
            schedule.save()

        schedule.sync_next_run()
        schedule.save(update_fields=['next_run'])

        if created:
            self.stdout.write(self.style.SUCCESS(f'[OK] Создано расписание: {schedule.name}'))
        else:
            self.stdout.write(f'[INFO] Обновлено расписание: {schedule.name}')

        self.stdout.write(
            f'  Интервал между запусками: {interval_hours} ч {interval_mins_only} мин '
            f'(≈ {interval_minutes} мин суммарно)'
        )
        self.stdout.write(f'  Первый запуск (якорь): {first_run_at}')
        self.stdout.write(self.style.WARNING(
            '\nЗапустите воркер Django-Q: python manage.py qcluster'
        ))

        setup_schedules()
        self.stdout.write(self.style.SUCCESS(
            '[OK] django-q: минутный опрос tick_ai_schedules и очистка старых задач run_schedule_task.'
        ))
