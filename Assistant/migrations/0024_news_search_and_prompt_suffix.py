# NewsSearchEndpoint, PromptTemplate.news_search_suffix

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Blog', '0018_alter_post_title_and_seo_field_lengths'),
        ('Assistant', '0023_aischedule_interval_first_run'),
    ]

    operations = [
        migrations.AddField(
            model_name='prompttemplate',
            name='news_search_suffix',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Добавляется к категории и ключевым словам при поиске новостей '
                    '(например: «события сегодня», «обзор»). Оставьте пустым — только глобальные суффиксы из NEWS_* в .env.'
                ),
                max_length=300,
                verbose_name='Уточнение поиска новостей',
            ),
        ),
        migrations.CreateModel(
            name='NewsSearchEndpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                (
                    'kind',
                    models.CharField(
                        choices=[('html', 'HTML (скрапинг списка статей)'), ('rss', 'RSS / Atom')],
                        default='html',
                        max_length=10,
                        verbose_name='Тип',
                    ),
                ),
                ('sort_order', models.IntegerField(default=0, verbose_name='Порядок')),
                ('base_url', models.URLField(blank=True, max_length=500, verbose_name='Базовый URL')),
                (
                    'search_url',
                    models.CharField(
                        blank=True,
                        help_text='Для HTML: можно использовать плейсхолдеры {query} и {category}. Для RSS с динамикой — {query} в URL ленты.',
                        max_length=1000,
                        verbose_name='URL поиска / ленты',
                    ),
                ),
                (
                    'article_selector',
                    models.CharField(blank=True, max_length=500, verbose_name='CSS селектор ссылок на статьи'),
                ),
                (
                    'title_selector',
                    models.CharField(blank=True, max_length=500, verbose_name='CSS селектор заголовка (опционально)'),
                ),
                ('rss_feed_url', models.URLField(blank=True, max_length=1000, verbose_name='URL RSS (если kind=rss)')),
                ('notes', models.CharField(blank=True, max_length=500, verbose_name='Заметки')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                (
                    'category',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='news_search_endpoints',
                        to='Blog.category',
                        verbose_name='Категория блога',
                        help_text='Пусто — использовать для всех категорий',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Источник поиска новостей',
                'verbose_name_plural': 'Источники поиска новостей',
                'ordering': ['sort_order', 'name'],
            },
        ),
    ]
