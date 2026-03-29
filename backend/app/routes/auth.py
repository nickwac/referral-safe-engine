"""Auth routes: login, token refresh, logout, current-user lookup, and session management."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, decode_token, generate_raw_refresh_token, hash_refresh_token, verify_password
from app.config import get_settings
from app.database import get_db_session
from app.dependencies import get_current_admin
from app.enums import AdminUserStatus
from app.models import AdminSession, AdminUser, Organisation
from app.schemas import AdminSessionListResponse, AdminSessionRead

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_OPTS: dict = {
    "httponly": True,
    "samesite": "lax",
    "secure": False,
    "path": "/",
}


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin_id: str
    email: str
    role: str
    org_id: str | None
    org_name: str | None


async def _create_session(session: AsyncSession, admin: AdminUser, request: Request) -> str:
    raw = generate_raw_refresh_token()
    token_hash = hash_refresh_token(raw)
    db_session = AdminSession(
        admin_user_id=admin.id,
        refresh_token_hash=token_hash,
        device_hint=request.headers.get("user-agent", "")[:255],
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(db_session)
    return raw


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=raw_token,
        max_age=settings.refresh_token_expire_days * 86400,
        **_COOKIE_OPTS,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="refresh_token", path="/")


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    admin = await session.scalar(select(AdminUser).where(AdminUser.email == payload.email.lower().strip()))
    if admin is None or not admin.password_hash or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "message": "Incorrect email or password."},
        )
    if admin.status == AdminUserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "account_suspended", "message": "This account has been suspended."},
        )

    org_name: str | None = None
    if admin.org_id:
        org = await session.scalar(select(Organisation).where(Organisation.id == admin.org_id))
        org_name = org.name if org else None

    async with session.begin_nested():
        raw_refresh = await _create_session(session, admin, request)
        admin.last_login_at = datetime.now(timezone.utc)

    access_token = create_access_token(admin.id, admin.org_id, admin.role.value)
    _set_refresh_cookie(response, raw_refresh)

    return AuthResponse(
        access_token=access_token,
        admin_id=admin.id,
        email=admin.email,
        role=admin.role.value,
        org_id=admin.org_id,
        org_name=org_name,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = hash_refresh_token(raw_token)
    db_session = await session.scalar(
        select(AdminSession).where(
            AdminSession.refresh_token_hash == token_hash,
            AdminSession.revoked.is_(False),
            AdminSession.expires_at > datetime.now(timezone.utc),
        )
    )
    if db_session is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    admin = await session.scalar(select(AdminUser).where(AdminUser.id == db_session.admin_user_id))
    if admin is None or admin.status == AdminUserStatus.SUSPENDED:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")

    async with session.begin_nested():
        db_session.revoked = True
        raw_new = await _create_session(session, admin, request)

    org_name: str | None = None
    if admin.org_id:
        org = await session.scalar(select(Organisation).where(Organisation.id == admin.org_id))
        org_name = org.name if org else None

    access_token = create_access_token(admin.id, admin.org_id, admin.role.value)
    _set_refresh_cookie(response, raw_new)

    return AuthResponse(
        access_token=access_token,
        admin_id=admin.id,
        email=admin.email,
        role=admin.role.value,
        org_id=admin.org_id,
        org_name=org_name,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        token_hash = hash_refresh_token(raw_token)
        db_session = await session.scalar(select(AdminSession).where(AdminSession.refresh_token_hash == token_hash))
        if db_session:
            async with session.begin_nested():
                db_session.revoked = True
    _clear_auth_cookies(response)
    return {"status": "logged_out"}


@router.get("/me", response_model=AuthResponse)
async def get_me(request: Request, session: AsyncSession = Depends(get_db_session)) -> AuthResponse:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid or expired") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    admin = await session.scalar(select(AdminUser).where(AdminUser.id == payload["sub"]))
    if admin is None or admin.status == AdminUserStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")

    org_name: str | None = None
    if admin.org_id:
        org = await session.scalar(select(Organisation).where(Organisation.id == admin.org_id))
        org_name = org.name if org else None

    return AuthResponse(
        access_token="",
        admin_id=admin.id,
        email=admin.email,
        role=admin.role.value,
        org_id=admin.org_id,
        org_name=org_name,
    )


@router.get("/sessions", response_model=AdminSessionListResponse)
async def list_sessions(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> AdminSessionListResponse:
    raw_token = request.cookies.get("refresh_token")
    current_hash = hash_refresh_token(raw_token) if raw_token else None
    sessions = (
        await session.scalars(
            select(AdminSession)
            .where(AdminSession.admin_user_id == admin.admin_id)
            .order_by(AdminSession.last_active_at.desc())
        )
    ).all()

    items: list[AdminSessionRead] = []
    for item in sessions:
        session_read = AdminSessionRead.model_validate(item)
        session_read.is_current = bool(current_hash and item.refresh_token_hash == current_hash)
        items.append(session_read)
    return AdminSessionListResponse(total=len(items), items=items)


@router.post("/sessions/revoke-others")
async def revoke_other_sessions(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> dict[str, int]:
    raw_token = request.cookies.get("refresh_token")
    current_hash = hash_refresh_token(raw_token) if raw_token else None
    sessions = (
        await session.scalars(
            select(AdminSession).where(AdminSession.admin_user_id == admin.admin_id, AdminSession.revoked.is_(False))
        )
    ).all()
    revoked = 0
    async with session.begin_nested():
        for item in sessions:
            if current_hash and item.refresh_token_hash == current_hash:
                continue
            item.revoked = True
            revoked += 1
    await session.commit()
    return {"revoked": revoked}


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> dict[str, str]:
    target = await session.scalar(select(AdminSession).where(AdminSession.id == session_id, AdminSession.admin_user_id == admin.admin_id))
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    raw_token = request.cookies.get("refresh_token")
    current_hash = hash_refresh_token(raw_token) if raw_token else None
    async with session.begin_nested():
        target.revoked = True
    await session.commit()

    if current_hash and target.refresh_token_hash == current_hash:
        _clear_auth_cookies(response)
    return {"status": "revoked"}
