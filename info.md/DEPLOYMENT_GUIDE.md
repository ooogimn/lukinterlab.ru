# Руководство по развертыванию на сервере

## 📋 Что нужно заменить/обновить на сервере

### Измененные файлы (обязательно заменить):

1. ✅ **Assistant/article_generator.py** 
   - Валидация объема текста (800-1300 слов)
   - Проверка дубликатов статей
   - Замена эмодзи в логах
   - Методы: `_count_words()`, `_truncate_to_words()`

2. ✅ **Assistant/news_parser.py**
   - Retry механизм (3 попытки)
   - Кэширование парсинга (1 час)
   - Использование статистики источников в `get_best_source()`
   - Замена эмодзи в логах
   - ✅ **ИСПРАВЛЕНА ОШИБКА ОТСТУПОВ** (строка 257)

3. ✅ **Assistant/search_engines_submitter.py**
   - Замена эмодзи в логах

4. ✅ **Blog/views.py**
   - Обновление статистики категорий при просмотре статьи
   - Интеграция с `CategoryStats`

5. ✅ **Assistant/models.py**
   - Модели `NewsSource` и `CategoryStats` (уже в миграциях)
   - Метод `update_rating()` для источников

6. ✅ **requirements.txt**
   - Зависимости: `feedparser==6.0.11`, `beautifulsoup4==4.12.3`, `lxml==5.3.0`

### Новые файлы (опционально):

- `Assistant/IMPROVEMENTS_COMPLETED.md` - документация
- `DEPLOYMENT_GUIDE.md` - эта инструкция

### Миграции базы данных:

- `Blog/migrations/0009_post_faq_data_post_news_source_url_and_more.py`
- `Assistant/migrations/0012_prompttemplate_faq_prompt_newssource_categorystats.py`

## 🚀 Инструкция по развертыванию

### Шаг 1: Загрузка файлов на сервер

Загрузите обновленные файлы на сервер через FTP/SFTP или Git:

```bash
# Если используете Git
git pull origin main

# Или загрузите файлы вручную через FTP/SFTP
```

### Шаг 2: Активация виртуального окружения

```bash
cd /path/to/your/project
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows
```

### Шаг 3: Установка/обновление зависимостей

```bash
pip install feedparser beautifulsoup4 lxml
# Или обновите все зависимости
pip install -r requirements.txt
```

### Шаг 4: Применение миграций

```bash
python manage.py makemigrations Assistant Blog
python manage.py migrate
```

### Шаг 5: Создание шаблона промпта (если еще не создан)

```bash
python manage.py create_default_prompt_template
```

### Шаг 6: Настройка расписания (если еще не настроено)

```bash
python manage.py setup_autoposting_schedule
```

### Шаг 7: Запуск Django-Q воркера

#### Для разработки (в терминале):

```bash
python manage.py qcluster
```

#### Для production (через systemd):

Создайте файл `/etc/systemd/system/django-q-worker.service`:

```ini
[Unit]
Description=Django-Q Cluster Worker
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/your/project
Environment="PATH=/path/to/your/project/.venv/bin"
ExecStart=/path/to/your/project/.venv/bin/python /path/to/your/project/manage.py qcluster
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем запустите:

```bash
sudo systemctl daemon-reload
sudo systemctl enable django-q-worker
sudo systemctl start django-q-worker
sudo systemctl status django-q-worker
```

#### Для production (через supervisor):

Создайте файл `/etc/supervisor/conf.d/django-q-worker.conf`:

```ini
[program:django-q-worker]
command=/path/to/your/project/.venv/bin/python /path/to/your/project/manage.py qcluster
directory=/path/to/your/project
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/path/to/your/project/logs/qcluster.log
```

Затем:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start django-q-worker
```

#### Для production (через screen/tmux):

```bash
# Создайте сессию
screen -S django-q-worker
# или
tmux new -s django-q-worker

# Запустите воркер
cd /path/to/your/project
source .venv/bin/activate
python manage.py qcluster

# Отключитесь (Ctrl+A затем D для screen, Ctrl+B затем D для tmux)
```

### Шаг 8: Проверка работы

#### Проверьте расписания:

```bash
python manage.py shell -c "from django_q.models import Schedule; print(f'Расписаний: {Schedule.objects.count()}')"
```

#### Проверьте логи:

```bash
tail -f logs/django.log
# или
tail -f logs/qcluster.log
```

#### Проверьте админ-панель:

1. Откройте админ-панель Django
2. Перейдите в **Django Q → Schedules** - должно быть 10 расписаний
3. Перейдите в **Assistant → Расписания генерации** - должно быть активное расписание
4. Перейдите в **Assistant → Источники новостей** - проверьте источники
5. Перейдите в **Assistant → Статистика категорий** - проверьте статистику

## 🔍 Мониторинг и отладка

### Просмотр логов Django-Q:

