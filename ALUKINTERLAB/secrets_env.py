"""
Чтение настроек из переменных окружения и опционально из файла .env в корне проекта.
Секреты не хранятся в репозитории — только имена переменных в env.example.
"""
from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def load_env_file(base_dir: Path) -> None:
    """Подхватывает BASE_DIR/.env, если установлен python-dotenv."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = base_dir / ".env"
    if env_path.is_file():
        load_dotenv(env_path)


def _get(key: str, default: str | None = None) -> str | None:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return default
    return str(v).strip()


def env_str(key: str, default: str = "") -> str:
    v = _get(key)
    return v if v is not None else default


def env_bool(key: str, default: bool = False) -> bool:
    v = _get(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def env_int(key: str, default: int | None = None) -> int | None:
    v = _get(key)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def require_secret_key() -> str:
    """DJANGO_SECRET_KEY или SECRET_KEY (оба имени поддерживаются)."""
    key = _get("DJANGO_SECRET_KEY") or _get("SECRET_KEY")
    if not key:
        raise ImproperlyConfigured(
            "Задайте переменную окружения DJANGO_SECRET_KEY (или SECRET_KEY). "
            "Пример в env.example. Сгенерировать: "
            "python -c \"from django.core.management.utils import get_random_secret_key; "
            "print(get_random_secret_key())\""
        )
    return key


def split_hosts(value: str | None, fallback: str) -> list[str]:
    raw = value if (value and value.strip()) else fallback
    return [h.strip() for h in raw.split(",") if h.strip()]


def split_origins(value: str | None, site_url: str) -> list[str]:
    """CSV URL для CSRF; если пусто — SITE_URL и вариант с www."""
    if value and value.strip():
        return [o.strip() for o in value.split(",") if o.strip()]
    base = site_url.rstrip("/")
    if not base:
        return []
    out: list[str] = [base]
    for prefix in ("https://", "http://"):
        if base.startswith(prefix) and "://www." not in base:
            host = base[len(prefix) :]
            out.append(f"{prefix}www.{host}")
            break
    return out
