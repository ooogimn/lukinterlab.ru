# help_text для news_search_suffix приведён к актуальной формулировке (дашборд вместо NEWS_* в .env)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Assistant', '0025_news_search_settings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prompttemplate',
            name='news_search_suffix',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Добавляется к категории и ключевым словам при поиске новостей '
                    '(например: «события сегодня», «обзор»). Оставьте пустым — только глобальные настройки в дашборде «Поиск новостей».'
                ),
                max_length=300,
                verbose_name='Уточнение поиска новостей',
            ),
        ),
    ]
