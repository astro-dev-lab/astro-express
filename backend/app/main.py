"""Single-origin, ephemeral, synthetic demo. No vendor clients or network calls."""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import secrets
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import Settings

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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="ME Astro Fast offline demo", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
    sessions: dict[str, Session] = {}
    app.state.sessions = sessions

    @app.middleware("http")
    async def safeguards(request: Request, call_next):
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
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY", "Content-Security-Policy": "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    def authorized(request: Request, mutate=False) -> Session:
        token = request.cookies.get(COOKIE, "")
        session = sessions.get(token)
        if not session or session.expires <= time.monotonic():
            sessions.pop(token, None)
            raise HTTPException(401, "Demo session required")
        if mutate and not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
            raise HTTPException(403, "Invalid CSRF token")
        return session

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "mode": "simulation"}

    @app.post("/api/auth/demo-login")
    async def login(request: Request, response: Response):
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
        return {"user": USER, "csrf_token": authorized(request).csrf}

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response):
        authorized(request, True)
        sessions.pop(request.cookies.get(COOKIE, ""), None)
        response.delete_cookie(COOKIE, path="/", secure=settings.origin.startswith("https:"), httponly=True, samesite="strict")
        return {"status": "logged_out"}

    @app.get("/api/integrations")
    async def integrations(request: Request):
        authorized(request)
        return {"integrations": [{"id": key, "name": f[0], "mode": "simulated", "connected": False,
                    "actions": [{"id": action, "label": action.replace("-", " ").capitalize(), "status": status}
                                for action, status in [(f[1], "success"), (f[2], "failed")]]} for key, f in FIXTURES.items()]}

    @app.post("/api/integrations/{provider}/simulate", response_model=SimulationResult)
    async def simulate(provider: str, body: SimulationRequest, request: Request):
        session = authorized(request, True)
        fixture = FIXTURES.get(provider)
        if not fixture:
            raise HTTPException(404, "Unknown simulated provider")
        if body.action not in fixture[1:3]:
            raise HTTPException(422, "Unsupported fixture action")
        success = body.action == fixture[1]
        event = {"provider": provider, "action": body.action, "mode": "simulated", "connected": False,
                 "status": "success" if success else "failed", "reference": "demo-" + secrets.token_hex(12),
                 "message": fixture[3] if success else fixture[4], "timestamp": datetime.now(timezone.utc).isoformat()}
        session.events.appendleft(event)
        return event

    @app.get("/api/activity", response_model=ActivityResult)
    async def activity(request: Request):
        return {"events": list(authorized(request).events)}

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        @app.get("/")
        async def index():
            return FileResponse(dist / "index.html")
    return app

app = create_app()
