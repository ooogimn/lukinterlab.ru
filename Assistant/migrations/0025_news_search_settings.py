# Singleton-настройки поиска новостей (дашборд)

from django.db import migrations, models


def create_singleton(apps, schema_editor):
    NewsSearchSettings = apps.get_model('Assistant', 'NewsSearchSettings')
    NewsSearchSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):

    dependencies = [
        ('Assistant', '0024_news_search_and_prompt_suffix'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsSearchSettings',
            fields=[
                (
                    'id',
                    models.PositiveSmallIntegerField(
                        default=1,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'ddg_query_suffix',
                    models.CharField(
                        blank=True,
                        default='новости',
                        help_text='Добавляется к фразе поиска. Пусто — не добавлять.',
                        max_length=200,
                        verbose_name='Суффикс запроса (DuckDuckGo)',
                    ),
                ),
                (
                    'ddg_search_url_template',
                    models.CharField(
                        default='https://html.duckduckgo.com/html/?q={query}',
                        help_text='Обязательно включите плейсхолдер {query}',
                        max_length=600,
                        verbose_name='Шаблон URL DuckDuckGo',
                    ),
                ),
                (
                    'search_per_source_limit',
                    models.PositiveIntegerField(default=18, verbose_name='Ссылок с одного источника (макс.)'),
                ),
                (
                    'search_max_collect',
                    models.PositiveIntegerField(default=48, verbose_name='Размер пула после ранжирования'),
                ),
                (
                    'search_pool_timeout',
                    models.PositiveIntegerField(default=35, verbose_name='Таймаут ожидания источников (сек)'),
                ),
                (
                    'search_parallel_max',
                    models.PositiveIntegerField(default=6, verbose_name='Параллельных потоков поиска'),
                ),
                (
                    'freshness_hours',
                    models.PositiveIntegerField(
                        default=72,
                        help_text='Отсев по дате, если она надёжно известна (RSS и т.д.)',
                        verbose_name='Свежесть (часы), 0 = выкл.',
                    ),
                ),
                (
                    'penalize_unknown_published',
                    models.BooleanField(
                        default=True,
                        verbose_name='Штрафовать неизвестную дату в ранжировании',
                    ),
                ),
                (
                    'rank_random_jitter',
                    models.BooleanField(default=True, verbose_name='Случайный джиттер в ранжировании'),
                ),
                (
                    'query_variant_suffixes',
                    models.TextField(
                        blank=True,
                        help_text='Например: последние новости|сегодня|обзор — один вариант выбирается случайно.',
                        verbose_name='Варианты уточнения через |',
                    ),
                ),
                (
                    'force_fresh_news_on_content_retry',
                    models.BooleanField(
                        default=True,
                        verbose_name='При коротком тексте — новый поиск новостей',
                    ),
                ),
                (
                    'top_list_random_offset_max',
                    models.PositiveIntegerField(
                        default=4,
                        verbose_name='Случайный сдвиг в топе кандидатов (0 = нет)',
                    ),
                ),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Настройки поиска новостей',
                'verbose_name_plural': 'Настройки поиска новостей',
            },
        ),
        migrations.RunPython(create_singleton, migrations.RunPython.noop),
    ]
