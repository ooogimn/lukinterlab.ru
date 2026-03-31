# 🚀 Быстрое развертывание на сервере

## ✅ Что заменить на сервере

### Обязательные файлы (обновить):

1. **Assistant/article_generator.py** - валидация объема, дубликаты, логи
2. **Assistant/news_parser.py** - retry, кэширование, статистика, логи (**ИСПРАВЛЕНА ОШИБКА ОТСТУПОВ**)
3. **Assistant/search_engines_submitter.py** - логи
4. **Blog/views.py** - обновление статистики категорий
5. **requirements.txt** - зависимости (feedparser, beautifulsoup4, lxml)

### Миграции (применить):

- `Blog/migrations/0009_post_faq_data_post_news_source_url_and_more.py`
- `Assistant/migrations/0012_prompttemplate_faq_prompt_newssource_categorystats.py`

## 📝 Пошаговая инструкция

### 1. Загрузите файлы на сервер

```bash
# Через Git
git pull origin main

# Или через FTP/SFTP загрузите измененные файлы вручную
```

### 2. Войдите на сервер и активируйте окружение

```bash
cd /path/to/your/project
source .venv/bin/activate  # Linux/Mac
```

### 3. Установите зависимости

```bash
pip install feedparser beautifulsoup4 lxml
# или
pip install -r requirements.txt
```

### 4. Примените миграции

```bash
python manage.py makemigrations Assistant Blog
python manage.py migrate
```

### 5. Создайте шаблон промпта (если еще не создан)

```bash
python manage.py create_default_prompt_template
```

### 6. Настройте расписание (если еще не настроено)

```bash
python manage.py setup_autoposting_schedule
```

### 7. Запустите Django-Q воркер

#### Вариант A: Для тестирования (в терминале)

```bash
python manage.py qcluster
```

#### Вариант B: Для production (через systemd)

Создайте `/etc/systemd/system/django-q-worker.service`:

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

Запустите:

```bash
sudo systemctl daemon-reload
sudo systemctl enable django-q-worker
sudo systemctl start django-q-worker
sudo systemctl status django-q-worker
```

#### Вариант C: Через screen/tmux (простой способ)

```bash
# Создайте сессию
screen -S django-q-worker
# или
tmux new -s django-q-worker

# Запустите воркер
cd /path/to/your/project
source .venv/bin/activate
python manage.py qcluster

# Отключитесь (Ctrl+A затем D для screen)
```

### 8. Проверьте работу

```bash
# Проверьте расписания
python manage.py shell -c "from django_q.models import Schedule; print(f'Расписаний: {Schedule.objects.count()}')"

# Проверьте логи
tail -f logs/django.log
```

## ✅ Проверка успешного развертывания

1. **Воркер запущен:**
   ```bash
   ps aux | grep qcluster
   ```

2. **Расписания созданы:**
   - В админ-панели: **Django Q → Schedules** (должно быть 10 расписаний)

3. **Расписание активно:**
   - В админ-панели: **Assistant → Расписания генерации** (должно быть активное расписание)

4. **Зависимости установлены:**
   ```bash
   python -c "import feedparser, bs4, lxml; print('OK')"
   ```

5. **Миграции применены:**
   ```bash
   python manage.py showmigrations Assistant Blog | grep '\[X\]'
   ```

## 🔧 Устранение проблем

### Если воркер не запускается:

```bash
# Проверьте ошибки
python manage.py qcluster

# Проверьте логи
tail -f logs/qcluster.log
```

### Если статьи не генерируются:

1. Проверьте расписание в админ-панели (должно быть активно)
2. Проверьте настройки GigaChat: **Assistant → Настройки ассистента**
3. Проверьте активные категории: **Blog → Категории**
4. Проверьте логи: `logs/django.log`

### Если ошибки миграций:

```bash
# Откатите и примените заново
python manage.py migrate Assistant 0011
python manage.py migrate Blog 0008
python manage.py migrate
```

## 📊 Мониторинг

- **Логи Django:** `logs/django.log`
- **Логи Django-Q:** В админ-панели → Django Q → OQ (Orchestration Queue)
- **Статистика:** Assistant → Источники новостей, Статистика категорий
- **Сгенерированные статьи:** Blog → Статьи

## 🎯 Готово!

Система автопостинга запущена и будет генерировать статьи:
- **Расписание:** С 8:00 до 11:00 каждый день
- **Частота:** По 1 статье каждые 20 минут (10 статей)
- **Категории:** Ротация с приоритетом популярных (в 2 раза чаще)

Удачи! 🚀
