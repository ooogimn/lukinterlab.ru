import io
import logging
import re
from mimetypes import guess_type

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

VK_API_VERSION = '5.131'
# Лимит текста для wall.post (символы; полную статью всё равно только по ссылке на сайт).
MAX_VK_MESSAGE_CHARS = 3948


def _collapse_ws(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip())


def _build_vk_message(post, site_url: str) -> str:
    """
    Текст поста: заголовок + максимум текста из описания и начала статьи,
    в конце всегда полная ссылка «Читать далее» (не отрезается обрезкой с конца).
    """
    article_url = f"{site_url.rstrip('/')}{post.get_absolute_url()}"
    footer = f"\n\nЧитать далее: {article_url}"
    header = f"{(post.title or '').strip()}\n\n"
    budget = MAX_VK_MESSAGE_CHARS - len(header) - len(footer)
    if budget < 120:
        budget = 120

    desc = _collapse_ws(strip_tags(post.description or ''))
    content = _collapse_ws(strip_tags(post.content or ''))

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
        body = body[: budget - 1] + '…'

    return header + body + footer


def send_to_vk_by_id(post_id: int):
    """
    Точка входа для Django-Q: не держать HTTP-запрос на wall.post/загрузку фото
    (Passenger иначе даёт «Incomplete response received from application»).
    """
    from Blog.models import Post

    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        logger.warning('VK: статья id=%s не найдена', post_id)
        return False
    return send_to_vk(post)


def _prepare_preview_bytes(post):
    """
    Байты и имя файла для загрузки превью. WebP конвертируем в JPEG —
    иначе загрузка на стену VK часто падает.
    """
    from pathlib import Path

    name = Path(post.kartinka.name).name if post.kartinka.name else 'photo.jpg'
    data = post.kartinka.read()
    is_webp = name.lower().endswith('.webp') or (
        len(data) >= 12 and data[0:4] == b'RIFF' and data[8:12] == b'WEBP'
    )
    if is_webp:
        try:
            from PIL import Image

            im = Image.open(io.BytesIO(data)).convert('RGB')
            out = io.BytesIO()
            im.save(out, format='JPEG', quality=88)
            out.seek(0)
            return out, 'preview.jpg', 'image/jpeg'
        except Exception as e:
            logger.warning('VK: конвертация WebP → JPEG не удалась, пробуем как есть: %s', e)

    mime = guess_type(name)[0] or 'application/octet-stream'
    return io.BytesIO(data), name, mime


def send_to_vk(post):
    """
    Публикация анонса статьи на стене сообщества VK.
    Вызывается из сигнала publish_to_social при первой публикации (vk_posted_at пустой).
    """
    if not getattr(settings, 'VK_AUTO_POST', True):
        logger.debug('VK_AUTO_POST отключён, пропуск')
        return False

    if not settings.VK_ACCESS_TOKEN or not settings.VK_GROUP_ID:
        logger.warning(
            'VK: задайте VK_ACCESS_TOKEN (ключ доступа сообщества с правами wall, photos) '
            'и VK_GROUP_ID в переменных окружения / .env'
        )
        return False

    access_token = settings.VK_ACCESS_TOKEN
    group_id = int(str(settings.VK_GROUP_ID).lstrip('-'))
    site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru').rstrip('/')

    message = _build_vk_message(post, site_url)

    logger.info('VK: публикация «%s»', (post.title or '')[:80])

    attachments = []
    user_photo_tok = (getattr(settings, 'VK_USER_ACCESS_TOKEN', None) or '').strip()
    if post.kartinka:
        if user_photo_tok:
            att = _upload_wall_photo(post, user_photo_tok, group_id)
            if att:
                attachments.append(att)
        else:
            logger.warning(
                'VK: пост «%s» уйдёт в ленту без картинки: не задан VK_USER_ACCESS_TOKEN. '
                'Ключ сообщества (VK_ACCESS_TOKEN) не поддерживает загрузку фото на стену (API error 27).',
                (post.title or '')[:70],
            )

    params = {
        'owner_id': f'-{group_id}',
        'message': message,
        'access_token': access_token,
        'v': VK_API_VERSION,
        'from_group': 1,
    }
    if attachments:
        params['attachments'] = ','.join(attachments)

    try:
        post_response = requests.post(
            'https://api.vk.com/method/wall.post',
            data=params,
            timeout=30,
        )
        post_response.raise_for_status()
        post_data = post_response.json()

        if 'error' in post_data:
            logger.error('VK wall.post: %s', post_data['error'])
            return False

        raw = post_data.get('response')
        wall_post_id = None
        if isinstance(raw, dict):
            wall_post_id = raw.get('post_id')
        elif isinstance(raw, int):
            wall_post_id = raw
        try:
            wall_post_id = int(wall_post_id) if wall_post_id is not None else None
        except (TypeError, ValueError):
            wall_post_id = None

        post.vk_posted_at = timezone.now()
        update_fields = ['vk_posted_at']
        if wall_post_id is not None:
            post.vk_wall_post_id = wall_post_id
            update_fields.append('vk_wall_post_id')
        post.save(update_fields=update_fields)
        logger.info('VK: пост опубликован для «%s» (wall_post_id=%s)', (post.title or '')[:80], wall_post_id)
        return True

    except requests.RequestException as e:
        logger.error('VK wall.post сеть: %s', e)
        return False


def _upload_wall_photo(post, user_access_token: str, group_id: int):
    """
    Загрузка превью для стены сообщества.
    Токен должен быть пользовательским (админ группы); ключ сообщества даёт error 27.
    """
    try:
        upload_url_response = requests.get(
            'https://api.vk.com/method/photos.getWallUploadServer',
            params={
                'group_id': group_id,
                'access_token': user_access_token,
                'v': VK_API_VERSION,
            },
            timeout=30,
        )
        upload_url_response.raise_for_status()
        upload_url_data = upload_url_response.json()

        if 'error' in upload_url_data:
            logger.error('VK getWallUploadServer: %s', upload_url_data['error'])
            return None

        photo_upload_url = upload_url_data['response']['upload_url']

        file_obj, upload_name, mime = _prepare_preview_bytes(post)

        upload_response = requests.post(
            photo_upload_url,
            files={'photo': (upload_name, file_obj, mime)},
            timeout=120,
        )
        upload_response.raise_for_status()
        try:
            upload_data = upload_response.json()
        except ValueError:
            logger.error('VK upload photo: не JSON в ответе, статус=%s', upload_response.status_code)
            return None

        if upload_data.get('photo') in (None, '') or 'server' not in upload_data:
            logger.error('VK upload photo: плохой ответ: %s', upload_data)
            return None

        save_photo_response = requests.post(
            'https://api.vk.com/method/photos.saveWallPhoto',
            data={
                'group_id': group_id,
                'photo': upload_data['photo'],
                'server': upload_data['server'],
                'hash': upload_data['hash'],
                'access_token': user_access_token,
                'v': VK_API_VERSION,
            },
            timeout=30,
        )
        save_photo_response.raise_for_status()
        save_photo_data = save_photo_response.json()

        if 'error' in save_photo_data:
            logger.error('VK saveWallPhoto: %s', save_photo_data['error'])
            return None

        saved = save_photo_data['response'][0]
        owner_id = saved['owner_id']
        photo_id = saved['id']
        att = f'photo{owner_id}_{photo_id}'
        logger.info('VK: превью прикреплено к посту (%s)', att)
        return att

    except Exception as e:
        logger.exception('VK: не удалось прикрепить фото, пост будет только текстом: %s', e)
        return None
