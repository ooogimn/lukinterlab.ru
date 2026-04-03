# Generated manually for SiteMarketingSettings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0021_restore_mptt_tree_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteMarketingSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'yandex_rsya_html',
                    models.TextField(
                        blank=True,
                        help_text='Вставьте код рекламных блоков (например, из кабинета Яндекса). Выводится в зоне reclama (подключается на всех страницах с base.html).',
                        verbose_name='HTML блоков РСЯ / медийной рекламы',
                    ),
                ),
                (
                    'yandex_metrika_html',
                    models.TextField(
                        blank=True,
                        help_text='Если заполнено и включена подмена — выводится вместо встроенного счётчика в шаблоне.',
                        verbose_name='Яндекс.Метрика и счётчики (фрагмент для <head> или полный)',
                    ),
                ),
                (
                    'google_tag_head_html',
                    models.TextField(blank=True, verbose_name='Google Tag Manager / аналитика (часть для <head>)'),
                ),
                (
                    'google_tag_body_html',
                    models.TextField(blank=True, verbose_name='Google Tag Manager (noscript сразу после <body>)'),
                ),
                (
                    'head_extra_html',
                    models.TextField(
                        blank=True,
                        help_text='Проверка сайта, пиксели и т.п.',
                        verbose_name='Дополнительно в <head>',
                    ),
                ),
                (
                    'body_end_html',
                    models.TextField(
                        blank=True,
                        help_text='Доп. скрипты, вторичные пиксели.',
                        verbose_name='Перед закрытием </body>',
                    ),
                ),
                (
                    'custom_promo_banner_html',
                    models.TextField(
                        blank=True,
                        help_text='Произвольный блок: баннер, встроенное видео, текст. Рендерится |safe рядом с рекламной зоной.',
                        verbose_name='Свой промо-блок (HTML)',
                    ),
                ),
                (
                    'promo_image',
                    models.ImageField(blank=True, null=True, upload_to='marketing/', verbose_name='Промо-картинка (опционально)'),
                ),
                (
                    'promo_link',
                    models.URLField(blank=True, verbose_name='Ссылка с промо-картинки'),
                ),
                (
                    'replace_builtin_counters',
                    models.BooleanField(
                        default=False,
                        help_text='Если включено — блоки из полей выше подставляются вместо захардкоженных скриптов в base.html (заполните Metrika/GTM вручную).',
                        verbose_name='Заменить встроенные GTM и Метрику в шаблоне',
                    ),
                ),
                ('active', models.BooleanField(default=True, verbose_name='Включить вывод с БД')),
            ],
            options={
                'verbose_name': 'Реклама и метрики (сайт)',
                'verbose_name_plural': 'Реклама и метрики (сайт)',
            },
        ),
    ]
