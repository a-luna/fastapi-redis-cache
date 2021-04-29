"""cache.py"""
import asyncio
from datetime import timedelta
from functools import partial, update_wrapper, wraps
from http import HTTPStatus
from typing import Union

from fastapi import Response

from fastapi_redis_cache.client import FastApiRedisCache
from fastapi_redis_cache.util import (
    deserialize_json,
    ONE_DAY_IN_SECONDS,
    ONE_HOUR_IN_SECONDS,
    ONE_MONTH_IN_SECONDS,
    ONE_WEEK_IN_SECONDS,
    ONE_YEAR_IN_SECONDS,
    serialize_json,
)


def cache(*, expire: Union[int, timedelta] = ONE_YEAR_IN_SECONDS):
    """Enable caching behavior for the decorated function.

    Args:
        expire (Union[int, timedelta], optional): The number of seconds
            from now when the cached response should expire. Defaults to 31,536,000
            seconds (i.e., the number of seconds in one year).
    """

    def outer_wrapper(func):
        @wraps(func)
        async def inner_wrapper(*args, **kwargs):
            """Return cached value if one exists, otherwise evaluate the wrapped function and cache the result."""

            func_kwargs = kwargs.copy()
            request = func_kwargs.pop("request", None)
            response = func_kwargs.pop("response", None)
            create_response_directly = not response
            if create_response_directly:
                response = Response()
            redis_cache = FastApiRedisCache()
            if redis_cache.not_connected or redis_cache.request_is_not_cacheable(request):
                # if the redis client is not connected or request is not cacheable, no caching behavior is performed.
                return await get_api_response_async(func, *args, **kwargs)
            key = redis_cache.get_cache_key(func, *args, **kwargs)
            ttl, in_cache = redis_cache.check_cache(key)
            if in_cache:
                if redis_cache.requested_resource_not_modified(request, in_cache):
                    response.status_code = int(HTTPStatus.NOT_MODIFIED)
                    return response
                cached_data = deserialize_json(in_cache)
                redis_cache.set_response_headers(response, cache_hit=True, response_data=cached_data, ttl=ttl)
                if create_response_directly:
                    return Response(content=in_cache, media_type="application/json", headers=response.headers)
                return cached_data
            response_data = await get_api_response_async(func, *args, **kwargs)
            ttl = calculate_ttl(expire)
            cached = redis_cache.add_to_cache(key, response_data, ttl)
            if cached:
                redis_cache.set_response_headers(response, cache_hit=False, response_data=response_data, ttl=ttl)
            if create_response_directly:
                return Response(
                    content=serialize_json(response_data),
                    media_type="application/json",
                    headers=response.headers,
                )
            return response_data

        return inner_wrapper

    return outer_wrapper


async def get_api_response_async(func, *args, **kwargs):
    """Helper function that allows decorator to work with both async and non-async functions."""
    return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)


def calculate_ttl(expire: Union[int, timedelta]) -> int:
    if isinstance(expire, timedelta):
        expire = int(expire.total_seconds())
    return min(expire, ONE_YEAR_IN_SECONDS)


cache_one_minute = partial(cache, expire=60)
cache_one_hour = partial(cache, expire=ONE_HOUR_IN_SECONDS)
cache_one_day = partial(cache, expire=ONE_DAY_IN_SECONDS)
cache_one_week = partial(cache, expire=ONE_WEEK_IN_SECONDS)
cache_one_month = partial(cache, expire=ONE_MONTH_IN_SECONDS)
cache_one_year = partial(cache, expire=ONE_YEAR_IN_SECONDS)

update_wrapper(cache_one_minute, cache)
update_wrapper(cache_one_hour, cache)
update_wrapper(cache_one_day, cache)
update_wrapper(cache_one_week, cache)
update_wrapper(cache_one_month, cache)
update_wrapper(cache_one_year, cache)
