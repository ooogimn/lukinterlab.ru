from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0028_customer_avatar_customersupportthread_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rabota',
            name='is_visible',
            field=models.BooleanField(
                default=True,
                help_text='Снимите галку, чтобы скрыть проект с сайта',
                verbose_name='Отображать на сайте',
            ),
        ),
    ]
