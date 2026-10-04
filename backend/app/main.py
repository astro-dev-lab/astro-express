"""Single-origin app with ephemeral demo or PostgreSQL-backed credential authentication. No vendor clients."""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
import psycopg
from starlette.concurrency import run_in_threadpool
from .auth import DUMMY_HASH, verify_password, csrf_for
from .store import PostgresStore, StoreUnavailable
from .observability import event as log_event

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import Settings
from .security import HardenedFastAPI

USER = {"id": "demo-admin", "display_name": "Demo Operator", "role": "demo_admin"}
COOKIE = "astro_demo_session"
TTL = 3600
MAX_SESSIONS = 128
FIXTURES = {
    "stripe": ("Stripe", "checkout-success", "payment-declined", "Synthetic checkout completed.", "Synthetic payment declined."),
    "hubspot": ("HubSpot", "contact-qualified", "duplicate", "Synthetic contact qualified.", "Synthetic duplicate contact rejected."),
    "notion": ("Notion", "create-page", "permission-denied", "Synthetic page created.", "Synthetic permission denied."),
    "resend": ("Resend", "email-queued", "bounced", "Synthetic email queued; nothing sent.", "Synthetic email bounced; nothing sent."),
    "twilio": ("Twilio", "sms-queued", "invalid-number", "Synthetic SMS queued; nothing sent.", "Synthetic number rejected; nothing sent."),
    "google": ("Google", "calendar-event-created", "authorization-rejected", "Synthetic event created; no calendar written.", "Synthetic authorization rejected; no sign-in attempted."),
}

@dataclass
class Session:
    csrf: str
    expires: float
    events: deque = field(default_factory=lambda: deque(maxlen=100))

class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9_.-]{2,63}$")
    password: str = Field(min_length=1, max_length=256, repr=False)


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: str = Field(min_length=1, max_length=64)


class SimulationResult(BaseModel):
    provider: str
    action: str
    mode: Literal["simulated"]
    connected: Literal[False]
    status: Literal["success", "failed"]
    reference: str
    message: str
    timestamp: str

class ActivityResult(BaseModel):
    events: list[SimulationResult]


