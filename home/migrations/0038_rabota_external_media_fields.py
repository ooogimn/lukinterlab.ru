from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0037_rabota_preview_video"),
    ]

    operations = [
        migrations.AddField(
            model_name="rabota",
            name="preview_image_url",
            field=models.URLField(
                blank=True,
                help_text="Прямая ссылка на изображение (jpg/png/webp/gif).",
                max_length=500,
                verbose_name="Ссылка на внешнее изображение",
            ),
        ),
        migrations.AddField(
            model_name="rabota",
            name="preview_video_url",
            field=models.URLField(
                blank=True,
                help_text="YouTube / Rutube / VK Video. Имеет высший приоритет показа.",
                max_length=500,
                verbose_name="Ссылка на внешнее видео",
            ),
        ),
        migrations.AddField(
            model_name="rabotamedia",
            name="external_type",
            field=models.CharField(
                blank=True,
                choices=[("image", "Изображение"), ("video", "Видео")],
                max_length=10,
                verbose_name="Тип внешнего медиа",
            ),
        ),
        migrations.AddField(
            model_name="rabotamedia",
            name="external_url",
            field=models.URLField(
                blank=True,
                help_text="YouTube / Rutube / VK Video или прямая ссылка на изображение.",
                max_length=500,
                verbose_name="Внешняя ссылка на медиа",
            ),
        ),
        migrations.AlterField(
            model_name="rabotamedia",
            name="file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="rabota_media/",
                verbose_name="Файл (Изображение или Видео)",
            ),
        ),
    ]
