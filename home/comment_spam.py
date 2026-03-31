"""
Антиспам для публичных комментариев и отзывов: HTML, перечень URL, одноразовая почта на поле email.
"""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from .registration_guards import validate_person_name

_HTMLISH = re.compile(r'<\s*[/]?[a-zA-Z][^>\n]{0,200}>', re.I)
_HREF = re.compile(r'href\s*=', re.I)
_URL_FINDALL = re.compile(
    r'https?://[^\s<>"\'\)]+|www\.[^\s<>"\'\)]+',
    re.I,
)
# Не более стольких полных URL в одном тексте
_MAX_URLS_PER_COMMENT = 2


def validate_comment_plaintext(
    value: str | None,
    field_label: str = 'Текст',
    max_urls: int = _MAX_URLS_PER_COMMENT,
) -> str:
    s = (value or '').strip()
    if not s:
        raise ValidationError(f'Заполните поле «{field_label}».')
    if len(s) > 12000:
        raise ValidationError('Текст слишком длинный.')
    if _HTMLISH.search(s) or _HREF.search(s) or re.search(r'<\s*a\s+[^>]*href', s, re.I):
        raise ValidationError(
            'HTML и теги ссылок в тексте не допускаются. Используйте обычный текст; '
            f'не больше {max_urls} ссылок в одном сообщении.'
        )
    urls = _URL_FINDALL.findall(s)
    if len(urls) > max_urls:
        raise ValidationError(
            f'В одном сообщении не больше {max_urls} ссылок (полных адресов http(s) или www…).'
        )
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if len(lines) >= 4:
        short_url_lines = sum(
            1 for ln in lines if _URL_FINDALL.search(ln) and len(ln) < 220
        )
        if short_url_lines >= 3:
            raise ValidationError(
                'Похоже на рекламный список ссылок. Уберите лишние URL или объедините мысль в обычный текст.'
            )
    return s


def validate_comment_display_name(value: str | None, field_label: str = 'Имя') -> str:
    """Имя автора: как у регистрации + без цифр (типичные бот-ники)."""
    v = validate_person_name(value, field_label)
    if re.search(r'\d', v):
        raise ValidationError(f'{field_label}: уберите цифры из имени.')
    return v
