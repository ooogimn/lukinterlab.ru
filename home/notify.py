"""
Уведомления администратору о событиях сайта: письмо на почту, Telegram и MAX (личные чаты с ботами).

Каждый канал независим: не настроен — пропускается, упал — остальные всё равно уходят, сайт не ломается.
Отправка идёт из фоновых задач django-q (home/tasks.py), чтобы посетитель не ждал.

Настройки — в .env.docker (см. env.docker.example, ввод секретов — scripts/set_notify_secrets.sh):
- почта: EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL → ADMIN_EMAIL;
- Telegram: TELEGRAM_BOT_TOKEN + TELEGRAM_NOTIFY_CHAT_ID — личный чат с ботом (не канал блога TELEGRAM_CHANNEL_ID),
  запросы идут через TELEGRAM_API_BASE (мост Cloudflare Worker, deploy/telegram-bridge/worker.js);
- MAX: MAX_BOT_TOKEN + MAX_NOTIFY_CHAT_ID — личный диалог с ботом (не канал MAX_CHAT_ID).
Проверка и поиск чатов: python manage.py notify_setup [--find-chats] [--test].
"""
import logging

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email

logger = logging.getLogger(__name__)

MAX_PLATFORM_API = "https://platform-api.max.ru"
TELEGRAM_TEXT_LIMIT = 4000  # у Telegram предел 4096 символов
MAX_TEXT_LIMIT = 3900  # у MAX предел 4000 символов
EMAIL_ATTACHMENT_LIMIT = 20 * 1024 * 1024  # больше — не прикладываем (почтовые ящики режут крупные письма)


def _truncate(text, limit):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def email_configured():
    return bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD and settings.ADMIN_EMAIL)


def telegram_configured():
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_NOTIFY_CHAT_ID)


def max_configured():
    return bool(settings.MAX_BOT_TOKEN and settings.MAX_NOTIFY_CHAT_ID)


def _valid_email_or_none(value):
    try:
        validate_email(value)
        return value
    except (ValidationError, TypeError):
        return None


def send_email(subject, text, attachments=(), reply_to=None):
    """Письмо на ADMIN_EMAIL. True/False — отправлено или нет, None — почта не настроена."""
    if not email_configured():
        return None
    try:
        reply_to = _valid_email_or_none(reply_to) if reply_to else None
        message = EmailMessage(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.ADMIN_EMAIL],
            reply_to=[reply_to] if reply_to else None,
        )
        for path, size in attachments:
            if size <= EMAIL_ATTACHMENT_LIMIT:
                message.attach_file(path)
        message.send()
        return True
    except Exception:
        logger.exception("Уведомление: письмо «%s» не отправлено", subject)
        return False


def send_telegram(text):
    """Сообщение в личный чат Telegram. True/False/None — как у send_email."""
    if not telegram_configured():
        return None
    try:
        response = requests.post(
            # TELEGRAM_API_BASE — мост Cloudflare: с VPS api.telegram.org недоступен.
            f"{settings.TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": settings.TELEGRAM_NOTIFY_CHAT_ID,
                "text": _truncate(text, TELEGRAM_TEXT_LIMIT),
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        data = response.json() if response.content else {}
        if response.ok and data.get("ok"):
            return True
        logger.error("Уведомление: Telegram ответил %s: %s", response.status_code, data.get("description"))
    except Exception as exc:
        # Текст ошибки requests содержит адрес с токеном — в лог пишем только тип.
        logger.error("Уведомление: Telegram недоступен (%s)", type(exc).__name__)
    return False


def send_max(text):
    """Сообщение в личный диалог MAX. True/False/None — как у send_email."""
    if not max_configured():
        return None
    from Blog.max_utils import _max_chat_query_value

    try:
        response = requests.post(
            f"{MAX_PLATFORM_API}/messages",
            params={"chat_id": _max_chat_query_value(settings.MAX_NOTIFY_CHAT_ID)},
            headers={"Authorization": settings.MAX_BOT_TOKEN, "Content-Type": "application/json"},
            json={"text": _truncate(text, MAX_TEXT_LIMIT)},
            timeout=15,
        )
        data = response.json() if response.content else {}
        if response.ok and not data.get("error") and data.get("success") is not False:
            return True
        logger.error("Уведомление: MAX ответил %s: %s", response.status_code, data.get("error") or data)
    except Exception as exc:
        logger.error("Уведомление: MAX недоступен (%s)", type(exc).__name__)
    return False


def notify_admin(subject, text, short_text=None, attachments=(), reply_to=None):
    """
    Во все настроенные каналы. В мессенджеры — тема + short_text (или весь text).
    attachments — список (путь к файлу, размер). Возвращает {"email": …, "telegram": …, "max": …}.
    """
    chat_text = f"{subject}\n\n{short_text or text}"
    result = {
        "email": send_email(subject, text, attachments=attachments, reply_to=reply_to),
        "telegram": send_telegram(chat_text),
        "max": send_max(chat_text),
    }
    logger.info("Уведомление «%s»: %s", subject, result)
    return result


def queue_notification(func_path, *args):
    """Поставить задачу уведомления в django-q после сохранения в БД. Ошибка не мешает посетителю."""
    from django.db import transaction

    def _enqueue():
        try:
            from django_q.tasks import async_task

            async_task(func_path, *args)
        except Exception:
            logger.exception("Уведомление: не удалось поставить задачу %s%s", func_path, args)

    transaction.on_commit(_enqueue)
