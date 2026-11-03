"""Password hashing and single-process bearer sessions for customer sign-in."""

import hashlib
import hmac
import secrets
from threading import Lock
from time import monotonic


SESSION_TTL_SECONDS = 3600
_sessions: dict[str, tuple[int, float]] = {}
_session_lock = Lock()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    # Only the supported format is accepted; stored parameters cannot force
    # unexpectedly expensive work. Malformed hashes are storage errors (500).
    algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$")
    salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    if (algorithm, n, r, p) != ("scrypt", "16384", "8", "1") or len(salt) != 16 or len(expected) != 64:
        raise ValueError("Invalid stored password hash")
    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return hmac.compare_digest(actual, expected)


def issue_token(customer_id: int) -> str:
    token = secrets.token_urlsafe(32)
    key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = monotonic()
    with _session_lock:
        for expired in [key for key, (_, expiry) in _sessions.items() if expiry <= now]:
            del _sessions[expired]
        _sessions[key] = (customer_id, now + SESSION_TTL_SECONDS)
    return token


def resolve_token(token: str) -> int | None:
    """Resolve a credential for #77; guards must re-read account state/roles."""
    key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _session_lock:
        session = _sessions.get(key)
        if session is None:
            return None
        customer_id, expiry = session
        if expiry <= monotonic():
            del _sessions[key]
            return None
        return customer_id
