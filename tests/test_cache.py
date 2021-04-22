from fastapi.testclient import TestClient

from tests.main import app

client = TestClient(app)


def test_cache_never_expire():
    response = client.get("/cache_never_expire")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "this data can be cached indefinitely"}
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Miss"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
    response = client.get("/cache_never_expire")
    assert "x-fastapi-cache" in response.headers and response.headers["x-fastapi-cache"] == "Hit"
    assert "cache-control" in response.headers
    assert "expires" in response.headers
    assert "etag" in response.headers
