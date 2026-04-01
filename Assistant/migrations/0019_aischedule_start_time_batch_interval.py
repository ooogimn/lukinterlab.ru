# Generated manually for AISchedule start_time / batch_interval

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Assistant', '0018_add_subscription_token_limits'),
    ]

    operations = [
        migrations.AddField(
            model_name='aischedule',
            name='start_time',
            field=models.TimeField(
                default=datetime.time(9, 0),
                help_text='Для пресетов (кроме «Произвольное»): час и минута срабатывания CRON',
                verbose_name='Время старта',
            ),
        ),
        migrations.AddField(
            model_name='aischedule',
            name='batch_interval',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Интервал в минутах между статьями в одной пачке (0 — без паузы; используется в генераторе при articles_per_run > 1)',
                verbose_name='Интервал между статьями в пачке',
            ),
        ),
    ]
