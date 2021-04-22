import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple, Type, Union

from fastapi import Request, Response
from pydantic import RedisDsn
from redis import client

from fastapi_redis_cache.enums import RedisEvent, RedisStatus
from fastapi_redis_cache.key_gen import get_cache_key
from fastapi_redis_cache.redis import redis_connect
from fastapi_redis_cache.util import deserialize_json, serialize_json

DEFAULT_RESPONSE_HEADER = "X-FastAPI-Cache"
DEFAULT_ALLOWED_TYPES = ["GET"]
ONE_YEAR_IN_SECONDS = 31535990
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

    host_url: RedisDsn
    prefix: str = None
    response_header: str = None
    allow_request_types: List[str] = []
    status: RedisStatus = RedisStatus.NONE
    redis: client.Redis = None

    @property
    def connected(self):
        return self.status == RedisStatus.CONNECTED

    def connect(
        self,
        host_url: RedisDsn,
        prefix: Optional[str] = None,
        response_header: Optional[str] = None,
        allow_request_types: List[str] = None,
        ignore_arg_types: Optional[List[Type[object]]] = None,
    ) -> None:
        self.host_url = host_url
        self.prefix = prefix
        self.response_header = response_header or DEFAULT_RESPONSE_HEADER
        self.allow_request_types = allow_request_types or DEFAULT_ALLOWED_TYPES
        self.ignore_arg_types = ignore_arg_types
        self._connect()

    def _connect(self):
        self.log(RedisEvent.CONNECT_BEGIN, msg="Attempting to connect to Redis server...")
        self.status, self.redis = redis_connect(self.host_url)
        if self.status == RedisStatus.CONNECTED:
            self.log(RedisEvent.CONNECT_SUCCESS, msg="Redis client is connected to server.")
        if self.status == RedisStatus.AUTH_ERROR:
            self.log(RedisEvent.CONNECT_FAIL, msg="Unable to connect to redis server due to authentication error.")
        if self.status == RedisStatus.CONN_ERROR:
            self.log(RedisEvent.CONNECT_FAIL, msg="Redis server did not respond to PING message.")

    def request_is_cacheable(self, request: Request) -> bool:
        return not request or (
            request.method in self.allow_request_types
            and all(directive not in request.headers.get("Cache-Control", "") for directive in ["no-store", "no-cache"])
        )

    def get_cache_key(self, func: Callable, *args: List, **kwargs: Dict) -> str:
        return get_cache_key(func, self.ignore_arg_types, *args, **kwargs)

    def check_cache(self, key: str) -> Tuple[int, str]:
        pipe = self.redis.pipeline()
        ttl, in_cache = pipe.ttl(key).get(key).execute()
        if in_cache:
            self.log(RedisEvent.KEY_FOUND_IN_CACHE, key=key)
        return (ttl, in_cache)

    def requested_resource_not_modified(self, request: Request, cached_data: Union[str, Dict]) -> bool:
        if not request or "If-None-Match" not in request.headers:
            return False
        check_etags = [etag.strip() for etag in request.headers["If-None-Match"].split(",") if etag]
        if len(check_etags) == 1 and check_etags[0] == "*":
            return True
        return self.get_etag(cached_data) in check_etags

    def add_to_cache(
        self,
        key: str,
        value: str,
        ex: Optional[Union[int, timedelta]] = None,
        px: Optional[Union[int, timedelta]] = None,
    ) -> None:
        if self.redis.set(name=key, value=self.serialize_json(value), ex=ex, px=px):
            self.log(RedisEvent.KEY_ADDED_TO_CACHE, key=key)
        else:
            self.log(RedisEvent.FAILED_TO_CACHE_KEY, key=key, value=value)

    def set_response_headers(
        self, response: Response, cache_hit: bool, response_data: str = None, ttl: int = None
    ) -> None:
        response.headers[self.response_header] = "Hit" if cache_hit else "Miss"
        ttl = ttl if ttl != -1 else ONE_YEAR_IN_SECONDS
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        response.headers["Expires"] = expires_at.strftime(HTTP_TIME)
        response.headers["Cache-Control"] = f"max-age={ttl}"
        response.headers["ETag"] = self.get_etag(response_data)
        if "last_modified" in response_data:
            response.headers["Last-Modified"] = response_data["last_modified"]

    def log(self, event: RedisEvent, msg: Optional[str] = None, key: Optional[str] = None, value: Optional[str] = None):
        """Log `RedisEvent` using the configured `Logger` object"""
        message = f" {self.get_log_time()} | {event.name}"
        if msg:
            message += f": {msg}"
        if key:
            message += f": key={key}"
        if value:
            message += f", value={value}"
        logger.info(message)

    @staticmethod
    def deserialize_json(json_str: str) -> Dict:
        return deserialize_json(json_str)

    @staticmethod
    def serialize_json(json_dict: Dict) -> str:
        return serialize_json(json_dict)

    @staticmethod
    def get_etag(cached_data: Union[str, Dict]) -> str:
        if not isinstance(cached_data, str):
            cached_data = str(cached_data)
        return f"W/{hash(cached_data)}"

    @staticmethod
    def get_log_time():
        """Get a timestamp to include with a log message."""
        return datetime.now().strftime(LOG_TIMESTAMP)
