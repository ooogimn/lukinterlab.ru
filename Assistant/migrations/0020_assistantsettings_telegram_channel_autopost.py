# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Assistant', '0019_aischedule_start_time_batch_interval'),
    ]

    operations = [
        migrations.AddField(
            model_name='assistantsettings',
            name='telegram_channel_autopost_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Анонсы опубликованных статей в Telegram-канал. Выключите при блокировках или сбоях API; VK не затрагивается.',
                verbose_name='Автопост статей в Telegram-канал',
            ),
        ),
    ]
