# Интервальное расписание (первый запуск + шаг); удалены frequency/cron/start_time.

from django.db import migrations, models
from django.utils import timezone


def forwards_fill_interval_schedule(apps, schema_editor):
    AISchedule = apps.get_model('Assistant', 'AISchedule')
    for s in AISchedule.objects.all():
        freq = getattr(s, 'frequency', None) or 'daily'
        if freq == 'hourly':
            ih, im = 1, 0
        elif freq == 'weekly':
            ih, im = 24 * 7, 0
        elif freq == 'monthly':
            ih, im = 24 * 30, 0
        else:
            ih, im = 24, 0
        nr = getattr(s, 'next_run', None)
        s.first_run_at = nr if nr else timezone.now()
        s.interval_hours = ih
        s.interval_minutes = im
        s.completed_schedule_runs = 0
        s.save(
            update_fields=[
                'first_run_at',
                'interval_hours',
                'interval_minutes',
                'completed_schedule_runs',
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ('Assistant', '0022_remove_aischedule_text_model_image_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='aischedule',
            name='first_run_at',
            field=models.DateTimeField(
                help_text='От этой точки отсчитываются повторы: следующие запуски через заданный интервал.',
                null=True,
                verbose_name='Первый запуск (дата и время)',
            ),
        ),
        migrations.AddField(
            model_name='aischedule',
            name='interval_hours',
            field=models.PositiveIntegerField(default=24, help_text='Например 24 и 0 минут — один запуск раз в сутки от счёта первого запуска.', verbose_name='Интервал — часы'),
        ),
        migrations.AddField(
            model_name='aischedule',
            name='interval_minutes',
            field=models.PositiveIntegerField(default=0, help_text='Дополнительно к часам (0–59). Минимум 1 минута суммарно с часами.', verbose_name='Интервал — минуты'),
        ),
        migrations.AddField(
            model_name='aischedule',
            name='max_schedule_runs',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Пусто = без ограничения. После достижения лимита расписание выключается.',
                null=True,
                verbose_name='Макс. число запусков',
            ),
        ),
        migrations.AddField(
            model_name='aischedule',
            name='completed_schedule_runs',
            field=models.PositiveIntegerField(default=0, help_text='Счётчик завершённых запусков (пачек генерации), увеличивается после каждого успешного цикла.', verbose_name='Выполнено запусков'),
        ),
        migrations.RunPython(forwards_fill_interval_schedule, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='aischedule',
            name='first_run_at',
            field=models.DateTimeField(
                help_text='От этой точки отсчитываются повторы: следующие запуски через заданный интервал.',
                verbose_name='Первый запуск (дата и время)',
            ),
        ),
        migrations.RemoveField(model_name='aischedule', name='cron_expression'),
        migrations.RemoveField(model_name='aischedule', name='frequency'),
        migrations.RemoveField(model_name='aischedule', name='start_time'),
    ]
