"""Fail-closed configuration for a loopback-only offline demonstration."""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

@dataclass(frozen=True)
class Settings:
    origin: str = "http://127.0.0.1:8000"
    mode: str = "simulation"

    def __post_init__(self):
        parsed = urlsplit(self.origin)
        _ = parsed.port
        if self.mode != "simulation":
            raise ValueError("Only offline simulation mode is supported")
        if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ValueError("DEMO_ORIGIN must be an exact loopback HTTP(S) origin")

    @classmethod
    def from_env(cls):
        return cls(origin=os.getenv("DEMO_ORIGIN", cls.origin), mode=os.getenv("APP_MODE", "simulation"))
