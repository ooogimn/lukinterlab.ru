import logging

from identity_auth import auth_settings

logger = logging.getLogger(__name__)


def vkid_oauth(request):
    """Параметры VK ID SDK и флаги OAuth для шаблонов виджета входа."""
    try:
        flags = auth_settings.oauth_providers_enabled_flags()
        return {
            'vkid_app_id': auth_settings.get_vkid_app_id(),
            'vkid_redirect_url': auth_settings.get_vkid_redirect_url(request),
            'oauth_provider_yandex_ready': flags['yandex'],
            'oauth_provider_google_ready': flags['google'],
            'oauth_provider_max_ready': flags['max'],
            'oauth_icon_yandex': auth_settings.oauth_button_icon_url('yandex'),
            'oauth_icon_google': auth_settings.oauth_button_icon_url('google'),
            'oauth_icon_max': auth_settings.oauth_button_icon_url('max'),
        }
    except Exception:
        logger.exception('vkid_oauth: ошибка настроек OAuth/VK ID, отдаём пустые флаги')
        return {
            'vkid_app_id': None,
            'vkid_redirect_url': '',
            'oauth_provider_yandex_ready': False,
            'oauth_provider_google_ready': False,
            'oauth_provider_max_ready': False,
            'oauth_icon_yandex': '',
            'oauth_icon_google': '',
            'oauth_icon_max': '',
        }
