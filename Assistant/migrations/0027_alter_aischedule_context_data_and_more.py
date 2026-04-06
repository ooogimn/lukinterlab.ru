# Синхронизация help_text tags / keywords / context_data с models.AISchedule (после правок дашборда)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Assistant', '0026_alter_prompttemplate_news_search_suffix'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aischedule',
            name='tags',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Через запятую: теги, которые точно попадут в пост. '
                    'Если пусто — берутся из шаблона промпта (default_tags) или из ключа tags в JSON ниже. '
                    'Отдельно модель добавляет 3–4 тега по смыслу текста статьи.'
                ),
                max_length=500,
                verbose_name='Теги',
            ),
        ),
        migrations.AlterField(
            model_name='aischedule',
            name='keywords',
            field=models.TextField(
                blank=True,
                help_text=(
                    'Через запятую: тема запроса при поиске новостей/источников и контекст промпта. '
                    'Если пусто, для поиска может использоваться название категории. '
                    'Для шаблонов без шага поиска влияние обычно слабее.'
                ),
                verbose_name='Ключевые слова',
            ),
        ),
        migrations.AlterField(
            model_name='aischedule',
            name='context_data',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    'JSON с дополнительными переменными для промптов (например topic, tone). '
                    'Сливается с контекстом генерации: ключи из этого поля дополняют шаблон; '
                    'необязательно, если всё задано в шаблоне.'
                ),
                verbose_name='Дополнительные данные',
            ),
        ),
    ]
