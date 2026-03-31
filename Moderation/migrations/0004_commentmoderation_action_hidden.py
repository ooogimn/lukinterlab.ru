# Generated manually for new CommentModeration.action choice "hidden"

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Moderation', '0003_add_generic_foreign_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commentmoderation',
            name='action',
            field=models.CharField(
                blank=True,
                choices=[
                    ('approved', 'Одобрено'),
                    ('hidden', 'Скрыто (ожидает ручной проверки)'),
                    ('deleted', 'Удалено'),
                    ('corrected', 'Исправлено'),
                    ('replied', 'Ответ добавлен'),
                ],
                max_length=20,
                null=True,
                verbose_name='Действие',
            ),
        ),
    ]
