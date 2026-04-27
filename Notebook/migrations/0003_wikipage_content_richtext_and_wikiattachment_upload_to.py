# Sync models with DB: content → RichTextUploadingField; file.upload_to as callable (was string in 0002).

import Notebook.models
import ckeditor_uploader.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Notebook", "0002_wikiattachment_external_url_and_optional_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="wikipage",
            name="content",
            field=ckeditor_uploader.fields.RichTextUploadingField(
                blank=True, verbose_name="Содержимое"
            ),
        ),
        migrations.AlterField(
            model_name="wikiattachment",
            name="file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=Notebook.models.wiki_attachment_upload_to,
                verbose_name="Файл",
            ),
        ),
    ]
