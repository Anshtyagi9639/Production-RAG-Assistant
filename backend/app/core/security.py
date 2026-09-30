import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

_JWT_ALGORITHM = "HS256"
_password_hasher = PasswordHasher()

# Verifying against this when the email is unknown keeps login timing the same for
# existing and non-existing accounts, so response time doesn't reveal which emails exist.
_DUMMY_HASH = _password_hasher.hash("timing-equalizer")


class InvalidTokenError(Exception):
    """The access token is missing claims, malformed, expired or wrongly signed."""


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _password_hasher.verify(password_hash or _DUMMY_HASH, password) and bool(
            password_hash
        )
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID, settings: Settings) -> tuple[str, int]:
    """Return a signed JWT for the user and its lifetime in seconds."""
    lifetime = timedelta(minutes=settings.jwt_expire_minutes)
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "iat": now, "exp": now + lifetime}
    token = jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), _JWT_ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError from exc
