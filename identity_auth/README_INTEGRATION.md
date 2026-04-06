# identity_auth — автономный модуль входа, регистрации и OAuth

Всё, что относится к **входу по паролю, регистрации, OAuth (Янд/Google/MAX), VK ID и настройке ключей в админке/дашборде**, сосредоточено в приложении `identity_auth/`.

---

## Важно: это не «скопировал папку — и всё заработало»

Модуль **нужно осознанно вписать** в целевой Django-проект: настройки, маршруты, контекст для виджета VK ID, модель профиля (если есть), миграции, шаблоны меню и ссылок, `.env` (или эквивалент) и/или форма «Вход и OAuth».

**Объём работ** зависит от того, как устроен **ваш** сайт:

| Ситуация | Что обычно дольше |
|----------|-------------------|
| Тот же стек, свой `User`, профиль `OneToOne` как `home.Customer` | Минимум: настройки + URL + шаблоны ссылок |
| Свой `AUTH_USER_MODEL`, другая модель профиля | Проверить `IDENTITY_AUTH_CUSTOMER_MODEL`, поля в `CustomerRegistrationForm` / OAuth |
| Свой `base.html`, другие блоки шаблонов | Подправить `identity_auth/templates/...` под ваш каркас |
| Уже есть полноценные страницы «Вход» и «Регистрация» | Решить: отключить старые маршруты и вести на `identity_auth:` **или** постепенно заменить ссылки — **две полные цепочки входа не дублировать** |

Ниже — **стандартный минимум** по шагам. Нетипичные случаи всё равно требуют точечных правок в коде.

---

## Карта папки `identity_auth/` (что за что отвечает)

| Путь | Назначение |
|------|------------|
| `models.py` | `LinkedSocialAccount` (привязки провайдер → `User`), `SiteCustomerAuthSettings` (ключи VK/OAuth в БД; в LukInterLab таблица исторически совпадает с прежней в `home`) |
| `auth_settings.py` | Чтение настроек: **непустое значение в БД перекрывает** то же из `settings`/`.env` |
| `forms.py` | Формы регистрации/входа и форма настроек OAuth для страницы `/manage/auth/oauth/` |
| `views.py` | Регистрация, вход, `customer_vkid_complete`, выход, страница настроек OAuth |
| `oauth_views.py` | Старт и callback OAuth (PKCE) |
| `services.py` | Слияние аккаунтов по email и legacy-username; создание профиля из `IDENTITY_AUTH_CUSTOMER_MODEL` |
| `context_processors.py` | **`vkid_oauth`** — переменные для виджета VK ID (иконки, `vkid_app_id`, флаги) |
| `urls.py` | Все имена с **namespace** `identity_auth` (`app_name = 'identity_auth'`) |
| `templates/identity_auth/` | `login.html`, `register.html`, `admin/oauth_settings.html` |
| `templates/identity_auth/partials/` | `oauth_widget.html`, `flash_messages.html` |
| `static/identity_auth/img/oauth/` | SVG для кнопок OAuth по умолчанию |
| `management/commands/backfill_linked_social.py` | Одноразовый бэкофилл `LinkedSocialAccount` из старых username вида `vkid_*`, `yandex_*`, … |

Личный кабинет (заказы, профиль) **не** в этом приложении — он остаётся в вашем `home` или другом приложении.

---

## Имена URL (обязательно с префиксом `identity_auth:`)

В шаблонах используйте **`{% url 'identity_auth:...' %}`**, а не голые пути — так проще переносить сайт между окружениями.

| Имя | Назначение | Параметры |
|-----|------------|-----------|
| `identity_auth:customer_register` | Регистрация | — |
| `identity_auth:customer_login` | Вход | — |
| `identity_auth:customer_logout` | Выход | — |
| `identity_auth:customer_oauth_start` | Старт OAuth | аргумент `provider`: `yandex`, `google`, `max` |
| `identity_auth:customer_oauth_callback` | Callback OAuth (обычно только в redirect_uri у провайдера) | — |
| `identity_auth:customer_vkid_complete` | Завершение VK ID (точка, куда уходит виджет после логина) | — |
| `identity_auth:admin_customer_auth_oauth_settings` | Страница «Вход и OAuth» (ключи в БД), **только для суперпользователя** | — |

Примеры в шаблоне:

```django
<a href="{% url 'identity_auth:customer_login' %}">Войти</a>
<a href="{% url 'identity_auth:customer_register' %}">Регистрация</a>
<a href="{% url 'identity_auth:customer_logout' %}">Выйти</a>
<a href="{% url 'identity_auth:customer_oauth_start' 'yandex' %}">Яндекс</a>
```

