"""FastAPI dependencies shared across all route modules."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError

from app.auth import decode_token
from app.config import Settings, get_settings
from app.dag_engine import dag_engine
from app.enums import AdminRole
from app.events import event_hub


# ── Existing infrastructure dependencies ──────────────────────────────────────

def get_app_settings() -> Settings:
    return get_settings()


def get_dag_engine():
    return dag_engine


def get_event_hub():
    return event_hub


# ── Auth dependencies ──────────────────────────────────────────────────────────

async def get_current_admin(request: Request):
    """
    Reads Bearer token from Authorization header, verifies it, and returns
    an AdminContext namedtuple with (admin_id, org_id, role).

    Raises 401 if missing/invalid, 403 if account is suspended.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "not_authenticated", "message": "Authorization header required."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "token_invalid", "message": "Access token is invalid or has expired."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    from app.auth import _AdminContext  # avoid circular import
    return _AdminContext(
        admin_id=payload["sub"],
        org_id=payload.get("org_id"),
        role=payload.get("role", "analyst"),
    )


def require_role(*allowed_roles: AdminRole):
    """Dependency factory — raises 403 if current admin's role is not in allowed_roles."""
    def _check(admin=Depends(get_current_admin)):
        if admin.role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "insufficient_permissions", "message": f"Requires one of: {[r.value for r in allowed_roles]}"},
            )
        return admin
    return _check
