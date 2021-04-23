"""cache.py"""
import asyncio
import math
from datetime import timedelta
from functools import wraps
from http import HTTPStatus
from typing import Union

from fastapi import Response

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
            """Return cached value if one exists, otherwise evaluate the wrapped function and cache the result."""

            func_kwargs = kwargs.copy()
            request = func_kwargs.pop("request", None)
            response = func_kwargs.pop("response", None)
            create_response_directly = False
            if not response:
                response = Response()
                create_response_directly = True
            redis_cache = FastApiRedisCache()

            # if the redis client is not connected or request is not cacheable, no caching behavior is performed.
            if redis_cache.not_connected or redis_cache.request_is_not_cacheable(request):
                return await get_api_response_async(func, *args, **kwargs)
            key = redis_cache.get_cache_key(func, *args, **kwargs)
            ttl, in_cache = redis_cache.check_cache(key)
            if in_cache:
                if redis_cache.requested_resource_not_modified(request, in_cache):
                    response.status_code = HTTPStatus.NOT_MODIFIED
                    return response
                cached_data = redis_cache.deserialize_json(in_cache)
                redis_cache.set_response_headers(response, cache_hit=True, response_data=cached_data, ttl=ttl)
                if create_response_directly:
                    return Response(content=in_cache, media_type="application/json", headers=response.headers)
                return cached_data
            response_data = await get_api_response_async(func, *args, **kwargs)
            redis_cache.add_to_cache(key, response_data, expire_after_seconds, expire_after_milliseconds)
            ttl = calculate_ttl(expire_after_seconds, expire_after_milliseconds)
            redis_cache.set_response_headers(response, cache_hit=False, response_data=response_data, ttl=ttl)
            if create_response_directly:
                return Response(
                    content=redis_cache.serialize_json(response_data),
                    media_type="application/json",
                    headers=response.headers,
                )
            return response_data

        return inner_wrapper

    return outer_wrapper


async def get_api_response_async(func, *args, **kwargs):
    """Helper function that allows decorator to work with both async and non-async functions."""
    return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)


def calculate_ttl(expire_s, expire_ms):
    if (not expire_s and not expire_ms) or (expire_s == 0 and expire_ms == 0):
        return -1
    expire_s = expire_s or 0
    expire_ms = expire_ms or 0
    ttl = expire_s + math.floor(expire_ms / 1000)
    return ttl or 1
