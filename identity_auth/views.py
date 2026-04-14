"""Вход, регистрация, VK ID complete, выход, настройки OAuth (/manage/auth/oauth/)."""
import json

import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from identity_auth import auth_settings
from identity_auth.forms import (
    CustomerLoginForm,
    CustomerRegistrationForm,
    SiteCustomerAuthSettingsForm,
)
from identity_auth.models import SiteCustomerAuthSettings
from identity_auth.services import resolve_linked_user


def customer_register(request):
    def safe_next_url():
        raw = (request.POST.get('next') or request.GET.get('next') or '').strip()
        if raw and url_has_allowed_host_and_scheme(
            raw,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return raw
        return None

    next_url = safe_next_url()
    if request.user.is_authenticated:
        if next_url:
            return redirect(next_url)
        return redirect('home:customer_dashboard')

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать в личный кабинет.')
            next_url = safe_next_url()
            if next_url:
                return redirect(next_url)
            return redirect('home:customer_dashboard')
    else:
        form = CustomerRegistrationForm()

    return render(
        request,
        'identity_auth/register.html',
        {'form': form, 'title': 'Регистрация', 'next': request.GET.get('next', '')},
    )


def customer_login(request):
    def safe_next_url():
        raw = (request.POST.get('next') or request.GET.get('next') or '').strip()
        if raw and url_has_allowed_host_and_scheme(
            raw,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return raw
        return None

    next_url = safe_next_url()
    if request.user.is_authenticated:
        if next_url:
            return redirect(next_url)
        return redirect('home:customer_dashboard')

    if request.method == 'POST':
        form = CustomerLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.get_full_name() or user.username}!')
                next_url = safe_next_url()
                if next_url:
                    return redirect(next_url)
                return redirect('home:customer_dashboard')
    else:
        form = CustomerLoginForm()

    return render(
        request,
        'identity_auth/login.html',
        {
            'form': form,
            'title': 'Вход в личный кабинет',
            'next': request.GET.get('next', ''),
        },
    )


@require_POST
def customer_vkid_complete(request):
    def safe_next_url(raw):
        raw = (raw or '').strip()
        if raw and url_has_allowed_host_and_scheme(
            raw,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return raw
        return ''

    app_id = auth_settings.get_vkid_app_id()
    if not app_id:
        return JsonResponse({'error': 'vkid_disabled'}, status=503)
    try:
        payload = json.loads(request.body.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid_json'}, status=400)

    access_token = payload.get('access_token')
    if not access_token:
        return JsonResponse({'error': 'missing_token'}, status=400)

    try:
        r = requests.post(
            'https://id.vk.ru/oauth2/user_info',
            data={'client_id': str(app_id), 'access_token': access_token},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=15,
        )
    except requests.RequestException:
        return JsonResponse({'error': 'vk_unreachable'}, status=502)

    try:
        body = r.json()
    except ValueError:
        return JsonResponse({'error': 'invalid_vk_response'}, status=502)

    if r.status_code != 200 or 'error' in body:
        return JsonResponse({
            'error': body.get('error', 'vk_error'),
            'detail': body.get('error_description', ''),
        }, status=400)

    user_info = body.get('user') or {}
    vk_user_id = user_info.get('user_id')
    if vk_user_id is None:
        return JsonResponse({'error': 'no_user'}, status=400)

    vk_user_id = str(vk_user_id)
    first_name = (user_info.get('first_name') or '')[:30]
    last_name = (user_info.get('last_name') or '')[:30]
    email_from_vk = user_info.get('email')

    user, is_new_user = resolve_linked_user(
        provider='vkid',
        provider_user_id=vk_user_id,
        email=email_from_vk,
        first_name=first_name,
        last_name=last_name,
    )
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    display = user.get_full_name() or user.username
    if is_new_user:
        messages.success(
            request,
            f'Регистрация выполнена. Добро пожаловать, {display}! '
            f'Профиль можно дополнить в личном кабинете.',
        )
    else:
        messages.success(request, f'Добро пожаловать, {display}!')
    next_url = safe_next_url(payload.get('next'))
    return JsonResponse({'ok': True, 'redirect': next_url or reverse('home:customer_dashboard')})


@login_required
def customer_logout(request):
    logout(request)
    messages.success(request, 'Вы успешно вышли из личного кабинета.')
    return redirect('home:home')


@login_required
def admin_customer_auth_oauth_settings(request):
    if not request.user.is_superuser:
        messages.error(request, 'Раздел доступен только главному администратору (суперпользователю).')
        return redirect('home:customer_dashboard')

    obj = SiteCustomerAuthSettings.get_solo()
    if request.method == 'POST':
        form = SiteCustomerAuthSettingsForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Параметры входа сохранены. Активные значения: из БД, если поле заполнено, иначе из .env.',
            )
            return redirect('identity_auth:admin_customer_auth_oauth_settings')
    else:
        form = SiteCustomerAuthSettingsForm(instance=obj)

    return render(
        request,
        'identity_auth/admin/oauth_settings.html',
        {'form': form, 'title': 'Параметры входа (OAuth)'},
    )
