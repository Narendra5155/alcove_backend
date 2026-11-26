"""Shared Redis client for app data (OTP challenges, live GEO positions)."""
from functools import lru_cache

import redis
from django.conf import settings


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_APP_URL, decode_responses=True)
