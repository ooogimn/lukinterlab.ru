"""
VK Callback API сообщества (https://dev.vk.com/ru/api/community-events/json-schema).
Подтверждение: POST с type=confirmation → тело ответа строго строка из кабинета (не JSON, без кавычек и лишних символов).
В теле запроса 5.x часто есть secret — при заданном VK_CALLBACK_SECRET проверяем и для confirmation.
"""
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _plain(text: str, status: int = 200) -> HttpResponse:
    return HttpResponse(text, status=status, content_type='text/plain')


def _parse_json_body(raw: bytes):
    for enc in ('utf-8-sig', 'utf-8', 'cp1251'):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return None


def _group_id_match(body_gid, settings_gid) -> bool:
    """Сравнение group_id из JSON и VK_GROUP_ID (int или строка, допускается минус у owner)."""
    try:
        a = abs(int(str(body_gid).replace('-', '').strip()))
        b = abs(int(str(settings_gid).replace('-', '').strip()))
        return a == b
    except (TypeError, ValueError):
        return False


def _sanitize_confirmation(token: str) -> str:
    # Как в кабинете VK, без смены регистра и без пробелов/BOM.
    return (token or '').strip().strip('\ufeff')


@csrf_exempt
@require_POST
def vk_group_callback(request, slug: str):
    slug_expected = (getattr(settings, 'VK_CALLBACK_PATH_SLUG', None) or '').strip()
    confirmation = _sanitize_confirmation(
        (getattr(settings, 'VK_CALLBACK_CONFIRMATION', None) or '').strip()
    )
    secret_expected = (getattr(settings, 'VK_CALLBACK_SECRET', None) or '').strip()

    if not slug_expected or not confirmation:
        logger.warning('VK Callback: не заданы VK_CALLBACK_PATH_SLUG или VK_CALLBACK_CONFIRMATION')
        return _plain('callback not configured', status=503)
    if slug != slug_expected:
        return _plain('not found', status=404)

    body = _parse_json_body(request.body)
    if body is None:
        logger.warning('VK Callback: невалидный JSON, len=%s', len(request.body))
        return _plain('bad json', status=400)

    if body.get('type') == 'confirmation':
        if not _group_id_match(body.get('group_id'), settings.VK_GROUP_ID):
            logger.warning(
                'VK Callback: confirmation group_id=%s ожидался %s',
                body.get('group_id'),
                settings.VK_GROUP_ID,
            )
            return _plain('group', status=403)
        if secret_expected and body.get('secret') != secret_expected:
            logger.warning('VK Callback: неверный secret при confirmation')
            return _plain('secret', status=403)
        try:
            payload = confirmation.encode('ascii')
            ct = 'text/plain; charset=us-ascii'
        except UnicodeEncodeError:
            payload = confirmation.encode('utf-8')
            ct = 'text/plain; charset=utf-8'
        return HttpResponse(payload, status=200, content_type=ct)

    if secret_expected and body.get('secret') != secret_expected:
        logger.warning('VK Callback: invalid secret for type=%s', body.get('type'))
        return _plain('secret', status=403)

    logger.debug('VK Callback: %s', body.get('type'))
    return _plain('ok')
