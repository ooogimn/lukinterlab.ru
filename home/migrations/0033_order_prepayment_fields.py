from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0032_rabota_tariff_fields_and_portfolio_cart_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='final_payment_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Сумма финальной оплаты'),
        ),
        migrations.AddField(
            model_name='order',
            name='prepayment_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Сумма предоплаты'),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='prepayment_percent',
            field=models.PositiveSmallIntegerField(default=50, verbose_name='Процент предоплаты'),
        ),
    ]
