"""Small, fail-closed jury access gate for every FormFlow route.

One shared jury account, PBKDF2-SHA256 password, short-lived server-side
sessions and secure host-only cookie. No external auth service or third-party JS.
Only /login, /auth/login, the public login CSS and Docker liveness are exempt.
"""
from __future__ import annotations

from collections import deque
from hashlib import pbkdf2_hmac, sha256
from html import escape
import hmac
import os
import re
import secrets
import time
from urllib.parse import parse_qs, quote, urlsplit

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

COOKIE = "__Host-formflow_jury"
SESSION_SECONDS = 8 * 60 * 60
MAX_FAILURES = 10
FAILURE_WINDOW_SECONDS = 5 * 60

_sessions: dict[str, float] = {}
_failed: deque[float] = deque()


def enabled() -> bool:
    # Authentication is ON unless deliberately disabled (only for local tests).
    return os.getenv("FORMFLOW_AUTH_MODE", "on").strip().lower() != "off"


def make_password_hash(password: str, *, rounds: int = 310_000) -> str:
    if len(password) < 16:
        raise ValueError("Jury password must contain at least 16 characters.")
    if rounds < 100_000 or rounds > 1_000_000:
        raise ValueError("Invalid PBKDF2 cost.")
    salt = secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), rounds)
    return f"pbkdf2_sha256:{rounds}:{salt}:{digest.hex()}"


def configured() -> bool:
    return bool(os.getenv("FORMFLOW_AUTH_USER")) and _hash_components() is not None


def _hash_components() -> tuple[int, bytes, bytes] | None:
    try:
        algorithm, count, salt_hex, digest_hex = os.getenv(
            "FORMFLOW_AUTH_PASSWORD_HASH", ""
        ).split(":")
        rounds = int(count)
        salt, digest = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
        if (
            algorithm != "pbkdf2_sha256"
            or rounds < 100_000 or rounds > 1_000_000
            or len(salt) != 16 or len(digest) != 32
        ):
            return None
        return rounds, salt, digest
    except (ValueError, TypeError):
        return None


def verify_password(username: str, password: str) -> bool:
    values = _hash_components()
    if values is None or len(username) > 128 or len(password) > 1024:
        return False
    rounds, salt, expected = values
    derived = pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return (
        hmac.compare_digest(derived, expected)
        and hmac.compare_digest(
            username.encode(), os.getenv("FORMFLOW_AUTH_USER", "").encode()
        )
    )


def safe_destination(value: str | None) -> str:
    """Allow only same-origin relative navigation; never redirect off-host."""
    target = value or "/projekt/"
    if (
        not target.startswith("/")
        or target.startswith("//")
        or "\\" in target
        or len(target) > 256
        or any(ord(c) < 32 or ord(c) == 127 for c in target)
    ):
        return "/projekt/"
    # URL-encoded //, backslashes and credentials are not valid destinations.
    if target.lower().startswith(("/%2f", "/%5c")):
        return "/projekt/"
    return target


def _session_valid(request: Request) -> bool:
    token = request.cookies.get(COOKIE, "")
    if len(token) != 43 or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return False
    key = sha256(token.encode("ascii")).hexdigest()
    now = time.time()
    expires = _sessions.get(key)
    if expires is None:
        return False
    if expires <= now:
        _sessions.pop(key, None)
        return False
    return True


def _start_session(response: Response) -> None:
    now = time.time()
    for key, expiry in tuple(_sessions.items()):
        if expiry <= now:
            _sessions.pop(key, None)
    if len(_sessions) >= 256:
        _sessions.pop(next(iter(_sessions)))
    token = secrets.token_urlsafe(32)
    _sessions[sha256(token.encode()).hexdigest()] = now + SESSION_SECONDS
    response.set_cookie(
        COOKIE, token, httponly=True, secure=True, samesite="lax",
        max_age=SESSION_SECONDS, path="/",
    )


