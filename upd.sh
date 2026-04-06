#!/bin/bash
# === LUKINTERLAB AUTODEPLOY SCRIPT ===
# Этот скрипт автоматизирует обновление сайта на сервере.

set -e

echo "--------------------------------------------------"
echo "🚀 [1/3] Забираем свежий код из GitHub..."
git pull origin main

echo "--------------------------------------------------"
echo "🐳 [2/3] Пересборка Docker (только если были изменения)..."
# Мы убрали профили, поэтому теперь взлетает всё сразу
docker compose up -d --build

echo "--------------------------------------------------"
echo "🛠️ [3/3] Выполняем миграции и сборку статики..."
# Хотя эти команды есть в Dockerfile, запуск здесь гарантирует успех
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py collectstatic --noinput

echo "--------------------------------------------------"
echo "✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО!"
echo "Статус контейнеров:"
docker compose ps
