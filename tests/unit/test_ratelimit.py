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


def test_get_requests_are_not_limited() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, post_limit_per_minute=1, window_seconds=60)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/api/health").status_code == 200


def _limited_app(**kwargs: int) -> TestClient:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, post_limit_per_minute=2, window_seconds=60, **kwargs)

    @app.post("/api/ask")
    def ask() -> dict[str, str]:
        return {"ok": "true"}

    return TestClient(app)


def test_spoofed_forwarded_for_does_not_bypass_limit() -> None:
    """A client rotating X-Forwarded-For values must still share one bucket."""
    client = _limited_app()
    codes = [
        client.post("/api/ask", headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
        for i in range(5)
    ]
    assert codes == [200, 200, 429, 429, 429]


def test_trusted_proxy_hop_keys_on_proxy_appended_address() -> None:
    """Behind one proxy, only the right-most entry (written by the proxy) is used."""
    client = _limited_app(trusted_proxy_hops=1)
    # Client-controlled left entries rotate; the proxy-appended right entry is fixed.
    codes = [
        client.post(
            "/api/ask", headers={"X-Forwarded-For": f"203.0.113.{i}, 198.51.100.7"}
        ).status_code
        for i in range(3)
    ]
    assert codes == [200, 200, 429]
    # A different real client (different right-most entry) has its own bucket.
    other = client.post("/api/ask", headers={"X-Forwarded-For": "198.51.100.8"})
    assert other.status_code == 200


def test_client_address_falls_back_to_peer() -> None:
    from starlette.requests import Request

    from vitiligo.web.ratelimit import client_address

    def request(xff: str | None) -> Request:
        headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
        return Request({"type": "http", "headers": headers, "client": ("10.0.0.5", 1234)})

    assert client_address(request("1.1.1.1, 2.2.2.2")) == "10.0.0.5"
    assert client_address(request("1.1.1.1, 2.2.2.2"), trusted_proxy_hops=1) == "2.2.2.2"
    assert client_address(request("1.1.1.1, 2.2.2.2"), trusted_proxy_hops=2) == "1.1.1.1"
    # Fewer entries than trusted hops: the header cannot be trusted at all.
    assert client_address(request("2.2.2.2"), trusted_proxy_hops=2) == "10.0.0.5"
    assert client_address(request(None), trusted_proxy_hops=1) == "10.0.0.5"


def test_idle_buckets_are_swept_at_capacity() -> None:
    middleware = RateLimitMiddleware(
        FastAPI(), post_limit_per_minute=5, window_seconds=60, max_tracked_clients=2
    )
    from collections import deque

    middleware._hits = {"old": deque([0.0]), "empty": deque(), "recent": deque([100.0])}
    middleware._sweep(now=100.0)
    assert set(middleware._hits) == {"recent"}


def test_forwarded_proto_trusts_only_proxy_hops() -> None:
    from vitiligo.web.proxy import forwarded_proto

    assert forwarded_proto("https", 0) is None  # no proxies configured: never trusted
    assert forwarded_proto("https", 1) == "https"
    assert forwarded_proto("http, https", 1) == "https"  # right-most is the proxy's
    assert forwarded_proto("https", 2) is None  # fewer entries than hops
    assert forwarded_proto("javascript", 1) is None
    assert forwarded_proto("", 1) is None


def test_redirects_keep_https_behind_trusted_proxy() -> None:
    """Behind a TLS proxy, trailing-slash redirects must not downgrade to http://."""
    from vitiligo.web.proxy import ForwardedProtoMiddleware

    def client_for(hops: int) -> TestClient:
        app = FastAPI()
        if hops:
            app.add_middleware(ForwardedProtoMiddleware, trusted_proxy_hops=hops)

        @app.get("/api/health")
        def health() -> dict[str, str]:
            return {"status": "ok"}

        return TestClient(app, base_url="http://engine.example")

    headers = {"X-Forwarded-Proto": "https"}
    behind_proxy = client_for(1).get("/api/health/", headers=headers, follow_redirects=False)
    assert behind_proxy.headers["location"] == "https://engine.example/api/health"
    # Without configured proxies the header is client-controlled and ignored.
    direct = client_for(0).get("/api/health/", headers=headers, follow_redirects=False)
    assert direct.headers["location"] == "http://engine.example/api/health"
