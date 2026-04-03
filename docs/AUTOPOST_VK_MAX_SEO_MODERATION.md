# Автопостинг блога в VK и MAX, модерация и SEO (перенос на другой проект)

Документ описывает реализацию в **lukinterlab.ru**: что настроить на сайте и в окружении, как устроены сигналы, очередь, модерация перед публикацией и SEO до/после выхода статьи. Его можно использовать как чеклист при внедрении на другом Django-проекте с блогом.

**Официальная документация MAX:** [dev.max.ru/docs-api](https://dev.max.ru/docs-api) · хост API: `https://platform-api.max.ru`

---

## 1. Общая схема

1. Редактор сохраняет статью со статусом **«Опубликовано»**.
2. **`pre_save`** фиксирует прежний статус и может **заблокировать** публикацию (модерация по критериям).
3. **`pre_save`** и **`post_save`** дополняют SEO-мета, контент (ссылки), считают **`published_at`**.
4. После успешного коммита транзакции **`publish_to_social`** ставит в **Django-Q** задачи: Telegram (опционально), **VK**, **MAX** (если включено).
5. Воркер **`python manage.py qcluster`** выполняет **`send_to_*_by_id(post_id)`** — сеть не блокирует HTTP-запрос админки (Passenger).

```
[Админка: Сохранить published]
   → pre_save: cache_post_previous_status, gate_draft_to_published_article_moderation, generate_seo_meta_tags
   → post_save: set_post_published_at, publish_to_social (on_commit → async_task), analyze_post_seo, sync_article_moderation_when_published, …
   → qcluster: send_to_telegram_by_id | send_to_vk_by_id | send_to_max_by_id
```

---

## 2. Зависимости и приложения

| Компонент | Назначение |
|-----------|------------|
| **`django-q`** | Очередь фоновых задач (`async_task`, `manage.py qcluster`) |
| **`requests`** | HTTP к VK и MAX |
| **Pillow (`PIL`)** | Нормализация превью (`ImageOps.fit`) и JPEG для соцсетей |
| **`Blog`** | Модель **`Post`**, сигналы публикации и SEO |
| **`Moderation`** | Критерии статей, **`ArticleModeration`**, ворота при **draft → published** |
| **`home`** | **`home/seo_utils.py`**, **`home/tasks.py`** (ночной SEO по расписанию) |

В **`INSTALLED_APPS`** должны быть `'django_q'`, `'Blog'`, `'Moderation'`, `'home'` (или эквиваленты после переноса).

**`settings.py` — фрагмент `Q_CLUSTER`** (упрощённо; в проекте см. `ALUKINTERLAB/settings.py`):

```python
Q_CLUSTER = {
    "name": "LukInterLab",
    "workers": 1,
    "recycle": 500,
    "timeout": 3600,  # длинные задачи генерации; для только постинга можно меньше
    "retry": 7200,
    "queue_limit": 50,
    "orm": "default",
    "sync": False,  # на проде False — обязателен qcluster
}
```

---

## 3. Переменные окружения (`.env`)

См. корневой **`env.example`**. Ключевые имена:

| Переменная | Назначение |
|------------|------------|
| **`SITE_URL`** | База ссылок «Читать далее» (без хвостового `/` в коде обрабатывается) |
| **`VK_ACCESS_TOKEN`** | Ключ **сообщества** VK — **`wall.post`** |
| **`VK_USER_ACCESS_TOKEN`** | Токен **пользователя**-админа группы — загрузка фото (**`photos.*`**), иначе пост без картинки (ошибка 27) |
| **`VK_GROUP_ID`** | ID сообщества (число) |
| **`VK_AUTO_POST`** | `True` / `False` |
| **`MAX_BOT_TOKEN`** | Токен бота MAX (заголовок `Authorization: <токен>`) |
| **`MAX_CHAT_ID`** | ID чата/канала назначения (из API или кабинета) |
| **`MAX_AUTO_POST`** | `True` для постановки задачи MAX |
| **`SOCIAL_ANNOUNCE_MAX_WORDS`** | Лимит слов **тела** анонса (без заголовка и «Читать далее»); по умолч. **100**; **0** = только лимит символов API |
| **`SOCIAL_SHARE_IMAGE_WIDTH`**, **`SOCIAL_SHARE_IMAGE_HEIGHT`** | Кадр JPEG превью для VK/MAX; по умолч. **1200×630** |

Telegram (при переносе целиком): **`TELEGRAM_BOT_TOKEN`**, **`TELEGRAM_CHANNEL_ID`**, **`TELEGRAM_CHANNEL_AUTOPOST`**, плюс флаг в **`AssistantSettings`** в этом проекте.

Загрузка в **`ALUKINTERLAB/settings.py`** через **`secrets_env.env_str` / `env_bool` / `env_int`**.

---

## 4. Модель поста: поля, важные для соцсетей и SEO

В **`Blog/models.py`** (модель **`Post`**):

- **`kartinka`** — `ImageField`, превью для сайта и для загрузки в VK/MAX.
- **`telegram_posted_at`**, **`vk_posted_at`**, **`max_posted_at`** — защита от **повторного** автопоста при следующих `save`.
- SEO: **`meta_title`**, **`meta_description`**, **`meta_keywords`**, **`focus_keyword`**, **`seo_score`**, при необходимости **`og_image`**.

Индексация сигналами завязана на **`status`** (`'draft'` / `'published'`).

---

## 5. Сигнал публикации в соцсети

**Файл:** `Blog/models.py`

```python
@receiver(post_save, sender=Post)
def publish_to_social(sender, instance, created, **kwargs):
    if instance.status != 'published':
        return
    prev = getattr(instance, '_post_prev_status', None)
    if not created and prev == 'published':
        return  # уже была опубликована — не дублировать задачи
    need_tg = not instance.telegram_posted_at
    need_vk = not instance.vk_posted_at
    need_max = not instance.max_posted_at
    ...
    def _enqueue_social():
        from django_q.tasks import async_task
        ...
        if need_vk:
            async_task('Blog.vk_utils.send_to_vk_by_id', post_pk)
        if need_max and getattr(dj_settings, 'MAX_AUTO_POST', False):
            if tok and cid:
                async_task('Blog.max_utils.send_to_max_by_id', post_pk)
    transaction.on_commit(_enqueue_social)
```

**Нюанс:** **`_post_prev_status`** выставляется в **`Blog/signals.py`** в **`cache_post_previous_status`** (`pre_save`), иначе каждый повторный save опубликованной статьи поставил бы новые задачи, пока пусты `*_posted_at`.

---

## 6. VK: код и настройка в кабинете

**Файл:** `Blog/vk_utils.py`

| Функция | Роль |
|---------|------|
| **`_build_vk_message(post, site_url)`** | Текст: заголовок + описание/начало статьи + «Читать далее: URL»; учёт **`SOCIAL_ANNOUNCE_MAX_WORDS`** |
| **`_prepare_preview_bytes(post)`** | Единый **JPEG** кадра **W×H** (`ImageOps.fit`), прозрачность на белый фон |
| **`_upload_wall_photo`** | `photos.getWallUploadServer` → POST файла → `photos.saveWallPhoto` с **`VK_USER_ACCESS_TOKEN`** |
| **`send_to_vk(post)`** | Сбор вложения + **`wall.post`** с **`VK_ACCESS_TOKEN`** |
| **`send_to_vk_by_id(post_id)`** | Точка входа для Django-Q |

**Кабинет VK:** ключ сообщества с правом **«Стена»**; отдельно получить **пользовательский** токен с **photos** (и при необходимости **offline**), не публиковать токены в Git.

**Тест:** `python manage.py test_vk_autopost` (см. `Blog/management/commands/test_vk_autopost.py`).

---

## 7. MAX: код и настройка

**Файл:** `Blog/max_utils.py`

| Этап | Метод |
|------|--------|
| Текст | **`_build_max_message`** (как VK по смыслу + лимит слов) |
| Картинка | **`POST /uploads?type=image`** → второй POST **multipart** `data=@file` на выданный **`url`** → **`attachments`** с **`type: "image"`** |
| Отправка | **`POST /messages?chat_id=...`**, JSON **`{ "text", "attachments"? }`** |
| Превью ссылки | Параметр **`disable_link_preview`** **не** передаётся — клиент может показать карточку URL |

Логи префикс **`MAX:`** в **`logs/django.log`** (и частично в **`logs/qcluster.log`**).

Документация: [POST /uploads](https://dev.max.ru/docs-api/methods/POST/uploads), [POST /messages](https://dev.max.ru/docs-api/methods/POST/messages).

---

## 8. Модерация перед публикацией

**Файл:** `Moderation/signals.py`

При переходе **черновик → опубликовано** (`pre_save` на **`Post`**):

```python
@receiver(pre_save, sender=Post)
def gate_draft_to_published_article_moderation(sender, instance, **kwargs):
    prev = getattr(instance, '_post_prev_status', None)
    if prev != 'draft' or instance.status != 'published':
        return
    criteria = ModerationCriteria.objects.filter(is_active=True).first()
    if not criteria:
        return  # без активного критерия ворот нет
    result = article_moderation_service.moderate_article(instance, criteria)
    if result.get('status') != 'approved':
        instance.status = 'draft'  # откат публикации
```

**Что сделать на сайте:** в админке **Модерация → Критерии модерации** создать хотя бы один **активный** критерий для статей, иначе логи django-q могут содержать «Нет активных критериев» для **почасовых** задач комментариев/статей, а ворота публикации при этом **не** срабатывают.

После публикации **`sync_article_moderation_when_published`** помечает **`ArticleModeration`** как **`approved`**.

---

## 9. SEO: до и после публикации

### 9.1 При каждом сохранении статьи

**Файл:** `Blog/signals.py`

| Сигнал | Назначение |
|--------|------------|
| **`generate_seo_meta_tags`** (`pre_save`) | Slug, meta title/description/keywords, focus_keyword, **`rel=nofollow`** на внешние ссылки, внутренние ссылки для **published** |
| **`post_tags_changed_fill_meta_keywords`** | Дозаполнение keywords после M2M тегов |

Утилиты текста: **`home/seo_utils.py`** (`SEOUtils.plain_text_for_meta`, длина description и т.д.).

### 9.2 После сохранения опубликованной статьи

**`analyze_post_seo`** (`post_save`): **`Moderation.services.SEOService`** пишет анализ, **`seo_score`** обновляется в БД через **`Post.objects.filter(pk=...).update(...)`** (без рекурсии сигналов).

### 9.3 Ночной массовый прогон (отдельно от одного поста)

**`home/tasks.optimize_seo_task`** вызывает команду **`optimize_seo_for_ai`**. Расписание создаётся **`python manage.py setup_schedule`** — см. **`home/management/commands/setup_schedule.py`** (CRON **02:00** и др.).

Это **не** заменяет per-post сигналы; это пакетная оптимизация под AI/поиск по задумке проекта.

---

## 10. Что сделать на сервере (деплой)

1. **`.env`** с переменными из раздела 3 (токены не в Git).
2. **`git pull`**, **`python manage.py migrate`**, при необходимости **`collectstatic`**, перезапуск приложения (**`touch tmp/restart.txt`** под Passenger).
3. Запуск воркера: **`nohup /path/to/venv/bin/python manage.py qcluster >> logs/qcluster.log 2>&1 &`**
4. Проверка: **`pgrep -af qcluster`**, **`tail logs/qcluster.log`**, **`grep VK\|MAX logs/django.log`**
5. После смены кода **обязательно перезапустить `qcluster`**, иначе старый код в памяти.

---

## 11. Перенос на другой сайт (чеклист)

1. Скопировать/адаптировать модули: **`Blog/vk_utils.py`**, **`Blog/max_utils.py`**, **`Blog/telegram_utils.py`** (если нужен), сигналы из **`Blog/models.py`** и **`Blog/signals.py`**, **`cache_post_previous_status`**.
2. Добавить в модель поста поля **`vk_posted_at`**, **`max_posted_at`** (и миграции), **`kartinka`**, SEO-поля по необходимости.
3. Подключить **`django-q`** и **`Q_CLUSTER`**.
П. Перенести **`Moderation`** ворота или упростить под свой процесс модерации.
5. Вынести секреты в **`.env`**, продублировать имена в **`env.example`**.
6. Убедиться, что **`MEDIA_ROOT`** доступен воркеру **`qcluster`** для чтения **`kartinka`**.
7. Лимиты **`SOCIAL_ANNOUNCE_MAX_WORDS`** и размеры **`SOCIAL_SHARE_*`** привести к одному **`settings`** или оставить дефолты.

---

## 12. Типичные проблемы

| Симптом | Что проверить |
|---------|----------------|
| Дубли постов в VK/MAX | Заполнены ли **`vk_posted_at`/`max_posted_at`**; не сброшен ли **`_post_prev_status`** |
| **Incomplete response** у веб-сервера | Постинг должен идти только через **`async_task`**, не синхронно в **`post_save`** |
| VK без фото | Задан ли **`VK_USER_ACCESS_TOKEN`** |
| MAX без картинки | Есть ли **`kartinka`** **до** первой отправки; лог **`kartinka пустое`** / **`вложение image подготовлено`** |
| Задачи не выполняются | Не запущен **`qcluster`** или убит хостингом — cron-автозапуск |
| Публикация откатывается в черновик | Модерация **`moderate_article`** не **`approved`** — править контент или критерии |
| Долгий текст в лентах | Уменьшить **`SOCIAL_ANNOUNCE_MAX_WORDS`** или оставить **0** |

---

## 13. Связанные пути в репозитории

| Путь | Содержание |
|------|------------|
| `ALUKINTERLAB/settings.py` | VK, MAX, `SOCIAL_*`, `Q_CLUSTER` |
| `Blog/models.py` | `Post`, `publish_to_social` |
| `Blog/signals.py` | SEO pre_save, `analyze_post_seo`, `cache_post_previous_status` |
| `Blog/vk_utils.py` | VK + **`_prepare_preview_bytes`** |
| `Blog/max_utils.py` | MAX API |
| `Moderation/signals.py` | Ворота публикации, модерация комментариев |
| `home/seo_utils.py` | Очистка текста для meta |
| `home/tasks.py` | `optimize_seo_task` |
| `home/management/commands/setup_schedule.py` | CRON django-q |

---

*Документ создан для внутреннего использования команды lukinterlab.ru; при переносе сверяйте версии API VK/MAX с актуальной документацией.*
