"""
OAuth2 + PKCE для входа в ЛК: Яндекс, Google, MAX (OIDC).
"""
import base64
import hashlib
import secrets
from urllib.parse import urlencode, urlparse

import requests
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from identity_auth import auth_settings
from identity_auth.services import resolve_linked_user

OAUTH_PROVIDERS = frozenset({'yandex', 'google', 'max'})

OAUTH_UNAVAILABLE_USER_MSG = (
    'Недоступно. Попробуйте другой способ регистрации и входа.'
)


def _redirect_back_or_login(request):
    """После отказа в OAuth — остаёмся на странице входа/регистрации, если Referer свой."""
    ref = (request.META.get('HTTP_REFERER') or '').strip()
    if ref and url_has_allowed_host_and_scheme(
        ref,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(ref)
    return redirect('identity_auth:customer_login')


def _pkce_pair():
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    return verifier, challenge


def _oauth_safe_next(request):
    raw = (request.GET.get('next') or request.POST.get('next') or '').strip()
    if raw and url_has_allowed_host_and_scheme(
        raw,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return raw
    return ''


def _normalize_issuer(url):
    if not url:
        return ''
    s = str(url).strip().rstrip('/')
    if not s:
        return ''
    parsed = urlparse(s)
    if parsed.scheme not in ('http', 'https'):
        return ''
    return s


def _callback_url(request, provider):
    return request.build_absolute_uri(
        reverse('identity_auth:customer_oauth_callback', kwargs={'provider': provider})
    )


def customer_oauth_start(request, provider):
    if request.user.is_authenticated:
        return redirect('home:customer_dashboard')
    if provider not in OAUTH_PROVIDERS:
        messages.error(request, 'Неизвестный способ входа.')
        return redirect('identity_auth:customer_login')

    callback = _callback_url(request, provider)
    next_url = _oauth_safe_next(request)
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce_pair()

    if provider == 'yandex':
        cid = auth_settings.get_yandex_oauth_client_id()
        sec = auth_settings.get_yandex_oauth_client_secret()
        if not cid or not sec:
            messages.error(request, OAUTH_UNAVAILABLE_USER_MSG)
            return _redirect_back_or_login(request)
        request.session['oauth_pkce_verifier'] = verifier
        request.session['oauth_state'] = state
        request.session['oauth_provider'] = provider
        request.session['oauth_next'] = next_url
        params = {
            'response_type': 'code',
            'client_id': cid,
            'redirect_uri': callback,
            'scope': 'login:email login:info',
            'state': state,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        }
        url = 'https://oauth.yandex.ru/authorize?' + urlencode(params)
        return redirect(url)

    if provider == 'google':
        cid = auth_settings.get_google_oauth_client_id()
        sec = auth_settings.get_google_oauth_client_secret()
        if not cid or not sec:
            messages.error(request, OAUTH_UNAVAILABLE_USER_MSG)
            return _redirect_back_or_login(request)
        request.session['oauth_pkce_verifier'] = verifier
        request.session['oauth_state'] = state
        request.session['oauth_provider'] = provider
        request.session['oauth_next'] = next_url
        params = {
            'response_type': 'code',
            'client_id': cid,
            'redirect_uri': callback,
            'scope': 'openid email profile',
            'state': state,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'access_type': 'online',
            'prompt': 'select_account',
        }
        url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(params)
        return redirect(url)

    # MAX OIDC (эндпоинты относительно issuer из кабинета партнёра)
    issuer = _normalize_issuer(auth_settings.get_max_oidc_issuer())
    cid = auth_settings.get_max_oidc_client_id()
    sec = auth_settings.get_max_oidc_client_secret()
    if not issuer or not cid or not sec:
        messages.error(request, OAUTH_UNAVAILABLE_USER_MSG)
        return _redirect_back_or_login(request)
    request.session['oauth_pkce_verifier'] = verifier
    request.session['oauth_state'] = state
    request.session['oauth_provider'] = provider
    request.session['oauth_next'] = next_url
    params = {
        'response_type': 'code',
        'client_id': cid,
        'redirect_uri': callback,
        'scope': 'openid profile email',
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    url = f'{issuer}/oauth/authorize?' + urlencode(params)
    return redirect(url)


def _exchange_yandex(code, redirect_uri, verifier):
    cid = auth_settings.get_yandex_oauth_client_id()
    sec = auth_settings.get_yandex_oauth_client_secret()
    try:
        r = requests.post(
            'https://oauth.yandex.ru/token',
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': cid,
                'client_secret': sec,
                'redirect_uri': redirect_uri,
                'code_verifier': verifier,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=20,
        )
    except requests.RequestException:
        return None, 'yandex_unreachable'
    if r.status_code != 200:
        return None, r.text[:200]
    body = r.json()
    return body.get('access_token'), None


def _yandex_user(access_token):
    try:
        r = requests.get(
            'https://login.yandex.ru/info',
            params={'format': 'json'},
            headers={'Authorization': f'OAuth {access_token}'},
            timeout=15,
        )
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    return r.json()


def _exchange_google(code, redirect_uri, verifier):
    cid = auth_settings.get_google_oauth_client_id()
    sec = auth_settings.get_google_oauth_client_secret()
    try:
        r = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': cid,
                'client_secret': sec,
                'redirect_uri': redirect_uri,
                'code_verifier': verifier,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=20,
        )
    except requests.RequestException:
        return None, 'google_unreachable'
    if r.status_code != 200:
        return None, r.text[:200]
    body = r.json()
    return body.get('access_token'), None


def _google_user(access_token):
    try:
        r = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=15,
        )
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    return r.json()


def _exchange_max(issuer, code, redirect_uri, verifier):
    cid = auth_settings.get_max_oidc_client_id()
    sec = auth_settings.get_max_oidc_client_secret()
    token_url = f'{issuer}/oauth/token'
    try:
        r = requests.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': cid,
                'client_secret': sec,
                'redirect_uri': redirect_uri,
                'code_verifier': verifier,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=20,
        )
    except requests.RequestException:
        return None, 'max_unreachable'
    if r.status_code != 200:
        return None, r.text[:300]
    body = r.json()
    return body.get('access_token'), None