В коде модуля после успешного входа/регистрации стоит редирект на **`home:customer_dashboard`**. Если у вас другой ЛК — **нужно заменить** эти редиректы в `identity_auth/views.py` (и при необходимости в других местах, где встретите то же имя URL).

---

## Пошаговое подключение к проекту

Делайте по порядку и отмечайте пункты.

### Шаг 1. Скопировать приложение

Скопируйте каталог **`identity_auth/`** в корень проекта (рядом с другими приложениями, например `home/`). Убедитесь, что внутри есть `__init__.py`, `apps.py`, миграции, `templates`, `static`.

### Шаг 2. `INSTALLED_APPS`

Откройте **`settings.py`** вашего проекта (часто `имя_проекта/settings.py`).

Добавьте строку (порядок относительно `home` в этом репозитории не критичен для работы кода, но **миграции** см. ниже):

```python
INSTALLED_APPS = [
    # ...
    'identity_auth',
    # 'home',  # ваше приложение профиля/кабинета
]
```

### Шаг 3. Корневой `urls.py`

Откройте главный файл URL (там, где `urlpatterns` у всего сайта).

Подключите маршруты `identity_auth` **до** `home.urls` (или до любых старых маршрутов `/customer/login/` и т.п.), чтобы новые адреса перехватывались первыми:

```python
from django.urls import path, include

urlpatterns = [
    path('', include('identity_auth.urls')),
    path('', include('home.urls')),
    # ...
]
```

Если у вас был **свой** вход по тем же путям (`customer/login/` …) — его нужно **убрать из `home.urls`**, иначе будет путаница или конфликт.

### Шаг 4. Context processor для VK ID

В том же **`settings.py`**, в `TEMPLATES` → `OPTIONS` → `context_processors`, добавьте:

```python
'identity_auth.context_processors.vkid_oauth',
```

Без этого шаблоны с виджетом VK ID не получат `vkid_app_id` и связанные флаги из `auth_settings`.

### Шаг 5. Модель профиля заказчика — `IDENTITY_AUTH_CUSTOMER_MODEL`

В **`settings.py`**:

```python
# Профиль с OneToOne к User (как в LukInterLab — home.Customer).
IDENTITY_AUTH_CUSTOMER_MODEL = 'home.Customer'

# Если профиля нет и достаточно одного User:
# IDENTITY_AUTH_CUSTOMER_MODEL = ''   # или не задавать / None — см. services._ensure_customer
```

В коде используется **`get_or_create(user=user, defaults={'phone': ''})`**. Ваша модель должна иметь поле **`user`** (обычно `OneToOneField` на `AUTH_USER_MODEL`) и по возможности поддерживать `phone` в `defaults`, либо вам нужно поправить **`identity_auth/services.py`** (`_ensure_customer`) под ваши поля.

### Шаг 6. Переменные окружения / `settings` (VK ID и OAuth)

Значения можно задать **только в `.env`** и дублировать в `settings`, **или** часть оставить пустой в `.env` и заполнить в **форме на `/manage/auth/oauth/`** (шаг 8 ниже) — БД перекрывает `.env`, когда поле в БД непустое (см. `auth_settings.py`).

Типовые имена (как в `env.example` проекта LukInterLab):

| Переменная | Для чего |
|------------|----------|
| `VKID_APP_ID` | ID приложения VK ID |
| `VKID_REDIRECT_URL` | Доверенный redirect: **URL страницы входа** (`…/customer/login/`), где подключён виджет VK ID; не корень сайта, иначе после согласия цепочка `exchangeCode` не выполняется |
| `VKID_PROTECTED_KEY`, `VKID_SERVICE_KEY` | Ключи VK ID |
| `YANDEX_OAUTH_CLIENT_ID`, `YANDEX_OAUTH_CLIENT_SECRET` | Яндекс OAuth |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth |
| `MAX_OIDC_ISSUER`, `MAX_OIDC_CLIENT_ID`, `MAX_OIDC_CLIENT_SECRET` | MAX (OIDC) |

Подключите их в `settings.py` через `os.environ` / `django-environ` так же, как остальные секреты проекта.

### Шаг 7. Миграции и порядок с `home`

В **этом репозитории** миграция `identity_auth/migrations/0002_sitecustomerauthsettings_state.py` **зависит** от миграции `home` (`0027_remove_sitecustomerauthsettings_state`), потому что таблица настроек OAuth раньше «жила» в `home`, а Django переносит **только состояние** модели в `identity_auth`.

