from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Notebook", "0003_wikipage_content_richtext_and_wikiattachment_upload_to"),
    ]

    operations = [
        migrations.AddField(
            model_name="wikipage",
            name="avatar",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="wiki/notebook_avatars/",
                verbose_name="Аватар блокнота",
            ),
        ),
    ]
