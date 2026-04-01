# Инструкция по деплою LukInterLab на сервер Jino

## Подготовка к деплою

### 1. Локальная подготовка

1. **Создайте секретный ключ Django:**
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

2. **Соберите статические файлы:**
   ```bash
   python manage.py collectstatic --noinput
   ```

3. **Создайте миграции:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Создайте суперпользователя:**
   ```bash
   python manage.py createsuperuser
   ```

### 2. Подготовка файлов для загрузки

Создайте архив со следующими файлами и папками:
- `ALUKINTERLAB/` (папка с настройками)
- `home/` (приложение)
- `Blog/` (приложение)
- `Users/` (приложение)
- `templates/` (шаблоны)
- `static/` (статические файлы)
- `media/` (медиа файлы)
- `requirements.txt`
- `ALUKINTERLAB/wsgi_prod.py`
- `passenger_wsgi.py`
- `manage.py`
- `db.sqlite3` (если есть данные)

## Деплой на сервер Jino

### 1. Подключение к серверу

1. Подключитесь к серверу Jino через SSH
2. Перейдите в папку с вашим доменом: `cd /var/www/lukinterlab.ru/`

### 2. Загрузка файлов

1. Загрузите архив с файлами на сервер
2. Распакуйте архив в папку домена
3. Установите права доступа:
   ```bash
   chmod -R 755 /var/www/lukinterlab.ru/
   chown -R www-data:www-data /var/www/lukinterlab.ru/
   ```

### 3. Настройка Python окружения

1. Создайте виртуальное окружение:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

### 4. Настройка переменных окружения

1. Создайте файл `.env` в корне проекта:
   ```bash
   nano .env
   ```

2. Добавьте переменные окружения:
   ```env
   SECRET_KEY=ваш-секретный-ключ
   DEBUG=False
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=ваш-email@gmail.com
   EMAIL_HOST_PASSWORD=ваш-пароль-приложения
   TELEGRAM_BOT_TOKEN=ваш-токен-бота
   TELEGRAM_CHANNEL_ID=ваш-id-канала
   ```

### 5. Настройка базы данных

1. Примените миграции:
   ```bash
   python manage.py migrate
   ```

2. Создайте суперпользователя:
   ```bash
   python manage.py createsuperuser
   ```

### 6. Сборка статических файлов

```bash
python manage.py collectstatic --noinput
```

### 7. Настройка веб-сервера

#### Для Apache (mod_wsgi):

1. Создайте файл конфигурации:
   ```bash
   nano /etc/apache2/sites-available/lukinterlab.ru.conf
   ```

2. Добавьте конфигурацию:
   ```apache
   <VirtualHost *:80>
       ServerName lukinterlab.ru
       ServerAlias www.lukinterlab.ru
       
       DocumentRoot /var/www/lukinterlab.ru
       
       Alias /static/ /var/www/lukinterlab.ru/staticfiles/
       Alias /media/ /var/www/lukinterlab.ru/media/
       
       <Directory /var/www/lukinterlab.ru/staticfiles>
           Require all granted
       </Directory>
       
       <Directory /var/www/lukinterlab.ru/media>
           Require all granted
       </Directory>
       
       WSGIDaemonProcess lukinterlab python-path=/var/www/lukinterlab.ru:/var/www/lukinterlab.ru/venv/lib/python3.8/site-packages
       WSGIProcessGroup lukinterlab
       WSGIScriptAlias / /var/www/lukinterlab.ru/ALUKINTERLAB/wsgi_prod.py
       
       <Directory /var/www/lukinterlab.ru/ALUKINTERLAB>
           <Files wsgi_prod.py>
               Require all granted
           </Files>
       </Directory>
       
       ErrorLog ${APACHE_LOG_DIR}/lukinterlab_error.log
       CustomLog ${APACHE_LOG_DIR}/lukinterlab_access.log combined
   </VirtualHost>
   ```

3. Активируйте сайт:
   ```bash
   a2ensite lukinterlab.ru.conf
   systemctl reload apache2
   ```

#### Для Nginx + Gunicorn:

1. Установите Gunicorn:
   ```bash
   pip install gunicorn
   ```

2. Создайте файл конфигурации Nginx:
   ```nginx
   server {
       listen 80;
       server_name lukinterlab.ru www.lukinterlab.ru;
       
       root /var/www/lukinterlab.ru;
       
       location /static/ {
           alias /var/www/lukinterlab.ru/staticfiles/;
           expires 30d;
           add_header Cache-Control "public, immutable";
       }
       
       location /media/ {
           alias /var/www/lukinterlab.ru/media/;
           expires 30d;
           add_header Cache-Control "public, immutable";
       }
       
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. Запустите Gunicorn:
   ```bash
   gunicorn --bind 127.0.0.1:8000 ALUKINTERLAB.wsgi_prod:application
   ```

### 8. Настройка SSL (HTTPS)

1. Установите Certbot:
   ```bash
   apt install certbot python3-certbot-apache
   ```

2. Получите SSL сертификат:
   ```bash
   certbot --apache -d lukinterlab.ru -d www.lukinterlab.ru
   ```

### 9. Настройка автоматического запуска

Создайте systemd сервис для автоматического запуска:

```bash
nano /etc/systemd/system/lukinterlab.service
```

```ini
[Unit]
Description=LukInterLab Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/lukinterlab.ru
Environment="PATH=/var/www/lukinterlab.ru/venv/bin"
ExecStart=/var/www/lukinterlab.ru/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 ALUKINTERLAB.wsgi_prod:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Активируйте сервис:
```bash
systemctl enable lukinterlab
systemctl start lukinterlab
```

## Проверка работы

1. Откройте сайт в браузере: https://lukinterlab.ru
2. Проверьте админ-панель: https://lukinterlab.ru/admin/
3. Проверьте логи на ошибки:
   ```bash
   tail -f /var/www/lukinterlab.ru/logs/django.log
   ```

## Обновление сайта

1. Загрузите новые файлы на сервер
2. Активируйте виртуальное окружение: `source venv/bin/activate`
3. Установите новые зависимости: `pip install -r requirements.txt`
4. Примените миграции: `python manage.py migrate`
5. Соберите статические файлы: `python manage.py collectstatic --noinput`
6. Перезапустите сервис: `systemctl restart lukinterlab`

## Резервное копирование

Создайте скрипт для автоматического резервного копирования:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/lukinterlab"

mkdir -p $BACKUP_DIR

# Резервная копия базы данных
cp /var/www/lukinterlab.ru/db.sqlite3 $BACKUP_DIR/db_$DATE.sqlite3

# Резервная копия медиа файлов
tar -czf $BACKUP_DIR/media_$DATE.tar.gz -C /var/www/lukinterlab.ru media/

# Удаление старых резервных копий (старше 30 дней)
find $BACKUP_DIR -name "*.sqlite3" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

Добавьте в crontab для ежедневного выполнения:
```bash
0 2 * * * /path/to/backup_script.sh
``` 