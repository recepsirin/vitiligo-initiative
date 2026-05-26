"""Tests for POST rate limiting middleware."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from vitiligo.web.ratelimit import RateLimitMiddleware


def test_rate_limit_blocks_excess_post_requests() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, post_limit_per_minute=2, window_seconds=60)

    @app.post("/api/search")
    def search() -> dict[str, str]:
        return {"ok": "true"}

    client = TestClient(app)
    assert client.post("/api/search").status_code == 200
    assert client.post("/api/search").status_code == 200
    blocked = client.post("/api/search")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_health_post_is_not_limited() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, post_limit_per_minute=1, window_seconds=60)

    @app.post("/api/health")
    def health_post() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    for _ in range(5):
        assert client.post("/api/health").status_code == 200


def test_get_requests_are_not_limited() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, post_limit_per_minute=1, window_seconds=60)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/api/health").status_code == 200
