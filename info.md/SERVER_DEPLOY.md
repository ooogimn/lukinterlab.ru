# 📤 Развертывание на сервере - Краткая инструкция

## 🔄 Что заменить на сервере

### Обязательные файлы:

1. ✅ `Assistant/article_generator.py` - валидация объема текста, проверка дубликатов
2. ✅ `Assistant/news_parser.py` - retry механизм, кэширование, статистика (**ИСПРАВЛЕНА ОШИБКА**)
3. ✅ `Assistant/search_engines_submitter.py` - логи
4. ✅ `Blog/views.py` - обновление статистики категорий
5. ✅ `requirements.txt` - зависимости (feedparser, beautifulsoup4, lxml)

### Миграции:

- `Blog/migrations/0009_post_faq_data_post_news_source_url_and_more.py`
- `Assistant/migrations/0012_prompttemplate_faq_prompt_newssource_categorystats.py`

## 🚀 Как запустить на сервере

### Вариант 1: Через Git (рекомендуется)

```bash
# 1. Подключитесь к серверу
ssh user@your-server.com

# 2. Перейдите в директорию проекта
cd /path/to/your/project

# 3. Активируйте виртуальное окружение
source .venv/bin/activate

# 4. Получите обновления
git pull origin main

# 5. Установите зависимости
pip install -r requirements.txt

# 6. Примените миграции
python manage.py migrate

# 7. Запустите воркер Django-Q
python manage.py qcluster
```

### Вариант 2: Через FTP/SFTP (если нет Git)

1. **Загрузите файлы на сервер** через FileZilla или другой FTP-клиент:
   - `Assistant/article_generator.py`
   - `Assistant/news_parser.py`
   - `Assistant/search_engines_submitter.py`
   - `Blog/views.py`
   - `requirements.txt`
   - Папка `Blog/migrations/`
   - Папка `Assistant/migrations/`

2. **Подключитесь к серверу по SSH:**
   ```bash
   ssh user@your-server.com
   cd /path/to/your/project
   source .venv/bin/activate
   ```

3. **Установите зависимости:**
   ```bash
   pip install feedparser beautifulsoup4 lxml
   ```

4. **Примените миграции:**
   ```bash
   python manage.py migrate
   ```

5. **Запустите воркер:**
   ```bash
   python manage.py qcluster
   ```

### Вариант 3: Через systemd (для production)

1. **Создайте файл сервиса:**
   ```bash
   sudo nano /etc/systemd/system/django-q-worker.service
   ```

2. **Вставьте содержимое:**
   ```ini
   [Unit]
   Description=Django-Q Cluster Worker для автопостинга
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/path/to/your/project
   Environment="PATH=/path/to/your/project/.venv/bin"
   ExecStart=/path/to/your/project/.venv/bin/python /path/to/your/project/manage.py qcluster
   Restart=always
   RestartSec=10
   StandardOutput=append:/path/to/your/project/logs/qcluster.log
   StandardError=append:/path/to/your/project/logs/qcluster_error.log

   [Install]
   WantedBy=multi-user.target
   ```

3. **Замените `/path/to/your/project`** на реальный путь к проекту

4. **Запустите сервис:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable django-q-worker
   sudo systemctl start django-q-worker
   sudo systemctl status django-q-worker
   ```

5. **Проверьте логи:**
   ```bash
   sudo journalctl -u django-q-worker -f
   ```

## ✅ Проверка работы

### 1. Проверьте, что воркер запущен:

```bash
ps aux | grep qcluster
```

### 2. Проверьте расписания:

```bash
python manage.py shell -c "
from django_q.models import Schedule
print(f'Расписаний Django-Q: {Schedule.objects.count()}')
for s in Schedule.objects.filter(name__startswith='ai_autoposting'):
    print(f'  - {s.name}: {s.cron}')
"
```

### 3. Проверьте админ-панель:

1. Откройте админ-панель Django
2. **Django Q → Schedules** - должно быть 10 расписаний
3. **Assistant → Расписания генерации** - должно быть активное расписание
4. **Assistant → Источники новостей** - проверьте источники
5. **Blog → Статьи** - будут появляться новые статьи

### 4. Проверьте логи:

```bash
tail -f logs/django.log
# или
tail -f logs/qcluster.log
```

## 🐛 Решение проблем

### Проблема: Воркер не запускается

```bash
# Проверьте ошибки
python manage.py qcluster

# Проверьте, что все зависимости установлены
pip list | grep -E "feedparser|beautifulsoup4|lxml|django-q"

# Проверьте настройки
python manage.py check
```

### Проблема: Ошибка "IndentationError"

✅ **Уже исправлено!** Если видите ошибку отступов в `news_parser.py`, убедитесь, что файл обновлен (исправлена строка 257).

### Проблема: Статьи не генерируются

1. Проверьте настройки GigaChat: **Assistant → Настройки ассистента**
2. Проверьте активные категории: `Blog → Категории` (должны быть активные категории)
3. Проверьте шаблон промпта: **Assistant → Шаблоны промптов** (должен быть активный)
4. Проверьте логи: `logs/django.log`

### Проблема: Ошибки миграций

```bash
# Откатите и примените заново
python manage.py migrate Assistant 0011
python manage.py migrate Blog 0008
python manage.py migrate
```

## 📊 Мониторинг

### Просмотр логов в реальном времени:

```bash
tail -f logs/django.log
tail -f logs/qcluster.log
```

### Проверка статуса через админ-панель:

- **Django Q → OQ (Orchestration Queue)** - выполнение задач
- **Django Q → Failed Tasks** - ошибки
- **Assistant → Сгенерированные статьи** - история генерации

## 🎯 Быстрая команда для запуска

Если все уже настроено, просто запустите:

```bash
cd /path/to/your/project
source .venv/bin/activate
python manage.py qcluster
```

Или через systemd:

```bash
sudo systemctl start django-q-worker
sudo systemctl status django-q-worker
```

## 📝 Важные замечания

1. **Воркер должен работать постоянно** - это фоновый процесс для автопостинга
2. **Используйте systemd или supervisor** для production - чтобы воркер перезапускался автоматически
3. **Проверьте настройки кэша** - для работы кэширования парсинга нужен настроенный кэш (Redis или Memcached)
4. **Проверьте права доступа** - файлы должны быть доступны пользователю, который запускает воркер

## ✅ Готово!

После выполнения всех шагов система автопостинга будет:
- ✅ Генерировать статьи с 8:00 до 11:00 каждый день
- ✅ По 1 статье каждые 20 минут (10 статей в день)
- ✅ Ротация категорий с приоритетом популярных
- ✅ Валидация объема текста (800-1300 слов)
- ✅ Проверка дубликатов
- ✅ Кэширование и retry механизм

Удачи! 🚀
