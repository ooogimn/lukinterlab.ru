"""
Локальный файл видео для соцсетей: поле video_file или встраивание в HTML поля Post.video (CKEditor).
"""
import logging
import mimetypes
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

_VIDEO_RE = re.compile(
    r'(?:src|href)=["\']([^"\']+\.(?:mp4|webm|mov|mkv)(?:\?[^"\']*)?)["\']',
    re.IGNORECASE,
)


def get_local_video_path_and_mime(post) -> Tuple[Optional[str], str]:
    """
    Возвращает (абсолютный путь к файлу, mime) или (None, '') если видео не найдено локально.
    """
    vf = getattr(post, 'video_file', None)
    if vf and getattr(vf, 'name', None):
        try:
            path = vf.path
            if path and Path(path).is_file():
                mime = mimetypes.guess_type(path)[0] or 'video/mp4'
                return path, mime
        except Exception as e:
            logger.warning('social_video: video_file недоступен: %s', e)

    html = (getattr(post, 'video', None) or '').strip()
    if not html:
        return None, ''

    m = _VIDEO_RE.search(html)
    if not m:
        return None, ''

    raw = m.group(1).strip()
    if raw.startswith('//'):
        raw = 'https:' + raw
    parsed = urlparse(raw)
    path_part = parsed.path or ''

    media_root = Path(getattr(settings, 'MEDIA_ROOT', '') or '')
    if not media_root.exists():
        return None, ''

    if path_part.startswith('/media/'):
        rel = path_part[len('/media/') :].lstrip('/')
    elif '/media/' in path_part:
        rel = path_part.split('/media/', 1)[1].lstrip('/')
    else:
        return None, ''

    local = media_root / rel
    if not local.is_file():
        return None, ''

    mime = mimetypes.guess_type(str(local))[0] or 'video/mp4'
    return str(local.resolve()), mime
