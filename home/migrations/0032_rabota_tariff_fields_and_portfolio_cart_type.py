from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0031_rabota_game_html'),
    ]

    operations = [
        migrations.AddField(
            model_name='rabota',
            name='tariff_price_value',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Укажите стоимость в цифрах, например 150000.',
                max_digits=12,
                null=True,
                verbose_name='Тарифы и стоимость: цена (числом)',
            ),
        ),
        migrations.AddField(
            model_name='rabota',
            name='tariff_short_description',
            field=models.TextField(
                blank=True,
                help_text='Краткое описание того, что входит в стоимость этого проекта.',
                verbose_name='Тарифы и стоимость: краткое описание',
            ),
        ),
        migrations.AlterField(
            model_name='cartitem',
            name='service_type',
            field=models.CharField(
                choices=[
                    ('service', 'Основная услуга'),
                    ('extra_service', 'Дополнительная услуга'),
                    ('portfolio', 'Проект из портфолио'),
                ],
                max_length=20,
                verbose_name='Тип услуги',
            ),
        ),
        migrations.AlterField(
            model_name='orderitem',
            name='service_type',
            field=models.CharField(
                choices=[
                    ('service', 'Основная услуга'),
                    ('extra_service', 'Дополнительная услуга'),
                    ('portfolio', 'Проект из портфолио'),
                ],
                max_length=20,
                verbose_name='Тип услуги',
            ),
        ),
    ]
