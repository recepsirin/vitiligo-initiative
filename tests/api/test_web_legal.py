"""Smoke tests for public legal pages."""

from __future__ import annotations

from fastapi.testclient import TestClient

from vitiligo.web.app import create_app


def test_legal_pages_are_served() -> None:
    client = TestClient(create_app())
    for path in ("/", "/privacy", "/terms"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert "Vitiligo Initiative" in resp.text

    privacy = client.get("/privacy")
    assert "Privacy Policy" in privacy.text

    terms = client.get("/terms")
    assert "Not medical advice" in terms.text
