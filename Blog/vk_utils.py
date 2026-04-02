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


def strip_test_article_marker(text: str) -> str:
    """Убирает служебную пометку тестовой генерации в любом месте строки."""
    if not text:
        return ''
    return re.sub(r'\[TEST_ARTICLE\]\s*', '', text, flags=re.I).strip()


def is_test_article_description(text: str) -> bool:
    return bool(text and re.search(r'\[TEST_ARTICLE\]', text, re.I))


def _html_or_markdown_to_plain(text: str) -> str:
    """Грубая очистка для анонса VK: HTML, Markdown-разметка, служебные метки, без схлопывания в одну строку."""
    if not text:
        return ''
    t = strip_test_article_marker(text)
    t = strip_tags(t)
    # Остатки угловых скобок после strip_tags
    t = re.sub(r'<[^>]+>', '', t)
    # Markdown: решётки, жирность/курсив без аккуратного парсинга
    t = re.sub(r'#+\s*', '', t)
    t = re.sub(r'[*_]{1,3}', '', t)
    # Разделители «---», длинные тире
    t = re.sub(r'\s*[—\-]{2,}\s*', '\n', t)
    # Маркеры списков в начале строки
    t = re.sub(r'(?m)^\s*[-*]\s+', '', t)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    t = '\n\n'.join(lines)
    return re.sub(r'\n{3,}', '\n\n', t).strip()


def _truncate_at_word_boundary(text: str, max_chars: int) -> str:
    """Обрезка по лимиту VK без обрыва на полуслове (если возможно)."""
    if max_chars < 8 or len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rstrip()
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0].rstrip()
    return cut + '…'


def _truncate_to_word_count(text: str, max_words: int) -> str:
    """Обрезка текста по числу слов (разделитель — пробельные символы); хвост «…» при обрезке."""
    if max_words <= 0 or not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    return ' '.join(words[:max_words]) + '…'


def _strip_common_prefix(a: str, b: str, min_len: int = 80) -> tuple[str, str]:
    """Если b начинается с теми же словами, что и a — отрезаем префикс у b (анонс без дубля)."""
    if not a or not b or len(a) < min_len:
        return a, b
    al = a.lower()
    bl = b.lower()
    if bl.startswith(al[: min(len(al), 600)]):
        return a, b[len(a) :].strip()
    # Совпадение по первым словам (описание часто = начало статьи)
    aw = a.split()
    if len(aw) < 12:
        return a, b
    prefix = ' '.join(aw[:20])
    if len(prefix) >= min_len and bl.startswith(prefix.lower()):
        return a, b[len(prefix) :].lstrip(' ,.;—-')
    return a, b


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

    raw_desc = post.description or ''
    # Тест из дашборда: в description попадает [TEST_ARTICLE] и часто дубль начала статьи в Markdown —
    # для VK берём анонс только из тела (после заголовка поста).
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
    Байты для загрузки превью в VK и MAX: единый альбомный кадр (по умолчанию 1200×630),
    масштаб с центр-обрезкой (ImageOps.fit), затем JPEG. И квадрат, и вертикаль — приводятся к одному формату.
    """
    from pathlib import Path

    name = Path(post.kartinka.name).name if post.kartinka.name else 'photo.jpg'
    data = post.kartinka.read()

    w = int(getattr(settings, 'SOCIAL_SHARE_IMAGE_WIDTH', 1200))
    h = int(getattr(settings, 'SOCIAL_SHARE_IMAGE_HEIGHT', 630))
    if w < 320 or h < 180:
        w, h = 1200, 630

    try:
        from PIL import Image, ImageOps

        im = Image.open(io.BytesIO(data))
        im.load()

        if im.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', im.size, (255, 255, 255))
            if im.mode == 'RGBA':
                background.paste(im, mask=im.split()[3])
            else:
                background.paste(im, mask=im.split()[1])
            im = background
        elif im.mode == 'P':
            im = im.convert('RGBA')
            background = Image.new('RGB', im.size, (255, 255, 255))
            background.paste(im, mask=im.split()[3])
            im = background
        elif im.mode != 'RGB':
            im = im.convert('RGB')

        # Возвращаем жесткую обрезку (как было изначально)
        fitted = ImageOps.fit(
            im,
            (w, h),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        
        out = io.BytesIO()
        fitted.save(out, format='JPEG', quality=88, optimize=True)
        out.seek(0)
        return out, 'social_preview.jpg', 'image/jpeg'
    except Exception as e:
        logger.warning('Соц. превью: PIL-нормализация не удалась (%s), запасной путь', e)

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
    
    if post.video_file:
        att = _upload_wall_video(post, user_photo_tok or access_token, group_id)
        if att:
            attachments.append(att)
        else:
            logger.warning('VK: не удалось загрузить видео, возможно токен не имеет прав video')
    elif post.kartinka:
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

def _upload_wall_video(post, access_token: str, group_id: int):
    """
    Загрузка видео для стены сообщества.
    Токен должен иметь права "video".
    """
    try:
        if not post.video_file:
            return None
            
        # 1. Получаем URL для загрузки видео
        save_response = requests.post(
            'https://api.vk.com/method/video.save',
            data={
                'name': (post.title or '')[:128],
                'description': (post.meta_description or '')[:200],
                'group_id': group_id,
                'wallpost': 0, # Прикрепим видео сами к посту
                'access_token': access_token,
                'v': VK_API_VERSION,
            },
            timeout=30,
        )
        save_response.raise_for_status()
        save_data = save_response.json()
        
        if 'error' in save_data:
            logger.error('VK video.save error: %s', save_data['error'])
            return None
            
        upload_url = save_data['response']['upload_url']
        video_id = save_data['response']['video_id']
        owner_id = save_data['response']['owner_id']
        
        # 2. Загружаем сам файл
        with open(post.video_file.path, 'rb') as f:
            upload_response = requests.post(
                upload_url,
                files={'video_file': f},
                timeout=600, # Видео может грузиться долго
            )
            upload_response.raise_for_status()
            try:
                upload_data = upload_response.json()
            except ValueError:
                logger.error('VK upload video: не JSON в ответе, статус=%s', upload_response.status_code)
                return None
                
            if 'error' in upload_data and upload_data.get('size', 1) == 0:
                logger.warning('VK upload video странная ошибка (size=0, но возможно загружено): %s', upload_data)
                
        # 3. Формируем строку attachment
        att = f'video{owner_id}_{video_id}'
        logger.info('VK: видео прикреплено к посту (%s)', att)
        return att
        
    except Exception as e:
        logger.exception('VK: не удалось прикрепить видео: %s', e)
        return None

