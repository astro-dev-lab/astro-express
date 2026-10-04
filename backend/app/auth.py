"""Password and opaque-token primitives; no reusable signing secret or seeded password."""
import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

# Argon2id vetted implementation with its current RFC9106 low-memory defaults.
PASSWORD_HASHER = PasswordHasher()
DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    if not 16 <= len(password) <= 256:
        raise ValueError("Password must contain 16 to 256 characters")
    return PASSWORD_HASHER.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_for(token: str) -> str:
    return hashlib.sha256(("astro-csrf:" + token).encode("utf-8")).hexdigest()
