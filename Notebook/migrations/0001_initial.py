import Notebook.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WikiPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("path", models.CharField(max_length=255, unique=True)),
                ("depth", models.PositiveIntegerField()),
                ("numchild", models.PositiveIntegerField(default=0)),
                ("title", models.CharField(max_length=255, verbose_name="Заголовок")),
                ("slug", models.SlugField(max_length=255, verbose_name="Slug")),
                ("content", models.TextField(blank=True, verbose_name="Содержимое")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={
                "verbose_name": "Wiki страница",
                "verbose_name_plural": "Wiki страницы",
            },
        ),
        migrations.CreateModel(
            name="WikiAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "file",
                    models.FileField(upload_to=Notebook.models.wiki_attachment_upload_to, verbose_name="Файл"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Загружено")),
                (
                    "page",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="attachments",
                        to="Notebook.wikipage",
                        verbose_name="Страница",
                    ),
                ),
            ],
            options={
                "verbose_name": "Вложение Wiki",
                "verbose_name_plural": "Вложения Wiki",
            },
        ),
    ]
