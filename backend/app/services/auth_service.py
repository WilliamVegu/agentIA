"""Server authentication for a single operator of this local studio."""
import hashlib
import hmac
import ipaddress
import os
import secrets
import threading
import time
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])
_lock = threading.Lock()
_sessions = {}
_attempts = {}
COOKIE = "agentia_session"
TTL = 8 * 60 * 60


def _local_host(host):
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host or "")
        return address.is_loopback or bool(
            getattr(address, "ipv4_mapped", None) and address.ipv4_mapped.is_loopback
        )
    except ValueError:
        return False


def _automatic_local_user(request):
    if os.environ.get("STUDIO_AUTO_LOGIN", "true").strip().lower() not in {"true", "1", "yes"}:
        return None
    if not request.client or not _local_host(request.client.host):
        return None
    if not _local_host(request.url.hostname):
        return None
    # Browser requests through the local development proxy retain their origin.
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if value:
            try:
                if not _local_host(urlsplit(value).hostname):
                    return None
            except ValueError:
                return None
    if request.headers.get("forwarded") or request.headers.get("x-forwarded-for"):
        return None
    return {"email": "mvp@localhost", "name": "MVP local", "role": "Architect", "accessMode": "mvp"}


def authenticated_user(request):
    token = request.cookies.get(COOKIE, "")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with _lock:
        entry = _sessions.get(digest)
        if entry and entry[0] > time.time():
            return entry[1]
        _sessions.pop(digest, None)
    return None


def _create_session(user, request, response):
    now = time.time()
    token = secrets.token_urlsafe(32)
    with _lock:
        for key, entry in list(_sessions.items()):
            if entry[0] <= now:
                del _sessions[key]
        _sessions[hashlib.sha256(token.encode()).hexdigest()] = (now + TTL, user)
    response.set_cookie(COOKIE, token, httponly=True, secure=request.url.scheme == "https",
                        samesite="strict", max_age=TTL, path="/api/v1")
    return user


@router.post("/mvp")
def enter_mvp(request: Request, response: Response):
    user = _automatic_local_user(request)
    if not user:
        raise HTTPException(403, "El acceso al MVP está disponible únicamente en modo local habilitado.")
    return _create_session(user, request, response)


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    password = os.environ.get("STUDIO_ACCESS_TOKEN", "")
    email = os.environ.get("STUDIO_USER_EMAIL", "").strip().lower()
    if len(password) < 16 or not email:
        raise HTTPException(503, "Configure STUDIO_USER_EMAIL and STUDIO_ACCESS_TOKEN (at least 16 characters) on the backend.")
    address = request.client.host if request.client else "unknown"
    now = time.time()
    with _lock:
        recent = [t for t in _attempts.get(address, []) if t > now - 60]
        if len(recent) >= 10:
            raise HTTPException(429, "Too many login attempts. Retry in one minute.")
        _attempts[address] = recent + [now]
    if not (hmac.compare_digest(payload.email.strip().lower().encode(), email.encode())
            and hmac.compare_digest(payload.password.encode(), password.encode())):
        raise HTTPException(401, "Invalid credentials")
    user = {"email": email, "name": email.split("@")[0], "role": "Architect"}
    return _create_session(user, request, response)


@router.get("/session")
def session(request: Request):
    user = authenticated_user(request)
    if not user:
        raise HTTPException(401, "Authentication required")
    return user


@router.post("/logout")
def logout(request: Request, response: Response):
    digest = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
    with _lock:
        _sessions.pop(digest, None)
    response.delete_cookie(COOKIE, path="/api/v1")
    return {"success": True}
