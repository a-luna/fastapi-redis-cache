"""redis.py"""
import os
from typing import Tuple

import redis
from fakeredis import FakeRedis
from pydantic import RedisDsn

from fastapi_redis_cache.enums import RedisStatus


def redis_connect(host_url: RedisDsn) -> Tuple[RedisStatus, redis.client.Redis]:
    """Attempt to connect to `host_url` and return a Redis client instance if successful."""
    return _connect(host_url) if os.environ.get("CACHE_ENV") != "TEST" else _connect_fake()


def _connect(host_url: RedisDsn) -> Tuple[RedisStatus, redis.client.Redis]:
    try:
        redis_client = redis.from_url(host_url)
        if redis_client.ping():
            return (RedisStatus.CONNECTED, redis_client)
        return (RedisStatus.CONN_ERROR, None)
    except redis.RedisAuthenticationError:
        return (RedisStatus.AUTH_ERROR, None)


def _connect_fake() -> Tuple[RedisStatus, redis.client.Redis]:
    return (RedisStatus.CONNECTED, FakeRedis())
