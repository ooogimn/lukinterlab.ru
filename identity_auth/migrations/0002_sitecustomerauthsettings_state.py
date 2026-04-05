# Таблица уже создана миграциями home; только состояние Django переносится в identity_auth.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('identity_auth', '0001_initial_linked_social'),
        ('home', '0027_remove_sitecustomerauthsettings_state'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='SiteCustomerAuthSettings',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('vkid_app_id', models.CharField(blank=True, help_text='Пусто = брать из VKID_APP_ID в .env', max_length=32, verbose_name='VK ID — ID приложения (app id)')),
                        ('vkid_redirect_url', models.URLField(blank=True, help_text='Полный URL со слэшем в конце, как в кабинете VK ID. Пусто = VKID_REDIRECT_URL из .env или авто с текущего хоста.', verbose_name='VK ID — доверенный redirect URL')),
                        ('vkid_protected_key', models.TextField(blank=True, help_text='Пусто в форме при сохранении = не менять. Пусто в БД = VKID_PROTECTED_KEY из .env.', verbose_name='VK ID — защищённый ключ')),
                        ('vkid_service_key', models.TextField(blank=True, help_text='Пусто при сохранении = не менять. Пусто в БД = VKID_SERVICE_KEY из .env.', verbose_name='VK ID — сервисный ключ')),
                        ('yandex_oauth_client_id', models.CharField(blank=True, help_text='Пусто = YANDEX_OAUTH_CLIENT_ID в .env', max_length=256, verbose_name='Яндекс OAuth — Client ID')),
                        ('yandex_oauth_client_secret', models.TextField(blank=True, help_text='Пусто при сохранении = не менять. Пусто в БД = .env', verbose_name='Яндекс OAuth — Client Secret')),
                        ('google_oauth_client_id', models.CharField(blank=True, help_text='Пусто = GOOGLE_OAUTH_CLIENT_ID в .env', max_length=512, verbose_name='Google OAuth — Client ID')),
                        ('google_oauth_client_secret', models.TextField(blank=True, help_text='Пусто при сохранении = не менять. Пусто в БД = .env', verbose_name='Google OAuth — Client Secret')),
                        ('max_oidc_issuer', models.URLField(blank=True, help_text='Без завершающего слэша или со слэшем — код нормализует. Пусто = MAX_OIDC_ISSUER в .env.', verbose_name='MAX OIDC — базовый URL (issuer)')),
                        ('max_oidc_client_id', models.CharField(blank=True, help_text='Пусто = MAX_OIDC_CLIENT_ID в .env', max_length=256, verbose_name='MAX OIDC — Client ID')),
                        ('max_oidc_client_secret', models.TextField(blank=True, help_text='Пусто при сохранении = не менять. Пусто в БД = .env', verbose_name='MAX OIDC — Client Secret')),
                        ('yandex_oauth_button_icon', models.ImageField(blank=True, help_text='Пусто — встроенная иконка из static приложения identity_auth', null=True, upload_to='oauth_buttons/', verbose_name='Иконка кнопки «Яндекс» (PNG/SVG)')),
                        ('google_oauth_button_icon', models.ImageField(blank=True, help_text='Пусто — встроенная иконка из static приложения identity_auth', null=True, upload_to='oauth_buttons/', verbose_name='Иконка кнопки «Google»')),
                        ('max_oauth_button_icon', models.ImageField(blank=True, help_text='Пусто — встроенная иконка из static приложения identity_auth', null=True, upload_to='oauth_buttons/', verbose_name='Иконка кнопки «MAX»')),
                    ],
                    options={
                        'db_table': 'home_sitecustomerauthsettings',
                        'verbose_name': 'Параметры входа пользователей (OAuth, VK ID)',
                        'verbose_name_plural': 'Параметры входа пользователей (OAuth, VK ID)',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
