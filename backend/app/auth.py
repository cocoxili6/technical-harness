from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: Optional[str] = None


def _bearer(value: Optional[str]) -> str:
    if not value or not value.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    token = value[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return token


def verify_gateway_token(
    token: Optional[str] = Header(default=None, alias="x-harness-gateway-token"),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.harness_shared_token and token != settings.harness_shared_token:
        raise HTTPException(status_code=401, detail="unauthorized")


@lru_cache(maxsize=1)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url)


def decode_user(token: str, settings: Settings) -> CurrentUser:
    try:
        if settings.supabase_jwks_url:
            signing_key = _jwks_client(
                settings.supabase_jwks_url
            ).get_signing_key_from_jwt(token)
            algorithm = signing_key.algorithm_name
            if algorithm not in {"RS256", "ES256"}:
                raise ValueError("Unsupported Supabase signing algorithm")
            key = signing_key.key
            algorithms = [algorithm]
        else:
            secret = settings.supabase_jwt_secret.get_secret_value()
            if not secret:
                raise ValueError("JWT verifier is not configured")
            key = secret
            algorithms = ["HS256"]
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer or None,
        )
        user_id = UUID(str(claims["sub"]))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="unauthorized") from exc
    return CurrentUser(id=user_id, email=claims.get("email"))


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    return decode_user(_bearer(authorization), settings)
