"""JWT creation/verification and bcrypt password utilities."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.config import get_settings

settings = get_settings()


@dataclass
class _AdminContext:
    admin_id: str
    org_id: str | None
    role: str

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"


def _normalize_password_bytes(plain: str) -> bytes:
    raw = plain.encode("utf-8")
    if len(raw) <= 72:
        return raw
    return hashlib.sha256(raw).hexdigest().encode("utf-8")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_normalize_password_bytes(plain), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_normalize_password_bytes(plain), hashed.encode("utf-8"))


def _make_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(admin_id: str, org_id: str | None, role: str) -> str:
    return _make_token(
        {"sub": admin_id, "org_id": org_id, "role": role, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(admin_id: str) -> str:
    return _make_token(
        {"sub": admin_id, "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_raw_refresh_token() -> str:
    return secrets.token_urlsafe(48)
