# Generated manually for Post.max_posted_at (MAX messenger autopost)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Blog', '0014_remove_category_blog_category_tree_id_lft_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='max_posted_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Ставится при успешной отправке анонса в чат/канал MAX (django-q).',
                null=True,
                verbose_name='Время публикации в MAX',
            ),
        ),
    ]
