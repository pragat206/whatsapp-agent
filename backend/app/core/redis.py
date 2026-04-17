"""Shared Redis client + distributed locking primitive."""
from __future__ import annotations

import contextlib
import secrets
import time
from typing import Iterator

import redis
from redis import Redis

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


@contextlib.contextmanager
def lock(key: str, ttl_ms: int = 30_000, wait_ms: int = 5_000) -> Iterator[bool]:
    """Acquire a best-effort distributed lock. Yields True if acquired."""
    r = get_redis()
    token = secrets.token_hex(16)
    deadline = time.monotonic() + (wait_ms / 1000.0)
    acquired = False
    while True:
        if r.set(key, token, nx=True, px=ttl_ms):
            acquired = True
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.05)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                r.eval(_RELEASE_SCRIPT, 1, key, token)
            except Exception:  # noqa: BLE001
                pass
