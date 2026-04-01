"""
Автопостинг анонсов статей в мессенджер MAX (HTTP API platform-api.max.ru).
Текст собирается так же, как для VK: заголовок, описание + начало статьи, ссылка «Читать далее».
Превью статьи (post.kartinka): POST /uploads?type=image → multipart на выданный url → attachments в POST /messages.
"""
import logging
import time

import requests
from django.conf import settings
from django.utils import timezone

from Blog.vk_utils import (
    _html_or_markdown_to_plain,
    _prepare_preview_bytes,
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


def _max_image_payload_from_upload_response(uploaded: dict):
    """
    Из тела ответа после multipart-загрузки картинки — payload для вложения type=image.
    См. PhotoTokens / PhotoAttachmentRequestPayload в клиенте MAX (token | photos).
    """
    if not isinstance(uploaded, dict):
        return None
    photos = uploaded.get('photos')
    if isinstance(photos, dict) and photos:
        normalized = {}
        for key, val in photos.items():
            k = str(key)
            if isinstance(val, str):
                normalized[k] = {'token': val}
            elif isinstance(val, dict) and val.get('token'):
                normalized[k] = val
            else:
                normalized[k] = val
        return {'photos': normalized}
    tok = uploaded.get('token')
    if tok:
        return {'token': tok}
    if uploaded.get('url') or uploaded.get('photo_id') is not None:
        out = {}
        if 'photo_id' in uploaded:
            out['photo_id'] = uploaded['photo_id']
        if uploaded.get('token'):
            out['token'] = uploaded['token']
        if uploaded.get('url'):
            out['url'] = uploaded['url']
        if out:
            return out
    return None


def _max_build_image_attachment(token: str, image_bytes: bytes, filename: str, mime: str):
    """
    POST /uploads?type=image, затем POST на upload url с полем data (multipart).
    Возвращает элемент для messages.attachments или None при ошибке.
    """
    base = MAX_PLATFORM_API.rstrip('/')
    try:
        up = requests.post(
            f'{base}/uploads',
            params={'type': 'image'},
            headers={'Authorization': token},
            timeout=30,
        )
        up.raise_for_status()
        meta = up.json()
    except (requests.RequestException, ValueError) as e:
        logger.error('MAX: /uploads (image): %s', e)
        return None

    upload_url = meta.get('url') if isinstance(meta, dict) else None
    if not upload_url:
        logger.error('MAX: /uploads (image): нет url в ответе: %s', meta)
        return None

    try:
        ul = requests.post(
            upload_url,
            headers={'Authorization': token},
            files={'data': (filename, image_bytes, mime or 'image/jpeg')},
            timeout=120,
        )
        ul.raise_for_status()
        try:
            uploaded = ul.json()
        except ValueError:
            logger.error('MAX: ответ загрузки картинки не JSON: %s', (ul.text or '')[:400])
            return None
    except requests.RequestException as e:
        logger.error('MAX: загрузка файла на CDN: %s', e)
        if getattr(e, 'response', None) is not None and e.response is not None:
            try:
                logger.error('MAX: тело ответа CDN: %s', (e.response.text or '')[:400])
            except Exception:
                pass
        return None

    payload = _max_image_payload_from_upload_response(uploaded)
    if not payload:
        logger.error('MAX: не разобрать payload картинки: %s', uploaded)
        return None
    return {'type': 'image', 'payload': payload}


def _max_response_attachment_not_ready(response: requests.Response) -> bool:
    try:
        data = response.json()
    except ValueError:
        return False
    if not isinstance(data, dict):
        return False
    if data.get('code') == 'attachment.not.ready':
        return True
    msg = (data.get('message') or '') if isinstance(data.get('message'), str) else ''
    return 'attachment.not.processed' in msg or 'attachment.file.not.processed' in msg


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
        logger.warning('MAX: пропуск — MAX_AUTO_POST=False (включите в .env на сервере)')
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

    post.refresh_from_db(
        fields=[
            'max_posted_at',
            'status',
            'title',
            'description',
            'content',
            'slug',
            'category_id',
            'kartinka',
        ]
    )
    if post.max_posted_at:
        logger.info('MAX: «%s» уже с max_posted_at, повторная отправка пропущена', (post.title or '')[:80])
        return True
    if post.status != 'published':
        logger.warning('MAX: пост id=%s не published, отправка отменена', post.pk)
        return False

    site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru').rstrip('/')
    text = _build_max_message(post, site_url)

    if len(text) > 4000:
        text = text[:3997] + '…'

    logger.info('MAX: отправка анонса «%s»', (post.title or '')[:80])

    image_attachment = None
    if post.kartinka:
        try:
            file_obj, upload_name, mime = _prepare_preview_bytes(post)
            raw = file_obj.read()
            image_attachment = _max_build_image_attachment(token, raw, upload_name, mime)
            if not image_attachment:
                logger.warning('MAX: «%s» — картинка не прикреплена, уходит только текст', (post.title or '')[:80])
            else:
                logger.info('MAX: «%s» — вложение image подготовлено (upload + payload)', (post.title or '')[:80])
        except Exception as e:
            logger.warning('MAX: превью (kartinka) не подготовилось, только текст: %s', e)
    else:
        logger.info(
            'MAX: «%s» — поле kartinka пустое, в MAX уходит только текст (без attachments image)',
            (post.title or '')[:80],
        )

    url = f"{MAX_PLATFORM_API.rstrip('/')}/messages"
    body = {'text': text}
    if image_attachment:
        body['attachments'] = [image_attachment]

    # После загрузки файла API рекомендует паузу; при attachment.not.ready — повтор с бэкоффом.
    backoff_seconds = (1.5, 2.5, 4.0, 8.0, 16.0)
    delays = list(backoff_seconds) if image_attachment else [0]
    try:
        for attempt, wait in enumerate(delays):
            if wait:
                time.sleep(wait)
            r = requests.post(
                url,
                params={'chat_id': chat_id},
                headers={
                    'Authorization': token,
                    'Content-Type': 'application/json',
                },
                json=body,
                timeout=30,
            )

            data = None
            if r.content:
                try:
                    data = r.json()
                except ValueError:
                    data = None

            err_obj = data.get('error') if isinstance(data, dict) else None
            if isinstance(err_obj, dict) and err_obj.get('code') == 'attachment.not.ready':
                if attempt < len(delays) - 1:
                    logger.warning('MAX: attachment.not.ready, попытка %s/%s', attempt + 1, len(delays))
                    continue

            if r.ok:
                if isinstance(data, dict):
                    if err_obj:
                        logger.error('MAX API: %s', err_obj)
                        return False
                    if data.get('success') is False:
                        logger.error('MAX API success=false: %s', data)
                        return False
                post.max_posted_at = timezone.now()
                post.save(update_fields=['max_posted_at'])
                logger.info('MAX: сообщение отправлено для «%s»', (post.title or '')[:80])
                return True

            if _max_response_attachment_not_ready(r) and attempt < len(delays) - 1:
                logger.warning(
                    'MAX: attachment.not.ready (HTTP %s), повтор %s/%s',
                    r.status_code,
                    attempt + 1,
                    len(delays),
                )
                continue

            r.raise_for_status()
            return False

        logger.error('MAX: не удалось отправить после %s попыток (attachment.not.ready)', len(delays))
        return False

    except requests.RequestException as e:
        logger.error('MAX: сеть / HTTP: %s', e)
        if getattr(e, 'response', None) is not None and e.response is not None:
            try:
                logger.error('MAX: тело ответа: %s', e.response.text[:500])
            except Exception:
                pass
        return False
