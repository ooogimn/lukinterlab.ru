import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

VK_API_VERSION = '5.131'
# Лимит текста поста VK (с запасом по UTF-8)
MAX_MESSAGE_LENGTH = 3800


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
    group_id = str(settings.VK_GROUP_ID).lstrip('-')
    site_url = getattr(settings, 'SITE_URL', 'https://lukinterlab.ru').rstrip('/')

    message = f"{post.title}\n\n"
    if post.description:
        plain = strip_tags(post.description).strip()
        if plain:
            message += f"{plain}\n\n"
    message += f"Читать далее: {site_url}{post.get_absolute_url()}"

    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[: MAX_MESSAGE_LENGTH - 1] + '…'

    logger.info('VK: публикация «%s»', post.title[:80])

    attachments = []
    if post.kartinka:
        att = _upload_wall_photo(post, access_token, group_id)
        if att:
            attachments.append(att)

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
        post_response = requests.get(
            'https://api.vk.com/method/wall.post',
            params=params,
            timeout=30,
        )
        post_response.raise_for_status()
        post_data = post_response.json()

        if 'error' in post_data:
            logger.error('VK wall.post: %s', post_data['error'])
            return False

        post.vk_posted_at = timezone.now()
        post.save(update_fields=['vk_posted_at'])
        logger.info('VK: пост опубликован для «%s»', post.title[:80])
        return True

    except requests.RequestException as e:
        logger.error('VK wall.post сеть: %s', e)
        return False


def _upload_wall_photo(post, access_token, group_id):
    """Загрузка превью на сервер VK, возвращает строку вложения photo{owner_id}_{id}."""
    try:
        upload_url_response = requests.get(
            'https://api.vk.com/method/photos.getWallUploadServer',
            params={
                'group_id': group_id,
                'access_token': access_token,
                'v': VK_API_VERSION,
            },
            timeout=30,
        )
        upload_url_response.raise_for_status()
        upload_url_data = upload_url_response.json()

        if 'error' in upload_url_data:
            logger.warning('VK getWallUploadServer: %s', upload_url_data['error'])
            return None

        photo_upload_url = upload_url_data['response']['upload_url']

        with post.kartinka.open('rb') as photo_file:
            upload_response = requests.post(
                photo_upload_url,
                files={'photo': photo_file},
                timeout=120,
            )
        upload_response.raise_for_status()
        upload_data = upload_response.json()

        if upload_data.get('photo') in (None, '') or 'server' not in upload_data:
            logger.warning('VK upload photo: неожиданный ответ загрузки')
            return None

        save_photo_response = requests.get(
            'https://api.vk.com/method/photos.saveWallPhoto',
            params={
                'group_id': group_id,
                'photo': upload_data['photo'],
                'server': upload_data['server'],
                'hash': upload_data['hash'],
                'access_token': access_token,
                'v': VK_API_VERSION,
            },
            timeout=30,
        )
        save_photo_response.raise_for_status()
        save_photo_data = save_photo_response.json()

        if 'error' in save_photo_data:
            logger.warning('VK saveWallPhoto: %s', save_photo_data['error'])
            return None

        saved = save_photo_data['response'][0]
        owner_id = saved['owner_id']
        photo_id = saved['id']
        return f'photo{owner_id}_{photo_id}'

    except Exception as e:
        logger.warning('VK: не удалось прикрепить фото, пост будет только текстом: %s', e)
        return None
