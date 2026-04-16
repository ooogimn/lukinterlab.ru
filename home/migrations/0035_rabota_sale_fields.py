from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0034_update_rabota_category_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='rabota',
            name='is_for_sale',
            field=models.BooleanField(
                default=False,
                help_text='Отметьте, если проект доступен к продаже.',
                verbose_name='Продаётся',
            ),
        ),
        migrations.AddField(
            model_name='rabota',
            name='sale_description',
            field=models.TextField(
                blank=True,
                help_text='Опишите, что покупатель получает вместе с проектом.',
                verbose_name='Что входит в комплект продажи',
            ),
        ),
        migrations.AddField(
            model_name='rabota',
            name='sale_price_value',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Укажите стоимость продажи в цифрах, например 450000.',
                max_digits=12,
                null=True,
                verbose_name='Стоимость продажи (числом)',
            ),
        ),
    ]
