# Приложение "Модерация"

Приложение для системы контроля за статьями блога, включающее три основных модуля:

## 📋 Структура модулей

### 1. Модерация статей (`ArticleModeration`, `ModerationCriteria`)

**Модели:**
- `ModerationCriteria` - Критерии модерации статей (JSON формат)
- `ArticleModeration` - Записи модерации статей со статусами:
  - `pending` - Ожидает модерации
  - `approved` - Одобрено
  - `rejected` - Отклонено
  - `needs_revision` - Требует доработки

**Функционал:**
- Автоматическая проверка статей по критериям
- Проверка длины текста, ключевых слов, запрещенных слов
- Комментарии модератора
- История модерации

### 2. SEO оптимизация (`SEOAnalysis`)

**Модели:**
- `SEOAnalysis` - SEO анализ статей

**Функционал:**
- Автоматический SEO анализ статей
- Генерация Meta Title и Meta Description
- Проверка структуры контента
- SEO Score (0-100 баллов)
- Рекомендации по улучшению

**Проверяемые параметры:**
- Длина заголовка (30-60 символов)
- Мета-описание (120-160 символов)
- Длина контента (минимум 300 слов)
- Наличие изображения
- Структура (H2, H3, списки, параграфы)
- Ключевые слова и теги

### 3. Модерация комментариев (`CommentModeration`, `CommentModerationCriteria`)

**Модели:**
- `CommentModerationCriteria` - Критерии модерации комментариев
- `CommentModeration` - Записи модерации комментариев

**Действия:**
- `approved` - Одобрено
- `deleted` - Удалено
- `corrected` - Исправлено
- `replied` - Ответ добавлен

**Функционал:**
- Автоматическая проверка комментариев
- Обнаружение спама и запрещенных слов
- Автокоррекция текста
- Автоматические ответы

## 🔧 Сервисы

### `ArticleModerationService`
- `moderate_article()` - Модерация статьи
- `check_criteria()` - Проверка по критериям

### `CommentModerationService`
- `moderate_comment()` - Модерация комментария
- `check_criteria()` - Проверка по критериям

### `SEOService`
- `analyze_post()` - SEO анализ статьи
- `generate_meta_tags()` - Генерация мета-тегов

## 📊 Фоновые задачи (Django-Q)

### `moderate_articles_task()`
Автоматическая модерация статей со статусом `pending`

### `moderate_comments_task()`
Автоматическая модерация комментариев без действия

### `analyze_seo_task()`
SEO анализ опубликованных статей (обновление раз в 30 дней)

## 🔗 URL маршруты

- `/moderation/` - Дашборд модерации
- `/moderation/articles/` - Список статей на модерации
- `/moderation/articles/<id>/` - Детальная страница модерации статьи
- `/moderation/comments/` - Список комментариев на модерации
- `/moderation/seo/` - Список SEO анализов
- `/moderation/seo/<id>/` - Детальная страница SEO анализа

## 🔔 Сигналы

- `post_save` на `Post` - Автоматическое создание записи модерации для черновиков
- `post_save` на `Comment` - Автоматическое создание записи модерации для комментариев

## 📝 Использование

### Создание критериев модерации

В админ-панели создайте набор критериев в формате JSON:

**Для статей:**
```json
{
  "min_length": 1000,
  "max_length": 5000,
  "required_keywords": ["красота", "стиль"],
  "forbidden_words": ["спам", "реклама"],
  "tone": "дружелюбный и профессиональный",
  "structure": "заголовок, вступление, основная часть, заключение"
}
```

**Для комментариев:**
```json
{
  "forbidden_words": ["спам", "реклама", "оскорбление"],
  "min_length": 5,
  "max_length": 2000,
  "spam_patterns": ["купить", "ссылка на"],
  "tone_rules": "вежливый, без оскорблений"
}
```

### Ручная модерация

1. Перейдите в `/moderation/`
2. Выберите статью или комментарий
3. Проверьте результаты автоматической проверки
4. Установите статус и добавьте комментарий
5. Сохраните

### Автоматическая модерация

Настройте задачи Django-Q для автоматического запуска:

```python
from django_q.models import Schedule
from Moderation.tasks import moderate_articles_task, moderate_comments_task, analyze_seo_task

# Ежечасная модерация статей
Schedule.objects.create(
    func='Moderation.tasks.moderate_articles_task',
    schedule_type=Schedule.HOURLY,
)

# Ежечасная модерация комментариев
Schedule.objects.create(
    func='Moderation.tasks.moderate_comments_task',
    schedule_type=Schedule.HOURLY,
)

# Ежедневный SEO анализ
Schedule.objects.create(
    func='Moderation.tasks.analyze_seo_task',
    schedule_type=Schedule.DAILY,
)
```

## 🎯 Следующие шаги

1. Создать шаблоны для интерфейса модерации
2. Настроить автоматические задачи Django-Q
3. Добавить уведомления модераторам
4. Расширить критерии проверки
5. Добавить статистику и аналитику

