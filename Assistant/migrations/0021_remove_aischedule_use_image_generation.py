# Generated manually — поле не использовалось в коде генерации

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Assistant', '0020_assistantsettings_telegram_channel_autopost'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='aischedule',
            name='use_image_generation',
        ),
    ]
