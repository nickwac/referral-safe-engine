"""Admin routes - org management, reward seed-config, audit log viewer, and team management."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password
from app.config import get_settings
from app.database import get_db_session
from app.dependencies import get_current_admin, require_role
from app.enums import AdminRole, AdminUserStatus, OrgStatus, RewardType
from app.models import AdminUser, AuditLog, Organisation, RewardConfig
from app.schemas import (
    AdminUserRead,
    AuditLogListResponse,
    AuditLogRead,
    OrganisationCreateRequest,
    OrganisationListResponse,
    OrganisationRead,
    RewardConfigRead,
    TeamInviteRequest,
    TeamListResponse,
)
from seed import ensure_reward_backfill

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


@router.get("/orgs", response_model=OrganisationListResponse)
async def list_organisations(
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN)),
) -> OrganisationListResponse:
    orgs = (await session.scalars(select(Organisation).order_by(Organisation.created_at.asc()))).all()
    return OrganisationListResponse(total=len(orgs), items=[OrganisationRead.model_validate(org) for org in orgs])


@router.post("/orgs", response_model=OrganisationRead, status_code=status.HTTP_201_CREATED)
async def create_organisation(
    payload: OrganisationCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN)),
) -> OrganisationRead:
    existing = None
    if payload.domain:
        existing = await session.scalar(select(Organisation).where(Organisation.domain == payload.domain.lower()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organisation domain already exists")

    now = datetime.now(timezone.utc)
    org = Organisation(
        name=payload.name,
        domain=payload.domain.lower() if payload.domain else None,
        plan=payload.plan,
        status=OrgStatus.ACTIVE,
        max_users=payload.max_users,
        max_depth=payload.max_depth,
        api_rate_limit=payload.api_rate_limit,
        created_at=now,
        updated_at=now,
    )
    async with session.begin_nested():
        session.add(org)
        await session.flush()
        session.add(RewardConfig(
            org_id=org.id,
            version=1,
            max_depth=payload.max_depth or settings.reward_max_depth,
            reward_type=RewardType.FIXED,
            reward_values=settings.reward_amount_list,
            is_active=True,
        ))
        session.add(AuditLog(
            org_id=org.id,
            actor_id=admin.admin_id,
            action="org.created",
            resource_type="organisation",
            resource_id=org.id,
            after_state={"name": org.name, "domain": org.domain, "plan": org.plan.value},
        ))
    await session.commit()
    await session.refresh(org)
    return OrganisationRead.model_validate(org)


@router.put("/orgs/{org_id}/suspend", response_model=OrganisationRead)
async def suspend_organisation(
    org_id: str,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN)),
) -> OrganisationRead:
    org = await session.scalar(select(Organisation).where(Organisation.id == org_id))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")

    async with session.begin_nested():
        before = org.status.value
        org.status = OrgStatus.SUSPENDED
        session.add(AuditLog(
            org_id=org.id,
            actor_id=admin.admin_id,
            action="org.suspended",
            resource_type="organisation",
            resource_id=org.id,
            before_state={"status": before},
            after_state={"status": org.status.value},
        ))
    await session.commit()
    await session.refresh(org)
    return OrganisationRead.model_validate(org)


@router.post("/seed-config", response_model=RewardConfigRead, summary="Ensure active reward config exists")
async def seed_reward_config(
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> RewardConfigRead:
    async with session.begin():
        config = await session.scalar(
            select(RewardConfig)
            .where(RewardConfig.org_id == admin.org_id, RewardConfig.is_active.is_(True))
            .order_by(RewardConfig.version.desc())
        )
        if config is None:
            config = RewardConfig(
                org_id=admin.org_id,
                version=1,
                max_depth=3,
                reward_type=RewardType.FIXED,
                reward_values=[10.0, 5.0, 2.0],
                is_active=True,
            )
            session.add(config)
            await session.flush()
        await ensure_reward_backfill(session, admin.org_id)
    await session.refresh(config)
    return RewardConfigRead.model_validate(config)


@router.get("/audit-log", response_model=AuditLogListResponse)
async def get_audit_log(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> AuditLogListResponse:
    org_filter = AuditLog.org_id == admin.org_id if not admin.is_super_admin else True
    stmt = select(AuditLog).where(org_filter).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count(AuditLog.id)).where(org_filter)

    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)

    logs = (await session.scalars(stmt)).all()
    total = int(await session.scalar(count_stmt) or 0)
    return AuditLogListResponse(total=total, items=[AuditLogRead.model_validate(l) for l in logs])


@router.get("/team", response_model=TeamListResponse)
async def list_team(
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN, AdminRole.ORG_ADMIN)),
) -> TeamListResponse:
    query = select(AdminUser)
    if admin.is_super_admin:
        query = query.order_by(AdminUser.created_at.asc())
    else:
        query = query.where(AdminUser.org_id == admin.org_id).order_by(AdminUser.created_at.asc())
    members = (await session.scalars(query)).all()
    return TeamListResponse(total=len(members), items=[AdminUserRead.model_validate(m) for m in members])


@router.post("/team/invite", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
async def invite_team_member(
    payload: TeamInviteRequest,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN, AdminRole.ORG_ADMIN)),
) -> AdminUserRead:
    existing = await session.scalar(select(AdminUser).where(AdminUser.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    now = datetime.now(timezone.utc)
    new_member = AdminUser(
        org_id=admin.org_id,
        email=payload.email.lower(),
        password_hash=hash_password("TempPass123!"),
        role=payload.role,
        status=AdminUserStatus.INVITED,
        created_at=now,
        updated_at=now,
    )
    async with session.begin_nested():
        session.add(new_member)
        session.add(AuditLog(
            org_id=admin.org_id,
            actor_id=admin.admin_id,
            action="team.member_invited",
            resource_type="admin_user",
            after_state={"email": payload.email, "role": payload.role.value},
        ))
    await session.commit()
    await session.refresh(new_member)
    print(f"[DEV] Invite link for {payload.email}: http://localhost:5173/accept-invite?id={new_member.id}")
    return AdminUserRead.model_validate(new_member)


@router.delete("/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN, AdminRole.ORG_ADMIN)),
) -> Response:
    if member_id == admin.admin_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")

    member = await session.scalar(select(AdminUser).where(AdminUser.id == member_id, AdminUser.org_id == admin.org_id))
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    async with session.begin_nested():
        member.status = AdminUserStatus.SUSPENDED
        session.add(AuditLog(
            org_id=admin.org_id,
            actor_id=admin.admin_id,
            action="team.member_removed",
            resource_type="admin_user",
            resource_id=member_id,
            before_state={"email": member.email, "role": member.role.value},
        ))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/team/{member_id}/role", response_model=AdminUserRead)
async def update_member_role(
    member_id: str,
    role: AdminRole = Query(...),
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN, AdminRole.ORG_ADMIN)),
) -> AdminUserRead:
    if member_id == admin.admin_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    member = await session.scalar(select(AdminUser).where(AdminUser.id == member_id, AdminUser.org_id == admin.org_id))
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    old_role = member.role.value
    async with session.begin_nested():
        member.role = role
        session.add(AuditLog(
            org_id=admin.org_id,
            actor_id=admin.admin_id,
            action="team.role_changed",
            resource_type="admin_user",
            resource_id=member_id,
            before_state={"role": old_role},
            after_state={"role": role.value},
        ))
    await session.commit()
    await session.refresh(member)
    return AdminUserRead.model_validate(member)
