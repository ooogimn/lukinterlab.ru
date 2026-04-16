from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0036_alter_sitemarketingsettings_google_tag_head_html_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rabota',
            name='preview_video',
            field=models.FileField(
                blank=True,
                help_text='Опционально: MP4/WebM видео для карточки портфолио (автовоспроизведение, зацикливание).',
                null=True,
                upload_to='rabotas/videos/',
                verbose_name='Главное видео проекта',
            ),
        ),
    ]
