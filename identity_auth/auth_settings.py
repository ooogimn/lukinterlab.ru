"""
Параметры входа (VK ID, OAuth): при непустом значении в БД берётся оно,
иначе — django.conf.settings из .env.

Секреты в БД — форма /manage/auth/oauth/ (суперпользователь).
"""
from django.conf import settings
from django.templatetags.static import static


def _solo():
    from identity_auth.models import SiteCustomerAuthSettings
    return SiteCustomerAuthSettings.get_solo()


def _strip_or_none(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def get_vkid_app_id():
    row = _solo()
    raw = _strip_or_none(row.vkid_app_id)
    if raw:
        try:
            return int(raw)
        except ValueError:
            return getattr(settings, 'VKID_APP_ID', None)
    return getattr(settings, 'VKID_APP_ID', None)


def get_vkid_redirect_url(request):
    """
    URL возврата после экрана согласия VK / OK / Mail (должен совпадать с кабинетом VK ID).

    Важно: на этой странице должен быть тот же VK ID SDK и обработчик LOGIN_SUCCESS →
    exchangeCode → POST customer_vkid_complete. Виджет подключён на страницах входа
    и регистрации, не на главной — поэтому по умолчанию используем /customer/login/,
    а не корень сайта (иначе редирект на «/» обрывает цепочку и пользователь остаётся гостем).
    """
    row = _solo()
    fixed = _strip_or_none(row.vkid_redirect_url)
    if fixed:
        if not fixed.endswith('/'):
            fixed += '/'
        return fixed
    env = _strip_or_none(getattr(settings, 'VKID_REDIRECT_URL', '') or '')
    if env:
        return env if env.endswith('/') else env + '/'
    from django.urls import reverse

    login_path = reverse('identity_auth:customer_login')
    redirect = request.build_absolute_uri(login_path)
    if not redirect.endswith('/'):
        redirect += '/'
    return redirect


def get_vkid_protected_key():
    row = _solo()
    v = _strip_or_none(row.vkid_protected_key)
    return v if v is not None else (_strip_or_none(getattr(settings, 'VKID_PROTECTED_KEY', None)) or '')


def get_vkid_service_key():
    row = _solo()
    v = _strip_or_none(row.vkid_service_key)
    return v if v is not None else (_strip_or_none(getattr(settings, 'VKID_SERVICE_KEY', None)) or '')


def get_yandex_oauth_client_id():
    row = _solo()
    v = _strip_or_none(row.yandex_oauth_client_id)
    return v if v is not None else _strip_or_none(getattr(settings, 'YANDEX_OAUTH_CLIENT_ID', '') or '')


def get_yandex_oauth_client_secret():
    row = _solo()
    v = _strip_or_none(row.yandex_oauth_client_secret)
    return v if v is not None else _strip_or_none(getattr(settings, 'YANDEX_OAUTH_CLIENT_SECRET', '') or '')


def get_google_oauth_client_id():
    row = _solo()
    v = _strip_or_none(row.google_oauth_client_id)
    return v if v is not None else _strip_or_none(getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '') or '')


def get_google_oauth_client_secret():
    row = _solo()
    v = _strip_or_none(row.google_oauth_client_secret)
    return v if v is not None else _strip_or_none(getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '') or '')


def get_max_oidc_issuer():
    row = _solo()
    v = _strip_or_none(row.max_oidc_issuer)
    return v if v is not None else _strip_or_none(getattr(settings, 'MAX_OIDC_ISSUER', '') or '')


def get_max_oidc_client_id():
    row = _solo()
    v = _strip_or_none(row.max_oidc_client_id)
    return v if v is not None else _strip_or_none(getattr(settings, 'MAX_OIDC_CLIENT_ID', '') or '')


def get_max_oidc_client_secret():
    row = _solo()
    v = _strip_or_none(row.max_oidc_client_secret)
    return v if v is not None else _strip_or_none(getattr(settings, 'MAX_OIDC_CLIENT_SECRET', '') or '')


def oauth_providers_enabled_flags():
    """Для шаблонов: какие провайдеры считаем настроенными (БД или .env)."""
    return {
        'yandex': bool(get_yandex_oauth_client_id() and get_yandex_oauth_client_secret()),
        'google': bool(get_google_oauth_client_id() and get_google_oauth_client_secret()),
        'max': bool(
            get_max_oidc_issuer()
            and get_max_oidc_client_id()
            and get_max_oidc_client_secret()
        ),
    }


def oauth_button_icon_url(provider: str) -> str:
    """URL иконки: загрузка из БД или static identity_auth/img/oauth/{provider}.svg."""
    row = _solo()
    field = {
        'yandex': 'yandex_oauth_button_icon',
        'google': 'google_oauth_button_icon',
        'max': 'max_oauth_button_icon',
    }.get(provider)
    if not field:
        return static('identity_auth/img/oauth/yandex.svg')
    img = getattr(row, field, None)
    if img and getattr(img, 'name', None):
        return img.url
    return static(f'identity_auth/img/oauth/{provider}.svg')
