## fastapi-redis-cache <!-- omit in toc -->

[![PyPI version](https://badge.fury.io/py/fastapi-redis-cache.svg)](https://badge.fury.io/py/fastapi-redis-cache)
![PyPI - Downloads](https://img.shields.io/pypi/dm/fastapi-redis-cache?color=%234DC71F)
![PyPI - License](https://img.shields.io/pypi/l/fastapi-redis-cache?color=%25234DC71F)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/fastapi-redis-cache)
[![Maintainability](https://api.codeclimate.com/v1/badges/ec0b1d7afb21bd8c23dc/maintainability)](https://codeclimate.com/github/a-luna/fastapi-redis-cache/maintainability)
[![codecov](https://codecov.io/gh/a-luna/fastapi-redis-cache/branch/main/graph/badge.svg?token=dUaILJcgWY)](https://codecov.io/gh/a-luna/fastapi-redis-cache)

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Initialize Redis](#initialize-redis)
  - [`@cache` Decorator](#cache-decorator)
    - [Response Headers](#response-headers)
    - [Pre-defined Lifetimes](#pre-defined-lifetimes)
  - [Cache Keys](#cache-keys)
  - [Cache Keys Pt 2.](#cache-keys-pt-2)
- [Questions/Contributions](#questionscontributions)

## Features

- Cache response data for async and non-async path operation functions.
- Lifetime of cached data is configured separately for each API endpoint.
- Requests with `Cache-Control` header containing `no-cache` or `no-store` are handled correctly (all caching behavior is disabled).
- Requests with `If-None-Match` header will receive a response with status `304 NOT MODIFIED` if `ETag` for requested resource matches header value.

## Installation

`pip install fastapi-redis-cache`

## Usage

### Initialize Redis

Create a `FastApiRedisCache` instance when your application starts by [defining an event handler for the `"startup"` event](https://fastapi.tiangolo.com/advanced/events/) as shown below:

```python {linenos=table}
import os

from fastapi import FastAPI, Request, Response
from fastapi_redis_cache import FastApiRedisCache, cache
from sqlalchemy.orm import Session

LOCAL_REDIS_URL = "redis://127.0.0.1:6379"

app = FastAPI(title="FastAPI Redis Cache Example")

@app.on_event("startup")
def startup():
    redis_cache = FastApiRedisCache()
    redis_cache.init(
        host_url=os.environ.get("REDIS_URL", LOCAL_REDIS_URL),
        prefix="myapi-cache",
        response_header="X-MyAPI-Cache",
        ignore_arg_types=[Request, Response, Session]
    )
```

After creating the instance, you must call the `init` method. The only required argument for this method is the URL for the Redis database (`host_url`). All other arguments are optional:

- `host_url` (`str`) &mdash; Redis database URL. (_**Required**_)
- `prefix` (`str`) &mdash; Prefix to add to every cache key stored in the Redis database. (_Optional_, defaults to `None`)
- `response_header` (`str`) &mdash; Name of the custom header field used to identify cache hits/misses. (_Optional_, defaults to `X-FastAPI-Cache`)
- `ignore_arg_types` (`List[Type[object]]`) &mdash; Cache keys are created (in part) by combining the name and value of each argument used to invoke a path operation function. If any of the arguments have no effect on the response (such as a `Request` or `Response` object), including their type in this list will ignore those arguments when the key is created. (_Optional_, defaults to `[Request, Response]`)
  - The example shown here includes the `sqlalchemy.orm.Session` type, if your project uses SQLAlchemy as a dependency ([as demonstrated in the FastAPI docs](https://fastapi.tiangolo.com/tutorial/sql-databases/)), you should include `Session` in `ignore_arg_types` in order for cache keys to be created correctly ([More info](#cache-keys)).

### `@cache` Decorator

Decorating a path function with `@cache` enables caching for the endpoint. **Response data is only cached for `GET` operations**, decorating path functions for other HTTP method types will have no effect. If no arguments are provided, responses will be set to expire after one year, which, historically, is the correct way to mark data that "never expires".

```python
# WILL NOT be cached
@app.get("/data_no_cache")
def get_data():
    return {"success": True, "message": "this data is not cacheable, for... you know, reasons"}

# Will be cached for one year
@app.get("/immutable_data")
@cache()
async def get_immutable_data():
    return {"success": True, "message": "this data can be cached indefinitely"}
```

Response data for the API endpoint at `/immutable_data` will be cached by the Redis server. Log messages are written to standard output whenever a response is added to or retrieved from the cache:

```console
INFO:fastapi_redis_cache:| 04/21/2021 12:26:26 AM | CONNECT_BEGIN: Attempting to connect to Redis server...
INFO:fastapi_redis_cache:| 04/21/2021 12:26:26 AM | CONNECT_SUCCESS: Redis client is connected to server.
INFO:fastapi_redis_cache:| 04/21/2021 12:26:34 AM | KEY_ADDED_TO_CACHE: key=api.get_immutable_data()
INFO:     127.0.0.1:61779 - "GET /immutable_data HTTP/1.1" 200 OK
INFO:fastapi_redis_cache:| 04/21/2021 12:26:45 AM | KEY_FOUND_IN_CACHE: key=api.get_immutable_data()
INFO:     127.0.0.1:61779 - "GET /immutable_data HTTP/1.1" 200 OK
```

The log messages show two successful (**`200 OK`**) responses to the same request (**`GET /immutable_data`**). The first request executed the `get_immutable_data` function and stored the result in Redis under key `api.get_immutable_data()`. The second request _**did not**_ execute the `get_immutable_data` function, instead the cached result was retrieved and sent as the response.

In most situations, response data must expire in a much shorter period of time than one year. Using the `expire` parameter, You can specify the number of seconds before data is deleted:

```python
# Will be cached for thirty seconds
@app.get("/dynamic_data")
@cache(expire=30)
def get_dynamic_data(request: Request, response: Response):
    return {"success": True, "message": "this data should only be cached temporarily"}
```

> **NOTE!** `expire` can be either an `int` value or `timedelta` object. When the TTL is very short (like the example above) this results in a decorator that is expressive and requires minimal effort to parse visually. For durations an hour or longer (e.g., `@cache(expire=86400)`), IMHO, using a `timedelta` object is much easier to grok (`@cache(expire=timedelta(days=1))`).

#### Response Headers

A response from the `/dynamic_data` endpoint showing all header values is given below:

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

- The `x-fastapi-cache` header field indicates that this response was found in the Redis cache (a.k.a. a `Hit`). The only other possible value for this field is `Miss`.
- The `expires` field and `max-age` value in the `cache-control` field indicate that this response will be considered fresh for 29 seconds. This is expected since `expire=30` was specified in the `@cache` decorator.
- The `etag` field is an identifier that is created by converting the response data to a string and applying a hash function. If a request containing the `if-none-match` header is received, any `etag` value(s) included in the request will be used to determine if the data requested is the same as the data stored in the cache. If they are the same, a `304 NOT MODIFIED` response will be sent. If they are not the same, the cached data will be sent with a `200 OK` response.

These header fields are used by your web browser's cache to avoid sending unnecessary requests. After receiving the response shown above, if a user requested the same resource before the `expires` time, the browser wouldn't send a request to the FastAPI server. Instead, the cached response would be served directly from disk.

Of course, this assumes that the browser is configured to perform caching. If the browser sends a request with the `cache-control` header containing `no-cache` or `no-store`, the `cache-control`, `etag`, `expires`, and `x-fastapi-cache` response header fields will not be included and the response data will not be stored in Redis.

#### Pre-defined Lifetimes

The decorators listed below define several common durations and can be used in place of the `@cache` decorator:

- `@cache_one_minute`
- `@cache_one_hour`
- `@cache_one_day`
- `@cache_one_week`
- `@cache_one_month`
- `@cache_one_year`

For example, instead of `@cache(expire=timedelta(days=1))`, you could use:

```python
from fastapi_redis_cache import cache_one_day

@app.get("/cache_one_day")
@cache_one_day()
def partial_cache_one_day(response: Response):
    return {"success": True, "message": "this data should be cached for 24 hours"}
```

If a duration that you would like to use throughout your project is missing from the list, you can easily create your own:

```python
from functools import partial, update_wrapper
from fastapi_redis_cache import cache

ONE_HOUR_IN_SECONDS = 3600

cache_two_hours = partial(cache, expire=ONE_HOUR_IN_SECONDS * 2)
update_wrapper(cache_two_hours, cache)
```

Then, simply import `cache_two_hours` and use it to decorate your API endpoint path functions:

```python
@app.get("/cache_two_hours")
@cache_two_hours()
def partial_cache_two_hours(response: Response):
    return {"success": True, "message": "this data should be cached for two hours"}
```

### Cache Keys

Consider the `/get_user` API route defined below. This is the first path function we have seen where the response depends on the value of an argument (`id: int`). This is a typical CRUD operation where `id` is used to retrieve a `User` record from a database. The API route also includes a dependency that injects a `Session` object (`db`) into the function, [per the instructions from the FastAPI docs](https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-dependency):

```python
@app.get("/get_user", response_model=schemas.User)
@cache(expire=3600)
def get_user(id: int, db: Session = Depends(get_db)):
    return db.query(models.User).filter(models.User.id == id).first()
```

In the [Initialize Redis](#initialize-redis) section of this document, the `FastApiRedisCache.init` method was called with `ignore_arg_types=[Request, Response, Session]`. Why is it necessary to include `Session` in this list?

Before we can answer that question, we must understand how a cache key is created. If the following request was received: `GET /get_user?id=1`, the cache key generated would be `myapi-cache:api.get_user(id=1)`.

The source of each value used to construct this cache key is given below:

1) The optional `prefix` value provided as an argument to the `FastApiRedisCache.init` method => `"myapi-cache"`.
2) The module containing the path function => `"api"`.
3) The name of the path function => `"get_user"`.
4) The name and value of all arguments to the path function **EXCEPT for arguments with a type that exists in** `ignore_arg_types` => `"id=1"`.

Since `Session` is included in `ignore_arg_types`, the `db` argument was not included in the cache key when **Step 4** was performed.

If `Session` had not been included in `ignore_arg_types`, caching would be completely broken. To understand why this is the case, see if you can figure out what is happening in the log messages below:

```console
INFO:uvicorn.error:Application startup complete.
INFO:fastapi_redis_cache.client: 04/23/2021 07:04:12 PM | KEY_ADDED_TO_CACHE: key=myapi-cache:api.get_user(id=1,db=<sqlalchemy.orm.session.Session object at 0x11b9fe550>)
INFO:     127.0.0.1:50761 - "GET /get_user?id=1 HTTP/1.1" 200 OK
INFO:fastapi_redis_cache.client: 04/23/2021 07:04:15 PM | KEY_ADDED_TO_CACHE: key=myapi-cache:api.get_user(id=1,db=<sqlalchemy.orm.session.Session object at 0x11c7f73a0>)
INFO:     127.0.0.1:50761 - "GET /get_user?id=1 HTTP/1.1" 200 OK
INFO:fastapi_redis_cache.client: 04/23/2021 07:04:17 PM | KEY_ADDED_TO_CACHE: key=myapi-cache:api.get_user(id=1,db=<sqlalchemy.orm.session.Session object at 0x11c7e35e0>)
INFO:     127.0.0.1:50761 - "GET /get_user?id=1 HTTP/1.1" 200 OK
```

The log messages indicate that three requests were received for the same endpoint, with the same arguments (`GET /get_user?id=1`). However, the cache key that is created is different for each request:

```console
KEY_ADDED_TO_CACHE: key=myapi-cache:api.get_user(id=1,db=<sqlalchemy.orm.session.Session object at 0x11b9fe550>
KEY_ADDED_TO_CACHE: key=myapi-cache:api.get_user(id=1,db=<sqlalchemy.orm.session.Session object at 0x11c7f73a0>
KEY_ADDED_TO_CACHE: key=myapi-cache:api.get_user(id=1,db=<sqlalchemy.orm.session.Session object at 0x11c7e35e0>
```

The value of each argument is added to the cache key by calling `str(arg)`. The `db` object includes the memory location when converted to a string, causing the same response data to be cached under three different keys! This is obviously not what we want.

The correct behavior (with `Session` included in `ignore_arg_types`) is shown below:

```console
INFO:uvicorn.error:Application startup complete.
INFO:fastapi_redis_cache.client: 04/23/2021 07:04:12 PM | KEY_ADDED_TO_CACHE: key=myapi-cache:api.get_user(id=1)
INFO:     127.0.0.1:50761 - "GET /get_user?id=1 HTTP/1.1" 200 OK
INFO:fastapi_redis_cache.client: 04/23/2021 07:04:12 PM | KEY_FOUND_IN_CACHE: key=myapi-cache:api.get_user(id=1)
INFO:     127.0.0.1:50761 - "GET /get_user?id=1 HTTP/1.1" 200 OK
INFO:fastapi_redis_cache.client: 04/23/2021 07:04:12 PM | KEY_FOUND_IN_CACHE: key=myapi-cache:api.get_user(id=1)
INFO:     127.0.0.1:50761 - "GET /get_user?id=1 HTTP/1.1" 200 OK
```

Now, every request for the same `id` generates the same key value (`myapi-cache:api.get_user(id=1)`). As expected, the first request adds the key/value pair to the cache, and each subsequent request retrieves the value from the cache based on the key.

### Cache Keys Pt 2.

What about this situation? You create a custom dependency for your API that performs input validation, but you can't ignore it because _**it does**_ have an effect on the response data. There's a simple solution for that, too.

Here is an endpoint from one of my projects:

```python
@router.get("/scoreboard", response_model=ScoreboardSchema)
@cache()
def get_scoreboard_for_date(
    game_date: MLBGameDate = Depends(), db: Session = Depends(get_db)
):
    return get_scoreboard_data_for_date(db, game_date.date)
```

The `game_date` argument is a `MLBGameDate` type. This is a custom type that parses the value from the querystring to a date, and determines if the parsed date is valid by checking if it is within a certain range. The implementation for `MLBGameDate` is given below:

```python
class MLBGameDate:
    def __init__(
        self,
        game_date: str = Query(..., description="Date as a string in YYYYMMDD format"),
        db: Session = Depends(get_db),
    ):
        try:
            parsed_date = parse_date(game_date)
        except ValueError as ex:
            raise HTTPException(status_code=400, detail=ex.message)
        result = Season.is_date_in_season(db, parsed_date)
        if result.failure:
            raise HTTPException(status_code=400, detail=result.error)
        self.date = parsed_date
        self.season = convert_season_to_dict(result.value)

    def __str__(self):
        return self.date.strftime("%Y-%m-%d")
```

Please note the `__str__` method that overrides the default behavior. This way, instead of `<MLBGameDate object at 0x11c7e35e0>`, the value will be formatted as, for example, `2019-05-09`. You can use this strategy whenever you have an argument that has en effect on the response data but converting that argument to a string results in a value containing the object's memory location.

## Questions/Contributions

If you have any questions, please open an issue. Any suggestions and contributions are absolutely welcome. This is still a very small and young project, I plan on adding a feature roadmap and further documentation in the near future.