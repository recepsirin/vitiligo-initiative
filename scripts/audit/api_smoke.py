#!/usr/bin/env python3
"""Smoke-test every public API route against the local corpus."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from vitiligo.storage import init_db
from vitiligo.web.app import create_app


def main() -> int:
    init_db()
    client = TestClient(create_app())
    errors: list[str] = []

    def check(name: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — audit script
            errors.append(f"{name}: {exc}")

    def get(path: str, **kw):
        r = client.get(path, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"GET {path} -> {r.status_code} {r.text[:200]}")

    def post(path: str, body: dict):
        r = client.post(path, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"POST {path} -> {r.status_code} {r.text[:200]}")

    check("health", lambda: get("/api/health"))
    check("stats", lambda: get("/api/stats"))
    check("index", lambda: get("/"))
    check("privacy", lambda: get("/privacy"))
    check("terms", lambda: get("/terms"))
    check("graph_stats", lambda: get("/api/graph/stats"))
    check("graph_search", lambda: get("/api/graph/search", params={"q": "vitiligo", "limit": 5}))
    check("graph_neighbors", lambda: get("/api/graph/neighbors", params={"name": "vitiligo", "limit": 5}))
    check("graph_export", lambda: get("/api/graph/export", params={"edge_limit": 10}))
    check("trials_stats", lambda: get("/api/trials/stats"))
    check(
        "trials_search",
        lambda: post(
            "/api/trials/search",
            {"query": "tacrolimus", "limit": 5, "offset": 0},
        ),
    )
    check(
        "trials_intervention_only",
        lambda: _assert_nct_in_trials(client, "tacrolimus", "NCT03365141"),
    )
    check("search", lambda: post("/api/search", {"query": "vitiligo JAK", "top_k": 3}))
    check(
        "candidates",
        lambda: _assert_candidates(client),
    )

    # LLM routes — 503 without key is acceptable; 500 is not.
    for name, path, body in [
        ("ask", "/api/ask", {"question": "What is vitiligo?", "top_k": 3}),
        ("hypothesize", "/api/hypothesize", {"intent": "stop spread vitiligo", "top_k": 10}),
    ]:
        r = client.post(path, json=body)
        if r.status_code not in (200, 503):
            errors.append(f"{name}: POST -> {r.status_code} {r.text[:200]}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    return 0


def _assert_nct_in_trials(client: TestClient, query: str, nct: str) -> None:
    r = client.post("/api/trials/search", json={"query": query, "limit": 50, "offset": 0})
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    ids = {t["source_id"] for t in r.json().get("results", [])}
    if nct not in ids:
        raise RuntimeError(f"{nct} not in trials search for {query!r}")


def _assert_candidates(client: TestClient) -> None:
    r = client.get("/api/report/candidates", params={"top_n": 3})
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    data = r.json()
    if not data.get("global_top"):
        raise RuntimeError("empty global_top")
    if not isinstance(data.get("notes"), list):
        raise RuntimeError("notes must be list")


if __name__ == "__main__":
    raise SystemExit(main())
