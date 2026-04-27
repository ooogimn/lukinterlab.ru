from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Notebook", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="wikiattachment",
            name="external_url",
            field=models.URLField(
                blank=True,
                help_text="YouTube / Rutube / VK Video или прямая ссылка на изображение.",
                max_length=500,
                verbose_name="Внешняя ссылка",
            ),
        ),
        migrations.AlterField(
            model_name="wikiattachment",
            name="file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="Notebook.models.wiki_attachment_upload_to",
                verbose_name="Файл",
            ),
        ),
    ]
