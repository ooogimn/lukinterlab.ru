"""
Обёртка над Django RedisCache: при недоступном Redis, read-only реплике и т.п.
логируем и ведём себя как пустой кэш, чтобы HTTP-запросы не превращались в 500.

Django-Q по-прежнему использует свой клиент Redis из Q_CLUSTER — очередь без Redis
не заведётся; это только про CACHE (страницы, context processors, cache.set/get).
"""
import logging

from django.core.cache.backends.redis import RedisCache, RedisCacheClient

logger = logging.getLogger(__name__)

try:
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover
    RedisError = Exception  # type: ignore[misc, assignment]

_SAFE_EXC = (RedisError, OSError)


def _log(op: str, exc: BaseException) -> None:
    logger.warning("Redis cache %s: %s (работа без кэша)", op, exc)


class ResilientRedisCacheClient(RedisCacheClient):
    def get(self, key, default):
        try:
            return super().get(key, default)
        except _SAFE_EXC as e:
            _log("get", e)
            return default

    def set(self, key, value, timeout):
        try:
            super().set(key, value, timeout)
        except _SAFE_EXC as e:
            _log("set", e)

    def add(self, key, value, timeout):
        try:
            return super().add(key, value, timeout)
        except _SAFE_EXC as e:
            _log("add", e)
            return False

    def touch(self, key, timeout):
        try:
            return super().touch(key, timeout)
        except _SAFE_EXC as e:
            _log("touch", e)
            return False

    def delete(self, key):
        try:
            return super().delete(key)
        except _SAFE_EXC as e:
            _log("delete", e)
            return False

    def get_many(self, keys):
        try:
            return super().get_many(keys)
        except _SAFE_EXC as e:
            _log("get_many", e)
            return {}

    def has_key(self, key):
        try:
            return super().has_key(key)
        except _SAFE_EXC as e:
            _log("has_key", e)
            return False

    def incr(self, key, delta):
        try:
            return super().incr(key, delta)
        except _SAFE_EXC as e:
            _log("incr", e)
            raise ValueError("Redis cache unavailable for incr") from e

    def set_many(self, data, timeout):
        try:
            super().set_many(data, timeout)
        except _SAFE_EXC as e:
            _log("set_many", e)

    def delete_many(self, keys):
        try:
            super().delete_many(keys)
        except _SAFE_EXC as e:
            _log("delete_many", e)

    def clear(self):
        try:
            return super().clear()
        except _SAFE_EXC as e:
            _log("clear", e)
            return False


class ResilientRedisCache(RedisCache):
    """Тот же RedisCache, но с ResilientRedisCacheClient."""

    def __init__(self, server, params):
        super().__init__(server, params)
        self._class = ResilientRedisCacheClient
