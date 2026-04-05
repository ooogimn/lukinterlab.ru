# Generated manually for identity_auth

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LinkedSocialAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('vkid', 'VK ID'), ('yandex', 'Яндекс'), ('google', 'Google'), ('max', 'MAX')], db_index=True, max_length=16, verbose_name='Провайдер')),
                ('provider_user_id', models.CharField(db_index=True, max_length=191, verbose_name='ID у провайдера')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Привязано')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='linked_social_accounts', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Привязанный вход',
                'verbose_name_plural': 'Привязки входа',
            },
        ),
        migrations.AddConstraint(
            model_name='linkedsocialaccount',
            constraint=models.UniqueConstraint(fields=('provider', 'provider_user_id'), name='identity_auth_provider_uid_unique'),
        ),
    ]
