"""Seed script - creates demo orgs, admin users, referrals, fraud flags, and reward backfill."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password
from app.config import get_settings
from app.database import SessionLocal
from app.enums import AdminRole, AdminUserStatus, FraudReason, OrgPlan, OrgStatus, ReferralStatus, RewardType, UserStatus
from app.models import (
    ActivityEvent, AdminUser, FraudFlag, Organisation, Referral,
    RewardConfig, RewardTransaction, User,
)

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_SUPER_ADMIN_EMAIL = "owner@example.com"
DEFAULT_SUPER_ADMIN_PASSWORD = "Owner123!"
settings = get_settings()


def ancestor_chain(parent_by_child: dict[str, str], start_user_id: str, max_depth: int) -> list[str]:
    ancestors: list[str] = []
    current = start_user_id
    while len(ancestors) < max_depth:
        parent = parent_by_child.get(current)
        if parent is None:
            break
        ancestors.append(parent)
        current = parent
    return ancestors


async def _ensure_default_org(session: AsyncSession) -> Organisation:
    existing = await session.scalar(select(Organisation).where(Organisation.id == DEFAULT_ORG_ID))
    if existing is not None:
        return existing

    now = datetime.now(timezone.utc)
    org = Organisation(
        id=DEFAULT_ORG_ID,
        name="System",
        domain="example.com",
        plan=OrgPlan.ENTERPRISE,
        status=OrgStatus.ACTIVE,
        max_users=None,
        max_depth=5,
        api_rate_limit=100,
        created_at=now,
        updated_at=now,
    )
    session.add(org)
    await session.flush()
    return org


async def _ensure_admin_users(session: AsyncSession, org: Organisation) -> None:
    demo_admin = await session.scalar(select(AdminUser).where(AdminUser.email == settings.admin_bootstrap_email.lower()))
    if demo_admin is None:
        session.add(AdminUser(
            org_id=org.id,
            email=settings.admin_bootstrap_email.lower(),
            password_hash=hash_password(settings.admin_bootstrap_password),
            role=AdminRole.ORG_ADMIN,
            status=AdminUserStatus.ACTIVE,
        ))

    super_admin = await session.scalar(select(AdminUser).where(AdminUser.email == DEFAULT_SUPER_ADMIN_EMAIL))
    if super_admin is None:
        session.add(AdminUser(
            org_id=None,
            email=DEFAULT_SUPER_ADMIN_EMAIL,
            password_hash=hash_password(DEFAULT_SUPER_ADMIN_PASSWORD),
            role=AdminRole.SUPER_ADMIN,
            status=AdminUserStatus.ACTIVE,
        ))


async def ensure_reward_backfill(session: AsyncSession, org_id: str | None = None) -> None:
    reward_count_stmt = select(func.count(RewardTransaction.id))
    if org_id:
        reward_count_stmt = reward_count_stmt.where(RewardTransaction.org_id == org_id)
    reward_count = int(await session.scalar(reward_count_stmt) or 0)
    if reward_count > 0:
        return

    config_stmt = select(RewardConfig).where(RewardConfig.is_active.is_(True))
    if org_id:
        config_stmt = config_stmt.where(RewardConfig.org_id == org_id)
    config = await session.scalar(config_stmt.order_by(RewardConfig.version.desc()))
    if config is None:
        config = RewardConfig(
            org_id=org_id or DEFAULT_ORG_ID,
            version=1,
            max_depth=3,
            reward_type=RewardType.FIXED,
            reward_values=[10.0, 5.0, 2.0],
            is_active=True,
        )
        session.add(config)
        await session.flush()

    user_stmt = select(User)
    referral_stmt = select(Referral).where(Referral.status == ReferralStatus.VALID).where((Referral.expires_at.is_(None)) | (Referral.expires_at > datetime.now(timezone.utc)))
    if org_id:
        user_stmt = user_stmt.where(User.org_id == org_id)
        referral_stmt = referral_stmt.where(Referral.org_id == org_id)
    users = (await session.scalars(user_stmt)).all()
    user_map = {user.id: user for user in users}
    valid_referrals = (await session.scalars(referral_stmt.order_by(Referral.created_at.asc()))).all()
    parent_by_child = {ref.child_id: ref.parent_id for ref in valid_referrals}

    for referral in valid_referrals:
        payout_chain = [referral.parent_id, *ancestor_chain(parent_by_child, referral.parent_id, config.max_depth - 1)]
        for level, beneficiary_id in enumerate(payout_chain[: config.max_depth], start=1):
            if level - 1 >= len(config.reward_values):
                continue
            user = user_map.get(beneficiary_id)
            if user is None or user.status == UserStatus.FLAGGED:
                break
            amount = float(config.reward_values[level - 1]) if config.reward_type == RewardType.FIXED else 0.0
            if amount <= 0:
                continue
            session.add(RewardTransaction(
                org_id=referral.org_id,
                from_referral_id=referral.id,
                beneficiary_id=beneficiary_id,
                amount=amount,
                level=level,
                config_version=config.version,
            ))
            user.reward_balance += amount
            session.add(ActivityEvent(
                org_id=referral.org_id,
                event_type="reward_paid",
                payload={"beneficiary_id": beneficiary_id, "amount": amount, "level": level, "referral_id": referral.id},
            ))


async def seed() -> None:
    async with SessionLocal() as session:
        org = await _ensure_default_org(session)
        await _ensure_admin_users(session, org)
        await session.flush()

        existing = await session.scalar(select(User.id).where(User.org_id == org.id).limit(1))
        if existing is None:
            users: list[User] = []
            for index in range(1, 51):
                status = UserStatus.ROOT if index == 1 else UserStatus.ACTIVE
                users.append(User(
                    id=str(uuid4()),
                    org_id=org.id,
                    username=f"user{index}",
                    email=f"user{index}@example.com",
                    status=status,
                ))
            session.add_all(users)
            await session.flush()

            valid_referrals: list[Referral] = []
            for index in range(1, 25):
                parent_index = max(0, (index // 2) - 1)
                valid_referrals.append(Referral(
                    org_id=org.id,
                    child_id=users[index].id,
                    parent_id=users[parent_index].id,
                    status=ReferralStatus.VALID,
                ))
            valid_referrals.append(Referral(
                org_id=org.id,
                child_id=users[25].id,
                parent_id=users[5].id,
                status=ReferralStatus.VALID,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            ))
            session.add_all(valid_referrals)
            await session.flush()

            config = await session.scalar(select(RewardConfig).where(RewardConfig.org_id == org.id, RewardConfig.is_active.is_(True)))
            if config is None:
                session.add(RewardConfig(
                    org_id=org.id,
                    version=1,
                    max_depth=3,
                    reward_type=RewardType.FIXED,
                    reward_values=[10.0, 5.0, 2.0],
                    is_active=True,
                ))

            frauds = [
                FraudFlag(org_id=org.id, user_id=users[26].id, reason=FraudReason.CYCLE, detail="blocked cycle attempt 1"),
                FraudFlag(org_id=org.id, user_id=users[27].id, reason=FraudReason.CYCLE, detail="blocked cycle attempt 2"),
                FraudFlag(org_id=org.id, user_id=users[28].id, reason=FraudReason.CYCLE, detail="blocked cycle attempt 3"),
                FraudFlag(org_id=org.id, user_id=users[29].id, reason=FraudReason.VELOCITY, detail="velocity violation 1"),
                FraudFlag(org_id=org.id, user_id=users[30].id, reason=FraudReason.VELOCITY, detail="velocity violation 2"),
            ]
            session.add_all(frauds)
            session.add_all([
                ActivityEvent(org_id=org.id, event_type="seed_completed", payload={"users": 50, "valid_referrals": len(valid_referrals)}),
                ActivityEvent(org_id=org.id, event_type="cycle_prevented", payload={"attempts": 3}),
                ActivityEvent(org_id=org.id, event_type="velocity_detected", payload={"attempts": 2}),
            ])

        await ensure_reward_backfill(session, org.id)
        await session.commit()
        print("\nSeed complete.")
        print(f"   Org Admin  -> email: {settings.admin_bootstrap_email}  |  password: {settings.admin_bootstrap_password}")
        print(f"   Super Admin -> email: {DEFAULT_SUPER_ADMIN_EMAIL}  |  password: {DEFAULT_SUPER_ADMIN_PASSWORD}")
        print("   Dashboard   -> http://localhost:5173\n")


if __name__ == "__main__":
    asyncio.run(seed())
