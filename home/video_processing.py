"""Пережатие загруженных видео для сайта (ffmpeg, фоном через django-q).

Зачем: в портфолио грузили ролики по 15–100 МБ (до 4K), браузер качал их целиком.
После загрузки видео рядом с оригиналом появляются:
  <имя>_web.mp4      — H.264 до 1080p (вертикальное — до 1080×1920), AAC, +faststart
                       (играет до полной загрузки, перемотка через Range);
  <имя>_preview.mp4  — 8 с, до 720p, без звука — лёгкое превью для карточек;
  <имя>_web.jpg      — обложка (кадр из видео) для poster.
Поле модели переключается на _web.mp4. ОРИГИНАЛ НЕ УДАЛЯЕТСЯ и не перемещается
(на него могут ссылаться статьи; чистка — отдельно, когда настроен бэкап).

Одновременно пережимается одно видео (flock) с пониженным приоритетом (nice),
чтобы не тормозить сайт на 2 ядрах. Журнал — модель VideoTranscodeJob (админка).
Старые видео: python manage.py transcode_videos
"""
import json
import logging
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage

try:  # на Windows (локальная разработка) fcntl нет — там ffmpeg и не запускаем
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = ('.mp4', '.webm', '.mov', '.m4v', '.ogg', '.ogv', '.avi', '.mkv')
WEB_SUFFIX = '_web.mp4'
POSTER_SUFFIX = '_web.jpg'
PREVIEW_SUFFIX = '_preview.mp4'

# (app_label, модель, поле) — все поля, куда загружают видео. mute=True — звук не нужен (фон секции).
VIDEO_FIELDS = (
    ('home', 'Rabota', 'preview_video', False),
    ('home', 'RabotaMedia', 'file', False),
    ('home', 'SectionBackground', 'background_video', True),
    ('Blog', 'Post', 'video_file', False),
)

LOCK_PATH = '/tmp/lukinterlab-video-transcode.lock'
FFMPEG_TIMEOUT_SEC = 3 * 3600
PREVIEW_SECONDS = 8


def is_video_name(name):
    return bool(name) and name.lower().endswith(VIDEO_EXTENSIONS)


def is_processed_name(name):
    return bool(name) and (name.endswith(WEB_SUFFIX) or name.endswith(PREVIEW_SUFFIX))


def ffmpeg_available():
    return bool(fcntl and shutil.which('ffmpeg') and shutil.which('ffprobe'))


def _base_name(name):
    return name.rsplit('.', 1)[0]


def derived_urls(file_field):
    """(poster_url, preview_url) для уже пережатого видео, иначе (None, None)."""
    name = getattr(file_field, 'name', '') or ''
    if not name.endswith(WEB_SUFFIX):
        return None, None
    base = name[: -len(WEB_SUFFIX)]
    poster = base + POSTER_SUFFIX
    preview = base + PREVIEW_SUFFIX
    poster_url = default_storage.url(poster) if default_storage.exists(poster) else None
    preview_url = default_storage.url(preview) if default_storage.exists(preview) else None
    return poster_url, preview_url


