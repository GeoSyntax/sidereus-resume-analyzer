import json
import time
from typing import Any

from app.config import settings


class CacheClient:
    def __init__(self) -> None:
        self.ttl = settings.cache_ttl_seconds
        self._memory: dict[str, tuple[float, dict[str, Any]]] = {}
        self._redis = self._build_redis()

    def get(self, key: str) -> dict[str, Any] | None:
        if self._redis:
            try:
                value = self._redis.get(key)
                return json.loads(value) if value else None
            except Exception:
                pass

        item = self._memory.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._memory.pop(key, None)
            return None
        return value

    def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        ttl = ttl or self.ttl
        if self._redis:
            try:
                self._redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))
                return
            except Exception:
                pass
        self._memory[key] = (time.time() + ttl, value)

    @staticmethod
    def _build_redis() -> Any | None:
        if not settings.redis_url:
            return None
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

