import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple, Type, Union

from fastapi import Request, Response
from redis import client

from fastapi_redis_cache.enums import RedisEvent, RedisStatus
from fastapi_redis_cache.key_gen import get_cache_key
from fastapi_redis_cache.redis import redis_connect
from fastapi_redis_cache.util import serialize_json

DEFAULT_RESPONSE_HEADER = "X-FastAPI-Cache"
ALLOWED_HTTP_TYPES = ["GET"]
LOG_TIMESTAMP = "%m/%d/%Y %I:%M:%S %p"
HTTP_TIME = "%a, %d %b %Y %H:%M:%S GMT"

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class MetaSingleton(type):
    """Metaclass for creating classes that allow only a single instance to be created."""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class FastApiRedisCache(metaclass=MetaSingleton):
    """Communicates with Redis server to cache API response data."""

    host_url: str
    prefix: str = None
    response_header: str = None
    status: RedisStatus = RedisStatus.NONE
    redis: client.Redis = None

    @property
    def connected(self):
        return self.status == RedisStatus.CONNECTED

    @property
    def not_connected(self):
        return not self.connected

    def init(
        self,
        host_url: str,
        prefix: Optional[str] = None,
        response_header: Optional[str] = None,
        ignore_arg_types: Optional[List[Type[object]]] = None,
    ) -> None:
        """Connect to a Redis database using `host_url` and configure cache settings.

        Args:
            host_url (str): URL for a Redis database.
            prefix (str, optional): Prefix to add to every cache key stored in the
                Redis database. Defaults to None.
            response_header (str, optional): Name of the custom header field used to
                identify cache hits/misses. Defaults to None.
            ignore_arg_types (List[Type[object]], optional): Each argument to the
                API endpoint function is used to compose the cache key. If there
                are any arguments that have no effect on the response (such as a
                `Request` or `Response` object), including their type in this list
                will ignore those arguments when the key is created. Defaults to None.
        """
        self.host_url = host_url
        self.prefix = prefix
        self.response_header = response_header or DEFAULT_RESPONSE_HEADER
        self.ignore_arg_types = ignore_arg_types
        self._connect()

    def _connect(self):
        self.log(RedisEvent.CONNECT_BEGIN, msg="Attempting to connect to Redis server...")
        self.status, self.redis = redis_connect(self.host_url)
        if self.status == RedisStatus.CONNECTED:
            self.log(RedisEvent.CONNECT_SUCCESS, msg="Redis client is connected to server.")
        if self.status == RedisStatus.AUTH_ERROR:  # pragma: no cover
            self.log(RedisEvent.CONNECT_FAIL, msg="Unable to connect to redis server due to authentication error.")
        if self.status == RedisStatus.CONN_ERROR:  # pragma: no cover
            self.log(RedisEvent.CONNECT_FAIL, msg="Redis server did not respond to PING message.")

    def request_is_not_cacheable(self, request: Request) -> bool:
        return request and (
            request.method not in ALLOWED_HTTP_TYPES
            or any(directive in request.headers.get("Cache-Control", "") for directive in ["no-store", "no-cache"])
        )

    def get_cache_key(self, func: Callable, *args: List, **kwargs: Dict) -> str:
        return get_cache_key(self.prefix, self.ignore_arg_types, func, *args, **kwargs)

    def check_cache(self, key: str) -> Tuple[int, str]:
        pipe = self.redis.pipeline()
        ttl, in_cache = pipe.ttl(key).get(key).execute()
        if in_cache:
            self.log(RedisEvent.KEY_FOUND_IN_CACHE, key=key)
        return (ttl, in_cache)

    def requested_resource_not_modified(self, request: Request, cached_data: str) -> bool:
        if not request or "If-None-Match" not in request.headers:
            return False
        check_etags = [etag.strip() for etag in request.headers["If-None-Match"].split(",") if etag]
        if len(check_etags) == 1 and check_etags[0] == "*":
            return True
        return self.get_etag(cached_data) in check_etags

    def add_to_cache(self, key: str, value: Dict, expire: int) -> bool:
        response_data = None
        try:
            response_data = serialize_json(value)
        except TypeError:
            message = f"Object of type {type(value)} is not JSON-serializable"
            self.log(RedisEvent.FAILED_TO_CACHE_KEY, msg=message, key=key)
            return False
        cached = self.redis.set(name=key, value=response_data, ex=expire)
        if cached:
            self.log(RedisEvent.KEY_ADDED_TO_CACHE, key=key)
        else:  # pragma: no cover
            self.log(RedisEvent.FAILED_TO_CACHE_KEY, key=key, value=value)
        return cached

    def set_response_headers(
        self, response: Response, cache_hit: bool, response_data: Dict = None, ttl: int = None
    ) -> None:
        response.headers[self.response_header] = "Hit" if cache_hit else "Miss"
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        response.headers["Expires"] = expires_at.strftime(HTTP_TIME)
        response.headers["Cache-Control"] = f"max-age={ttl}"
        response.headers["ETag"] = self.get_etag(response_data)
        if "last_modified" in response_data:  # pragma: no cover
            response.headers["Last-Modified"] = response_data["last_modified"]

    def log(self, event: RedisEvent, msg: Optional[str] = None, key: Optional[str] = None, value: Optional[str] = None):
        """Log `RedisEvent` using the configured `Logger` object"""
        message = f" {self.get_log_time()} | {event.name}"
        if msg:
            message += f": {msg}"
        if key:
            message += f": key={key}"
        if value:  # pragma: no cover
            message += f", value={value}"
        logger.info(message)

    @staticmethod
    def get_etag(cached_data: Union[str, bytes, Dict]) -> str:
        if isinstance(cached_data, bytes):
            cached_data = cached_data.decode()
        if not isinstance(cached_data, str):
            cached_data = serialize_json(cached_data)
        return f"W/{hash(cached_data)}"

    @staticmethod
    def get_log_time():
        """Get a timestamp to include with a log message."""
        return datetime.now().strftime(LOG_TIMESTAMP)
