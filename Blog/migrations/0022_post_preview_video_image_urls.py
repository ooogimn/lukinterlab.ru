# Generated manually for preview URL fields (Blog Post).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Blog', '0021_post_trigram_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='preview_video_url',
            field=models.URLField(
                max_length=500,
                blank=True,
                null=True,
                verbose_name='Ссылка на внешнее видео (превью)',
                help_text='YouTube, Rutube, VK Video. Высший приоритет в ленте и на странице статьи.',
            ),
        ),
        migrations.AddField(
            model_name='post',
            name='preview_image_url',
            field=models.URLField(
                max_length=500,
                blank=True,
                null=True,
                verbose_name='Ссылка на внешнее изображение (превью)',
                help_text='Прямая ссылка на JPG/PNG/WebP/GIF.',
            ),
        ),
    ]
