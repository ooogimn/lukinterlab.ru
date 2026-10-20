"""Пережать уже загруженные видео (то же, что происходит автоматически после новой загрузки).

На проде (из каталога /srv/lukinterlab.ru):
    docker compose exec -T qcluster python manage.py transcode_videos --dry-run
    nohup docker compose exec -T qcluster python manage.py transcode_videos > /root/transcode.log 2>&1 &

Оригиналы не удаляются. Повторный запуск пропускает уже пережатое (журнал VideoTranscodeJob).
"""
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from pathlib import Path

from home import video_processing as vp


class Command(BaseCommand):
    help = 'Пережать загруженные видео для сайта (H.264 до 1080p + превью + обложка), оригиналы сохраняются'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать, что будет пережато')
        parser.add_argument('--limit', type=int, default=0, help='Обработать не больше N файлов')

    def handle(self, *args, **options):
        todo = {}  # source_name -> mute (mute, только если файл используется лишь как фон секции)
        for app_label, model_name, field, mute in vp.VIDEO_FIELDS:
            model = apps.get_model(app_label, model_name)
            names = (
                model.objects.exclude(**{f'{field}__isnull': True})
                .exclude(**{field: ''})
                .values_list(field, flat=True)
            )
            for name in names:
                if vp.is_video_name(name) and not vp.is_processed_name(name):
                    todo[name] = todo.get(name, True) and mute

        items = sorted(todo.items())
        if options['limit']:
            items = items[: options['limit']]
        total_mb = 0.0
        for name, mute in items:
            path = Path(settings.MEDIA_ROOT) / name
            size_mb = path.stat().st_size / 1048576 if path.is_file() else 0
            total_mb += size_mb
            self.stdout.write(f'  {size_mb:7.1f} МБ  {"(без звука) " if mute else ""}{name}')
        self.stdout.write(f'Видео к пережатию: {len(items)}, всего {total_mb:.0f} МБ')

        if options['dry_run']:
            return
        if not vp.ffmpeg_available():
            self.stderr.write('ffmpeg/ffprobe не найдены — запускайте в контейнере qcluster/web.')
            return

        from home.models import VideoTranscodeJob

        for index, (name, mute) in enumerate(items, 1):
            self.stdout.write(f'[{index}/{len(items)}] {name} …')
            self.stdout.flush()
            try:
                result = vp.process_video(name, mute)
            except Exception as exc:  # noqa: BLE001 — один сбойный файл не останавливает остальные
                result = f'error: {exc}'
            job = VideoTranscodeJob.objects.filter(source_name=name).first()
            if job and job.status == VideoTranscodeJob.STATUS_DONE and job.source_size and job.result_size:
                self.stdout.write(
                    f'    {result}: {job.source_size / 1048576:.1f} → {job.result_size / 1048576:.1f} МБ'
                )
            else:
                self.stdout.write(f'    {result}{": " + job.error[-300:] if job and job.error else ""}')
            self.stdout.flush()
        self.stdout.write('Готово.')
