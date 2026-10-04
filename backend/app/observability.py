"""Fixed-field structured events only; never accept request/user/exception details."""
import json
import logging

LOGGER = logging.getLogger("astro.security")
LOGGER.setLevel(logging.INFO)
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
EVENTS = {"startup_ready", "startup_blocked", "database_unavailable", "login_rejected", "login_throttled", "login_success", "logout", "sessions_revoked"}


def event(name: str, mode: str):
    if name not in EVENTS or mode not in {"simulation", "production"}:
        raise ValueError("Unsafe log fields rejected")
    LOGGER.info(json.dumps({"event": name, "mode": mode}, separators=(",", ":")))
