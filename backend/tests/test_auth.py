from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
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


def test_jwks_verification_accepts_es256_signing_key(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = jwt.PyJWK.from_dict(
        json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key())),
        algorithm="ES256",
    )
    now = datetime.now(timezone.utc)
    user_id = uuid4()
    signed = jwt.encode(
        {
            "sub": str(user_id),
            "email": "user@example.com",
            "iss": "https://example.supabase.co/auth/v1",
            "aud": "authenticated",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "ec-signing-key"},
    )

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, value):
            assert value == signed
            return public_jwk

    monkeypatch.setattr("app.auth._jwks_client", lambda url: FakeJwksClient())
    jwks_settings = Settings(
        supabase_jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
        supabase_jwt_audience="authenticated",
    )

    assert decode_user(signed, jwks_settings).id == user_id


def test_jwks_verification_rejects_unsupported_key_algorithm(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = jwt.PyJWK.from_dict(
        json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key())),
        algorithm="ES256",
    )
    now = datetime.now(timezone.utc)
    signed = jwt.encode(
        {
            "sub": str(uuid4()),
            "iss": "https://example.supabase.co/auth/v1",
            "aud": "authenticated",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "ec-signing-key"},
    )

    class UnsupportedKey:
        algorithm_name = "HS256"
        key = public_jwk.key

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, value):
            return UnsupportedKey()

    monkeypatch.setattr("app.auth._jwks_client", lambda url: FakeJwksClient())
    jwks_settings = Settings(
        supabase_jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
        supabase_jwt_audience="authenticated",
    )

    with pytest.raises(HTTPException) as error:
        decode_user(signed, jwks_settings)
    assert error.value.status_code == 401
