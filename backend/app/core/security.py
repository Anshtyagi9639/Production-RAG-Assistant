import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

_JWT_ALGORITHM = "HS256"
_UPLOAD_AUDIENCE = "document-upload"
_password_hasher = PasswordHasher()

# Verifying against this when the email is unknown keeps login timing the same for
# existing and non-existing accounts, so response time doesn't reveal which emails exist.
_DUMMY_HASH = _password_hasher.hash("timing-equalizer")


class InvalidTokenError(Exception):
    """The access token is missing claims, malformed, expired or wrongly signed."""


class ExpiredTokenError(InvalidTokenError):
    """A well-formed token whose lifetime has passed."""


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


@dataclass(frozen=True)
class UploadTicket:
    """What the server decided when it handed out a direct upload URL, signed so the client
    can't change it: who uploads, into which workspace, under which key, name and size."""

    user_id: uuid.UUID
    workspace_id: uuid.UUID
    storage_key: str
    filename: str
    size_bytes: int


def create_upload_token(ticket: UploadTicket, lifetime_seconds: int, settings: Settings) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(ticket.user_id),
        # The audience keeps upload tickets and access tokens from standing in for each other.
        "aud": _UPLOAD_AUDIENCE,
        "ws": str(ticket.workspace_id),
        "key": ticket.storage_key,
        "name": ticket.filename,
        "size": ticket.size_bytes,
        "iat": now,
        # A little longer than the upload URL, so a file that just made it can still be recorded.
        "exp": now + timedelta(seconds=lifetime_seconds + 300),
    }
    return jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), _JWT_ALGORITHM)


def decode_upload_token(token: str, settings: Settings) -> UploadTicket:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[_JWT_ALGORITHM],
            audience=_UPLOAD_AUDIENCE,
            options={"require": ["sub", "aud", "exp", "iat", "ws", "key", "name", "size"]},
        )
        return UploadTicket(
            user_id=uuid.UUID(claims["sub"]),
            workspace_id=uuid.UUID(claims["ws"]),
            storage_key=str(claims["key"]),
            filename=str(claims["name"]),
            size_bytes=int(claims["size"]),
        )
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError from exc
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise InvalidTokenError from exc


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
