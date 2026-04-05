# Перенос модели в приложение identity_auth; таблица home_sitecustomerauthsettings не удаляется.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0026_sitecustomerauthsettings_oauth_icons'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='SiteCustomerAuthSettings'),
            ],
            database_operations=[],
        ),
    ]
