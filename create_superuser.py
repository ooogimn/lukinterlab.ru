import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ALUKINTERLAB.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.filter(username='admin_new').delete()
User.objects.create_superuser('admin_new', 'admin@example.com', 'AdminPass123')
print('Пользователь admin_new успешно создан с паролем AdminPass123')
