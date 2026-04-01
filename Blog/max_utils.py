"""
Автопостинг анонсов статей в мессенджер MAX (HTTP API platform-api.max.ru).
Текст собирается так же, как для VK: заголовок, описание + начало статьи, ссылка «Читать далее».
"""
import logging

import requests
from django.conf import settings
from django.utils import timezone

from Blog.vk_utils import (
    _html_or_markdown_to_plain,
    _strip_common_prefix,
    _truncate_at_word_boundary,
    is_test_article_description,
)

logger = logging.getLogger(__name__)

MAX_PLATFORM_API = 'https://platform-api.max.ru'
# Поле text в POST /messages — до 4000 символов; оставляем запас под заголовок и футер.
MAX_MESSAGE_TOTAL_CHARS = 3980


def _build_max_message(post, site_url: str) -> str:
    article_url = f"{site_url.rstrip('/')}{post.get_absolute_url()}"
    footer = f"\n\nЧитать далее: {article_url}"
    header = f"{(post.title or '').strip()}\n\n"
    budget = MAX_MESSAGE_TOTAL_CHARS - len(header) - len(footer)
    if budget < 120:
        budget = 120

    raw_desc = post.description or ''
    if is_test_article_description(raw_desc):
        desc = ''
    else:
        desc = _html_or_markdown_to_plain(raw_desc)

    content = _html_or_markdown_to_plain(post.content or '')
    _, content = _strip_common_prefix(desc, content)

    body = desc[:budget] if desc else ''
    used = len(body)
    rem = budget - used
    if rem > 80 and content:
        sep = '\n\n' if body else ''
        chunk = content[: rem - len(sep)]
        if chunk:
            body = f"{body}{sep}{chunk}" if body else chunk

    body = body.strip()
    if len(body) > budget:
        body = _truncate_at_word_boundary(body, budget)

    return header + body + footer


def _max_chat_query_value(raw):
    """API ожидает chat_id в query; в кабинете часто целое число."""
    if raw is None or raw == '':
        return None
    s = str(raw).strip()
    try:
        return int(s)
    except ValueError:
        return s


def send_to_max_by_id(post_id: int):
    """Точка входа для Django-Q."""
    from Blog.models import Post

    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        logger.warning('MAX: статья id=%s не найдена', post_id)
        return False
    return send_to_max(post)


def send_to_max(post):
    """
    Публикация анонса в чат/канал MAX. Успех → max_posted_at.
    """
    if not getattr(settings, 'MAX_AUTO_POST', False):
        logger.debug('MAX_AUTO_POST отключён, пропуск')
        return False

    token = (getattr(settings, 'MAX_BOT_TOKEN', None) or '').strip()
    chat_raw = getattr(settings, 'MAX_CHAT_ID', None)
    chat_id = _max_chat_query_value(chat_raw)

    if not token or chat_id is None:
        logger.warning(
            'MAX: задайте MAX_BOT_TOKEN и MAX_CHAT_ID в .env / окружении '
            '(business.max.ru → Чат-боты → Интеграция → токен; id чата из интерфейса бота).'
        )
        return False

    post.refresh_from_db(fields=['max_posted_at', 'status', 'title', 'description', 'content', 'slug', 'category_id'])
    if post.max_posted_at:
        logger.debug('MAX: «%s» уже отмечен как отправленный', (post.title or '')[:80])
        return True
    if post.status != 'published':
        return False

    site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru').rstrip('/')
    text = _build_max_message(post, site_url)

    if len(text) > 4000:
        text = text[:3997] + '…'

    logger.info('MAX: отправка анонса «%s»', (post.title or '')[:80])

    url = f"{MAX_PLATFORM_API.rstrip('/')}/messages"
    try:
        r = requests.post(
            url,
            params={'chat_id': chat_id},
            headers={
                'Authorization': token,
                'Content-Type': 'application/json',
            },
            json={
                'text': text,
                'disable_link_preview': False,
            },
            timeout=30,
        )
        r.raise_for_status()
        try:
            data = r.json()
        except ValueError:
            data = None

        if isinstance(data, dict) and data.get('error'):
            logger.error('MAX API: %s', data.get('error'))
            return False

        post.max_posted_at = timezone.now()
        post.save(update_fields=['max_posted_at'])
        logger.info('MAX: сообщение отправлено для «%s»', (post.title or '')[:80])
        return True

    except requests.RequestException as e:
        logger.error('MAX: сеть / HTTP: %s', e)
        if getattr(e, 'response', None) is not None and e.response is not None:
            try:
                logger.error('MAX: тело ответа: %s', e.response.text[:500])
            except Exception:
                pass
        return False
