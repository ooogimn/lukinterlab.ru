# Moderation — интеграция на новый Django-сайт (статьи, комментарии, SEO)

## Триада модулей (читать обязательно)

**Moderation** рассчитан на работу с тем же блогом, что и **Assistant**:

| Модуль | Роль |
|--------|------|
| **`Blog/`** | Модели **`Post`**, **`Category`**, **`Comment`** — обязательный контракт; см. **[Blog/README_INTEGRATION.md](../Blog/README_INTEGRATION.md)**. |
| **`Assistant/`** | Генерация и автопостинг статей в те же `Post`; часто ставят в один проект. **[Assistant/README_INTEGRATION.md](../Assistant/README_INTEGRATION.md)**. |
| **`Moderation/`** (этот каталог) | Записи модерации статей, комментариев, SEO-анализ в UI. |

На новом сайте **рекомендуется** скопировать все **три** папки в корень Django-проекта и **заменить** существующий блог на эталонный `Blog`, затем точечно подстроить шаблоны и `settings`. Иначе потребуется переписать импорты `from Blog.models import …` и миграции.

---

## Размещение

- Каталог **`Moderation/`** — в **корне** проекта рядом с `manage.py`.
- Шаблоны интерфейса модератора: **`Moderation/templates/moderation/`**.

---

## Требования к каркасу сайта

| Компонент | Зачем |
|-----------|--------|
| **Django** + **PostgreSQL** | Модели и админка. |
| **`Blog`** с теми же сущностями, что в референсе | `ArticleModeration.post` — `OneToOne` к `Blog.Post`; комментарии — к `Blog.Comment`. |
| **`django.contrib.auth`** | Модераторы — пользователи; проверки доступа в views. |
| **`django.contrib.contenttypes`** | Опционально для обобщённых связей в модерации комментариев. |
| **Django-Q** (как в проекте) | Фоновые задачи из **`Moderation/tasks.py`** — по желанию настроить расписание. |

Форма редактирования поста в интерфейсе модерации использует **`Blog.forms.PostEditForm`** — блог должен её предоставлять (как в референсном `Blog`).

---

## Подключение в `settings.py`

```python
INSTALLED_APPS = [
    # ...
    'Blog.apps.BlogConfig',  # или 'Blog'
    'Assistant',  # опционально, но часто в одном стеке
    'Moderation',
]
```

Порядок уточняйте по зависимостям миграций: сначала **`Blog`**, затем **`Moderation`** (в миграциях есть ссылки на `Blog.post`, `Blog.comment`).

---

## URL

```python
path('moderation/', include('Moderation.urls', namespace='moderation')),
```

Шаблоны опираются на имена **`moderation:dashboard`**, **`moderation:article_list`**, **`Blog:post_edit`**, **`Blog:post_staff_preview`** и т.д. При смене маршрутов блога сохраните **имена** `Blog:` или обновите шаблоны в **`Moderation/templates/`**.

---

## Шаблоны

- База: **`Moderation/templates/moderation/base.html`** — по умолчанию `{% extends 'base/base.html' %}`.
- На новом сайте замените базовый шаблон на свой или заведите совместимый `base/base.html`.

---

## Миграции и команды

```bash
python manage.py migrate Blog
python manage.py migrate Moderation
```

Полезные management-команды из репозитория:

- `sync_published_article_moderation` — синхронизация статусов модерации с уже опубликованными постами;
- `setup_moderation_tasks` — привязка задач django-q (если используете);
- `seed_comment_moderation_strict` — тестовые критерии (по необходимости).

---

## Доступ пользователей

Views рассчитаны на **staff** / логику из референсного **`Moderation/views.py`**. При переносе проверьте декораторы и группы прав под вашу модель ролей.

---

## Проверка после внедрения

1. Открывается `/moderation/` у нужной роли пользователя.
2. Создание черновика поста порождает цепочку модерации (сигналы на `Blog.Post`).
3. Ссылки «Превью» и «Редактировать» ведут на существующие URL **`Blog:`**.
4. Комментарии к постам попадают в очередь модерации при активных критериях.

Подробное описание сущностей и JSON-критериев: **`README.md`** (внутренняя документация приложения).

---

## Связанные файлы

- Контракт блога и стратегия «заменить папку Blog на новом сайте»: **`Blog/README_INTEGRATION.md`**.
- ИИ и автопостинг: **`Assistant/README_INTEGRATION.md`**.
