"""
Единая логика: найти или создать User + профиль заказчика, привязать провайдера.

Порядок разрешения:
1) Уже есть LinkedSocialAccount(provider, provider_user_id)
2) Legacy-аккаунт с username vkid_* / yandex_* / google_* / max_*
3) Существующий пользователь с тем же реальным email (форма регистрации / другой вход)
4) Новый пользователь
"""
import re
import secrets

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import LinkedSocialAccount, LinkedSocialProvider

User = get_user_model()


def _is_placeholder_email(email: str) -> bool:
    if not email:
        return True
    e = email.strip().lower()
    if e.endswith('.invalid'):
        return True
    if e.endswith('.oauth.local'):
        return True
    return False


def _legacy_username(provider: str, provider_user_id: str) -> str:
    pid = str(provider_user_id).strip()
    if provider == LinkedSocialProvider.VKID:
        return f'vkid_{pid}'
    return f'{provider}_{pid}'


def _sanitize_username_base(raw: str) -> str:
    s = re.sub(r'[^\w.@+-]', '_', raw, flags=re.ASCII)[:40]
    s = s.strip('._') or 'user'
    return s


def _unique_username_from_email(email: str) -> str:
    local = _sanitize_username_base(email.split('@')[0])
    base = local[:30]
    candidate = base
    n = 0
    while User.objects.filter(username=candidate).exists():
        n += 1
        suffix = secrets.token_hex(2) if n > 50 else str(n)
        candidate = f'{base[:20]}_{suffix}'[:150]
    return candidate


def _unique_username_legacy(provider: str, provider_user_id: str) -> str:
    base = _legacy_username(provider, provider_user_id)[:150]
    if not User.objects.filter(username=base).exists():
        return base
    suffix = secrets.token_hex(3)
    merged = f'{base[:140]}_{suffix}'[:150]
    while User.objects.filter(username=merged).exists():
        suffix = secrets.token_hex(3)
        merged = f'{base[:140]}_{suffix}'[:150]
    return merged


def _ensure_customer(user):
    path = getattr(settings, 'IDENTITY_AUTH_CUSTOMER_MODEL', None)
    if not path:
        return
    try:
        Customer = django_apps.get_model(path)
    except (ValueError, LookupError):
        return
    Customer.objects.get_or_create(user=user, defaults={'phone': ''})


def _ensure_oauth_password_policy(user):
    """Не трогаем рабочий пароль; только «только OAuth» аккаунты остаются с unusable password."""
    if user.has_usable_password():
        return
    user.set_unusable_password()


def _apply_profile(user, email, first_name, last_name):
    """ФИО и email с провайдера; пароль не меняем."""
    fn = (first_name or '')[:30]
    ln = (last_name or '')[:30]
    email_norm = (email or '').strip() or None

    if fn:
        user.first_name = fn
    if ln:
        user.last_name = ln

    if email_norm and not _is_placeholder_email(email_norm):
        if not User.objects.filter(email__iexact=email_norm).exclude(pk=user.pk).exists():
            user.email = email_norm


def resolve_linked_user(
    *,
    provider: str,
    provider_user_id: str,
    email: str | None,
    first_name: str = '',
    last_name: str = '',
):
    """
    Возвращает (user, is_created).

    is_created=True если создан новый User.
    """
    uid = str(provider_user_id).strip()
    if not uid:
        raise ValueError('provider_user_id пустой')

    email_norm = (email or '').strip() or None

    with transaction.atomic():
        link = (
            LinkedSocialAccount.objects.select_related('user')
            .filter(provider=provider, provider_user_id=uid)
            .first()
        )
        if link:
            user = link.user
            _apply_profile(user, email_norm, first_name, last_name)
            _ensure_oauth_password_policy(user)
            user.save()
            _ensure_customer(user)
            return user, False

        legacy_name = _legacy_username(provider, uid)
        legacy_user = User.objects.filter(username=legacy_name).first()
        if legacy_user:
            acc, _ = LinkedSocialAccount.objects.get_or_create(
                provider=provider,
                provider_user_id=uid,
                defaults={'user': legacy_user},
            )
            if acc.user_id != legacy_user.pk:
                acc.user = legacy_user
                acc.save(update_fields=['user'])
            _apply_profile(legacy_user, email_norm, first_name, last_name)
            _ensure_oauth_password_policy(legacy_user)
            legacy_user.save()
            _ensure_customer(legacy_user)
            return legacy_user, False

        merge_user = None
        if email_norm and not _is_placeholder_email(email_norm):
            merge_user = User.objects.filter(email__iexact=email_norm).first()

        if merge_user:
            acc, _ = LinkedSocialAccount.objects.get_or_create(
                provider=provider,
                provider_user_id=uid,
                defaults={'user': merge_user},
            )
            if acc.user_id != merge_user.pk:
                acc.user = merge_user
                acc.save(update_fields=['user'])
            _apply_profile(merge_user, email_norm, first_name, last_name)
            _ensure_oauth_password_policy(merge_user)
            merge_user.save()
            _ensure_customer(merge_user)
            return merge_user, False

        if email_norm and not _is_placeholder_email(email_norm):
            username = _unique_username_from_email(email_norm)
            use_email = email_norm
        else:
            username = _unique_username_legacy(provider, uid)
            use_email = email_norm or f'{provider}_{uid}@{provider}.invalid'

        user = User(
            username=username,
            email=use_email,
            first_name=(first_name or '')[:30],
            last_name=(last_name or '')[:30],
        )
        user.set_unusable_password()
        user.save()
        LinkedSocialAccount.objects.create(user=user, provider=provider, provider_user_id=uid)
        _ensure_customer(user)
        return user, True


def attach_oauth_to_user(user, *, provider: str, provider_user_id: str, email=None, first_name: str = '', last_name: str = ''):
    """
    Привязать OAuth-провайдера к уже авторизованному пользователю.
    ValueError — если этот provider_user_id уже закреплён за другим User.
    """
    uid = str(provider_user_id).strip()
    if not uid:
        raise ValueError('provider_user_id пустой')

    email_norm = (email or '').strip() or None

    with transaction.atomic():
        link = (
            LinkedSocialAccount.objects.select_related('user')
            .filter(provider=provider, provider_user_id=uid)
            .first()
        )
        if link and link.user_id != user.pk:
            raise ValueError('already_linked_elsewhere')

        LinkedSocialAccount.objects.update_or_create(
            provider=provider,
            provider_user_id=uid,
            defaults={'user': user},
        )
        _apply_profile(user, email_norm, first_name, last_name)
        _ensure_oauth_password_policy(user)
        user.save()
        _ensure_customer(user)


def linked_labels_for_user(user):
    labels = {
        LinkedSocialProvider.VKID: 'VK ID (ВК, ОК, Mail)',
        LinkedSocialProvider.YANDEX: 'Яндекс',
        LinkedSocialProvider.GOOGLE: 'Google',
        LinkedSocialProvider.MAX: 'MAX',
    }
    codes = set(
        LinkedSocialAccount.objects.filter(user=user).values_list('provider', flat=True)
    )
    return [labels.get(c, c) for c in sorted(codes)]
