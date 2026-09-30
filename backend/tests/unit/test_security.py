import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_argon2_and_verifies() -> None:
    hashed = hash_password("correct horse battery")

    assert hashed.startswith("$argon2")
    assert "correct horse battery" not in hashed
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong password", hashed)


def test_unknown_user_never_verifies() -> None:
    # Login verifies against a dummy hash when the email doesn't exist (constant timing).
    assert not verify_password("timing-equalizer", None)
    assert not verify_password("anything", None)


def test_token_round_trip_and_lifetime(settings: Settings) -> None:
    user_id = uuid.uuid4()

    token, expires_in = create_access_token(user_id, settings)

    assert decode_access_token(token, settings) == user_id
    assert expires_in == settings.jwt_expire_minutes * 60


def test_expired_token_is_rejected(settings: Settings) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        settings.jwt_secret_key.get_secret_value(),
        "HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_token_signed_with_another_secret_is_rejected(settings: Settings) -> None:
    other = settings.model_copy(update={"jwt_secret_key": SecretStr("x" * 40)})
    token, _ = create_access_token(uuid.uuid4(), other)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
def test_malformed_token_is_rejected(settings: Settings, token: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_token_without_expiry_is_rejected(settings: Settings) -> None:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "iat": datetime.now(UTC)},
        settings.jwt_secret_key.get_secret_value(),
        "HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_unsigned_token_is_rejected(settings: Settings) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "iat": now, "exp": now + timedelta(hours=1)}, None, "none"
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)
