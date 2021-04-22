## `fastapi-redis-cache`

(badges, eventually)

### Installation

`pip install fastapi-redis-cache`

### Usage Examples

```python
import os

from fastapi import FastAPI, Request, Response
from fastapi_redis_cache import FastApiRedisCache, cache

LOCAL_REDIS_URL = "redis://127.0.0.1:6379"
CACHE_HEADER = "X-MyAPI-Cache"

app = FastAPI(title="FastAPI Redis Cache Example")


# On startup, initialize the cache with the URL of the Redis server.
# The name of the custom header field used to identify cache hits/misses
# can also be customized, but this is optional. The default name for the
# custom header field is "X-FastAPI-Cache"
@app.on_event("startup")
def startup():
    redis_cache = FastApiRedisCache()
    redis_cache.connect(
        host_url=os.environ.get("REDIS_URL", LOCAL_REDIS_URL),
        response_header=CACHE_HEADER
    )


# Data from this endpoint WILL NOT be cached
@app.get("/data_no_cache")
def get_data():
    return {"success": True, "message": "this is the data you requested"}


# Decorating a path function with @cache enables caching for the endpoint.
# If no arguments are provided, responses will be set to expire after 1 year,
# which, historically, is the correct way to mark data that "never expires".
@app.get("/immutable_data")
@cache()
async def get_immutable_data():
    return {"success": True, "message": "this data can be cached indefinitely"}
```

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

If `request` and `response` are found in the path operation function, `FastApiRedisCache` can read the request header fields and modify the response header fields that are sent. To understand the difference, here is the full HTTP response for a request for `/immutable_data`:

```shell-session
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

Next, here is the HTTP responses for `/dynamic_data`. Notice the addition of the following headers: `cache-control`, `etag`, and `expires`:

```shell-session
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

This response also includes the `x-fastapi-cache` header field which tells us that this response was found in the Redis cache (a.k.a. a `Hit`). If these requests were made from a web browser, and a request for the same resource was sent before `expires`, the browser would automatically serve the cached version and the request would never even be sent to the FastAPI server!