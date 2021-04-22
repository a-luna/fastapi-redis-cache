"""cache.py"""
import asyncio
import math
from datetime import timedelta
from functools import wraps
from http import HTTPStatus
from typing import Union

from fastapi_redis_cache.client import FastApiRedisCache


def cache(
    *,
    expire_after_seconds: Union[int, timedelta] = None,
    expire_after_milliseconds: Union[int, timedelta] = None,
):
    """Enable caching behavior for the decorated function.

    If no arguments are provided, this marks the response data for the decorated
    path function as "never expires". In this case, the `Expires` and
    `Cache-Control max-age`  headers will be set to expire after one year.
    Historically, this was the furthest time in the future that was allowed for
    these fields. This is no longer the case, but it is still not advisable to use
    values greater than one year.

    Args:
        expire_after_seconds (Union[int, timedelta], optional): The number of seconds
            from now when the cached response should expire. Defaults to None.
        expire_after_milliseconds (Union[int, timedelta], optional): The number of
            milliseconds from now when the cached response should expire. Defaults to None.
    """

    def outer_wrapper(func):
        @wraps(func)
        async def inner_wrapper(*args, **kwargs):
            """Return cached value if one exists, otherwise the value returned by the function is added to the cache."""
            func_kwargs = kwargs.copy()
            request = func_kwargs.pop("request", None)
            response = func_kwargs.pop("response", None)
            redis_cache = FastApiRedisCache()
            if not redis_cache.connected:
                # if the redis client is not connected to the server, no caching behavior is performed.
                return await get_api_response_async(func, *args, **kwargs)
            if not redis_cache.request_is_cacheable(request):
                return await get_api_response_async(func, *args, **kwargs)

            key = redis_cache.get_cache_key(func, *args, **kwargs)
            ttl, in_cache = redis_cache.check_cache(key)
            if in_cache:
                cached_data = redis_cache.deserialize_json(in_cache)
                if response and redis_cache.requested_resource_not_modified(request, cached_data):
                    response.status_code = HTTPStatus.NOT_MODIFIED
                    return response
                if response:
                    redis_cache.set_response_headers(response, cache_hit=True, response_data=cached_data, ttl=ttl)
                return redis_cache.deserialize_json(in_cache)
            response_data = await get_api_response_async(func, *args, **kwargs)
            redis_cache.add_to_cache(key, response_data, expire_after_seconds, expire_after_milliseconds)
            if response:
                ttl = calculate_ttl(expire_after_seconds, expire_after_milliseconds)
                redis_cache.set_response_headers(response, cache_hit=False, response_data=response_data, ttl=ttl)
            return response_data

        def calculate_ttl(expire_s=0, expire_ms=0):
            if not expire_s and not expire_ms:
                return -1
            ttl = expire_s + math.floor(expire_ms / 1000)
            return ttl or 1

        async def get_api_response_async(func, *args, **kwargs):
            """Helper function that allows decorator to work with both async and non-async functions."""
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        return inner_wrapper

    return outer_wrapper
