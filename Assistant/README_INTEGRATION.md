# Assistant — интеграция на новый Django-сайт (ИИ, парсинг, генерация, автопостинг)

## Триада модулей (читать обязательно)

Это приложение **не автономно в вакууме**. Его рассчитывают использовать вместе с:

1. **`Blog/`** — эталонный блог с моделями `Post`, `Category`, `Comment` и namespace URL **`Blog:`**; см. **[Blog/README_INTEGRATION.md](../Blog/README_INTEGRATION.md)**;
2. **`Moderation/`** — модерация статей и комментариев к тем же постам; см. **[Moderation/README_INTEGRATION.md](../Moderation/README_INTEGRATION.md)**.

На новом сайте **проще всего** скопировать в корень проекта все **три** папки и отключить старый блог, затем подправить шаблоны и настройки. Если оставляете свой блог под другим именем — придётся массово менять импорты `Blog` в коде и миграциях.

---

## Размещение в проекте

- Каталог **`Assistant/`** — в **корне** репозитория Django (рядом с `manage.py`), как обычное приложение.
- Шаблоны дашборда и виджет чата лежат в **`Assistant/templates/assistant/`** (загружаются через `APP_DIRS`).

---

## Минимальные требования к каркасу сайта

| Компонент | Зачем |
|-----------|--------|
| **Django** + **PostgreSQL** | Как в референс-проекте; миграции и модели рассчитаны на нормальный ORM. |
| **Redis** + **django-q2** | Фоновые задачи: генерация по расписанию, автопостинг, тяжёлые операции. |
| Приложение **`Blog`** | Создание и хранение статей; см. контракт в `Blog/README_INTEGRATION.md`. |
| **`AUTH_USER_MODEL`** | Автор постов — обычный пользователь Django; дашборд Assistant — **суперпользователь** (`is_superuser`). |
| **Настройки в `.env`** | GigaChat, при необходимости OpenAI, Telegram, ключи парсинга — см. `env.example` в корне репозитория. |

Опционально на целевом сайте: CKEditor, taggit, mptt — уже нужны **блогу**, не только Assistant.

---

## Подключение в `settings.py`

1. В **`INSTALLED_APPS`** добавьте (порядок согласуйте с миграциями, обычно после `Blog`):

   ```python
   'Assistant',
   ```

2. Убедитесь, что заданы переменные из корневого **`env.example`**, как минимум:

   - **GigaChat:** `GIGACHAT_AUTHORIZATION_KEY`, при необходимости `GIGACHAT_CLIENT_ID`, `GIGACHAT_CLIENT_SECRET`, `GIGACHAT_SCOPE`, `GIGACHAT_VERIFY_SSL`;
   - **Парсинг:** `USE_GIGACHAT_PARSING`, `GIGACHAT_PARSING_FALLBACK`, опции `USE_CLOUDSCRAPER`, `USE_TRAFILATURA`, `USE_ASYNC_PARSING`;
   - **Объём новости в промпт:** `ARTICLE_PARSED_NEWS_TARGET_WORDS`;
   - **Очередь:** `REDIS_URL`, блок `Q_CLUSTER` / `DJANGO_Q_*` как в референсном `settings.py`;
   - **Соцсети при автопосте:** `TELEGRAM_*`, при необходимости `VK_*`, `MAX_*`, `SITE_URL`.

3. Копируйте в целевой `settings.py` фрагменты, связанные с **django-q**, **кэшем Redis** и AI, из **`ALUKINTERLAB/settings.py`** этого репозитория — без очереди расписания генерации не поедет.

---

## URL

В корневом **`urls.py`**:

```python
path('assistant/', include('Assistant.urls', namespace='assistant')),
```

Префикс можно сменить, но тогда в **`Assistant/templates/assistant/chat_widget.html`** нужно заменить пути вида `/assistant/api/...` на ваш префикс.

Имена для шаблонов: namespace **`assistant`** (например `assistant:dashboard_main`).

---

## Шаблоны и базовый layout

- Дашборд: **`Assistant/templates/assistant/dashboard/base.html`** наследует **`base/base.html`**.
- На новом сайте замените **`{% extends 'base/base.html' %}`** на ваш базовый шаблон или заведите `templates/base/base.html` с теми же блоками (`title`, `meny`, `straniza`, `extra_css`, … — по факту вашей вёрстки).
- Виджет чата подключают в общем шаблоне: `{% include 'assistant/chat_widget.html' %}`.
- В LukInterLab файл продублирован в **`templates/assistant/chat_widget.html`** (каталог из `TEMPLATES['DIRS']`), чтобы include из `base/base.html` находился **до** загрузчика шаблонов приложений. При переносе на другой сайт либо оставьте такую копию рядом с базовым шаблоном, либо убедитесь, что `APP_DIRS` подхватывает `Assistant/templates/assistant/chat_widget.html`.

---

## Миграции и команды

```bash
python manage.py migrate Blog
python manage.py migrate Assistant
```

Далее — инициализация из репозитория: см. **`README_AUTO_POSTING.md`**, команды вида `init_assistant`, `setup_autoposting_schedule`, `create_default_prompt_template` и по необходимости `setup_gigachat`.

В продакшене запускайте воркер очереди (**`qcluster`**) для django-q.

---

## Что проверить после внедрения

1. Суперпользователь открывает `/assistant/dashboard/`.
2. API `/assistant/api/settings/` отвечает чат-виджету (нет жёсткой привязки к домену, но CSRF/сессии должны работать).
3. Создание черновика/поста из дашборда по-прежнему использует модели **`Blog.Post`**.
4. Расписание django-q вызывает задачи из **`Assistant/tasks.py`**.

Если что-то из этого отсутствует на новом сайте — **досоздайте** (базовый шаблон, Redis, приложение Blog по контракту).

---

## Дополнительная документация

- Внутренняя логика автопостинга: **`README_AUTO_POSTING.md`**.
- Модерация и SEO в интерфейсе редактора: **`Moderation/README_INTEGRATION.md`**.
- Контракт блога и замена чужого блога на наш: **`Blog/README_INTEGRATION.md`**.
