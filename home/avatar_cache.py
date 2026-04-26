"""Кэш URL аватара заказчика для шапки (контекст-процессор)."""

from django.core.cache import cache

HEADER_AVATAR_CACHE_TTL = 900


def header_avatar_cache_key(user_id):
    return f'user:header_avatar:{user_id}'


def invalidate_header_avatar_cache(user_id):
    if user_id:
        cache.delete(header_avatar_cache_key(user_id))
