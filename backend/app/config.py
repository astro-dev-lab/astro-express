"""Explicit, fail-closed mode and origin configuration. P1 database scope is local."""
import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
ACK = "I_ACCEPT_PRODUCTION_SECURITY_REQUIREMENTS"


def validate_database_url(value: str) -> str:
    if any(os.getenv(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        raise ValueError("libpq destination or options environment overrides are forbidden")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if (parsed.scheme not in {"postgresql", "postgres"} or parsed.hostname not in LOOPBACK
                or not parsed.path.strip("/") or parsed.query or parsed.fragment
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("DATABASE_URL must identify a local PostgreSQL database without query overrides") from None
    return value


@dataclass(frozen=True)
class Settings:
    origin: str = "http://127.0.0.1:8000"
    mode: str = "simulation"
    production_ack: str = field(default="", repr=False)
    database_url: str = field(default="", repr=False)

    def __post_init__(self):
        try:
            parsed = urlsplit(self.origin)
            port = parsed.port
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password
                    or (parsed.hostname not in LOOPBACK and not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", parsed.hostname))
                    or (port is not None and not 1 <= port <= 65535)):
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("APP_ORIGIN must be an exact HTTP(S) origin") from None
        if self.mode == "simulation":
            if parsed.hostname not in LOOPBACK or self.database_url or self.production_ack:
                raise ValueError("Simulation requires loopback origin and no production configuration")
        elif self.mode == "production":
            if parsed.scheme != "https" or self.production_ack != ACK:
                raise ValueError("Production requires HTTPS and explicit PRODUCTION_ACK")
            validate_database_url(self.database_url)
        else:
            raise ValueError("APP_MODE must be simulation or production")

    @classmethod
    def from_env(cls):
        mode = os.getenv("APP_MODE", "simulation")
        if mode == "production" and "APP_ORIGIN" not in os.environ:
            raise ValueError("Production requires explicit APP_ORIGIN")
        return cls(origin=os.getenv("APP_ORIGIN", os.getenv("DEMO_ORIGIN", cls.origin)), mode=mode,
                   production_ack=os.getenv("PRODUCTION_ACK", ""), database_url=os.getenv("DATABASE_URL", ""))
