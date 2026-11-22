"""Jury access gate protects every UI, documentation and API route."""
import pytest
from fastapi.testclient import TestClient

from app.jury_auth import (
    _failed, _sessions, COOKIE, make_password_hash, safe_destination,
)
from app.main import app


@pytest.fixture
def configured_jury(monkeypatch):
    monkeypatch.setenv("FORMFLOW_AUTH_MODE", "on")
    monkeypatch.setenv("FORMFLOW_AUTH_USER", "jury")
    monkeypatch.setenv(
        "FORMFLOW_AUTH_PASSWORD_HASH",
        make_password_hash("testing-password-for-jury-123", rounds=100_000),
    )
    _failed.clear()
    _sessions.clear()
    yield
    _failed.clear()
    _sessions.clear()


@pytest.fixture
def jury_client(configured_jury):
    # Secure cookies require HTTPS, like the Tailscale reverse-proxy deployment.
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def test_protected_paths_are_inaccessible_before_login(jury_client):
    ui = ("/", "/projekt/", "/documentation/", "/documentation/api.html",
          "/api/docs", "/api/openapi.json", "/readyz", "/api/v1/demo/convert",
          "/static/app.js", "/static/preview.bundle.js", "/static/project.css",
          "/static/documentation/docs.css", "/static/batch.js")
    for path in ui:
        response = jury_client.get(path, follow_redirects=False)
        assert response.status_code in (303, 401), (path, response.status_code)
        assert "FormFlow" not in response.text or "Wymagane logowanie" in response.text
    assert jury_client.get("/healthz").status_code == 200
    assert jury_client.get("/login").status_code == 200
    assert jury_client.get("/static/login.css").status_code == 200
    assert jury_client.get("/projekt/", follow_redirects=False).headers["location"].startswith("/login")
    assert jury_client.get("/api/openapi.json").status_code == 401


def test_post_endpoint_and_source_upload_require_auth(jury_client):
    response = jury_client.post(
        "/api/v1/forms/inspect",
        files={"file": ("form.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"
    response = jury_client.post("/api/v1/forms/batch/export", json={"forms": []})
    assert response.status_code == 401
    response = jury_client.post("/api/v1/forms/convert?mode=diagnostic",
        files={"file": ("a.pdf", b"%PDF-1.7\n", "application/pdf")})
    assert response.status_code == 401


def test_jury_login_allows_app_docs_and_api_then_logout_revokes(jury_client):
    response = jury_client.post("/auth/login", data={
        "username": "jury",
        "password": "testing-password-for-jury-123",
        "next": "/projekt/",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/projekt/"
    cookie = response.headers["set-cookie"]
    assert COOKIE in cookie and "Secure" in cookie and "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    for path in ("/", "/projekt/", "/documentation/", "/api/docs",
                 "/api/openapi.json", "/api/v1/demo/convert",
                 "/static/app.js", "/static/project.css", "/readyz"):
        response = jury_client.get(path, follow_redirects=False)
        assert response.status_code in (200, 307), (path, response.status_code)
    response = jury_client.post(
        "/api/v1/forms/inspect",
        files={"file": ("valid.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    assert response.status_code == 200
    response = jury_client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 303
    assert jury_client.get("/api/v1/demo/convert").status_code == 401
    assert jury_client.get("/projekt/", follow_redirects=False).status_code == 303


def test_bad_credentials_and_rate_limit(jury_client):
    wrong = jury_client.post("/auth/login", data={
        "username": "jury", "password": "wrong password"
    })
    assert wrong.status_code == 401
    assert "Nieprawidłowy login lub hasło" in wrong.text
    for _ in range(9):
        jury_client.post("/auth/login", data={
            "username": "jury", "password": "another wrong password"
        })
    limited = jury_client.post("/auth/login", data={
        "username": "jury", "password": "testing-password-for-jury-123"
    })
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "300"


def test_missing_configuration_fails_closed(jury_client, monkeypatch):
    monkeypatch.delenv("FORMFLOW_AUTH_PASSWORD_HASH", raising=False)
    response = jury_client.get("/projekt/", follow_redirects=False)
    assert response.status_code == 503
    assert jury_client.get("/api/openapi.json").status_code == 503


def test_block_cross_site_login_and_cookie_use(jury_client):
    cross_site = jury_client.post("/auth/login", headers={
        "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site",
    }, data={"username": "jury", "password": "testing-password-for-jury-123"})
    assert cross_site.status_code == 403
    jury_client.post("/auth/login", data={
        "username": "jury", "password": "testing-password-for-jury-123"
    })
    forbidden = jury_client.post(
        "/api/v1/forms/validate-json",
        headers={"Origin": "https://evil.example"},
        json={"title": "form"},
    )
    assert forbidden.status_code == 403


def test_no_open_redirect_after_login(jury_client):
    assert safe_destination("//evil.example") == "/projekt/"
    assert safe_destination("https://evil.example") == "/projekt/"
    assert safe_destination("/%2Fevil.example") == "/projekt/"
    result = jury_client.post("/auth/login", data={
        "username": "jury", "password": "testing-password-for-jury-123",
        "next": "//evil.example",
    }, follow_redirects=False)
    assert result.status_code == 303
    assert result.headers["location"] == "/projekt/"