**Если вы разворачиваете именно LukInterLab / тот же проект с той же историей `home`:**

```bash
python manage.py migrate home
python manage.py migrate identity_auth
```

**Если вы переносите только папку `identity_auth` на другой сайт** с **другой** историей миграций `home`, команда `migrate` может **упасть** из‑за отсутствия `home.0027_...`. Это **нетипичный случай**: нужно согласовать миграции с разработчиком (подменить зависимость в `0002` или создать таблицу настроек с нуля).

После успешных миграций для продакшена не забудьте:

```bash
python manage.py collectstatic
```

чтобы подтянулись `identity_auth/static/...`.

### Шаг 8. Страница «Вход и OAuth»

URL: **`/manage/auth/oauth/`**, view: `identity_auth:admin_customer_auth_oauth_settings`. Доступ рассчитан на **суперпользователя**. Здесь можно хранить ключи в БД (удобно, когда не хотите светить секреты только в `.env`).

### Шаг 9. Команда `backfill_linked_social` — когда нужна

Если на сайте уже были пользователи, созданные старыми способами с **username** вида `vkid_10…`, `yandex_…`, `google_…`, `max_…`, но **без** записей в `LinkedSocialAccount`, выполните **после миграций**:

```bash
python manage.py backfill_linked_social
```

Это заполняет таблицу привязок для дальнейшего единообразного входа и слияния. Если у вас «чистая» база — команду можно не запускать.

### Шаг 10. Шаблоны сайта (меню, «Войти», ссылки после входа)

1. Найдите в проекте все ссылки на старые имена URL входа/регистрации/выхода (например `home:customer_login`, прямые `href="/customer/login/"` и т.д.).
2. Замените на **`identity_auth:customer_login`**, **`identity_auth:customer_register`**, **`identity_auth:customer_logout`** (см. таблицу выше).
3. Если подключаете фрагменты OAuth/VK из LukInterLab — используйте имена с префиксом **`identity_auth:`** и при необходимости скопируйте partial’ы из `identity_auth/templates/`.

**Шаблоны внутри `identity_auth`** (`login.html`, `register.html`) в референс-проекте наследуют **`base/base.html`** и блоки вроде `meny`, `straniza`, фоны из контекста — на **другом** сайте почти наверняка придётся **поменять** `{% extends %}`, `{% include %}` и вёрстку под ваш общий шаблон.

### Шаг 11. Убрать дублирование со старой авторизацией

Выберите одну стратегию:

- **Резко:** удалить или закомментировать старые `path(...)` входа/регистрации в `home/urls.py` (или где они были), оставив только `identity_auth`.
- **Плавно:** временно оставить старые URL, но **в шаблонах** вести пользователей только на `identity_auth:`; старые адреса редиректить на новые через `RedirectView`, чтобы не поддерживать две формы входа.

Две полные независимые цепочки (две разные сессии, две логики) — источник багов.

---

## Проверка после внедрения (минимальный чеклист)

1. Открывается `/customer/login/` и `/customer/register/` без 500.
2. Регистрация создаёт пользователя, редирект в ЛК (или ваш URL после правки `views.py`).
3. Вход по паролю работает; «Выйти» очищает сессию.
4. На странице с виджетом VK ID при заготовленных ключах нет пустого `vkid_app_id` в контексте (или виджет не инициализируется — тогда проверить `.env` и context processor).
5. Один раз прогнать OAuth (Янд/Google/MAX) на тестовом окружении с правильными redirect URI у провайдера.
6. Суперпользователь открывает `/manage/auth/oauth/` и может сохранить настройки.

---

## Краткая сводка настроек (копипаста-ориентир)

```python
# settings.py — фрагменты
INSTALLED_APPS = [
    # ...
    'identity_auth',
]

TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            # ...
            'identity_auth.context_processors.vkid_oauth',
        ],
    },
}]

IDENTITY_AUTH_CUSTOMER_MODEL = 'home.Customer'  # или '' / ваша 'app.Model'

# + переменные VK / OAuth из .env (см. таблицу выше)
```

```python
# urls.py корневой
urlpatterns = [
    path('', include('identity_auth.urls')),
    path('', include('home.urls')),
]
```

---

## LukInterLab (особенности этого репозитория)

Модель настроек OAuth **физически** остаётся в той же таблице БД, что до выноса в `identity_auth`; отдельный перенос строк не требуется. Редирект после входа по умолчанию — **`home:customer_dashboard`**.
