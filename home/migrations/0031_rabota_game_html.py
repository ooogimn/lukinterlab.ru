from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0030_cartitem_price_value_extraservice_price_value_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rabota',
            name='game_html',
            field=models.TextField(
                blank=True,
                help_text='Вставьте HTML-код (например, мини-игры), который откроется в модальном окне в секции портфолио.',
                verbose_name='HTML-код приложения/игры',
            ),
        ),
    ]