```bash
# В админ-панели
Django Q → OQ (Orchestration Queue) → Failed Tasks

# Или в терминале
python manage.py shell -c "from django_q.models import Failure; print(Failure.objects.all().count())"
```

### Проверка расписаний:

```bash
python manage.py shell -c "
from django_q.models import Schedule
from Assistant.models import AISchedule
print(f'Django-Q расписаний: {Schedule.objects.count()}')
print(f'AISchedule расписаний: {AISchedule.objects.filter(is_active=True).count()}')
for s in Schedule.objects.all():
    print(f'  - {s.name}: {s.cron}')
"
```

### Ручной запуск генерации (для тестирования):

```bash
python manage.py shell
```

```python
from Assistant.models import AISchedule
from Assistant.article_generator import ArticleGeneratorService

# Получаем расписание
schedule = AISchedule.objects.filter(is_active=True).first()

# Создаем генератор
generator = ArticleGeneratorService(schedule)

# Генерируем одну статью
post = generator.generate_article()

if post:
    print(f"✅ Статья создана: {post.title}")
else:
    print("❌ Ошибка генерации")
```

## ⚠️ Важные замечания

### Для production сервера:

1. **Настройте правильные настройки Django-Q:**
   
   В `settings.py`:
   ```python
   Q_CLUSTER = {
       'name': 'DjangORM',
       'workers': 4,
       'timeout': 90,
       'retry': 120,
       'queue_limit': 50,
       'bulk': 10,
       'orm': 'default'
   }
   ```

2. **Настройте кэширование:**
   
   В `settings.py` (для кэширования парсинга):
   ```python
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.redis.RedisCache',
           'LOCATION': 'redis://127.0.0.1:6379/1',
       }
   }
   ```

3. **Проверьте настройки GigaChat:**
   
   В админ-панели: **Assistant → Настройки ассистента**
   - Убедитесь, что указаны правильные токены и ключи
   - Проверьте лимиты токенов

4. **Проверьте активные категории:**
   
   ```bash
   python manage.py shell -c "from Blog.models import Category; print(f'Активных категорий: {Category.objects.filter(activ=True).count()}')"
   ```

### Автоматический перезапуск воркера:

Если воркер упал, он должен автоматически перезапуститься (если настроен через systemd или supervisor).

Для ручного перезапуска:

```bash
# systemd
sudo systemctl restart django-q-worker

# supervisor
sudo supervisorctl restart django-q-worker

# screen/tmux
# Зайдите в сессию и перезапустите
screen -r django-q-worker
# или
tmux attach -t django-q-worker
```

## 📊 Проверка работы системы

### 1. Проверьте, что воркер запущен:

```bash
ps aux | grep qcluster
```

### 2. Проверьте расписания Django-Q:

В админ-панели: **Django Q → Schedules** - должно быть 10 расписаний для автопостинга

### 3. Проверьте сгенерированные статьи:

В админ-панели: **Blog → Статьи** - должны появляться новые статьи

### 4. Проверьте историю генерации:

В админ-панели: **Assistant → Сгенерированные статьи**

### 5. Проверьте статистику:

- **Assistant → Источники новостей** - рейтинг источников
- **Assistant → Статистика категорий** - приоритеты категорий

## 🐛 Устранение неполадок

### Проблема: Воркер не запускается

```bash
# Проверьте логи
tail -f logs/qcluster.log

# Проверьте права доступа
chmod +x manage.py

# Проверьте виртуальное окружение
which python
```

### Проблема: Статьи не генерируются

1. Проверьте, что расписание активно
2. Проверьте, что воркер запущен
3. Проверьте логи на ошибки
4. Проверьте настройки GigaChat в админ-панели

### Проблема: Ошибки парсинга новостей

1. Проверьте доступность источников новостей
2. Проверьте интернет-соединение на сервере
3. Проверьте логи для детальной информации

### Проблема: Ошибки миграций

```bash
# Если миграции не применяются
python manage.py migrate --fake-initial

# Если нужно откатить
python manage.py migrate Assistant 0011
python manage.py migrate Blog 0008
```

## ✅ Чеклист развертывания

- [ ] Загружены обновленные файлы
- [ ] Установлены зависимости (feedparser, beautifulsoup4, lxml)
- [ ] Применены миграции базы данных
- [ ] Создан шаблон промпта
- [ ] Настроено расписание автопостинга
- [ ] Запущен Django-Q воркер
- [ ] Проверены логи на наличие ошибок
- [ ] Проверена работа в админ-панели
- [ ] Протестирована генерация одной статьи вручную
- [ ] Настроен автоматический перезапуск воркера (systemd/supervisor)

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `logs/django.log` и `logs/qcluster.log`
2. Проверьте админ-панель: Django Q → Failed Tasks
3. Проверьте настройки: Assistant → Настройки ассистента
