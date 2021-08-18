import json
import re
import time
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from fastapi_redis_cache.client import HTTP_TIME

from fastapi_redis_cache.util import deserialize_json
from tests.main import app
from tests.main import REDIS_EXPIRE_SECONDS, WEB_EXPIRE_SECONDS

client = TestClient(app)
MAX_AGE_REGEX = re.compile(r"max-age=(?P<ttl>\d+)")


def test_cache_never_expire():
    # Initial request, X-FastAPI-Cache header field should equal "Miss"
    response = client.get("/cache_never_expire")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers

    # Send request to same endpoint, X-FastAPI-Cache header field should now equal "Hit"
    response = client.get("/cache_never_expire")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers


def test_cache_expires():
    # Store time when response data was added to cache
    added_at_utc = datetime.utcnow()

    # Initial request, X-FastAPI-Cache header field should equal "Miss"
    response = client.get("/cache_expires")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data should be cached for five seconds"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers

    # Store eTag value from response header
    check_etag = response.headers["etag"]

    # Send request, X-FastAPI-Cache header field should now equal "Hit"
    response = client.get("/cache_expires")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data should be cached for five seconds"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"

    # Verify eTag value matches the value stored from the initial response
    assert "etag" in response.headers
    assert response.headers["etag"] == check_etag

    # Store 'max-age' value of 'cache-control' header field
    assert "cache-control" in response.headers
    match = MAX_AGE_REGEX.search(response.headers.get("cache-control"))
    assert match
    ttl = int(match.groupdict()["ttl"])
    assert ttl <= 5

    # Store value of 'expires' header field
    assert "expires" in response.headers
    expire_at_utc = datetime.strptime(response.headers["expires"], HTTP_TIME)

    # Wait until expire time has passed
    now = datetime.utcnow()
    while expire_at_utc > now:
        time.sleep(1)
        now = datetime.utcnow()

    # Wait one additional second to ensure redis has deleted the expired response data
    time.sleep(1)
    second_request_utc = datetime.utcnow()

    # Verify that the time elapsed since the data was added to the cache is greater than the ttl value
    elapsed = (second_request_utc - added_at_utc).total_seconds()
    assert elapsed > ttl

    # Send request, X-FastAPI-Cache header field should equal "Miss" since the cached value has been evicted
    response = client.get("/cache_expires")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data should be cached for five seconds"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers

    # Check eTag value again. Since data is the same, the value should still match
    assert response.headers["etag"] == check_etag


def test_cache_json_encoder():
    # In order to verify that our custom BetterJsonEncoder is working correctly, the  /cache_json_encoder
    # endpoint returns a dict containing datetime.datetime, datetime.date and decimal.Decimal objects.
    response = client.get("/cache_json_encoder")
    assert response.status_code == 200
    response_json = response.json()
    assert response_json == {
        "success": True,
        "start_time": {"_spec_type": "<class 'datetime.datetime'>", "val": "04/20/2021 07:17:17 AM "},
        "finish_by": {"_spec_type": "<class 'datetime.date'>", "val": "04/21/2021"},
        "final_calc": {
            "_spec_type": "<class 'decimal.Decimal'>",
            "val": "3.140000000000000124344978758017532527446746826171875",
        },
    }

    # To verify that our custom object_hook function which deserializes types that are not typically
    # JSON-serializable is working correctly, we test it with the serialized values sent in the response.
    json_dict = deserialize_json(json.dumps(response_json))
    assert json_dict["start_time"] == datetime(2021, 4, 20, 7, 17, 17)
    assert json_dict["finish_by"] == datetime(2021, 4, 21)
    assert json_dict["final_calc"] == Decimal(3.14)


def test_cache_control_no_cache():
    # Simple test that verifies if a request is recieved with the cache-control header field containing "no-cache",
    # no caching behavior is performed
    response = client.get("/cache_never_expire", headers={"cache-control": "no-cache"})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" not in response.headers
    assert "cache-control" not in response.headers
    assert "expires" not in response.headers
    assert "etag" not in response.headers


def test_cache_control_no_store():
    # Simple test that verifies if a request is recieved with the cache-control header field containing "no-store",
    # no caching behavior is performed
    response = client.get("/cache_never_expire", headers={"cache-control": "no-store"})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" not in response.headers
    assert "cache-control" not in response.headers
    assert "expires" not in response.headers
    assert "etag" not in response.headers


