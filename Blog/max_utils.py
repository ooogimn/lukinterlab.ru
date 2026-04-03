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
    _truncate_to_word_count,
    is_test_article_description,
)

logger = logging.getLogger(__name__)

MAX_PLATFORM_API = 'https://platform-api.max.ru'
# Поле text в POST /messages — до 4000 символов; оставляем запас под заголовок и футер.
MAX_MESSAGE_TOTAL_CHARS = 3980


def _build_max_message(post, site_url: str) -> str:
    include_link = getattr(settings, 'SOCIAL_INCLUDE_ARTICLE_LINK', True)
    footer = ''
    if include_link:
        try:
            article_url = f"{site_url.rstrip('/')}{post.get_absolute_url()}"
            footer = f"\n\nЧитать далее: {article_url}"
        except Exception:
            footer = ''
    header = f"{(post.title or '').strip()}\n\n"
    budget = MAX_MESSAGE_TOTAL_CHARS - len(header) - len(footer or '')
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

    max_words = getattr(settings, 'SOCIAL_ANNOUNCE_MAX_WORDS', 100)
    if max_words > 0:
        body = _truncate_to_word_count(body, max_words)

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
            resp_text = (ul.text or '').strip()
            logger.error('MAX: ответ загрузки картинки не JSON: %s', resp_text[:400])
            # Если это XML с retval, попробуем понять, успех ли это
            if '<retval>' in resp_text:
                logger.info('MAX: ответ загрузки картинки похож на XML: %s', resp_text)
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

def _max_build_video_attachment(api_token: str, file_path: str, mime: str):
    """
    POST /uploads?type=video → POST на выданный url с полем data (multipart).
    По документации MAX: второй запрос на CDN идёт без Authorization; токен для вложения
    может прийти в ответе шага 2 как {"token": "..."} либо уже в шаге 1 вместе с url.
    В POST /messages для video нужен payload вида {"token": "..."}.
    """
    import os

    base = MAX_PLATFORM_API.rstrip('/')
    pre_token = None
    try:
        up = requests.post(
            f'{base}/uploads',
            params={'type': 'video'},
            headers={'Authorization': api_token},
            timeout=30,
        )
        up.raise_for_status()
        meta = up.json()
    except (requests.RequestException, ValueError) as e:
        logger.error('MAX: /uploads (video): %s', e)
        return None

    if not isinstance(meta, dict):
        logger.error('MAX: /uploads (video): некорректный ответ: %s', meta)
        return None

    upload_url = meta.get('url')
    pre_token = meta.get('token')
    if pre_token and isinstance(pre_token, str):
        pre_token = pre_token.strip() or None

    if not upload_url:
        logger.error('MAX: /uploads (video): нет url в ответе: %s', meta)
        return None

    upload_headers = {}
    # Официальный пример MAX не передаёт Authorization на CDN upload URL (достаточно query sig).
    mime = mime or 'video/mp4'
    file_name = os.path.basename(file_path) or 'video.mp4'

    try:
        with open(file_path, 'rb') as f:
            ul = requests.post(
                upload_url,
                headers=upload_headers,
                files={'data': (file_name, f, mime)},
                timeout=600,
            )
        ul.raise_for_status()
        body_text = (ul.text or '').strip()
        uploaded = None
        if body_text:
            try:
                uploaded = ul.json()
            except ValueError:
                uploaded = None
    except requests.RequestException as e:
        logger.error('MAX: загрузка видео на CDN: %s', e)
        if getattr(e, 'response', None) is not None and e.response is not None:
            try:
                logger.error('MAX: тело ответа CDN (видео): %s', (e.response.text or '')[:500])
            except Exception:
                pass
        return None

    tok = None
    if isinstance(uploaded, dict):
        tok = uploaded.get('token')
        if isinstance(tok, str):
            tok = tok.strip() or None

    if not tok and pre_token:
        tok = pre_token
        logger.info('MAX: токен видео взят из ответа POST /uploads (шаг 1)')

    if not tok and body_text:
        logger.error('MAX: ответ загрузки видео без token: %s', body_text[:500])
        if '<retval>1</retval>' in body_text and pre_token:
            tok = pre_token
            logger.info('MAX: CDN вернул retval без JSON — используем pre_token из /uploads')

    if not tok:
        logger.error('MAX: не удалось получить token для video-приложения')
        return None

    return {'type': 'video', 'payload': {'token': tok}}


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
            'video_file',
            'video',
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

    from Blog.social_video import get_local_video_path_and_mime

    media_attachment = None
    video_path, video_mime = get_local_video_path_and_mime(post)
    if video_path:
        try:
            media_attachment = _max_build_video_attachment(token, video_path, video_mime or 'video/mp4')
            if not media_attachment:
                logger.warning('MAX: «%s» — видео не прикреплено, уходит только текст', (post.title or '')[:80])
            else:
                logger.info('MAX: «%s» — вложение video подготовлено', (post.title or '')[:80])
        except Exception as e:
            logger.warning('MAX: видео не загрузилось: %s', e)
    elif post.kartinka:
        try:
            file_obj, upload_name, mime = _prepare_preview_bytes(post)
            raw = file_obj.read()
            media_attachment = _max_build_image_attachment(token, raw, upload_name, mime)
            if not media_attachment:
                logger.warning('MAX: «%s» — картинка не прикреплена, уходит только текст', (post.title or '')[:80])
            else:
                logger.info('MAX: «%s» — вложение image подготовлено (upload + payload)', (post.title or '')[:80])
        except Exception as e:
            logger.warning('MAX: превью (kartinka) не подготовилось, только текст: %s', e)
    else:
        logger.info(
            'MAX: «%s» — поле kartinka и video пустое, в MAX уходит только текст',
            (post.title or '')[:80],
        )

    url = f"{MAX_PLATFORM_API.rstrip('/')}/messages"
    body = {'text': text}
    if media_attachment:
        body['attachments'] = [media_attachment]

    # После загрузки видео MAX дольше обрабатывает файл — увеличиваем первые паузы.
    if media_attachment and media_attachment.get('type') == 'video':
        delays = [3.0, 5.0, 8.0, 16.0, 24.0]
    elif media_attachment:
        delays = [1.5, 2.5, 4.0, 8.0, 16.0]
    else:
        delays = [0]
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
