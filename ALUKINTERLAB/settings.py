"""
Django settings for ALUKINTERLAB project.

Секреты задаются через переменные окружения или файл .env в корне проекта (см. env.example).
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

from ALUKINTERLAB.secrets_env import (
    load_env_file,
    env_str,
    env_bool,
    env_int,
    require_secret_key,
    split_hosts,
    split_origins,
)

load_env_file(BASE_DIR)

SECRET_KEY = require_secret_key()

# На продакшене в .env или панели хостинга: DJANGO_DEBUG=False
DEBUG = env_bool("DJANGO_DEBUG", True)

# Админка: длинные списки (комментарии и т.д.), массовые действия и темы вроде Jazzmin
# могут отправлять >1000 полей в одном POST — иначе TooManyFieldsSent.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# Публичный URL сайта (CSRF, ссылки)
SITE_URL = env_str("SITE_URL", "https://lukinterlab.ru").rstrip("/")

ALLOWED_HOSTS = split_hosts(
    os.environ.get("DJANGO_ALLOWED_HOSTS"),
    "127.0.0.1,localhost,testserver,lukinterlab.ru,www.lukinterlab.ru",
)

TELEGRAM_BOT_TOKEN = env_str("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = env_str("TELEGRAM_CHANNEL_ID", "-1002200401634")
# Публичный канал: анонсы статей (можно выключить в .env при блокировках; дашборд может дополнительно выключить)
TELEGRAM_CHANNEL_AUTOPOST = env_bool("TELEGRAM_CHANNEL_AUTOPOST", True)

# VK API — автопостинг статей на стену сообщества (Blog.models.publish_to_social → send_to_vk).
# VK_ACCESS_TOKEN — ключ СООБЩЕСТВА (Работа с API → создать ключ): для wall.post достаточно прав «Стена».
# Ключ сообщества НЕ может вызывать photos.getWallUploadServer (ошибка API 27) — превью не прикрепится.
# VK_USER_ACCESS_TOKEN — пользовательский access_token администратора сообщества (OAuth приложения VK),
# для загрузки превью достаточно scope: photos (+ offline для бессрочного токена). Не добавляйте groups/wall
# без необходимости — иначе oauth.vk.com может вернуть invalid_scope (groups часто требует отдельных доступов в кабинете приложения).
_VK_TOKEN_FALLBACK = ""
VK_ACCESS_TOKEN = env_str("VK_ACCESS_TOKEN") or _VK_TOKEN_FALLBACK
VK_USER_ACCESS_TOKEN = env_str("VK_USER_ACCESS_TOKEN")
VK_GROUP_ID = env_str("VK_GROUP_ID", "231035215")
VK_AUTO_POST = env_bool("VK_AUTO_POST", True)

# VK Callback API: URL вида {SITE_URL}/callback/{VK_CALLBACK_PATH_SLUG}/ (метод POST, JSON).
VK_CALLBACK_PATH_SLUG = env_str("VK_CALLBACK_PATH_SLUG", "")
VK_CALLBACK_CONFIRMATION = env_str("VK_CALLBACK_CONFIRMATION", "")
VK_CALLBACK_SECRET = env_str("VK_CALLBACK_SECRET", "")

# VK ID (OAuth личного кабинета). Секреты только в .env / окружении.
_vkid_app_raw = env_str("VKID_APP_ID", "54515641")
try:
    VKID_APP_ID = int(_vkid_app_raw)
except ValueError:
    VKID_APP_ID = 54515641
VKID_REDIRECT_URL = env_str("VKID_REDIRECT_URL", "https://lukinterlab.ru/")
VKID_PROTECTED_KEY = env_str("VKID_PROTECTED_KEY")
VKID_SERVICE_KEY = env_str("VKID_SERVICE_KEY")

# GigaChat API
GIGACHAT_AUTHORIZATION_KEY = env_str("GIGACHAT_AUTHORIZATION_KEY")
GIGACHAT_SCOPE = env_str("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_CLIENT_ID = env_str("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = env_str("GIGACHAT_CLIENT_SECRET")
GIGACHAT_VERIFY_SSL = env_bool("GIGACHAT_VERIFY_SSL", False)

USE_GIGACHAT_PARSING = env_bool("USE_GIGACHAT_PARSING", True)
GIGACHAT_PARSING_FALLBACK = env_bool("GIGACHAT_PARSING_FALLBACK", True)
USE_CLOUDSCRAPER = env_bool("USE_CLOUDSCRAPER", True)
USE_TRAFILATURA = env_bool("USE_TRAFILATURA", True)
USE_ASYNC_PARSING = env_bool("USE_ASYNC_PARSING", False)

# Целевой объём спарсенного текста новости для генерации статьи (слов). Больше — меньше «добор воды» моделью, но длиннее промпт.
ARTICLE_PARSED_NEWS_TARGET_WORDS = env_int("ARTICLE_PARSED_NEWS_TARGET_WORDS", 480) or 480

INSTALLED_APPS = [
    'ckeditor', 'ckeditor_uploader',
    'jazzmin', 
    'mptt',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',  # Sitemap для SEO
    'home', 'Blog.apps.BlogConfig', 'Users', 'taggit', 'Assistant',
    'django_q',  # Django-Q для фоновых задач
    'Moderation',  # Модерация статей, комментариев и SEO
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'ALUKINTERLAB.middleware.DatabaseConnectionMiddleware',  # Закрываем соединения после запроса для SQLite
]

# Security settings for SEO and performance
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

# CSRF Settings
CSRF_COOKIE_HTTPONLY = False  # Разрешаем JavaScript доступ к CSRF cookie
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = split_origins(os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS"), SITE_URL)

ROOT_URLCONF = 'ALUKINTERLAB.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'home.context_processors.seo_meta_tags',
                'home.context_processors.section_backgrounds',
                'home.context_processors.cart_info',
                'home.context_processors.legal_info_context',
                'home.context_processors.vkid_oauth',
            ],
        },
    },
]

WSGI_APPLICATION = 'ALUKINTERLAB.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'ALUKINTERLAB.db_backends',  # Используем кастомный backend с WAL mode
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,  # Увеличиваем timeout для SQLite (по умолчанию 5 секунд)
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True


# Ститика и медиофайлы
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

STATIC_URL = "/static/"

# Только если каталог есть: иначе на сервере без этой папки — предупреждение staticfiles.W004.
_extra_static = BASE_DIR / "STATIC"
STATICFILES_DIRS = [_extra_static] if _extra_static.is_dir() else []
# В STATIC не должно быть своей папки vendor/adminlte (и т.п.) из старых collectstatic:
# она перекрывает статику пакета jazzmin → подключается старый AdminLTE без классов .app-wrapper,
# боковое меню «разъезжается» на всю ширину. Актуальные vendor/* идут из django-jazzmin.

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_IMAGE_BACKEND = "pillow"
CKEDITOR_JQUERY_URL = '//ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js'
CKEDITOR_CONFIGS = {
    'default': {
        'skin': 'moono',
        'height': 500,
        'width': '100%',
        'toolbar_Basic': [
            ['Source', '-', 'Bold', 'Italic']
        ],
        'toolbar_YourCustomToolbarConfig': [
            {'name': 'document', 'items': ['Source', '-', 'Save', 'NewPage', 'Preview', 'Print', '-', 'Templates']},
            {'name': 'clipboard', 'items': ['Cut', 'Copy', 'Paste', 'PasteText', 'PasteFromWord', '-', 'Undo', 'Redo']},
            {'name': 'editing', 'items': ['Find', 'Replace', '-', 'SelectAll']},
            {'name': 'basicstyles',
             'items': ['Bold', 'Italic', 'Underline', 'Strike', 'Subscript', 'Superscript', '-', 'RemoveFormat']},
            '/',
            {'name': 'paragraph',
             'items': ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Blockquote', 'CreateDiv', '-',
                      'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock', '-', 'BidiLtr', 'BidiRtl']},
            {'name': 'links', 'items': ['Link', 'Unlink', 'Anchor']},
            {'name': 'insert',
             'items': ['Image', 'Table', 'HorizontalRule', 'Smiley', 'SpecialChar', 'PageBreak', 'Iframe']},
            '/',
            {'name': 'styles', 'items': ['Styles', 'Format', 'Font', 'FontSize']},
            {'name': 'colors', 'items': ['TextColor', 'BGColor']},
            {'name': 'tools', 'items': ['Maximize', 'ShowBlocks']},
        ],
        'toolbar': 'YourCustomToolbarConfig',
        'tabSpaces': 4,
        'extraPlugins': ','.join([
            'uploadimage',
            'div',
            'autolink',
            'autoembed',
            'embedsemantic',
            'autogrow',
            'widget',
            'lineutils',
            'clipboard',
            'dialog',
            'dialogui',
            'elementspath'
        ]),
    },
    'vstavka': {
        'skin': 'moono',
        'height': 300,
        'width': '100%',
        'toolbar_Basic': [
            ['Source', '-', 'Bold', 'Italic']
        ],
        'toolbar_YourCustomToolbarConfigs': [
            {'name': 'document', 'items': ['Source', 'Image', 'Html5video']},
        ],
        'toolbar': 'YourCustomToolbarConfigs',
        'tabSpaces': 4,
        'extraPlugins': ','.join([
            'uploadimage',
            'html5video',
            'div',
            'autolink',
            'autoembed',
            'embedsemantic',
            'autogrow',
            'widget',
            'lineutils',
            'clipboard',
            'dialog',
            'dialogui',
            'elementspath'
        ]),
    },
}

JAZZMIN_SETTINGS = {
    # Текст в шапке/вкладке (не путь к картинке — иначе в интерфейсе дублируется «Logo/static/...»)
    "site_title": "LukInterLab — админка",
    "site_header": "Панель управления",
    "site_brand": "LukInterLab",
    # Путь относительно STATIC (как в {% static 'img/400-crug.png' %})
    "site_logo": "img/400-crug.png",
    "site_icon": None,
    "welcome_sign": "Вход в админ-панель",
    "copyright": "lukinterlab.ru",
    # Иначе подставляется логотип как «аватар» у всех пользователей
    "user_avatar": None,
    ############
    # Top Menu #
    ############
    # Ссылки для размещения в верхнем меню
    "topmenu_links": [
        # Url that gets reversed (Permissions can be added)
        #Url-адрес, который становится обратным (можно добавить разрешения)
        {"name": "lukinterlab.ru", "url": "https://lukinterlab.ru/", "permissions": ["auth.view_user"]},
        # model admin to link to (Permissions checked against model)
        #ссылка на администратора модели (права доступа проверены для модели)
        {"model": "auth.User"},
    ],
    #############
    # Side Menu #
    #############
    # Следует ли отображать боковое меню
    "show_sidebar": True,
    # Следует ли автоматически раскрывать меню
    "navigation_expanded": True,
    # Пользовательские значки для приложений/моделей бокового меню Смотрите здесь
    #  https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
    # полный список бесплатных классов иконок версии 5.13.0
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "users.User": "fas fa-user",
        "auth.Group": "fas fa-users",
        "admin.LogEntry": "fas fa-file",
    },
    # # Значки, которые используются, если они не заданы вручную
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-arrow-circle-right",
    #################
    # Related Modal #
    #################
    # Используйте модели вместо всплывающих окон
    "related_modal_active": False,
    #############
    # UI Tweaks #
    #############
    # Относительные пути к пользовательским CSS/JS скриптам (должны присутствовать в статических файлах)
    # Раскомментируйте эту строку после создания файла bootstrap-dark.css
    # "custom_css": "css/bootstrap-dark.css",
    "custom_js": None,
    # Следует ли отображать настройщик пользовательского интерфейса на боковой панели
    "show_ui_builder": False,
    ###############
    # Change view #
    ###############
    "changeform_format": "horizontal_tabs",
    # переопределение форм изменения для каждого администратора модели
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-success",
    "accent": "accent-teal",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-info",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "slate",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# Email (SMTP)
EMAIL_BACKEND = env_str(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env_str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = env_int("EMAIL_PORT", 587) or 587
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", f"LukInterLab <noreply@lukinterlab.ru>")

# Куда слать обращения с формы / админ-уведомления (можно оставить в .env)
CONTACT_EMAIL = env_str("CONTACT_EMAIL", "Ya@LukyanovSY.ru")
ADMIN_EMAIL = env_str("ADMIN_EMAIL", "Ya@LukyanovSY.ru")

# YooKassa (пустые — оплата не настроена)
YOOKASSA_SHOP_ID = env_str("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = env_str("YOOKASSA_SECRET_KEY")

AUTHENTICATION_BACKENDS = [
    'Users.auth.TelegramBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# AI Assistant Settings
OPENAI_API_KEY = env_str("OPENAI_API_KEY")
AI_MODEL = 'gpt-4'
AI_MAX_TOKENS = 1000
AI_TEMPERATURE = 0.7

# Django-Q Configuration
# sync=True: async_task выполняется в том же процессе, что и HTTP-запрос → долгие задачи
# рвут ответ Passenger («Incomplete response»). На проде держим sync=False, воркер — qcluster.
# При необходимости синхронной отладки: DJANGO_Q_SYNC=True в .env
#
# timeout — максимальная длительность ОДНОЙ задачи (сек): генерация статьи + time.sleep между
# статьями (batch_interval). 300 с недостаточно при интервалах 5–10 мин между статьями в пачке.
# Задаётся через DJANGO_Q_TASK_TIMEOUT (по умолчанию 3600 = 1 час). При очень длинных пачках
# увеличьте в .env на сервере.
_DJANGO_Q_TASK_TIMEOUT = env_int('DJANGO_Q_TASK_TIMEOUT', 3600) or 3600
_DJANGO_Q_RETRY = env_int('DJANGO_Q_RETRY', max(600, _DJANGO_Q_TASK_TIMEOUT * 2)) or max(
    600, _DJANGO_Q_TASK_TIMEOUT * 2
)

Q_CLUSTER = {
    'name': 'LukInterLab',
    'workers': 1,  # Один воркер для SQLite (меньше конкуренции за db.sqlite3)
    'timeout': _DJANGO_Q_TASK_TIMEOUT,
    'retry': _DJANGO_Q_RETRY,
    'queue_limit': 500,
    'bulk': 10,
    'orm': 'default',
    'cache': 'diskcache',
    'diskcache_dir': BASE_DIR / 'qcache',
    'save_limit': 250,
    'sync': env_bool('DJANGO_Q_SYNC', False),
    'catch_up': True,
    'label': 'Django Q',
    'db_timeout': 30,  # Timeout для операций с БД
}

# Caching Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'lukinterlab-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    },
    'filesystem': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': BASE_DIR / 'cache',
        'OPTIONS': {
            'MAX_ENTRIES': 5000,
        }
    }
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'ALUKINTERLAB.logging_handler.SafeRotatingFileHandler',
            'filename': BASE_DIR / 'logs/django.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
            'delay': True,  # Открываем файл только при первой записи
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'ALUKINTERLAB.logging_handler.SafeRotatingFileHandler',
            'filename': BASE_DIR / 'logs/errors.log',
            'maxBytes': 1024 * 1024 * 15,
            'backupCount': 10,
            'formatter': 'verbose',
            'delay': True,  # Открываем файл только при первой записи
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'home': {
            'handlers': ['file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django_q': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
