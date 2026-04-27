from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass
class ResolvedMedia:
    kind: str
    source_url: str
    embed_url: str | None = None
    autoplay_embed_url: str | None = None
    thumbnail_url: str | None = None
    provider: str = "unknown"


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _path_ext(path: str) -> str:
    if "." not in path:
        return ""
    return "." + path.rsplit(".", 1)[-1].lower()


def _resolve_youtube(parsed) -> ResolvedMedia | None:
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    query = parse_qs(parsed.query)
    video_id = ""

    if "youtu.be" in host and path:
        video_id = path.split("/")[0]
    elif "youtube.com" in host:
        if path == "watch":
            video_id = (query.get("v") or [""])[0]
        elif path.startswith("embed/"):
            video_id = path.split("/", 1)[1]
        elif path.startswith("shorts/"):
            video_id = path.split("/", 1)[1]

    if not video_id:
        return None

    embed_url = f"https://www.youtube.com/embed/{video_id}"
    return ResolvedMedia(
        kind="video",
        source_url=parsed.geturl(),
        embed_url=embed_url,
        autoplay_embed_url=f"{embed_url}?autoplay=1&mute=1&muted=1&controls=0&loop=1&playlist={video_id}&playsinline=1",
        thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        provider="youtube",
    )


def _resolve_rutube(parsed) -> ResolvedMedia | None:
    host = parsed.netloc.lower()
    if "rutube.ru" not in host:
        return None
    path = parsed.path.strip("/")
    video_id = ""
    if path.startswith("video/"):
        rest = path.split("/", 1)[1]
        video_id = rest.split("/")[0]
    if not video_id:
        return None
    embed_url = f"https://rutube.ru/play/embed/{video_id}/"
    return ResolvedMedia(
        kind="video",
        source_url=parsed.geturl(),
        embed_url=embed_url,
        autoplay_embed_url=f"{embed_url}?autoplay=1&muted=1&mute=1&controls=0",
        provider="rutube",
    )


def _resolve_vk_video(parsed) -> ResolvedMedia | None:
    host = parsed.netloc.lower()
    if "vk.com" not in host:
        return None
    path = parsed.path.strip("/")
    if not path.startswith("video"):
        return None

    value = path[len("video") :]
    if "_" not in value:
        return None
    oid, vid = value.split("_", 1)
    if not oid or not vid:
        return None
    embed_url = f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hd=2"
    return ResolvedMedia(
        kind="video",
        source_url=parsed.geturl(),
        embed_url=embed_url,
        autoplay_embed_url=f"{embed_url}&autoplay=1&mute=1",
        provider="vkvideo",
    )


def resolve_external_media(url: str) -> ResolvedMedia | None:
    if not url:
        return None
    raw = url.strip()
    if not _is_http_url(raw):
        return None

    parsed = urlparse(raw)
    ext = _path_ext(parsed.path)
    if ext in IMAGE_EXTENSIONS:
        return ResolvedMedia(kind="image", source_url=raw, thumbnail_url=raw, provider="image-url")

    youtube = _resolve_youtube(parsed)
    if youtube:
        return youtube
    rutube = _resolve_rutube(parsed)
    if rutube:
        return rutube
    vkvideo = _resolve_vk_video(parsed)
    if vkvideo:
        return vkvideo

    return None
