# Модели для пайплайна статей фиксированы в коде (GigaChat / GigaChat-Pro).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Assistant', '0021_remove_aischedule_use_image_generation'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='aischedule',
            name='text_model',
        ),
        migrations.RemoveField(
            model_name='aischedule',
            name='image_model',
        ),
    ]
