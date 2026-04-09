from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum
from datetime import timedelta
from typing import Dict, Any
import uuid
import base64
import json
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class ChatSession(models.Model):
    """Модель для хранения сессий чата с AI-ассистентом"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Пользователь')
    session_id = models.CharField(max_length=100, unique=True, verbose_name='ID сессии')
    ip_address = models.GenericIPAddressField(verbose_name='IP адрес')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    
    # Метаданные сессии
    page_url = models.URLField(blank=True, verbose_name='URL страницы')
    referrer = models.URLField(blank=True, verbose_name='Источник перехода')
    
    # Управление диалогом
    is_admin_controlled = models.BooleanField(default=False, verbose_name='Управляется администратором', help_text='True если диалог перехвачен администратором')
    telegram_message_id = models.CharField(max_length=50, blank=True, verbose_name='ID сообщения в Telegram', help_text='ID последнего сообщения в Telegram чате')
    admin_user_id = models.CharField(max_length=50, blank=True, verbose_name='ID администратора', help_text='ID пользователя Telegram, который управляет диалогом')
    
    class Meta:
        verbose_name = 'Сессия чата'
        verbose_name_plural = 'Сессии чата'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Сессия {self.session_id[:8]}... ({self.created_at.strftime('%d.%m.%Y %H:%M')})"


class ChatMessage(models.Model):
    """Модель для хранения сообщений в чате"""
    
    MESSAGE_TYPES = [
        ('user', 'Пользователь'),
        ('assistant', 'Ассистент'),
        ('system', 'Система'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', verbose_name='Сессия')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, verbose_name='Тип сообщения')
    content = models.TextField(verbose_name='Содержание')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Время')
    
    # Дополнительные поля для AI
    tokens_used = models.IntegerField(default=0, verbose_name='Использовано токенов')
    response_time = models.FloatField(default=0, verbose_name='Время ответа (сек)')
    model_used = models.CharField(max_length=50, blank=True, verbose_name='Использованная модель')
    
    # Метаданные
    is_helpful = models.BooleanField(null=True, blank=True, verbose_name='Полезно ли сообщение')
    user_feedback = models.TextField(blank=True, verbose_name='Отзыв пользователя')
    
    class Meta:
        verbose_name = 'Сообщение чата'
        verbose_name_plural = 'Сообщения чата'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.get_message_type_display()}: {self.content[:50]}..."


class AssistantKnowledge(models.Model):
    """База знаний для AI-ассистента"""
    
    CATEGORIES = [
        ('services', 'Услуги'),
        ('pricing', 'Ценообразование'),
        ('contacts', 'Контакты'),
        ('faq', 'Часто задаваемые вопросы'),
        ('company', 'О компании'),
        ('technical', 'Техническая поддержка'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    category = models.CharField(max_length=20, choices=CATEGORIES, verbose_name='Категория')
    content = models.TextField(verbose_name='Содержание')
    keywords = models.TextField(help_text='Ключевые слова через запятую', verbose_name='Ключевые слова')
    
    # SEO и метаданные
    priority = models.IntegerField(default=1, verbose_name='Приоритет')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'База знаний'
        verbose_name_plural = 'База знаний'
        ordering = ['-priority', 'title']
    
    def __str__(self):
        return self.title


class AssistantSettings(models.Model):
    """Настройки AI-ассистента"""
    
    # Основные настройки
    is_enabled = models.BooleanField(default=True, verbose_name='Включен')
    welcome_message = models.TextField(
        default='Привет! Я виртуальный ассистент LukInterLab. Чем могу помочь?',
        verbose_name='Приветственное сообщение'
    )
    
    # AI настройки
    ai_provider = models.CharField(
        max_length=20,
        choices=[('gigachat', 'GigaChat'), ('openai', 'OpenAI')],
        default='gigachat',
        verbose_name='AI провайдер'
    )
    ai_model = models.CharField(
        max_length=50, 
        default='GigaChat', 
        verbose_name='AI модель',
        help_text='Для GigaChat: GigaChat, GigaChat-Pro, GigaChat-Max, GigaChat-Plus и др.'
    )
    max_tokens = models.IntegerField(default=1000, verbose_name='Максимум токенов')
    temperature = models.FloatField(default=0.7, verbose_name='Температура')
    
    # GigaChat настройки
    gigachat_authorization_key = models.TextField(
        blank=True, 
        verbose_name='GigaChat Authorization Key',
        help_text='Ключ авторизации для GigaChat API (хранится в зашифрованном виде). Получите в личном кабинете Studio.'
    )
    gigachat_scope = models.CharField(
        max_length=100,
        default='GIGACHAT_API_PERS',
        choices=[
            ('GIGACHAT_API_PERS', 'Для физических лиц'),
            ('GIGACHAT_API_B2B', 'Для ИП и юр.лиц (платные пакеты)'),
            ('GIGACHAT_API_CORP', 'Для ИП и юр.лиц (pay-as-you-go)')
        ],
        help_text='Scope для доступа к GigaChat API',
        verbose_name='GigaChat Scope'
    )
    gigachat_verify_ssl_certs = models.BooleanField(
        default=False,  # Отключено по умолчанию для избежания ошибок SSL
        verbose_name='Проверять SSL сертификаты',
        help_text='Рекомендуется включить для продакшена. Можно переопределить через GIGACHAT_VERIFY_SSL в settings.py'
    )
    
    def get_gigachat_verify_ssl(self):
        """Получить значение проверки SSL с fallback на settings.py"""
        # Проверяем settings.py напрямую
        from django.conf import settings
        env_verify = getattr(settings, 'GIGACHAT_VERIFY_SSL', None)
        if env_verify is not None:
            return bool(env_verify)
        
        # Используем значение из БД
        return self.gigachat_verify_ssl_certs
    
    # Обратная совместимость (deprecated)
    gigachat_client_id = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name='GigaChat Client ID (deprecated)',
        help_text='Устаревшее поле. Используйте Authorization Key.'
    )
    gigachat_client_secret = models.TextField(
        blank=True, 
        verbose_name='GigaChat Client Secret (deprecated)',
        help_text='Устаревшее поле. Используйте Authorization Key.'
    )
    
    # OpenAI настройки (для обратной совместимости)
    openai_api_key = models.TextField(
        blank=True, 
        verbose_name='OpenAI API Key',
        help_text='API ключ OpenAI (хранится в зашифрованном виде)'
    )
    
    # Поведение
    auto_start = models.BooleanField(default=False, verbose_name='Автозапуск')
    auto_start_delay = models.IntegerField(default=3, verbose_name='Задержка автозапуска (секунды)', help_text='Через сколько секунд после загрузки страницы показать приветствие')
    show_typing_indicator = models.BooleanField(default=True, verbose_name='Показывать индикатор печати')
    enable_voice = models.BooleanField(default=False, verbose_name='Голосовое управление')
    
    # Персонализация
    assistant_name = models.CharField(max_length=50, default='Сергей', verbose_name='Имя ассистента')
    welcome_message_template = models.TextField(
        default='Доброго дня! Чем можем быть полезны? Я Ассистент {name}, готов ответить на Ваши вопросы. Сейчас действует скидка 30% на сайты с интеграцией AI. Интересно?',
        verbose_name='Шаблон приветственного сообщения',
        help_text='Используйте {name} для имени ассистента, {username} для имени пользователя'
    )
    use_personalized_greeting = models.BooleanField(default=True, verbose_name='Персонализированное приветствие', help_text='Использовать имя пользователя в приветствии')
    
    # Дизайн
    theme_color = models.CharField(max_length=7, default='#007bff', verbose_name='Цвет темы')
    position = models.CharField(
        max_length=20,
        choices=[('bottom-right', 'Правый нижний'), ('bottom-left', 'Левый нижний')],
        default='bottom-right',
        verbose_name='Позиция'
    )
    
    # Telegram интеграция
    telegram_bot_token = models.TextField(
        blank=True,
        verbose_name='Telegram Bot Token',
        help_text='Токен бота для уведомлений администратора (хранится в зашифрованном виде)'
    )
    telegram_admin_chat_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Telegram Chat ID администратора',
        help_text='ID чата администратора в Telegram'
    )
    enable_telegram_notifications = models.BooleanField(
        default=False,
        verbose_name='Включить уведомления в Telegram',
        help_text='Отправлять уведомления администратору о новых сообщениях'
    )
    enable_admin_takeover = models.BooleanField(
        default=False,
        verbose_name='Разрешить перехват диалога администратором',
        help_text='Позволить администратору перехватывать диалог через Telegram'
    )
    telegram_channel_autopost_enabled = models.BooleanField(
        default=True,
        verbose_name='Автопост статей в Telegram-канал',
        help_text='Анонсы опубликованных статей в Telegram-канал. Выключите при блокировках или сбоях API; VK не затрагивается.',
    )
    
    # Ограничения
    max_messages_per_session = models.IntegerField(default=50, verbose_name='Максимум сообщений в сессии')
    session_timeout = models.IntegerField(default=30, verbose_name='Таймаут сессии (минуты)')
    
    # Лимиты токенов подписки (JSON поле для гибкой настройки)
    # Формат: {"GigaChat-2-Max": 50000, "GigaChat-2-Pro": 44400, "GigaChat-2-Lite": 50000}
    subscription_token_limits = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Лимиты токенов подписки',
        help_text='JSON объект с лимитами токенов для каждой модели. Пример: {"GigaChat-2-Max": 50000, "GigaChat-2-Pro": 44400}. Если пусто, используются значения по умолчанию из TOKEN_LIMITS.'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'Настройки ассистента'
        verbose_name_plural = 'Настройки ассистента'
    
    def __str__(self):
        return 'Настройки AI-ассистента'
    
    def _get_encryption_key(self):
        """Получить ключ шифрования"""
        secret_key = getattr(settings, 'SECRET_KEY', '')
        if not secret_key:
            raise ValueError("SECRET_KEY не настроен в settings.py")
        
        # Используем SECRET_KEY для генерации ключа шифрования
        key = base64.urlsafe_b64encode(secret_key.encode()[:32].ljust(32, b'0'))
        return key
    
    def _encrypt_data(self, data):
        """Зашифровать данные"""
        if not data:
            return ''
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(data.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception:
            return data  # Возвращаем исходные данные в случае ошибки
    
    def _decrypt_data(self, encrypted_data):
        """Расшифровать данные"""
        if not encrypted_data:
            return ''
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            decoded_data = base64.b64decode(encrypted_data.encode())
            decrypted_data = fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception:
            return encrypted_data  # Возвращаем исходные данные в случае ошибки
    
    def get_gigachat_authorization_key(self):
        """Получить расшифрованный Authorization Key"""
        # Сначала пробуем получить из settings.py (приоритет)
        from django.conf import settings
        env_key = getattr(settings, 'GIGACHAT_AUTHORIZATION_KEY', '')
        if env_key and env_key.strip():
            return env_key.strip()
        
        # Fallback на БД (зашифрованный)
        if self.gigachat_authorization_key:
            db_key = self._decrypt_data(self.gigachat_authorization_key)
            if db_key and db_key.strip():
                # Если расшифровка не удалась и вернулся исходный (зашифрованный), пробуем использовать как есть
                # Это может быть если ключ не был зашифрован при сохранении
                if db_key != self.gigachat_authorization_key:
                    return db_key.strip()
                # Если это оригинальный зашифрованный ключ (слишком длинный), возвращаем пустую строку
                if len(db_key) > 150:  # Нормальный ключ не должен быть длиннее 150 символов
                    return ''
                return db_key.strip()
        
        return ''
    
    def set_gigachat_authorization_key(self, auth_key):
        """Установить зашифрованный Authorization Key"""
        self.gigachat_authorization_key = self._encrypt_data(auth_key)
    
    def get_gigachat_client_secret(self):
        """Получить расшифрованный Client Secret (deprecated)"""
        # Сначала пробуем получить из БД (зашифрованный)
        db_secret = self._decrypt_data(self.gigachat_client_secret)
        if db_secret and db_secret.strip():
            return db_secret
        
        # Fallback на переменные окружения
        from django.conf import settings
        env_secret = getattr(settings, 'GIGACHAT_CLIENT_SECRET', '')
        if env_secret and env_secret.strip():
            return env_secret
        
        return ''
    
    def set_gigachat_client_secret(self, secret):
        """Установить зашифрованный Client Secret (deprecated)"""
        self.gigachat_client_secret = self._encrypt_data(secret)
    
    def get_gigachat_client_id(self):
        """Получить Client ID (deprecated) с fallback на переменные окружения"""
        # Сначала пробуем получить из БД
        if self.gigachat_client_id and self.gigachat_client_id.strip():
            return self.gigachat_client_id
        
        # Fallback на переменные окружения
        from django.conf import settings
        env_client_id = getattr(settings, 'GIGACHAT_CLIENT_ID', '')
        if env_client_id and env_client_id.strip():
            return env_client_id
        
        return ''
    
    def get_gigachat_scope(self):
        """Получить Scope с fallback на переменные окружения"""
        # Сначала пробуем получить из БД
        if self.gigachat_scope and self.gigachat_scope.strip():
            return self.gigachat_scope
        
        # Fallback на переменные окружения
        from django.conf import settings
        env_scope = getattr(settings, 'GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')
        if env_scope and env_scope.strip():
            return env_scope
        
        return 'GIGACHAT_API_PERS'
    
    def get_openai_api_key(self):
        """Получить расшифрованный OpenAI API Key"""
        return self._decrypt_data(self.openai_api_key)
    
    def set_openai_api_key(self, api_key):
        """Установить зашифрованный OpenAI API Key"""
        self.openai_api_key = self._encrypt_data(api_key)
    
    def get_telegram_bot_token(self):
        """Получить расшифрованный Telegram Bot Token"""
        return self._decrypt_data(self.telegram_bot_token)
    
    def set_telegram_bot_token(self, token):
        """Установить зашифрованный Telegram Bot Token"""
        self.telegram_bot_token = self._encrypt_data(token)
    
    def save(self, *args, **kwargs):
        # Убеждаемся, что есть только одна запись настроек
        if not self.pk and AssistantSettings.objects.exists():
            return
        super().save(*args, **kwargs)


class ChatAnalytics(models.Model):
    """Аналитика чата"""
    
    date = models.DateField(verbose_name='Дата')
    total_sessions = models.IntegerField(default=0, verbose_name='Всего сессий')
    total_messages = models.IntegerField(default=0, verbose_name='Всего сообщений')
    unique_users = models.IntegerField(default=0, verbose_name='Уникальных пользователей')
    avg_response_time = models.FloatField(default=0, verbose_name='Среднее время ответа')
    satisfaction_rate = models.FloatField(default=0, verbose_name='Процент удовлетворенности')
    
    class Meta:
        verbose_name = 'Аналитика чата'
        verbose_name_plural = 'Аналитика чата'
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Аналитика за {self.date}"


class PromptTemplate(models.Model):
    """Шаблон промпта для генерации статей"""
    
    name = models.CharField(max_length=200, verbose_name='Название шаблона')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    
    # Промпты для каждого элемента статьи
    title_prompt = models.TextField(
        blank=True,
        verbose_name='Промпт для заголовка',
        help_text='Промпт для генерации заголовка статьи. Используйте {topic}, {category} для подстановки значений.'
    )
    # description_prompt удалено - описание генерируется автоматически из первых 200 слов контента
    content_prompt = models.TextField(
        blank=True,
        verbose_name='Промпт для основного контента',
        help_text='Промпт для генерации основного текста статьи. Используйте {topic}, {category}, {keywords} для подстановки.'
    )
    image_prompt = models.TextField(
        blank=True,
        verbose_name='Промпт для генерации изображения (GigaChat-Pro)',
        help_text='Промпт для генерации изображения через GigaChat-Pro. Используйте {title}, {topic} для подстановки.'
    )
    
    # Дополнительные настройки
    default_category = models.ForeignKey(
        'Blog.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Категория по умолчанию',
        help_text='Категория, которая будет использоваться, если не указана в расписании'
    )
    default_tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Теги по умолчанию',
        help_text='Теги через запятую, которые будут добавлены к статье'
    )
    news_search_suffix = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Уточнение поиска новостей',
        help_text=(
            'Добавляется к категории и ключевым словам при поиске новостей '
            '(например: «события сегодня», «обзор»). Оставьте пустым — только глобальные настройки в дашборде «Поиск новостей».'
        ),
    )
    
    # Режимы генерации контента
    CONTENT_GENERATION_CHOICES = [
        ('generate', 'Генерация основного текста статьи на основании промпта'),
        ('parse_and_generate', 'Поиск и парсинг 200 слов из интернета + генерация основного текста'),
        ('full_parse', 'Полный парсинг основного текста статьи в полном объёме как у источника'),
    ]
    
    content_generation_mode = models.CharField(
        max_length=20,
        choices=CONTENT_GENERATION_CHOICES,
        default='generate',
        verbose_name='Режим генерации контента',
        help_text='Способ получения основного контента статьи'
    )
    
    # Режимы генерации изображения
    IMAGE_GENERATION_CHOICES = [
        ('generate', 'Генерация на основании промпта из image_prompt'),
        ('search_and_parse', 'Искать и парсить изображение на основании запроса'),
    ]
    
    image_generation_mode = models.CharField(
        max_length=20,
        choices=IMAGE_GENERATION_CHOICES,
        default='generate',
        verbose_name='Режим генерации изображения',
        help_text='Способ получения изображения для статьи'
    )
    
    image_search_criteria = models.TextField(
        blank=True,
        verbose_name='Критерий поиска изображения',
        help_text='Критерии для поиска и парсинга изображения (используется при режиме "Искать и парсить")'
    )
    
    # Выключатели генерации элементов (для тестирования и гибкой настройки)
    generate_title = models.BooleanField(
        default=True,
        verbose_name='Генерировать заголовок',
        help_text='Включить генерацию заголовка статьи'
    )
    generate_content = models.BooleanField(
        default=True,
        verbose_name='Генерировать основной текст',
        help_text='Включить генерацию основного текста статьи'
    )
    generate_image = models.BooleanField(
        default=True,
        verbose_name='Генерировать изображение',
        help_text='Включить генерацию/поиск изображения для статьи'
    )
    
    # Дополнительная секция (универсальный блок после основного текста)
    generate_additional_section = models.BooleanField(
        default=False,
        verbose_name='Генерировать дополнительную секцию',
        help_text='Включить генерацию дополнительного блока после основного текста (FAQ, слоганы, TO-DO, таблица содержания и т.д.)'
    )
    additional_section_prompt = models.TextField(
        blank=True,
        verbose_name='Промпт для дополнительной секции',
        help_text='Промпт для генерации дополнительного блока. Используйте {title}, {content}, {category}, {keywords} для подстановки. Примеры: FAQ блок, мотивационные слоганы, TO-DO задачи, таблица содержания. Результат должен быть в формате HTML.'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Создал',
        related_name='created_prompt_templates'
    )
    
    class Meta:
        verbose_name = 'Шаблон промпта'
        verbose_name_plural = 'Шаблоны промптов'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def format_prompt(self, prompt_text: str, context: dict) -> str:
        """Форматирование промпта с подстановкой значений из контекста"""
        if not prompt_text or not prompt_text.strip():
            logger.warning("Попытка форматирования пустого промпта")
            return prompt_text
        
        try:
            # Используем безопасное форматирование через регулярные выражения
            # Это позволяет обрабатывать переменные с числовыми именами (например {456})
            import re
            
            def replace_var(match):
                var_name = match.group(1)
                if var_name in context:
                    value = context[var_name]
                    # Преобразуем значение в строку безопасным способом
                    return str(value) if value is not None else ''
                else:
                    # Если переменная не найдена, оставляем как есть и логируем
                    logger.warning(f"Переменная {{{var_name}}} не найдена в контексте")
                    return match.group(0)  # Возвращаем оригинальную строку {var_name}
            
            # Паттерн для поиска {variable} или {456} (любые символы внутри фигурных скобок)
            pattern = r'\{([^}]+)\}'
            result = re.sub(pattern, replace_var, prompt_text)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка форматирования промпта: {e}", exc_info=True)
            return prompt_text
    
    def extract_variables(self, include_system=False) -> dict:
        """
        Извлечение всех переменных из промптов шаблона
        Возвращает словарь с разделением на системные и пользовательские переменные
        
        Args:
            include_system: Если True, включает системные переменные (topic, category, keywords и т.д.)
            
        Returns:
            dict с ключами:
            - 'all': список всех переменных
            - 'system': список системных переменных (если include_system=True)
            - 'custom': список пользовательских переменных
        """
        import re
        variables = set()
        
        # Собираем все промпты
        prompts = [
            self.title_prompt or '',
            self.content_prompt or '',
            self.image_prompt or '',
            self.additional_section_prompt or '',
        ]
        
        # Ищем все переменные в формате {variable}
        # Используем более гибкий паттерн, который ловит переменные даже с опечатками
        pattern = r'\{(\w+)\}'
        for i, prompt in enumerate(prompts):
            if prompt:
                matches = re.findall(pattern, prompt)
                if matches:
                    logger.debug(f"Найдены переменные в промпте {i}: {matches}")
                variables.update(matches)
        
        # Определяем системные переменные
        # Базовые системные переменные
        system_vars = {
            'topic', 'category', 'keywords', 'title', 'content',
            'parsed_news_content', 'parsed_content_200_words',
            'news_title', 'news_url', 'news_source',
        }
        
        # Разделяем на системные и пользовательские
        all_variables = sorted(list(variables))
        system_variables = sorted([v for v in all_variables if v in system_vars])
        custom_variables = sorted([v for v in all_variables if v not in system_vars])
        
        if include_system:
            return {
                'all': all_variables,
                'system': system_variables,
                'custom': custom_variables
            }
        else:
            return {
                'all': custom_variables,
                'system': [],
                'custom': custom_variables
            }


class AISchedule(models.Model):
    """Расписание для автоматической генерации статей"""
    
    name = models.CharField(max_length=200, verbose_name='Название расписания')
    prompt_template = models.ForeignKey(
        PromptTemplate,
        on_delete=models.CASCADE,
        verbose_name='Шаблон промпта',
        help_text='Шаблон промпта, который будет использоваться для генерации'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    
    # Расписание: первый запуск + шаг по интервалу (не календарный CRON)
    first_run_at = models.DateTimeField(
        verbose_name='Первый запуск (дата и время)',
        help_text='От этой точки отсчитываются повторы: следующие запуски через заданный интервал.',
    )
    interval_hours = models.PositiveIntegerField(
        default=24,
        verbose_name='Интервал — часы',
        help_text='Например 24 и 0 минут — один запуск раз в сутки от счёта первого запуска.',
    )
    interval_minutes = models.PositiveIntegerField(
        default=0,
        verbose_name='Интервал — минуты',
        help_text='Дополнительно к часам (0–59). Минимум 1 минута суммарно с часами.',
    )
    max_schedule_runs = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Макс. число запусков',
        help_text='Пусто = без ограничения. После достижения лимита расписание выключается.',
    )
    completed_schedule_runs = models.PositiveIntegerField(
        default=0,
        verbose_name='Выполнено запусков',
        help_text='Счётчик завершённых запусков (пачек генерации), увеличивается после каждого успешного цикла.',
    )
    batch_interval = models.PositiveIntegerField(
        default=0,
        verbose_name='Интервал между статьями в пачке',
        help_text='Интервал в минутах между статьями в одной пачке (0 — без паузы; используется в генераторе при articles_per_run > 1)',
    )
    
    # Параметры генерации
    articles_per_run = models.IntegerField(
        default=1,
        verbose_name='Статей за раз',
        help_text='Количество статей, которые будут сгенерированы за один запуск'
    )
    category = models.ForeignKey(
        'Blog.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Категория',
        help_text='Категория для статей. Если не указана, используется из шаблона.'
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Теги',
        help_text=(
            'Через запятую: теги, которые точно попадут в пост. '
            'Если пусто — берутся из шаблона промпта (default_tags) или из ключа tags в JSON ниже. '
            'Отдельно модель добавляет 3–4 тега по смыслу текста статьи.'
        ),
    )
    keywords = models.TextField(
        blank=True,
        verbose_name='Ключевые слова',
        help_text=(
            'Через запятую: тема запроса при поиске новостей/источников и контекст промпта. '
            'Если пусто, для поиска может использоваться название категории. '
            'Для шаблонов без шага поиска влияние обычно слабее.'
        ),
    )
    
    # Контекст для промптов (JSON)
    context_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Дополнительные данные',
        help_text=(
            'JSON с дополнительными переменными для промптов (например topic, tone). '
            'Сливается с контекстом генерации: ключи из этого поля дополняют шаблон; '
            'необязательно, если всё задано в шаблоне.'
        ),
    )
    
    # Статистика
    last_run = models.DateTimeField(null=True, blank=True, verbose_name='Последний запуск')
    next_run = models.DateTimeField(null=True, blank=True, verbose_name='Следующий запуск')
    total_generated = models.IntegerField(default=0, verbose_name='Всего сгенерировано')
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Создал',
        related_name='created_ai_schedules'
    )
    
    class Meta:
        verbose_name = 'Расписание генерации'
        verbose_name_plural = 'Расписания генерации'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_interval_summary()})"
    
    def get_interval_timedelta(self) -> timedelta:
        return timedelta(hours=self.interval_hours or 0, minutes=self.interval_minutes or 0)
    
    def get_interval_summary(self) -> str:
        parts = []
        if self.interval_hours:
            parts.append(f'{self.interval_hours} ч')
        if self.interval_minutes:
            parts.append(f'{self.interval_minutes} мин')
        base = ' '.join(parts) if parts else '0'
        return f'каждые {base}'
    
    def get_runs_limit_display(self) -> str:
        if self.max_schedule_runs is None:
            return f'{self.completed_schedule_runs} (∞)'
        return f'{self.completed_schedule_runs} / {self.max_schedule_runs}'
    
    def sync_next_run(self):
        """Ближайший запуск >= текущего момента (для сохранения формы)."""
        self.sync_next_run_after(timezone.now())

    def sync_next_run_after(self, after_ts):
        """Следующий слот строго после after_ts по сетке first_run_at + n·interval."""
        delta = self.get_interval_timedelta()
        if delta.total_seconds() < 60:
            delta = timedelta(minutes=1)
        anchor = self.first_run_at
        if anchor is None:
            anchor = after_ts
        elif timezone.is_naive(anchor):
            anchor = timezone.make_aware(anchor, timezone.get_current_timezone())
        t = anchor
        if t <= after_ts:
            # Масштабируемый прыжок вперёд, если t сильно отстаёт от after_ts.
            # (after_ts - t) // delta в секундах
            diff_secs = (after_ts - t).total_seconds()
            delta_secs = delta.total_seconds()
            steps = int(diff_secs // delta_secs)
            t += delta * steps
            # Мини-цикл для точного попадания на следующий слот строго ПОСЛЕ after_ts
            while t <= after_ts:
                t += delta
        self.next_run = t
    


class AIGeneratedArticle(models.Model):
    """История генерации статей через AI"""
    
    schedule = models.ForeignKey(
        AISchedule,
        on_delete=models.CASCADE,
        related_name='generated_articles',
        verbose_name='Расписание',
        null=True,
        blank=True
    )
    prompt_template = models.ForeignKey(
        PromptTemplate,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Использованный шаблон'
    )
    post = models.ForeignKey(
        'Blog.Post',
        on_delete=models.CASCADE,
        related_name='ai_generated',
        verbose_name='Статья'
    )
    
    # Данные генерации
    generated_title = models.TextField(verbose_name='Сгенерированный заголовок')
    generated_description = models.TextField(blank=True, verbose_name='Сгенерированное описание')
    generated_content = models.TextField(verbose_name='Сгенерированный контент')
    generated_image_prompt = models.TextField(blank=True, verbose_name='Промпт для изображения')
    
    # Промпты, которые использовались
    title_prompt_used = models.TextField(verbose_name='Использованный промпт для заголовка')
    description_prompt_used = models.TextField(blank=True, verbose_name='Использованный промпт для описания')
    content_prompt_used = models.TextField(verbose_name='Использованный промпт для контента')
    image_prompt_used = models.TextField(blank=True, verbose_name='Использованный промпт для изображения')
    
    # Ответы от AI
    ai_title_response = models.TextField(blank=True, verbose_name='Ответ AI для заголовка')
    ai_description_response = models.TextField(blank=True, verbose_name='Ответ AI для описания')
    ai_content_response = models.TextField(blank=True, verbose_name='Ответ AI для контента')
    ai_image_response = models.TextField(blank=True, verbose_name='Ответ AI для изображения')
    
    # Контекст генерации
    context_data = models.JSONField(default=dict, blank=True, verbose_name='Контекст генерации')
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    generation_time = models.FloatField(null=True, blank=True, verbose_name='Время генерации (сек)')
    tokens_used = models.IntegerField(default=0, verbose_name='Использовано токенов')
    
    class Meta:
        verbose_name = 'Сгенерированная статья'
        verbose_name_plural = 'Сгенерированные статьи'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Статья от {self.created_at.strftime('%d.%m.%Y %H:%M')} - {self.post.title[:50]}"


class TokenUsage(models.Model):
    """Мониторинг использования токенов GigaChat API по дням и моделям"""
    
    date = models.DateField(verbose_name='Дата', default=timezone.now)
    model = models.CharField(max_length=50, verbose_name='Модель')
    prompt_tokens = models.IntegerField(default=0, verbose_name='Токены промпта')
    completion_tokens = models.IntegerField(default=0, verbose_name='Токены ответа')
    total_tokens = models.IntegerField(default=0, verbose_name='Всего токенов')
    
    # Стоимость (при подписке = 0)
    cost = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=0, 
        verbose_name='Стоимость (руб)',
        help_text='При подписке стоимость = 0'
    )
    
    # Метаданные
    requests_count = models.IntegerField(default=0, verbose_name='Количество запросов')
    
    # Лимиты токенов (из подписки/пакетов)
    # Обновлено на основе актуальных тарифов GigaChat 2 (2025)
    # Примечание: реальные лимиты получаются из API /balance, здесь - fallback значения
    # Для подписок (subscription) лимиты могут быть меньше, чем для пакетов
    TOKEN_LIMITS = {
        # Статьи: фиксированные имена в коде (см. gigachat_article_models)
        'GigaChat': 50_000,
        # Лимиты для подписки Freemium (по умолчанию)
        'GigaChat-2-Lite': 50_000,  # Freemium: 50,000 токенов
        'GigaChat-2-Pro': 44_400,  # Freemium: 44,400 токенов (примерно)
        'GigaChat-2-Max': 50_000,  # Freemium: 50,000 токенов
        'Embeddings': 10_000_000,  # Пакет 10M токенов за 400 ₽
        'EmbeddingsGigaR': 10_000_000,  # Пакет 10M токенов за 400 ₽
        # Обратная совместимость со старыми названиями
        'GigaChat-Lite': 50_000,
        'GigaChat-Pro': 44_400,
        'GigaChat-Max': 50_000,
        # Старые значения для пакетов (если используются пакеты, а не подписка)
        'GigaChat-2-Lite-Package': 5_000_000,  # Пакет 5M токенов за 1,000 ₽
        'GigaChat-2-Pro-Package': 1_000_000,  # Пакет 1M токенов за 1,500 ₽
        'GigaChat-2-Max-Package': 1_000_000,  # Пакет 1M токенов за 1,950 ₽
    }
    
    # Тарифы для расчета стоимости (руб за токен)
    # Обновлено на основе актуальных тарифов GigaChat 2 (2025)
    TOKEN_RATES = {
        'GigaChat': 0.0002,
        'GigaChat-2-Lite': 0.0002,  # 1,000 ₽ / 5,000,000 токенов (или 5,820 ₽ / 30,000,000 = 0.000194)
        'GigaChat-2-Pro': 0.0015,  # 1,500 ₽ / 1,000,000 токенов
        'GigaChat-2-Max': 0.00195,  # 1,950 ₽ / 1,000,000 токенов
        'Embeddings': 0.00004,  # 400 ₽ / 10,000,000 токенов
        'EmbeddingsGigaR': 0.00004,  # 400 ₽ / 10,000,000 токенов
        # Обратная совместимость
        'GigaChat-Lite': 0.0002,
        'GigaChat-Pro': 0.0015,
        'GigaChat-Max': 0.00195,
    }
    
    # Пакетные тарифы (для информации)
    PACKAGE_INFO = {
        'GigaChat-2-Lite': [
            {
                'tokens': 5_000_000,
                'price': 1_000,
                'price_per_token': 0.0002,
                'period': '12 месяцев',
            },
            {
                'tokens': 30_000_000,
                'price': 5_820,
                'price_per_token': 0.000194,
                'period': '12 месяцев',
            },
        ],
        'GigaChat-2-Pro': [
            {
                'tokens': 1_000_000,
                'price': 1_500,
                'price_per_token': 0.0015,
                'period': '12 месяцев',
            },
            {
                'tokens': 5_000_000,
                'price': 7_275,
                'price_per_token': 0.001455,
                'period': '12 месяцев',
            },
        ],
        'GigaChat-2-Max': [
            {
                'tokens': 1_000_000,
                'price': 1_950,
                'price_per_token': 0.00195,
                'period': '12 месяцев',
            },
            {
                'tokens': 4_000_000,
                'price': 7_566,
                'price_per_token': 0.0018915,
                'period': '12 месяцев',
            },
        ],
        'Embeddings': [
            {
                'tokens': 10_000_000,
                'price': 400,
                'price_per_token': 0.00004,
                'period': '12 месяцев',
            },
        ],
    }
    
    class Meta:
        verbose_name = 'Использование токенов'
        verbose_name_plural = 'Использование токенов'
        unique_together = ['date', 'model']
        ordering = ['-date', 'model']
        indexes = [
            models.Index(fields=['-date', 'model']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.date} - {self.model}: {self.total_tokens} токенов"
    
    @classmethod
    def record_usage(cls, model: str, usage_data: dict, date=None):
        """
        Записать использование токенов
        
        Args:
            model: Название модели
            usage_data: Словарь с ключами prompt_tokens, completion_tokens, total_tokens
            date: Дата (по умолчанию сегодня)
        """
        if date is None:
            date = timezone.now().date()
        
        try:
            token_usage, created = cls.objects.get_or_create(
                date=date,
                model=model,
                defaults={
                    'prompt_tokens': usage_data.get('prompt_tokens', 0),
                    'completion_tokens': usage_data.get('completion_tokens', 0),
                    'total_tokens': usage_data.get('total_tokens', 0),
                    'requests_count': 1,
                }
            )
            
            if not created:
                # Обновляем существующую запись
                token_usage.prompt_tokens += usage_data.get('prompt_tokens', 0)
                token_usage.completion_tokens += usage_data.get('completion_tokens', 0)
                token_usage.total_tokens += usage_data.get('total_tokens', 0)
                token_usage.requests_count += 1
                token_usage.save()
            
            # Рассчитываем стоимость на основе актуальных тарифов
            # Если используется подписка, стоимость = 0
            # Если пакетная оплата, рассчитываем по тарифам
            # По умолчанию считаем, что используется подписка (стоимость = 0)
            # Для расчета стоимости пакетной оплаты раскомментировать:
            # token_usage.cost = cls._calculate_cost(model, token_usage.total_tokens)
            token_usage.cost = 0.0  # При подписке стоимость = 0
            token_usage.save(update_fields=['cost'])
            
            return token_usage
            
        except Exception as e:
            logger.error(f"Ошибка записи использования токенов: {str(e)}")
            return None
    
    @staticmethod
    def _calculate_cost(model: str, total_tokens: int) -> float:
        """
        Рассчитать стоимость использования токенов
        
        Тарифы на основе официальных цен GigaChat (2025):
        - Lite: 30,000,000 токенов за 5,820 ₽/год = 0.000194 ₽/токен
        - Pro: 1,000,000 токенов за 1,500 ₽/год = 0.0015 ₽/токен
        - Max: 1,000,000 токенов за 1,950 ₽/год = 0.00195 ₽/токен
        
        При использовании подписки стоимость = 0 (токены включены)
        При пакетной оплате используется расчет на основе тарифов
        """
        # При подписке стоимость = 0 (токены включены в подписку)
        # Если используется пакетная оплата, рассчитываем стоимость
        
        # Тарифы на основе официальных цен GigaChat 2 (2025) (руб за токен)
        rates = {
            'GigaChat-2-Lite': 0.0002,  # 1,000 ₽ / 5,000,000 токенов
            'GigaChat-2-Pro': 0.0015,  # 1,500 ₽ / 1,000,000 токенов
            'GigaChat-2-Max': 0.00195,  # 1,950 ₽ / 1,000,000 токенов
            'Embeddings': 0.00004,  # 400 ₽ / 10,000,000 токенов
            'EmbeddingsGigaR': 0.00004,  # 400 ₽ / 10,000,000 токенов
            # Обратная совместимость
            'GigaChat-Lite': 0.0002,
            'GigaChat-Pro': 0.0015,
            'GigaChat-Max': 0.00195,
        }
        
        rate = rates.get(model, 0.0002)  # По умолчанию тариф Lite
        return float(total_tokens * rate)
    
    @classmethod
    def get_statistics(cls, days=30):
        """Получить статистику за последние N дней"""
        from datetime import timedelta
        date_from = timezone.now().date() - timedelta(days=days)
        
        stats = cls.objects.filter(date__gte=date_from).aggregate(
            total_tokens=Sum('total_tokens'),
            total_requests=Sum('requests_count'),
            total_cost=Sum('cost'),
        )
        
        # Статистика по моделям
        by_model = cls.objects.filter(date__gte=date_from).values('model').annotate(
            tokens=Sum('total_tokens'),
            requests=Sum('requests_count'),
            cost=Sum('cost'),
        ).order_by('-tokens')
        
        # Добавляем информацию о лимитах и использовании
        for model_stat in by_model:
            model_name = model_stat['model']
            limit = cls.TOKEN_LIMITS.get(model_name, 50000)
            used = model_stat['tokens'] or 0
            model_stat['limit'] = limit
            model_stat['used_percent'] = (used / limit * 100) if limit > 0 else 0
            model_stat['remaining'] = max(0, limit - used)
            model_stat['is_near_limit'] = model_stat['used_percent'] > 80
        
        return {
            'total': stats,
            'by_model': list(by_model),
        }
    
    @classmethod
    def check_limits(cls, model: str) -> Dict[str, Any]:
        """
        Проверить использование токенов для модели
        
        Returns:
            Dict с информацией о лимитах и использовании
        """
        # Получаем лимит из настроек подписки или fallback на TOKEN_LIMITS
        limit = cls.get_limit_for_model(model)
        
        # Использование за текущий период (с начала подписки)
        # Для упрощения считаем использование за последние 30 дней
        stats = cls.get_statistics(days=30)
        
        model_stats = next(
            (m for m in stats['by_model'] if m['model'] == model),
            {'tokens': 0}
        )
        
        used = model_stats.get('tokens', 0)
        used_percent = (used / limit * 100) if limit > 0 else 0
        
        return {
            'model': model,
            'limit': limit,
            'used': used,
            'remaining': max(0, limit - used),
            'used_percent': used_percent,
            'is_near_limit': used_percent > 80,
            'is_critical': used_percent > 95,
        }
    
    @classmethod
    def get_limit_for_model(cls, model: str) -> int:
        """
        Получить лимит токенов для модели
        
        Приоритет:
        1. Лимит из настроек подписки (AssistantSettings.subscription_token_limits)
        2. Лимит из TOKEN_LIMITS
        3. Значение по умолчанию (50000)
        """
        # Пробуем получить из настроек подписки
        try:
            # Используем прямой импорт для избежания циклических зависимостей
            from django.apps import apps
            AssistantSettings = apps.get_model('Assistant', 'AssistantSettings')
            settings = AssistantSettings.objects.first()
            if settings and settings.subscription_token_limits:
                subscription_limits = settings.subscription_token_limits
                if isinstance(subscription_limits, dict):
                    # Пробуем найти точное совпадение
                    if model in subscription_limits:
                        limit = subscription_limits[model]
                        if isinstance(limit, (int, float)) and limit > 0:
                            return int(limit)
                    
                    # Пробуем варианты названий моделей
                    model_variants = {
                        'GigaChat-2-Lite': ['GigaChat-2-Lite', 'GigaChat-Lite', 'GigaChat'],
                        'GigaChat-2-Pro': ['GigaChat-2-Pro', 'GigaChat-Pro'],
                        'GigaChat-2-Max': ['GigaChat-2-Max', 'GigaChat-Max'],
                    }
                    
                    for base_model, variants in model_variants.items():
                        if model in variants:
                            for variant in variants:
                                if variant in subscription_limits:
                                    limit = subscription_limits[variant]
                                    if isinstance(limit, (int, float)) and limit > 0:
                                        return int(limit)
        except Exception as e:
            logger.warning(f"Ошибка получения лимита из настроек подписки: {str(e)}")
        
        # Fallback на TOKEN_LIMITS
        return cls.TOKEN_LIMITS.get(model, 50000)
    
    @classmethod
    def get_daily_stats(cls, days=7):
        """Получить ежедневную статистику"""
        from datetime import timedelta
        date_from = timezone.now().date() - timedelta(days=days)
        
        return cls.objects.filter(date__gte=date_from).values('date').annotate(
            tokens=Sum('total_tokens'),
            requests=Sum('requests_count'),
            cost=Sum('cost'),
        ).order_by('date')


class NewsSearchEndpoint(models.Model):
    """
    Настраиваемый источник для сбора ссылок на новости (HTML-скрапинг или RSS).
    Подмешивается к встроенным источникам в NewsParserService.
    """
    KIND_CHOICES = [
        ('html', 'HTML (скрапинг списка статей)'),
        ('rss', 'RSS / Atom'),
    ]
    name = models.CharField(max_length=200, verbose_name='Название')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    category = models.ForeignKey(
        'Blog.Category',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='news_search_endpoints',
        verbose_name='Категория блога',
        help_text='Пусто — использовать для всех категорий',
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='html', verbose_name='Тип')
    sort_order = models.IntegerField(default=0, verbose_name='Порядок')
    # HTML
    base_url = models.URLField(blank=True, max_length=500, verbose_name='Базовый URL')
    search_url = models.CharField(
        max_length=1000,
        blank=True,
        verbose_name='URL поиска / ленты',
        help_text='Для HTML: можно использовать плейсхолдеры {query} и {category}. Для RSS с динамикой — {query} в URL ленты.',
    )
    article_selector = models.CharField(max_length=500, blank=True, verbose_name='CSS селектор ссылок на статьи')
    title_selector = models.CharField(max_length=500, blank=True, verbose_name='CSS селектор заголовка (опционально)')
    # RSS
    rss_feed_url = models.URLField(blank=True, max_length=1000, verbose_name='URL RSS (если kind=rss)')
    notes = models.CharField(max_length=500, blank=True, verbose_name='Заметки')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    class Meta:
        verbose_name = 'Источник поиска новостей'
        verbose_name_plural = 'Источники поиска новостей'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"


class NewsSearchSettings(models.Model):
    """
    Singleton (id=1): параметры пула поиска новостей для автопостинга.
    Редактируются в дашборде «Поиск новостей».
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    ddg_query_suffix = models.CharField(
        max_length=200,
        blank=True,
        default='новости',
        verbose_name='Суффикс запроса (DuckDuckGo)',
        help_text='Добавляется к фразе поиска. Пусто — не добавлять.',
    )
    ddg_search_url_template = models.CharField(
        max_length=600,
        default='https://html.duckduckgo.com/html/?q={query}',
        verbose_name='Шаблон URL DuckDuckGo',
        help_text='Обязательно включите плейсхолдер {query}',
    )
    search_per_source_limit = models.PositiveIntegerField(
        default=18,
        verbose_name='Ссылок с одного источника (макс.)',
    )
    search_max_collect = models.PositiveIntegerField(
        default=48,
        verbose_name='Размер пула после ранжирования',
    )
    search_pool_timeout = models.PositiveIntegerField(
        default=35,
        verbose_name='Таймаут ожидания источников (сек)',
    )
    search_parallel_max = models.PositiveIntegerField(
        default=6,
        verbose_name='Параллельных потоков поиска',
    )
    freshness_hours = models.PositiveIntegerField(
        default=72,
        verbose_name='Свежесть (часы), 0 = выкл.',
        help_text='Отсев по дате, если она надёжно известна (RSS и т.д.)',
    )
    penalize_unknown_published = models.BooleanField(
        default=True,
        verbose_name='Штрафовать неизвестную дату в ранжировании',
    )
    rank_random_jitter = models.BooleanField(
        default=True,
        verbose_name='Случайный джиттер в ранжировании',
    )
    query_variant_suffixes = models.TextField(
        blank=True,
        verbose_name='Варианты уточнения через |',
        help_text='Например: последние новости|сегодня|обзор — один вариант выбирается случайно.',
    )
    force_fresh_news_on_content_retry = models.BooleanField(
        default=True,
        verbose_name='При коротком тексте — новый поиск новостей',
    )
    top_list_random_offset_max = models.PositiveIntegerField(
        default=4,
        verbose_name='Случайный сдвиг в топе кандидатов (0 = нет)',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Настройки поиска новостей'
        verbose_name_plural = 'Настройки поиска новостей'

    def __str__(self):
        return 'Настройки поиска новостей'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def reset_to_factory_defaults(self):
        from .news_search_config import NEWS_SEARCH_SETTINGS_DEFAULTS

        for key, value in NEWS_SEARCH_SETTINGS_DEFAULTS.items():
            setattr(self, key, value)
        self.save()


class NewsSource(models.Model):
    """Статистика источников новостей для оптимизации выбора"""
    
    source_url = models.URLField(verbose_name='URL источника', max_length=500)
    source_name = models.CharField(verbose_name='Название источника', max_length=200)
    source_type = models.CharField(
        verbose_name='Тип источника',
        max_length=50,
        choices=[
            ('rss', 'RSS'),
            ('api', 'API'),
            ('scraping', 'Веб-скрапинг'),
        ],
        default='rss'
    )
    
    # Статистика
    total_views = models.IntegerField(default=0, verbose_name='Общее количество просмотров')
    articles_count = models.IntegerField(default=0, verbose_name='Количество использованных статей')
    last_used = models.DateTimeField(null=True, blank=True, verbose_name='Последнее использование')
    
    # Рейтинг источника (просмотры/статьи)
    rating = models.FloatField(default=0.0, verbose_name='Рейтинг источника')
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    
    class Meta:
        verbose_name = 'Источник новостей'
        verbose_name_plural = 'Источники новостей'
        unique_together = ['source_url', 'source_name']
        ordering = ['-rating', '-last_used']
        indexes = [
            models.Index(fields=['-rating', 'is_active']),
            models.Index(fields=['source_type']),
        ]
    
    def __str__(self):
        return f"{self.source_name} (рейтинг: {self.rating:.2f})"
    
    def update_rating(self):
        """Обновить рейтинг источника"""
        if self.articles_count > 0:
            self.rating = self.total_views / self.articles_count
        else:
            self.rating = 0.0
        self.save(update_fields=['rating'])
    
    def record_usage(self, views: int = 0):
        """Записать использование источника"""
        self.articles_count += 1
        self.total_views += views
        self.last_used = timezone.now()
        self.update_rating()


class CategoryStats(models.Model):
    """Статистика категорий для умной ротации"""
    
    category = models.OneToOneField(
        'Blog.Category',
        on_delete=models.CASCADE,
        related_name='stats',
        verbose_name='Категория'
    )
    
    # Статистика
    total_views = models.IntegerField(default=0, verbose_name='Общее количество просмотров')
    articles_count = models.IntegerField(default=0, verbose_name='Количество статей')
    last_publication = models.DateTimeField(null=True, blank=True, verbose_name='Последняя публикация')
    
    # Приоритет категории (для ротации: популярные в 2 раза чаще)
    priority = models.FloatField(default=1.0, verbose_name='Приоритет категории')
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'Статистика категории'
        verbose_name_plural = 'Статистика категорий'
        ordering = ['-priority', '-last_publication']
        indexes = [
            models.Index(fields=['-priority', 'last_publication']),
        ]
    
    def __str__(self):
        return f"Статистика: {self.category.title} (приоритет: {self.priority:.2f})"
    
    def update_priority(self):
        """Обновить приоритет категории на основе просмотров"""
        # Базовый приоритет: 1.0
        # Если есть просмотры, увеличиваем приоритет
        if self.articles_count > 0:
            avg_views = self.total_views / self.articles_count
            # Популярные категории (средние просмотры > 10) получают приоритет 2.0
            if avg_views > 10:
                self.priority = 2.0
            elif avg_views > 5:
                self.priority = 1.5
            else:
                self.priority = 1.0
        else:
            # Если нет статей, приоритет низкий
            self.priority = 0.5
        
        self.save(update_fields=['priority'])
    
    def record_publication(self, views: int = 0):
        """Записать публикацию статьи в категории"""
        self.articles_count += 1
        self.total_views += views
        self.last_publication = timezone.now()
        self.update_priority()