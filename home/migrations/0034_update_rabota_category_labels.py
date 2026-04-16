from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0033_order_prepayment_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rabota',
            name='category',
            field=models.CharField(
                choices=[
                    ('website', 'Сайт'),
                    ('bot', 'Бот'),
                    ('app', 'Приложение'),
                    ('shop', 'ИИследуем'),
                    ('other', 'ИИскуство'),
                ],
                default='website',
                max_length=20,
                verbose_name='Категория',
            ),
        ),
    ]
