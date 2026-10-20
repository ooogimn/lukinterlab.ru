"""
Раздача файлов из MEDIA_ROOT с проверкой прав для приватных папок.

Приватные папки (PRIVATE_MEDIA_PREFIXES) nginx не отдаёт сам, а передаёт запрос
в Django (deploy/nginx-lukinterlab.conf). Здесь проверяются права, а сам файл
отдаёт nginx по заголовку X-Accel-Redirect через внутренний location
/_protected_media/ — быстро и с поддержкой Range (перемотка видео).
Адреса файлов (/media/...) при этом не меняются.

Кто что видит:
- wiki/ (Блокнот), contact_attachments/ — только сотрудники (staff);
- order_files/ — сотрудники и владелец заказа;
- customer_avatars/ — сотрудники и сам клиент.
Остальные папки /media/ (портфолио, блог, видео, отзывы…) публичные.
"""
import mimetypes
import posixpath
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, HttpResponse, HttpResponseNotFound
from django.utils._os import safe_join
from django.utils.http import content_disposition_header
from django.views.static import serve

PRIVATE_MEDIA_PREFIXES = ("wiki", "contact_attachments", "order_files", "customer_avatars")

# Эти файлы загружают посетители сайта: отдаём только как скачивание, чтобы
# подложенный HTML/SVG не выполнился в браузере сотрудника на нашем домене.
DOWNLOAD_ONLY_PREFIXES = ("contact_attachments", "order_files")

# Внутренний location nginx (internal; alias на папку media/).
X_ACCEL_MEDIA_LOCATION = "/_protected_media/"


def _normalize(path):
    """Путь внутри MEDIA_ROOT или None, если он подозрительный (.., //, \\, NUL)."""
    if not path or "\x00" in path or "\\" in path:
        return None
    normalized = posixpath.normpath(path)
    if normalized != path or normalized.startswith(("/", "..")):
        return None
    return normalized


def _is_staff(user):
    return user.is_authenticated and user.is_active and user.is_staff


def can_access_private_media(user, path):
    """Может ли пользователь получить приватный файл по пути внутри MEDIA_ROOT."""
    if _is_staff(user):
        return True
    if not user.is_authenticated:
        return False
    prefix = path.split("/", 1)[0]
    if prefix == "order_files":
        from home.models import OrderFile

        return OrderFile.objects.filter(file=path, order__customer__user=user).exists()
    if prefix == "customer_avatars":
        from home.models import Customer

        return Customer.objects.filter(avatar=path, user=user).exists()
    # wiki/ и contact_attachments/ — только сотрудники.
    return False


def _private_file_response(path):
    """Ответ с файлом: на проде — X-Accel-Redirect (файл отдаёт nginx), локально — сам Django."""
    as_attachment = path.split("/", 1)[0] in DOWNLOAD_ONLY_PREFIXES
    filename = posixpath.basename(path)

    if not getattr(settings, "PRIVATE_MEDIA_X_ACCEL", not settings.DEBUG):
        try:
            full_path = safe_join(settings.MEDIA_ROOT, path)
            response = FileResponse(open(full_path, "rb"), as_attachment=as_attachment, filename=filename)
        except (OSError, ValueError):
            return HttpResponseNotFound()
    else:
        response = HttpResponse()
        # Заголовки Content-Type, Content-Disposition и Cache-Control nginx сохраняет
        # при X-Accel-Redirect, поэтому выставляем их здесь.
        response["Content-Type"] = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        # Кириллица в пути: заголовок должен быть ASCII, nginx сам раскодирует %XX.
        response["X-Accel-Redirect"] = X_ACCEL_MEDIA_LOCATION + quote(path)
        if as_attachment:
            response["Content-Disposition"] = content_disposition_header(True, filename)

    # private — не кэшировать на промежуточных прокси (фронтенд Jino), только в браузере.
    response["Cache-Control"] = "private, max-age=3600"
    return response


def media_file(request, path):
    """
    /media/<path>: приватные папки — только с правами, остальное — как обычная раздача медиа.

    На проде публичные /media/ отдаёт nginx и сюда они не доходят; маршрут нужен для
    приватных папок, для локальной разработки (DEBUG) и как запасной вариант.
    """
    normalized = _normalize(path)
    if normalized is None:
        return HttpResponseNotFound()

    if normalized.split("/", 1)[0] in PRIVATE_MEDIA_PREFIXES:
        # Нет прав — 404 без подробностей (не выдаём, существует ли файл).
        # Http404 не используем: handler404 сайта перенаправляет на блог.
        if not can_access_private_media(request.user, normalized):
            return HttpResponseNotFound()
        return _private_file_response(normalized)

    return serve(request, normalized, document_root=settings.MEDIA_ROOT)
