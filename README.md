## `fastapi-redis-cache`

[![PyPI version](https://badge.fury.io/py/fastapi-redis-cache.svg)](https://badge.fury.io/py/fastapi-redis-cache) ![PyPI - Downloads](https://img.shields.io/pypi/dm/fastapi-redis-cache?color=%234DC71F) ![PyPI - License](https://img.shields.io/pypi/l/fastapi-redis-cache?color=%25234DC71F) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/fastapi-redis-cache) [![Maintainability](https://api.codeclimate.com/v1/badges/4a1753c77add039c3850/maintainability)](https://codeclimate.com/github/a-luna/fastapi-redis-cache/maintainability) [![codecov](https://codecov.io/gh/a-luna/fastapi-redis-cache/branch/master/graph/badge.svg)](https://codecov.io/gh/a-luna/fastapi-redis-cache)


### Installation

`pip install fastapi-redis-cache`

### Usage

On startup, initialize the cache with the URL of the Redis server. The name of the custom header field used to identify cache hits/misses can also be customized. If `response_header` is not specified, the custom header field will be named `X-FastAPI-Cache`

```python
import os

from fastapi import FastAPI, Request, Response
from fastapi_redis_cache import FastApiRedisCache, cache

LOCAL_REDIS_URL = "redis://127.0.0.1:6379"
CACHE_HEADER = "X-MyAPI-Cache"

app = FastAPI(title="FastAPI Redis Cache Example")

@app.on_event("startup")
def startup():
    redis_cache = FastApiRedisCache()
    redis_cache.connect(
        host_url=os.environ.get("REDIS_URL", LOCAL_REDIS_URL),
        response_header=CACHE_HEADER
    )
```

Even if the cache has been initialized, you must apply the `@cache` decorator to each route to enable caching:

```python
# WILL NOT be cached
@app.get("/data_no_cache")
def get_data():
    return {"success": True, "message": "this is the data you requested"}

# Will be cached
@app.get("/immutable_data")
@cache()
async def get_immutable_data():
    return {"success": True, "message": "this data can be cached indefinitely"}
```

Decorating a path function with `@cache` enables caching for the endpoint. If no arguments are provided, responses will be set to expire after 1 year, which, historically, is the correct way to mark data that "never expires".

Response data for the API endpoint at `/immutable_data` will be cached by the Redis server. Log messages are written to standard output whenever a response is added to the cache, or a response is retrieved from the cache:

```console
INFO:fastapi_redis_cache:| 04/21/2021 12:26:26 AM | CONNECT_BEGIN: Attempting to connect to Redis server...
INFO:fastapi_redis_cache:| 04/21/2021 12:26:26 AM | CONNECT_SUCCESS: Redis client is connected to server.
INFO:fastapi_redis_cache:| 04/21/2021 12:26:34 AM | KEY_ADDED_TO_CACHE: key=api.get_immutable_data()
INFO:     127.0.0.1:61779 - "GET /immutable_data HTTP/1.1" 200 OK
INFO:fastapi_redis_cache:| 04/21/2021 12:26:45 AM | KEY_FOUND_IN_CACHE: key=api.get_immutable_data()
INFO:     127.0.0.1:61779 - "GET /immutable_data HTTP/1.1" 200 OK
```

The log messages show two successful (**`200 OK`**) responses to the same request (**`GET /immutable_data`**). The first request executed the `get_immutable_data` function and stored the result in Redis under key `api.get_immutable_data()`. The second request **did not** execute the `get_immutable_data` function, instead the cached result was retrieved and sent as the response.

If `get_immutable_data` took a substantial time to execute, enabling caching on the endpoint would save time and CPU resources every subsequent time it is called. However, to truly take advantage of caching, you should add a `Request` and `Response` argument to the path operation function as shown below:

```python
# The expire_after_seconds argument sets the length of time until a cached
# response is deleted from Redis.
@app.get("/dynamic_data")
@cache(expire_after_seconds=30)
def get_dynamic_data(request: Request, response: Response):
    return {"success": True, "message": "this data should only be cached temporarily"}
```

If `request` and `response` are found in the path operation function, `FastApiRedisCache` can read the request header fields and modify the header fields sent with the response. To understand the difference, here is the full HTTP response for a request for `/immutable_data` (Remember, this is the first endpoint that was demonstrated and this path function **DOES NOT** contain a `Request` or `Response` object):

```console
$ http "http://127.0.0.1:8000/immutable_data"
HTTP/1.1 200 OK
content-length: 65
content-type: text/plain; charset=utf-8
date: Wed, 21 Apr 2021 07:26:34 GMT
server: uvicorn
{
    "message": "this data can be cached indefinitely",
    "success": true
}
```

Next, here is the HTTP response for the `/dynamic_data` endpoint. Notice the addition of the following headers: `cache-control`, `etag`, and `expires`:

```console
$ http "http://127.0.0.1:8000/dynamic_data"
  HTTP/1.1 200 OK
  cache-control: max-age=29
  content-length: 72
  content-type: application/json
  date: Wed, 21 Apr 2021 07:54:33 GMT
  etag: W/-5480454928453453778
  expires: Wed, 21 Apr 2021 07:55:03 GMT
  server: uvicorn
  x-fastapi-cache: Hit
  {
      "message": "this data should only be cached temporarily",
      "success": true
  }
```

The header fields indicate that this response will be considered fresh for 29 seconds. This is expected since `expire_after_seconds=30` was specified in the `@cache` decorator for the `/dynamic_data` endpoint.

This response also includes the `x-fastapi-cache` header field which tells us that this response was found in the Redis cache (a.k.a. a `Hit`). If these requests were made from a web browser, and a request for the same resource was sent before the cached response expires, the browser would automatically serve the cached version and the request would never even be sent to the FastAPI server!