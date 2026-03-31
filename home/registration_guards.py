"""
Проверки при регистрации и создании аккаунта: «человеческие» имена, спам-паттерны, одноразовая почта.
Не заменяют CAPTCHA и rate limit, но отсекают типичный мусор ботов.
"""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError

_HAS_LETTER = re.compile(r"[a-zA-Zа-яА-ЯёЁ]")
_HAS_DIGIT = re.compile(r"\d")
# Буквы кирил/лат, дефисы, апостроф, одиночный пробел внутри составного имени (редко в одном поле)
_NAME_OK = re.compile(r"^[a-zA-Zа-яА-ЯёЁ]+([ \-–'][a-zA-Zа-яА-ЯёЁ]+)*$")

_SPAM_SUBSTRINGS = (
    "http://",
    "https://",
    "www.",
    ".com",
    ".ru/",
    ".ru\\",
    ".xyz",
    ".top",
    "@",
    "viagra",
    "cialis",
    "casino",
    "crypto",
    "bitcoin",
    "forex",
    "seo@",
    "купить подпис",
    "заработок в инт",
)

_DISPOSABLE_EMAIL_DOMAINS = frozenset({
    "mailinator.com",
    "guerrillamail.com",
    "guerrillamailblock.com",
    "tempmail.com",
    "temp-mail.org",
    "yopmail.com",
    "10minutemail.com",
    "dispostable.com",
    "trashmail.com",
    "getnada.com",
    "maildrop.cc",
    "fakeinbox.com",
    "throwaway.email",
})


def validate_person_name(value: str | None, field_label: str = "Имя") -> str:
    v = (value or "").strip()
    v = re.sub(r"\s+", " ", v)
    if len(v) < 2:
        raise ValidationError(f"Укажите {field_label.lower()} (минимум 2 символа).")
    if len(v) > 30:
        raise ValidationError(f"{field_label} слишком длинное.")
    if _HAS_DIGIT.search(v):
        raise ValidationError(f"{field_label}: цифры в имени недопустимы.")
    if not _HAS_LETTER.search(v):
        raise ValidationError(f"{field_label}: нужны буквы (русские или латиница).")
    if not _NAME_OK.fullmatch(v):
        raise ValidationError(
            f"{field_label}: допустимы только буквы, один пробел или дефис между частями имени."
        )
    lowered = v.lower()
    for s in _SPAM_SUBSTRINGS:
        if s in lowered:
            raise ValidationError("Указаны недопустимые данные. Проверьте поле и попробуйте снова.")
    letters_only = re.sub(r"[\s\-–']", "", v)
    if len(letters_only) >= 5 and len(set(letters_only.lower())) <= 1:
        raise ValidationError(f"Проверьте корректность {field_label.lower()}.")
    return v


def validate_registration_username(username: str | None) -> str:
    u = (username or "").strip()
    if len(u) < 3:
        raise ValidationError("Логин: минимум 3 символа.")
    if len(u) > 150:
        raise ValidationError("Логин слишком длинный.")
    low = u.lower()
    if "@" in u or "http://" in low or "https://" in low or "www." in low:
        raise ValidationError("Логин содержит недопустимые символы или фрагменты.")
    return u


def validate_registration_email_domain(email: str | None) -> None:
    if not email or "@" not in email:
        return
    domain = email.strip().split("@")[-1].lower()
    if domain in _DISPOSABLE_EMAIL_DOMAINS:
        raise ValidationError("Регистрация с этого почтового домена не поддерживается. Используйте обычную почту.")


def validate_customer_full_name_for_account(full_name: str | None) -> str:
    """Полное имя при заказе: как минимум имя; если есть слова — имя + фамилия отдельно проверяются."""
    raw = (full_name or "").strip()
    if not raw:
        raise ValidationError("Укажите имя.")
    parts = raw.split()
    validate_person_name(parts[0], "Имя")
    if len(parts) > 1:
        validate_person_name(" ".join(parts[1:]), "Фамилия")
    return raw


def reject_honeypot(value: str | None, message: str = "Не удалось отправить форму. Обновите страницу и попробуйте снова.") -> None:
    if (value or "").strip():
        raise ValidationError(message)
