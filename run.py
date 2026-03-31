#!/usr/bin/env python
"""
Скрипт для запуска Django приложения на сервере
"""
import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Устанавливаем переменные окружения
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ALUKINTERLAB.settings_prod')

# Инициализируем Django
django.setup()

# Импортируем WSGI приложение
from ALUKINTERLAB.wsgi_prod import application

if __name__ == '__main__':
    # Для локального тестирования
    from wsgiref.simple_server import make_server
    
    httpd = make_server('', 8000, application)
    print("Сервер запущен на http://localhost:8000/")
    httpd.serve_forever() 