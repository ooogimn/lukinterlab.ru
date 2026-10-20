"""Хранилище статики с хэшем в именах файлов (style.css → style.3f2a9c1b7e4d.css).

Зачем: nginx отдаёт такие файлы с кэшем браузера на год — повторные визиты не качают
CSS/JS заново, а после деплоя у файла меняется хэш, и браузер сразу берёт свежую версию.

«Мягкий» режим, чтобы деплой и страницы не падали:
- битые url()/sourceMappingURL в чужих CSS/JS (jazzmin, ckeditor и т.п.) оставляются как есть,
  а не роняют collectstatic (он выполняется при старте контейнера web);
- {% static %} на файл, которого нет в манифесте, отдаёт обычный путь, а не 500.
"""
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class LenientManifestStaticFilesStorage(ManifestStaticFilesStorage):
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            # Файл, на который ссылается CSS/JS, не найден — оставляем ссылку без хэша.
            return name
