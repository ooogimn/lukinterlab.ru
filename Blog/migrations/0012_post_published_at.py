# Generated manually for Post.published_at

from django.db import migrations, models
from django.db.models import F


def backfill_published_at(apps, schema_editor):
    Post = apps.get_model('Blog', 'Post')
    Post.objects.filter(status='published', published_at__isnull=True).update(published_at=F('created'))


class Migration(migrations.Migration):

    dependencies = [
        ('Blog', '0011_alter_post_meta_description_alter_post_meta_keywords'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='published_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Заполняется при каждом переходе из черновика в «Опубликовано» (последний выход на сайт). Не путать с датой создания черновика и датой решения модератора.',
                null=True,
                verbose_name='Дата публикации',
            ),
        ),
        migrations.RunPython(backfill_published_at, migrations.RunPython.noop),
    ]