@contextmanager
def _transcode_lock():
    """Одно пережатие за раз на весь сервер (воркеры qcluster + management-команда)."""
    with open(LOCK_PATH, 'w') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _run(cmd):
    proc = subprocess.run(
        ['nice', '-n', '10', *cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=FFMPEG_TIMEOUT_SEC,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode('utf-8', 'replace')[-1500:]
        raise RuntimeError(f'{cmd[0]} exit {proc.returncode}: {tail}')
    return proc.stdout


def probe(path):
    out = _run([
        'ffprobe', '-v', 'error', '-print_format', 'json',
        '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height',
        str(path),
    ])
    data = json.loads(out or b'{}')
    streams = data.get('streams') or []
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if not video:
        raise RuntimeError('в файле нет видеодорожки')
    return {
        'width': int(video.get('width') or 0),
        'height': int(video.get('height') or 0),
        'vcodec': video.get('codec_name') or '',
        'has_audio': any(s.get('codec_type') == 'audio' for s in streams),
        'duration': float((data.get('format') or {}).get('duration') or 0),
    }


def _box(info, long_side, short_side):
    """Рамка вписывания с учётом ориентации (вертикальные ролики не сплющиваем до 1080 по высоте)."""
    if info['height'] > info['width']:
        return short_side, long_side
    return long_side, short_side


def _scale_filter(box_w, box_h):
    return (
        f"scale='min({box_w},iw)':'min({box_h},ih)'"
        ':force_original_aspect_ratio=decrease:force_divisible_by=2,format=yuv420p'
    )


def _transcode_files(src, base_abs, info, mute):
    """Создаёт _web.mp4, _preview.mp4, _web.jpg. Пишет во временные файлы, затем os.replace."""
    web = Path(base_abs + WEB_SUFFIX)
    preview = Path(base_abs + PREVIEW_SUFFIX)
    poster = Path(base_abs + POSTER_SUFFIX)

    box_w, box_h = _box(info, 1920, 1080)
    web_tmp = web.with_name(web.name + '.part.mp4')
    cmd = [
        'ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(src),
        '-map', '0:v:0',
        '-vf', _scale_filter(box_w, box_h), '-fpsmax', '30',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26' if not mute else '28',
        '-maxrate', '5M', '-bufsize', '10M', '-profile:v', 'high',
        '-threads', '2',
    ]
    if info['has_audio'] and not mute:
        cmd += ['-map', '0:a:0', '-c:a', 'aac', '-b:a', '128k', '-ac', '2']
    else:
        cmd += ['-an']
    cmd += ['-movflags', '+faststart', str(web_tmp)]
    _run(cmd)

    # Если исходник уже был лёгким H.264 и пережатие его не уменьшило — берём исходник
    # как есть, только переупаковываем с faststart (без потери качества).
    src_size = src.stat().st_size
    if web_tmp.stat().st_size >= src_size and info['vcodec'] == 'h264' and src.suffix.lower() in ('.mp4', '.mov', '.m4v'):
        remux_tmp = web.with_name(web.name + '.remux.mp4')
        try:
            remux = ['ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(src), '-map', '0:v:0']
            remux += ['-map', '0:a:0?'] if not mute else ['-an']
            remux += ['-c', 'copy', '-movflags', '+faststart', str(remux_tmp)]
            _run(remux)
            os.replace(remux_tmp, web_tmp)
        except Exception:  # noqa: BLE001 — остаёмся на пережатой версии
            logger.warning('VIDEO: remux %s не удался, оставляем пережатую версию', src, exc_info=True)
            remux_tmp.unlink(missing_ok=True)
    os.replace(web_tmp, web)

    pw, ph = _box(info, 720, 720)
    preview_tmp = preview.with_name(preview.name + '.part.mp4')
    _run([
        'ffmpeg', '-hide_banner', '-nostdin', '-y', '-i', str(web), '-t', str(PREVIEW_SECONDS),
        '-map', '0:v:0', '-an', '-vf', _scale_filter(pw, ph), '-fpsmax', '24',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '30', '-maxrate', '1200k', '-bufsize', '2400k',
        '-threads', '2', '-movflags', '+faststart', str(preview_tmp),
    ])
    os.replace(preview_tmp, preview)

    seek = f"{min(1.0, max(0.0, info['duration'] * 0.1)):.2f}"
    poster_tmp = poster.with_name(poster.name + '.part.jpg')
    _run([
        'ffmpeg', '-hide_banner', '-nostdin', '-y', '-ss', seek, '-i', str(web),
        '-frames:v', '1', '-vf', "scale='min(1280,iw)':-2", '-q:v', '4', str(poster_tmp),
    ])
    os.replace(poster_tmp, poster)
    return web


def update_references(source_name, result_name):
    """Переключить все поля, где лежит source_name, на result_name (.update — без сигналов)."""
    total = 0
    for app_label, model_name, field, _mute in VIDEO_FIELDS:
        model = apps.get_model(app_label, model_name)
        total += model.objects.filter(**{field: source_name}).update(**{field: result_name})
    return total


def _references_exist(source_name):
    for app_label, model_name, field, _mute in VIDEO_FIELDS:
        model = apps.get_model(app_label, model_name)
        if model.objects.filter(**{field: source_name}).exists():
            return True
    return False


def enqueue_video(source_name, mute=False):
    """Поставить видео в очередь django-q (не дублируя уже стоящее/идущее задание)."""
    from django_q.tasks import async_task

    from .models import VideoTranscodeJob

    job, created = VideoTranscodeJob.objects.get_or_create(source_name=source_name)
    if not created and job.status in (VideoTranscodeJob.STATUS_QUEUED, VideoTranscodeJob.STATUS_PROCESSING):
        return False
    if not created and job.status == VideoTranscodeJob.STATUS_DONE and job.result_name:
        update_references(source_name, job.result_name)
        return False
    job.status = VideoTranscodeJob.STATUS_QUEUED
    job.error = ''
    job.save(update_fields=['status', 'error', 'updated'])
    async_task(
        'home.video_processing.process_video', source_name, mute,
        task_name=f'video:{source_name}'[:100],
        timeout=FFMPEG_TIMEOUT_SEC,
    )
    return True


def process_video(source_name, mute=False):
    """Задача django-q и management-команды. Идемпотентна: повтор не пережимает заново."""
    from .models import VideoTranscodeJob

    if not ffmpeg_available():
        logger.warning('VIDEO: ffmpeg недоступен, пропуск %s', source_name)
        return 'no-ffmpeg'

    with _transcode_lock():
        job, _ = VideoTranscodeJob.objects.get_or_create(source_name=source_name)
        if job.status == VideoTranscodeJob.STATUS_DONE and job.result_name and default_storage.exists(job.result_name):
            update_references(source_name, job.result_name)
            return 'already-done'
        if not _references_exist(source_name):
            job.status = VideoTranscodeJob.STATUS_SKIPPED
            job.error = 'на файл больше не ссылается ни одна запись'
            job.save(update_fields=['status', 'error', 'updated'])
            return 'skipped'

        src = Path(settings.MEDIA_ROOT) / source_name
        if not src.is_file():
            job.status = VideoTranscodeJob.STATUS_FAILED
            job.error = f'файл не найден: {src}'
            job.save(update_fields=['status', 'error', 'updated'])
            return 'missing'

        job.status = VideoTranscodeJob.STATUS_PROCESSING
        job.source_size = src.stat().st_size
        job.error = ''
        job.save(update_fields=['status', 'source_size', 'error', 'updated'])
        try:
            info = probe(src)
            job.duration_sec = info['duration']
            base_abs = str(Path(settings.MEDIA_ROOT) / _base_name(source_name))
            web = _transcode_files(src, base_abs, info, mute)
        except Exception as exc:  # noqa: BLE001
            logger.exception('VIDEO: не удалось пережать %s', source_name)
            job.status = VideoTranscodeJob.STATUS_FAILED
            job.error = str(exc)[-2000:]
            job.save(update_fields=['status', 'duration_sec', 'error', 'updated'])
            return 'failed'

        result_name = _base_name(source_name) + WEB_SUFFIX
        job.result_name = result_name
        job.result_size = web.stat().st_size
        job.status = VideoTranscodeJob.STATUS_DONE
        job.save(update_fields=['result_name', 'result_size', 'status', 'duration_sec', 'updated'])
        refs = update_references(source_name, result_name)
        logger.info(
            'VIDEO: %s → %s (%.1f → %.1f МБ), ссылок обновлено: %s',
            source_name, result_name, job.source_size / 1048576, job.result_size / 1048576, refs,
        )
        return 'done'
