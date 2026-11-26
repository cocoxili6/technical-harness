from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import HTTPException

from app.auth import decode_user, get_current_user
from app.config import Settings


def settings():
    return Settings(
        supabase_jwt_secret="test-secret-012345678901234567890",
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
        supabase_jwt_audience="authenticated",
    )


def token(user_id=None, **extra):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id or uuid4()),
        "email": "user@example.com",
        "iss": "https://example.supabase.co/auth/v1",
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        **extra,
    }
    return jwt.encode(claims, "test-secret-012345678901234567890", algorithm="HS256")


def test_valid_supabase_jwt_returns_user_identity():
    user_id = uuid4()
    user = decode_user(token(user_id), settings())
    assert user.id == user_id
    assert user.email == "user@example.com"


@pytest.mark.parametrize("claims", [{"aud": "wrong"}, {"iss": "wrong"}, {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)}])
def test_invalid_claims_are_rejected(claims):
    with pytest.raises(HTTPException) as error:
        decode_user(token(**claims), settings())
    assert error.value.status_code == 401


def test_missing_or_malformed_bearer_is_rejected():
    for value in (None, "Basic token", "Bearer "):
        with pytest.raises(HTTPException) as error:
            get_current_user(value, settings())
        assert error.value.status_code == 401
