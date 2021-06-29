import json
import re
import time
from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from fastapi_redis_cache.util import deserialize_json
from tests.main import app

client = TestClient(app)
MAX_AGE_REGEX = re.compile(r"max-age=(?P<ttl>\d+)")


def test_cache_never_expire():
    response = client.get("/cache_never_expire")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
    response = client.get("/cache_never_expire")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers


def test_cache_expires():
    start = datetime.now()
    response = client.get("/cache_expires")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data should be cached for eight seconds"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
    check_etag = response.headers["etag"]
    response = client.get("/cache_expires")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data should be cached for eight seconds"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
    assert response.headers["etag"] == check_etag
    elapsed = (datetime.now() - start).total_seconds()
    remaining = 8 - elapsed
    if remaining > 0:
        time.sleep(remaining)
    response = client.get("/cache_expires")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data should be cached for eight seconds"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
    assert response.headers["etag"] == check_etag


def test_cache_json_encoder():
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
    json_dict = deserialize_json(json.dumps(response_json))
    assert json_dict["start_time"] == datetime(2021, 4, 20, 7, 17, 17)
    assert json_dict["finish_by"] == datetime(2021, 4, 21)
    assert json_dict["final_calc"] == Decimal(3.14)


def test_cache_control_no_cache():
    response = client.get("/cache_never_expire", headers={"cache-control": "no-cache"})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" not in response.headers
    assert "cache-control" not in response.headers
    assert "expires" not in response.headers
    assert "etag" not in response.headers


def test_cache_control_no_store():
    response = client.get("/cache_never_expire", headers={"cache-control": "no-store"})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" not in response.headers
    assert "cache-control" not in response.headers
    assert "expires" not in response.headers
    assert "etag" not in response.headers


def test_if_none_match():
    response = client.get("/cache_never_expire")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
    etag = response.headers["etag"]
    invalid_etag = "W/-5480454928453453778"
    response = client.get("/cache_never_expire", headers={"if-none-match": f"{etag}, {invalid_etag}"})
    assert response.status_code == 304
    assert not response.content
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
    response = client.get("/cache_never_expire", headers={"if-none-match": "*"})
    assert response.status_code == 304
    assert not response.content
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
    response = client.get("/cache_never_expire", headers={"if-none-match": invalid_etag})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers


def test_partial_cache_one_hour():
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
