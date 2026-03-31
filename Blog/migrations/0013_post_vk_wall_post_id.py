from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Blog', '0012_post_published_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='vk_wall_post_id',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Из ответа wall.post (для прямой ссылки на пост в сообществе).',
                null=True,
                verbose_name='ID поста на стене VK',
            ),
        ),
    ]