def _end_session(request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        _sessions.pop(sha256(token.encode()).hexdigest(), None)
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")


def _origin_is_safe(request: Request) -> bool:
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    return (
        parsed.scheme in ("http", "https")
        and parsed.netloc.lower() == request.headers.get("host", "").lower()
        and not parsed.username and not parsed.password
    )


def _failure_limit() -> bool:
    now = time.monotonic()
    while _failed and _failed[0] < now - FAILURE_WINDOW_SECONDS:
        _failed.popleft()
    return len(_failed) >= MAX_FAILURES


def _login_html(*, failed: bool = False, blocked: bool = False, dest: str = "/projekt/") -> str:
    hint = ""
    if blocked:
        hint = '<p class="error" role="alert">Zbyt wiele prób logowania. Spróbuj ponownie za kilka minut.</p>'
    elif failed:
        hint = '<p class="error" role="alert">Nieprawidłowy login lub hasło.</p>'
    return """<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="robots" content="noindex,nofollow">
<title>Logowanie — FormFlow AI</title>
<link rel="stylesheet" href="/static/login.css"></head>
<body>
<main class="login-card">
  <div class="brand"><span class="brand-mark">F·</span> FormFlow <small>AI</small></div>
  <span class="eyebrow">HackNation 2026 · Dostęp dla jury</span>
  <h1>Zaloguj się</h1>
  <p>Materiały konkursowe i demonstracja są dostępne po zalogowaniu.</p>
  """ + hint + """
  <form method="post" action="/auth/login" autocomplete="on">
    <input type="hidden" name="next" value="""" + escape(dest, quote=True) + """">
    <label for="jury-user">Login</label>
    <input id="jury-user" name="username" type="text" autocomplete="username" required maxlength="128" autofocus>
    <label for="jury-pass">Hasło</label>
    <input id="jury-pass" name="password" type="password" autocomplete="current-password" required>
    <button type="submit">Zaloguj się →</button>
  </form>
</main>
<footer>FormFlow AI · HackNation 2026 · COI</footer>
</body></html>
"""


async def access_gate(request: Request) -> Response | None:
    if not enabled():
        return None
    path = request.url.path
    method = request.method.upper()

    # Only the liveness probe is publicly readable; it contains no protected data.
    if path == "/healthz" and method == "GET":
        return None
    if path == "/static/login.css" and method == "GET":
        return None

    if not configured():
        return HTMLResponse(
            "<!doctype html><html lang='pl'><meta charset='utf-8'>"
            "<title>FormFlow — konfiguracja</title>"
            "<h1>Logowanie nie jest skonfigurowane.</h1>"
            "<p>Administrator musi skonfigurować dostęp jury.</p></html>",
            status_code=503,
        )

    if path == "/login" and method == "GET":
        if _session_valid(request):
            return RedirectResponse("/projekt/", status_code=303)
        return HTMLResponse(_login_html(dest=safe_destination(request.query_params.get("next"))))

    if path == "/auth/login" and method == "POST":
        if not _origin_is_safe(request):
            return JSONResponse({"code": "INVALID_ORIGIN"}, status_code=403)
        if _failure_limit():
            response = HTMLResponse(_login_html(blocked=True), status_code=429)
            response.headers["Retry-After"] = "300"
            return response
        if not request.headers.get("content-type", "").startswith(
            "application/x-www-form-urlencoded"
        ):
            return JSONResponse({"code": "INVALID_LOGIN_BODY"}, status_code=415)
        body = await request.body()
        if len(body) > 2048:
            return JSONResponse({"code": "LOGIN_TOO_LARGE"}, status_code=413)
        try:
            form = parse_qs(body.decode("utf-8"), max_num_fields=4, keep_blank_values=True)
        except (UnicodeDecodeError, ValueError):
            form = {}
        username = (form.get("username") or [""])[0]
        password = (form.get("password") or [""])[0]
        dest = safe_destination((form.get("next") or [None])[0])
        if not verify_password(username, password):
            _failed.append(time.monotonic())
            return HTMLResponse(_login_html(failed=True, dest=dest), status_code=401)
        _failed.clear()
        response = RedirectResponse(dest, status_code=303)
        _start_session(response)
        return response

    if not _session_valid(request):
        if method == "GET" and (
            path == "/"
            or path == "/api/docs"
            or path == "/projekt" or path.startswith("/projekt/")
            or path == "/documentation" or path.startswith("/documentation/")
        ):
            return RedirectResponse(
                "/login?next=" + quote(safe_destination(
                    path + ("?" + request.url.query if request.url.query else "")
                ), safe="/"),
                status_code=303,
            )
        return JSONResponse(
            {"detail": "Wymagane logowanie do FormFlow.", "code": "AUTH_REQUIRED"},
            status_code=401,
            headers={"WWW-Authenticate": 'Form realm="FormFlow jury"'},
        )

    if method not in ("GET", "HEAD", "OPTIONS") and not _origin_is_safe(request):
        return JSONResponse({"detail": "Nieprawidłowe pochodzenie żądania.", "code": "INVALID_ORIGIN"}, status_code=403)

    if path == "/auth/logout" and method == "POST":
        response = RedirectResponse("/login", status_code=303)
        _end_session(request, response)
        return response
    return None