def create_app(settings: Settings | None = None, repository=None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = repository if repository is not None else (PostgresStore(settings.database_url) if settings.mode == "production" else None)

    @asynccontextmanager
    async def lifespan(app):
        if store is not None:
            try:
                await run_in_threadpool(store.ready)
            except (psycopg.Error, StoreUnavailable):
                log_event("startup_blocked", settings.mode)
                raise RuntimeError("Production startup blocked: local database or migrations not ready") from None
            log_event("startup_ready", settings.mode)
        yield

    app = HardenedFastAPI(title="ME Astro Fast", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlsplit(settings.origin).hostname if urlsplit(settings.origin).hostname != "::1" else "[::1]"] if settings.mode == "production" else ["127.0.0.1", "localhost", "[::1]"])
    sessions: dict[str, Session] = {}
    app.state.sessions = sessions
    app.state.repository = store

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Never echo validation inputs: they can include password/body secrets.
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @app.middleware("http")
    async def safeguards(request: Request, call_next):
        if settings.mode == "production" and request.url.scheme != "https":
            return Response("HTTPS required", status_code=400)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("origin") != settings.origin:
                return Response("Invalid request origin", status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return Response("Cross-site request rejected", status_code=403)
            length = request.headers.get("content-length", "0")
            if not length.isdigit() or int(length) > 4096:
                return Response("Request too large", status_code=413)
            chunks = []
            total = 0
            async for chunk in request.stream():
                total += len(chunk)
                if total > 4096:
                    return Response("Request too large", status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        return response

    async def database_call(method, *args):
        try:
            return await run_in_threadpool(method, *args)
        except (psycopg.Error, StoreUnavailable):
            log_event("database_unavailable", settings.mode)
            raise HTTPException(503, "Service temporarily unavailable") from None

    def session_token(request):
        token = request.cookies.get(COOKIE, "")
        if len(token) > 128:
            raise HTTPException(401, "Session required")
        return token

    async def authorized(request: Request, mutate=False):
        if store is not None:
            token = session_token(request)
            user = await database_call(store.session_user, token)
            if not user:
                raise HTTPException(401, "Session required")
            csrf = csrf_for(token)
            if mutate:
                if not secrets.compare_digest(request.headers.get("x-csrf-token", "").encode(), csrf.encode()):
                    raise HTTPException(403, "Invalid CSRF token")
                if user["role"] != "admin":
                    raise HTTPException(403, "Administrator role required")
            return {"user": {"id": str(user["id"]), "display_name": user["display_name"], "role": user["role"]}, "csrf_token": csrf}
        return authorized_demo(request, mutate)

    def authorized_demo(request: Request, mutate=False) -> Session:
        token = request.cookies.get(COOKIE, "")
        session = sessions.get(token)
        if not session or session.expires <= time.monotonic():
            sessions.pop(token, None)
            raise HTTPException(401, "Demo session required")
        if mutate and not secrets.compare_digest(request.headers.get("x-csrf-token", "").encode(), session.csrf.encode()):
            raise HTTPException(403, "Invalid CSRF token")
        return session

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "mode": settings.mode}

    @app.get("/readyz")
    async def readiness():
        if store is not None:
            await database_call(store.ready)
        return {"status": "ready", "mode": settings.mode}

    @app.get("/api/auth/config")
    async def auth_config():
        return {"mode": settings.mode, "credential_login": settings.mode == "production"}

    @app.post("/api/auth/login")
    async def credential_login(body: Credentials, request: Request, response: Response):
        if store is None:
            raise HTTPException(404, "Credential login unavailable")
        if not await database_call(store.allow_login_attempt, body.username):
            log_event("login_throttled", settings.mode)
            raise HTTPException(429, "Login temporarily unavailable; retry later")
        user = await database_call(store.user_by_username, body.username)
        valid = await run_in_threadpool(verify_password, user["password_hash"] if user else DUMMY_HASH, body.password)
        if not valid or not user or user["blocked"]:
            log_event("login_rejected", settings.mode)
            raise HTTPException(401, "Invalid credentials")
        token = secrets.token_urlsafe(32)
        await database_call(store.create_session, user["id"], token, session_token(request))
        response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, secure=True, samesite="strict", path="/")
        log_event("login_success", settings.mode)
        return {"user": {"id": str(user["id"]), "display_name": user["display_name"], "role": user["role"]}, "csrf_token": csrf_for(token)}

    @app.post("/api/auth/demo-login")
    async def login(request: Request, response: Response):
        if store is not None:
            raise HTTPException(404, "Demo login disabled")
        now = time.monotonic()
        for key in list(sessions):
            if sessions[key].expires <= now:
                del sessions[key]
        sessions.pop(request.cookies.get(COOKIE, ""), None)
        if len(sessions) >= MAX_SESSIONS:
            raise HTTPException(429, "Demo session limit reached; retry later")
        token = secrets.token_urlsafe(32)
        session = Session(secrets.token_urlsafe(32), now + TTL)
        sessions[token] = session
        response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, secure=settings.origin.startswith("https:"), samesite="strict", path="/")
        return {"user": USER, "csrf_token": session.csrf}

    @app.get("/api/auth/me")
    async def me(request: Request):
        session = await authorized(request)
        return session if store is not None else {"user": USER, "csrf_token": session.csrf}

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response):
        session = await authorized(request)
        csrf = session["csrf_token"] if store is not None else session.csrf
        if not secrets.compare_digest(request.headers.get("x-csrf-token", "").encode(), csrf.encode()):
            raise HTTPException(403, "Invalid CSRF token")
        if store is not None:
            await database_call(store.revoke_session, session_token(request))
            log_event("logout", settings.mode)
        else:
            sessions.pop(request.cookies.get(COOKIE, ""), None)
        response.delete_cookie(COOKIE, path="/", secure=settings.origin.startswith("https:"), httponly=True, samesite="strict")
        return {"status": "logged_out"}

    @app.post("/api/admin/users/{user_id}/revoke-sessions")
    async def revoke_sessions(user_id: str, request: Request):
        if store is None:
            raise HTTPException(404, "Administrative route unavailable")
        await authorized(request, True)
        from uuid import UUID
        try:
            UUID(user_id)
        except ValueError:
            raise HTTPException(422, "Invalid user identifier") from None
        await database_call(store.revoke_user_sessions, user_id)
        log_event("sessions_revoked", settings.mode)
        return {"status": "revoked"}

    @app.get("/api/integrations")
    async def integrations(request: Request):
        await authorized(request)
        return {"integrations": [{"id": key, "name": f[0], "mode": "simulated", "connected": False,
                    "sandbox_status": "not_configured",
                    "actions": [{"id": action, "label": action.replace("-", " ").capitalize(), "status": status}
                                for action, status in [(f[1], "success"), (f[2], "failed")]]} for key, f in FIXTURES.items()]}

    @app.post("/api/integrations/{provider}/simulate", response_model=SimulationResult)
    async def simulate(provider: str, body: SimulationRequest, request: Request):
        session = await authorized(request, True)
        fixture = FIXTURES.get(provider)
        if not fixture:
            raise HTTPException(404, "Unknown simulated provider")
        if body.action not in fixture[1:3]:
            raise HTTPException(422, "Unsupported fixture action")
        success = body.action == fixture[1]
        event = {"provider": provider, "action": body.action, "mode": "simulated", "connected": False,
                 "status": "success" if success else "failed", "reference": "demo-" + secrets.token_hex(12),
                 "message": fixture[3] if success else fixture[4], "timestamp": datetime.now(timezone.utc).isoformat()}
        if store is not None:
            await database_call(store.record_activity, session["user"]["id"], event)
        else:
            session.events.appendleft(event)
        return event

    @app.get("/api/activity", response_model=ActivityResult)
    async def activity(request: Request):
        session = await authorized(request)
        return {"events": await database_call(store.activity, session["user"]["id"]) if store is not None else list(session.events)}

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        @app.get("/")
        async def index():
            return FileResponse(dist / "index.html")
    return app

app = create_app()
