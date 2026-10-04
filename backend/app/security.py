"""Apply hardening at the outer ASGI boundary, including rejection/error paths."""
from fastapi import FastAPI

HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}


class HardenedFastAPI(FastAPI):
    async def __call__(self, scope, receive, send):
        async def hardened_send(message):
            if message["type"] == "http.response.start":
                headers = [
                    (key, value) for key, value in message.get("headers", [])
                    if key.decode("latin-1").lower() not in HEADERS
                ]
                headers.extend((key.encode(), value.encode()) for key, value in HEADERS.items())
                message = {**message, "headers": headers}
            await send(message)

        await super().__call__(scope, receive, hardened_send)
