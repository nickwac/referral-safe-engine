"""Fraud routes — flag listing, manual flag/unflag with audit log."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import get_current_admin, require_role
from app.enums import AdminRole, FraudReason, UserStatus
from app.models import AuditLog, FraudFlag, User
from app.schemas import (
    FlagUserRequest,
    FraudFlagListResponse,
    FraudFlagRead,
    UnflagUserRequest,
    UserRead,
)

router = APIRouter(prefix="/fraud", tags=["fraud"])


@router.get("/flags", response_model=FraudFlagListResponse)
async def list_fraud_flags(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    reason: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> FraudFlagListResponse:
    """Paginated fraud flags for this organisation, newest first."""
    stmt = (
        select(FraudFlag)
        .where(FraudFlag.org_id == admin.org_id)
        .order_by(FraudFlag.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    count_stmt = select(func.count(FraudFlag.id)).where(FraudFlag.org_id == admin.org_id)

    if reason:
        stmt = stmt.where(FraudFlag.reason == reason)
        count_stmt = count_stmt.where(FraudFlag.reason == reason)

    flags = (await session.scalars(stmt)).all()
    total = int(await session.scalar(count_stmt) or 0)
    return FraudFlagListResponse(total=total, items=[FraudFlagRead.model_validate(f) for f in flags])


@router.post("/{user_id}/flag", response_model=UserRead)
async def flag_user(
    user_id: str,
    payload: FlagUserRequest,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN, AdminRole.ORG_ADMIN, AdminRole.MANAGER)),
) -> UserRead:
    """Manually flag a user. Requires a reason (min 10 chars). Writes to audit log."""
    user = await session.scalar(select(User).where(User.id == user_id, User.org_id == admin.org_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.status == UserStatus.FLAGGED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already flagged")

    before_status = user.status.value
    async with session.begin_nested():
        user.status = UserStatus.FLAGGED
        session.add(FraudFlag(
            org_id=admin.org_id,
            user_id=user_id,
            reason=FraudReason.USER_BLOCKED,
            detail=f"[MANUAL FLAG] {payload.reason}",
        ))
        session.add(AuditLog(
            org_id=admin.org_id,
            actor_id=admin.admin_id,
            action="user.flagged",
            resource_type="user",
            resource_id=user_id,
            before_state={"status": before_status},
            after_state={"status": "flagged", "reason": payload.reason},
        ))
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.post("/{user_id}/unflag", response_model=UserRead)
async def unflag_user(
    user_id: str,
    payload: UnflagUserRequest,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN, AdminRole.ORG_ADMIN, AdminRole.MANAGER)),
) -> UserRead:
    """Clear a manual flag from a user. Requires justification. Writes to audit log."""
    user = await session.scalar(select(User).where(User.id == user_id, User.org_id == admin.org_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    before_status = user.status.value
    async with session.begin_nested():
        user.status = UserStatus.ACTIVE
        session.add(AuditLog(
            org_id=admin.org_id,
            actor_id=admin.admin_id,
            action="user.unflagged",
            resource_type="user",
            resource_id=user_id,
            before_state={"status": before_status},
            after_state={"status": "active", "justification": payload.justification},
        ))
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)
