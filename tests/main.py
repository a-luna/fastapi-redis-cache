from fastapi import FastAPI, Request, Response

from fastapi_redis_cache import cache

app = FastAPI(title="FastAPI Redis Cache Test App")


@app.get("/cache_never_expire")
@cache()
def cache_never_expire(request: Request, response: Response):
    return {"success": True, "message": "this data can be cached indefinitely"}