def test_if_none_match():
    # Initial request, response data is added to cache
    response = client.get("/cache_never_expire")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers

    # Store correct eTag value from response header
    etag = response.headers["etag"]
    # Create another eTag value that is different from the correct value
    invalid_etag = "W/-5480454928453453778"

    # Send request to same endpoint where If-None-Match header contains both valid and invalid eTag values
    response = client.get("/cache_never_expire", headers={"if-none-match": f"{etag}, {invalid_etag}"})
    assert response.status_code == 304
    assert not response.content
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers

    # Send request to same endpoint where If-None-Match header contains just the wildcard (*) character
    response = client.get("/cache_never_expire", headers={"if-none-match": "*"})
    assert response.status_code == 304
    assert not response.content
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers

    # Send request to same endpoint where If-None-Match header contains only the invalid eTag value
    response = client.get("/cache_never_expire", headers={"if-none-match": invalid_etag})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers


def test_cache_one_hour():
    # Simple test that verifies that the @cache_for_one_hour partial function version of the @cache decorator
    # is working correctly.
    response = client.get("/cache_one_hour")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data should be cached for one hour"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    match = MAX_AGE_REGEX.search(response.headers.get("cache-control"))
    assert match and int(match.groupdict()["ttl"]) == 3600
    assert "expires" in response.headers
    assert "etag" in response.headers


def test_cache_invalid_type():
    # Simple test that verifies the correct behavior when a value that is not JSON-serializable is returned
    # as response data
    with pytest.raises(ValueError):
        response = client.get("/cache_invalid_type")
        assert response.status_code == 200
        assert "x-fastapi-cache" not in response.headers
        assert "cache-control" not in response.headers
        assert "expires" not in response.headers
        assert "etag" not in response.headers


def test_cache_web_expires_before_redis():
    target_endpoint = "/cache_web_expires_before_redis"
    expected_response = {"success": True, "message": "this data should be web cached for five seconds"}

    # Store time when response data was added to cache
    added_at_utc = datetime.utcnow()

    # Initial request, X-FastAPI-Cache header field should equal "Miss"
    response = client.get(target_endpoint)
    assert response.status_code == 200
    assert response.json() == expected_response
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "expires" in response.headers
    assert "etag" in response.headers

    # Store 'max-age' value of 'cache-control' header field
    assert "cache-control" in response.headers
    match = MAX_AGE_REGEX.search(response.headers.get("cache-control"))
    assert match
    miss_ttl = int(match.groupdict()["ttl"])
    assert miss_ttl <= WEB_EXPIRE_SECONDS

    # Store eTag value from response header
    check_etag = response.headers["etag"]

    # Send request, X-FastAPI-Cache header field should now equal "Hit"
    response = client.get(target_endpoint)
    assert response.status_code == 200
    assert response.json() == expected_response
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"

    # Verify eTag value matches the value stored from the initial response
    assert "etag" in response.headers
    assert response.headers["etag"] == check_etag

    # Store 'max-age' value of 'cache-control' header field
    assert "cache-control" in response.headers
    match = MAX_AGE_REGEX.search(response.headers.get("cache-control"))
    assert match
    hit_ttl = int(match.groupdict()["ttl"])
    assert hit_ttl <= miss_ttl

    # Store value of 'expires' header field
    assert "expires" in response.headers
    expire_at_utc = datetime.strptime(response.headers["expires"], HTTP_TIME)

    # Wait until web expiration time has passed
    now = datetime.utcnow()
    time.sleep((expire_at_utc - now).total_seconds())
    # Wait any additional time neecessary to ensure the web expiration has passed
    now = datetime.utcnow()
    while expire_at_utc > now:
        time.sleep(1)
        now = datetime.utcnow()

    # Wait one additional second to ensure the web cache has expired
    time.sleep(1)

    # Verify that the time elapsed since the data was added to the cache is greater than the ttl value
    second_request_utc = datetime.utcnow()
    elapsed = (second_request_utc - added_at_utc).total_seconds()
    assert elapsed > hit_ttl

    # Send request, X-FastAPI-Cache header field should equal "Hit" since the Redis cached value has a longer
    # lifespan than the web cache value
    response = client.get(target_endpoint)
    assert response.status_code == 200
    assert response.json() == expected_response
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers

    # Check eTag value again. Since data is the same, the value should still match
    assert "etag" in response.headers
    assert response.headers["etag"] == check_etag

    # Wait until Redis expiration time has passed
    elapsed_since_added = (datetime.utcnow() - added_at_utc).total_seconds()
    if elapsed_since_added < REDIS_EXPIRE_SECONDS:
        time.sleep(REDIS_EXPIRE_SECONDS - elapsed_since_added)
    # Wait any additional time neecessary, waiting an additional second to ensure Redis has
    # deleted the response data
    while (datetime.utcnow() - added_at_utc).total_seconds() < REDIS_EXPIRE_SECONDS:
        time.sleep(1)

    # Send request, X-FastAPI-Cache header field should equal "Miss" since the Redis cached value has now expired
    response = client.get(target_endpoint)
    assert response.status_code == 200
    assert response.json() == expected_response
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
