# Generated manually for Customer.avatar + support tickets

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('home', '0027_remove_sitecustomerauthsettings_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='avatar',
            field=models.ImageField(
                blank=True,
                help_text='Отображается в шапке сайта и в кабинете (рекомендуем квадрат, до 2 МБ).',
                null=True,
                upload_to='customer_avatars/',
                verbose_name='Аватар',
            ),
        ),
        migrations.CreateModel(
            name='CustomerSupportThread',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=200, verbose_name='Тема')),
                (
                    'status',
                    models.CharField(
                        choices=[('open', 'Открыт'), ('answered', 'Есть ответ'), ('closed', 'Закрыт')],
                        db_index=True,
                        default='open',
                        max_length=16,
                        verbose_name='Статус',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='support_threads',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Клиент',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Обращение в поддержку',
                'verbose_name_plural': 'Обращения в поддержку',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='CustomerSupportMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_staff', models.BooleanField(default=False, verbose_name='Сообщение поддержки')),
                ('body', models.TextField(max_length=8000, verbose_name='Текст')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата')),
                (
                    'author',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Автор',
                    ),
                ),
                (
                    'thread',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='messages',
                        to='home.customersupportthread',
                        verbose_name='Обращение',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Сообщение поддержки',
                'verbose_name_plural': 'Сообщения поддержки',
                'ordering': ['created_at'],
            },
        ),
    ]
