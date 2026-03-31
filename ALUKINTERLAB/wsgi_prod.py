"""
WSGI config for LukInterLab project for production.
"""

import os
import sys

# Добавляем путь к проекту в sys.path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

# Устанавливаем переменную окружения для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ALUKINTERLAB.settings_prod')

# Импортируем приложение Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application() 