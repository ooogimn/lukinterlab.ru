# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0025_sitecustomerauthsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitecustomerauthsettings',
            name='yandex_oauth_button_icon',
            field=models.ImageField(
                blank=True,
                help_text='Пусто — встроенная иконка из static/img/oauth/yandex.svg',
                null=True,
                upload_to='oauth_buttons/',
                verbose_name='Иконка кнопки «Яндекс» (PNG/SVG)',
            ),
        ),
        migrations.AddField(
            model_name='sitecustomerauthsettings',
            name='google_oauth_button_icon',
            field=models.ImageField(
                blank=True,
                help_text='Пусто — встроенная иконка из static/img/oauth/google.svg',
                null=True,
                upload_to='oauth_buttons/',
                verbose_name='Иконка кнопки «Google»',
            ),
        ),
        migrations.AddField(
            model_name='sitecustomerauthsettings',
            name='max_oauth_button_icon',
            field=models.ImageField(
                blank=True,
                help_text='Пусто — встроенная иконка из static/img/oauth/max.svg',
                null=True,
                upload_to='oauth_buttons/',
                verbose_name='Иконка кнопки «MAX»',
            ),
        ),
    ]
