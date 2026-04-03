#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _load_root_env() -> None:
    """Загрузить корневой .env до импорта Django (Windows BOM, ранние переменные)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path, encoding="utf-8-sig")


def _should_skip_preflight(argv: list[str]) -> bool:
    """Команды вроде --version не требуют PostgreSQL/Redis в окружении."""
    if len(argv) < 2:
        return False
    cmd = argv[1]
    if cmd in ("--version", "--help", "-h"):
        return True
    if cmd == "version" and len(argv) == 2:
        return True
    if cmd == "help" and len(argv) == 2:
        return True
    return False


def _preflight_required_env() -> None:
    """
    Обязательные ключи как в ALUKINTERLAB/settings.py.
    Иначе execute_from_command_line глотает ImproperlyConfigured при первом доступе к
    INSTALLED_APPS и позже падает на проверке CSRF с неочевидным стеком.
    """
    secret = (os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY") or "").strip()
    pg = (
        (os.environ.get("POSTGRES_DB") or "").strip(),
        (os.environ.get("POSTGRES_USER") or "").strip(),
        (os.environ.get("POSTGRES_HOST") or "").strip(),
    )
    redis_url = (os.environ.get("REDIS_URL") or "").strip()
    missing = []
    if not secret:
        missing.append("DJANGO_SECRET_KEY (или SECRET_KEY)")
    if not all(pg):
        missing.append("POSTGRES_DB, POSTGRES_USER, POSTGRES_HOST")
    if not redis_url:
        missing.append("REDIS_URL")
    if missing:
        sys.stderr.write(
            "Задайте в корневом .env (шаблон env.example):\n  • "
            + "\n  • ".join(missing)
            + "\nФайл: %s\n" % (Path(__file__).resolve().parent / ".env")
        )
        sys.exit(1)


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ALUKINTERLAB.settings")
    _load_root_env()
    if not _should_skip_preflight(sys.argv):
        _preflight_required_env()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
