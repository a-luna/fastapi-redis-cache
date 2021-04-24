from enum import IntEnum


class RedisStatus(IntEnum):
    """Connection status for the redis client."""

    NONE = 0
    CONNECTED = 1
    AUTH_ERROR = 2
    CONN_ERROR = 3


class RedisEvent(IntEnum):
    """Redis client events."""

    CONNECT_BEGIN = 1
    CONNECT_SUCCESS = 2
    CONNECT_FAIL = 3
    KEY_ADDED_TO_CACHE = 4
    KEY_FOUND_IN_CACHE = 5
    FAILED_TO_CACHE_KEY = 6