def _max_user(issuer, access_token):
    url = f'{issuer}/userinfo'
    try:
        r = requests.get(
            url,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=15,
        )
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    return r.json()


def _upsert_oauth_user(
    *,
    provider,
    provider_user_id,
    email,
    first_name,
    last_name,
    request,
):
    """Создание/вход одного пользователя с привязкой провайдера (см. identity_auth)."""
    user, is_new = resolve_linked_user(
        provider=provider,
        provider_user_id=str(provider_user_id),
        email=email,
        first_name=first_name or '',
        last_name=last_name or '',
    )
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    display = user.get_full_name() or user.username
    if is_new:
        messages.success(
            request,
            f'Регистрация выполнена. Добро пожаловать, {display}! '
            f'Профиль можно дополнить в личном кабинете.',
        )
    else:
        messages.success(request, f'Добро пожаловать, {display}!')


def customer_oauth_callback(request, provider):
    if provider not in OAUTH_PROVIDERS:
        messages.error(request, 'Неизвестный способ входа.')
        return redirect('identity_auth:customer_login')

    sess_prov = request.session.pop('oauth_provider', None)
    state_sess = request.session.pop('oauth_state', None)
    verifier = request.session.pop('oauth_pkce_verifier', None)
    next_url = request.session.pop('oauth_next', '') or ''

    err = request.GET.get('error')
    if err:
        messages.error(request, f'Вход отменён или ошибка провайдера: {err}')
        return redirect('identity_auth:customer_login')

    code = request.GET.get('code')
    state_q = request.GET.get('state')
    if not code or state_q != state_sess or sess_prov != provider or not verifier:
        messages.error(request, 'Сессия входа устарела. Попробуйте снова.')
        return redirect('identity_auth:customer_login')

    callback = _callback_url(request, provider)

    if provider == 'yandex':
        token, terr = _exchange_yandex(code, callback, verifier)
        if not token:
            messages.error(request, 'Не удалось обменять код Яндекса на токен.')
            return redirect('identity_auth:customer_login')
        info = _yandex_user(token)
        if not info:
            messages.error(request, 'Не удалось получить профиль Яндекса.')
            return redirect('identity_auth:customer_login')
        uid = str(info.get('id') or info.get('client_id') or '')
        if not uid:
            messages.error(request, 'Яндекс не вернул идентификатор пользователя.')
            return redirect('identity_auth:customer_login')
        email = (info.get('default_email') or info.get('email') or '') or None
        fn = info.get('first_name') or ''
        ln = info.get('last_name') or ''
        _upsert_oauth_user(
            provider='yandex',
            provider_user_id=uid,
            email=email,
            first_name=fn,
            last_name=ln,
            request=request,
        )

    elif provider == 'google':
        token, _ = _exchange_google(code, callback, verifier)
        if not token:
            messages.error(request, 'Не удалось обменять код Google на токен.')
            return redirect('identity_auth:customer_login')
        info = _google_user(token)
        if not info:
            messages.error(request, 'Не удалось получить профиль Google.')
            return redirect('identity_auth:customer_login')
        uid = str(info.get('sub') or '')
        if not uid:
            messages.error(request, 'Google не вернул идентификатор пользователя.')
            return redirect('identity_auth:customer_login')
        email = info.get('email') or None
        fn = info.get('given_name') or ''
        ln = info.get('family_name') or ''
        _upsert_oauth_user(
            provider='google',
            provider_user_id=uid,
            email=email,
            first_name=fn,
            last_name=ln,
            request=request,
        )

    else:
        issuer = _normalize_issuer(auth_settings.get_max_oidc_issuer())
        if not issuer:
            messages.error(request, 'MAX issuer не настроен.')
            return redirect('identity_auth:customer_login')
        token, _ = _exchange_max(issuer, code, callback, verifier)
        if not token:
            messages.error(request, 'Не удалось обменять код MAX на токен. Проверьте issuer и формат в закрытой доке.')
            return redirect('identity_auth:customer_login')
        info = _max_user(issuer, token)
        if not info:
            messages.error(request, 'Не удалось получить userinfo MAX.')
            return redirect('identity_auth:customer_login')
        uid = str(info.get('sub') or info.get('user_id') or '')
        if not uid:
            messages.error(request, 'MAX не вернул sub.')
            return redirect('identity_auth:customer_login')
        email = info.get('email') or None
        fn = (info.get('given_name') or '')[:30]
        ln = (info.get('family_name') or '')[:30]
        if not fn and info.get('name'):
            parts = str(info['name']).strip().split(None, 1)
            fn = (parts[0] if parts else '')[:30]
            ln = (parts[1] if len(parts) > 1 else '')[:30]
        _upsert_oauth_user(
            provider='max',
            provider_user_id=uid,
            email=email,
            first_name=fn,
            last_name=ln,
            request=request,
        )

    if next_url:
        return redirect(next_url)
    return redirect('home:customer_dashboard')
