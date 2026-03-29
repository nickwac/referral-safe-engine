"""User routes - search, list, graph, rewards, profile, and status management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import get_current_admin, require_role
from app.enums import AdminRole, ReferralStatus
from app.models import AuditLog, FraudFlag, Referral, RewardTransaction, User
from app.schemas import (
    AuditLogRead,
    FraudFlagRead,
    GraphResponse,
    GraphTreeNode,
    ReferralRead,
    RewardHistoryResponse,
    RewardTransactionRead,
    UserListResponse,
    UserProfileResponse,
    UserRead,
    UserSearchResult,
    UserStatusUpdateRequest,
)

router = APIRouter(prefix="/user", tags=["users"])


@router.get("/search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> list[UserSearchResult]:
    pattern = f"%{q}%"
    stmt = (
        select(User)
        .where(
            User.org_id == admin.org_id,
            or_(
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.id.ilike(f"{q}%"),
            ),
        )
        .order_by(User.username.asc())
        .limit(limit)
    )
    users = (await session.scalars(stmt)).all()
    return [UserSearchResult.model_validate(u) for u in users]


@router.get("", response_model=UserListResponse)
async def list_users(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> UserListResponse:
    stmt = select(User).where(User.org_id == admin.org_id).order_by(User.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count(User.id)).where(User.org_id == admin.org_id)
    if status_filter:
        stmt = stmt.where(User.status == status_filter)
        count_stmt = count_stmt.where(User.status == status_filter)
    users = (await session.scalars(stmt)).all()
    total = int(await session.scalar(count_stmt) or 0)
    return UserListResponse(total=total, items=[UserRead.model_validate(u) for u in users])


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> UserProfileResponse:
    user = await session.scalar(select(User).where(User.id == user_id, User.org_id == admin.org_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    referral_count = int(
        await session.scalar(
            select(func.count(Referral.id)).where(
                Referral.org_id == admin.org_id,
                Referral.child_id == user_id,
                Referral.status == ReferralStatus.VALID,
            )
        ) or 0
    )
    fraud_flags = (
        await session.scalars(
            select(FraudFlag)
            .where(FraudFlag.org_id == admin.org_id, FraudFlag.user_id == user_id)
            .order_by(FraudFlag.timestamp.desc())
            .limit(20)
        )
    ).all()
    recent_txns = (
        await session.scalars(
            select(RewardTransaction)
            .where(RewardTransaction.org_id == admin.org_id, RewardTransaction.beneficiary_id == user_id)
            .order_by(RewardTransaction.created_at.desc())
            .limit(10)
        )
    ).all()
    recent_claims = (
        await session.scalars(
            select(Referral)
            .where(
                Referral.org_id == admin.org_id,
                or_(Referral.child_id == user_id, Referral.parent_id == user_id),
            )
            .order_by(Referral.created_at.desc())
            .limit(12)
        )
    ).all()
    audit_entries = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.org_id == admin.org_id, AuditLog.resource_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(12)
        )
    ).all()

    return UserProfileResponse(
        user=UserRead.model_validate(user),
        referral_count=referral_count,
        fraud_flags=[FraudFlagRead.model_validate(f) for f in fraud_flags],
        recent_transactions=[RewardTransactionRead.model_validate(t) for t in recent_txns],
        recent_claims=[ReferralRead.model_validate(r) for r in recent_claims],
        audit_entries=[AuditLogRead.model_validate(a) for a in audit_entries],
    )


@router.put("/{user_id}/status", response_model=UserRead)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(require_role(AdminRole.SUPER_ADMIN, AdminRole.ORG_ADMIN, AdminRole.MANAGER)),
) -> UserRead:
    user = await session.scalar(select(User).where(User.id == user_id, User.org_id == admin.org_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    before_status = user.status.value
    async with session.begin_nested():
        user.status = payload.status
        session.add(AuditLog(
            org_id=admin.org_id,
            actor_id=admin.admin_id,
            action="user.status_changed",
            resource_type="user",
            resource_id=user_id,
            before_state={"status": before_status},
            after_state={"status": payload.status.value, "reason": payload.reason},
        ))
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


def build_tree(root_id: str, user_map: dict[str, User], children_map: dict[str, list[Referral]], remaining_depth: int) -> GraphTreeNode:
    user = user_map[root_id]
    node = GraphTreeNode(user_id=root_id, username=user.username, status=user.status)
    if remaining_depth > 0:
        for child_ref in children_map.get(root_id, []):
            if child_ref.child_id in user_map:
                child_node = build_tree(child_ref.child_id, user_map, children_map, remaining_depth - 1)
                child_node.referral_id = child_ref.id
                child_node.referral_created_at = child_ref.created_at
                node.children.append(child_node)
    return node


@router.get("/{user_id}/graph", response_model=GraphResponse)
async def get_user_graph(
    user_id: str,
    depth: int = Query(default=3, ge=1, le=5),
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> GraphResponse:
    root_user = await session.scalar(select(User).where(User.id == user_id, User.org_id == admin.org_id))
    if root_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    referrals = (
        await session.scalars(
            select(Referral).where(Referral.org_id == admin.org_id, Referral.status == ReferralStatus.VALID)
        )
    ).all()
    children_map: dict[str, list[Referral]] = {}
    user_ids: set[str] = {user_id}
    for ref in referrals:
        children_map.setdefault(ref.parent_id, []).append(ref)
        user_ids.add(ref.child_id)
        user_ids.add(ref.parent_id)

    users = (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()
    user_map = {u.id: u for u in users}

    tree = build_tree(user_id, user_map, children_map, depth)
    return GraphResponse(root_user_id=user_id, depth=depth, tree=tree)


@router.get("/{user_id}/rewards", response_model=RewardHistoryResponse)
async def get_user_rewards(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> RewardHistoryResponse:
    user = await session.scalar(select(User).where(User.id == user_id, User.org_id == admin.org_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    txns = (
        await session.scalars(
            select(RewardTransaction)
            .where(RewardTransaction.org_id == admin.org_id, RewardTransaction.beneficiary_id == user_id)
            .order_by(RewardTransaction.created_at.desc())
        )
    ).all()
    return RewardHistoryResponse(
        user_id=user_id,
        total_rewards=user.reward_balance,
        transactions=[RewardTransactionRead.model_validate(t) for t in txns],
    )
