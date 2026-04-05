from django.conf import settings
from django.db import models


class LinkedSocialProvider(models.TextChoices):
    VKID = 'vkid', 'VK ID'
    YANDEX = 'yandex', 'Яндекс'
    GOOGLE = 'google', 'Google'
    MAX = 'max', 'MAX'


class LinkedSocialAccount(models.Model):
    """
    Связь «провайдер + стабильный id у провайдера» → один User.
    Один пользователь может иметь несколько записей (VK + Google + …).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='linked_social_accounts',
        verbose_name='Пользователь',
    )
    provider = models.CharField(
        'Провайдер',
        max_length=16,
        choices=LinkedSocialProvider.choices,
        db_index=True,
    )
    provider_user_id = models.CharField(
        'ID у провайдера',
        max_length=191,
        db_index=True,
    )
    created_at = models.DateTimeField('Привязано', auto_now_add=True)

    class Meta:
        verbose_name = 'Привязанный вход'
        verbose_name_plural = 'Привязки входа'
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'provider_user_id'],
                name='identity_auth_provider_uid_unique',
            ),
        ]

    def __str__(self):
        return f'{self.user_id} ← {self.provider}:{self.provider_user_id}'


class SiteCustomerAuthSettings(models.Model):
    """
    Секреты и публичные ключи входа (VK ID, OAuth Яндекс/Google/MAX).
    Одна строка pk=1. Таблица БД прежняя (home_sitecustomerauthsettings).
    """

    vkid_app_id = models.CharField(
        'VK ID — ID приложения (app id)',
        max_length=32,
        blank=True,
        help_text='Пусто = брать из VKID_APP_ID в .env',
    )
    vkid_redirect_url = models.URLField(
        'VK ID — доверенный redirect URL',
        blank=True,
        help_text='Полный URL со слэшем в конце, как в кабинете VK ID. Пусто = VKID_REDIRECT_URL из .env или авто с текущего хоста.',
    )
    vkid_protected_key = models.TextField(
        'VK ID — защищённый ключ',
        blank=True,
        help_text='Пусто в форме при сохранении = не менять. Пусто в БД = VKID_PROTECTED_KEY из .env.',
    )
    vkid_service_key = models.TextField(
        'VK ID — сервисный ключ',
        blank=True,
        help_text='Пусто при сохранении = не менять. Пусто в БД = VKID_SERVICE_KEY из .env.',
    )
    yandex_oauth_client_id = models.CharField(
        'Яндекс OAuth — Client ID',
        max_length=256,
        blank=True,
        help_text='Пусто = YANDEX_OAUTH_CLIENT_ID в .env',
    )
    yandex_oauth_client_secret = models.TextField(
        'Яндекс OAuth — Client Secret',
        blank=True,
        help_text='Пусто при сохранении = не менять. Пусто в БД = .env',
    )
    google_oauth_client_id = models.CharField(
        'Google OAuth — Client ID',
        max_length=512,
        blank=True,
        help_text='Пусто = GOOGLE_OAUTH_CLIENT_ID в .env',
    )
    google_oauth_client_secret = models.TextField(
        'Google OAuth — Client Secret',
        blank=True,
        help_text='Пусто при сохранении = не менять. Пусто в БД = .env',
    )
    max_oidc_issuer = models.URLField(
        'MAX OIDC — базовый URL (issuer)',
        blank=True,
        help_text='Без завершающего слэша или со слэшем — код нормализует. Пусто = MAX_OIDC_ISSUER в .env.',
    )
    max_oidc_client_id = models.CharField(
        'MAX OIDC — Client ID',
        max_length=256,
        blank=True,
        help_text='Пусто = MAX_OIDC_CLIENT_ID в .env',
    )
    max_oidc_client_secret = models.TextField(
        'MAX OIDC — Client Secret',
        blank=True,
        help_text='Пусто при сохранении = не менять. Пусто в БД = .env',
    )
    yandex_oauth_button_icon = models.ImageField(
        'Иконка кнопки «Яндекс» (PNG/SVG)',
        upload_to='oauth_buttons/',
        blank=True,
        null=True,
        help_text='Пусто — встроенная иконка из static приложения identity_auth',
    )
    google_oauth_button_icon = models.ImageField(
        'Иконка кнопки «Google»',
        upload_to='oauth_buttons/',
        blank=True,
        null=True,
        help_text='Пусто — встроенная иконка из static приложения identity_auth',
    )
    max_oauth_button_icon = models.ImageField(
        'Иконка кнопки «MAX»',
        upload_to='oauth_buttons/',
        blank=True,
        null=True,
        help_text='Пусто — встроенная иконка из static приложения identity_auth',
    )

    class Meta:
        db_table = 'home_sitecustomerauthsettings'
        verbose_name = 'Параметры входа пользователей (OAuth, VK ID)'
        verbose_name_plural = 'Параметры входа пользователей (OAuth, VK ID)'

    def __str__(self):
        return 'Параметры входа (OAuth / VK ID)'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
