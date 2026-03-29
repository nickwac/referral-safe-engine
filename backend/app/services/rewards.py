from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import RewardType, UserStatus
from app.models import Referral, RewardConfig, RewardTransaction, User
from app.schemas import RewardSummary


async def get_active_reward_config(session: AsyncSession, org_id: str | None = None) -> RewardConfig:
    stmt: Select[tuple[RewardConfig]] = select(RewardConfig).where(RewardConfig.is_active.is_(True))
    if org_id:
        stmt = stmt.where(RewardConfig.org_id == org_id)
    stmt = stmt.order_by(RewardConfig.version.desc()).limit(1)
    config = await session.scalar(stmt)
    if config is None:
        raise ValueError("No active reward configuration found")
    return config


def _calculate_reward_amount(config: RewardConfig, level: int, base_amount: float | None) -> float:
    if level - 1 >= len(config.reward_values):
        return 0.0
    value = float(config.reward_values[level - 1])
    if config.reward_type == RewardType.FIXED:
        return value
    if base_amount is None:
        return 0.0
    return round((base_amount * value) / 100.0, 2)


async def create_reward_entries(session: AsyncSession, referral: Referral, ancestors: list[str], config: RewardConfig, base_amount: float | None) -> list[RewardSummary]:
    rewards: list[RewardSummary] = []
    beneficiary_ids = ancestors[: config.max_depth]
    if not beneficiary_ids:
        return rewards

    users = {user.id: user for user in (await session.scalars(select(User).where(User.id.in_(beneficiary_ids), User.org_id == referral.org_id))).all()}
    for level, beneficiary_id in enumerate(beneficiary_ids, start=1):
        user = users.get(beneficiary_id)
        if user is None:
            continue
        if user.status == UserStatus.FLAGGED:
            break

        amount = _calculate_reward_amount(config, level, base_amount)
        if amount <= 0:
            continue

        transaction = RewardTransaction(org_id=referral.org_id, from_referral_id=referral.id, beneficiary_id=beneficiary_id, amount=amount, level=level, config_version=config.version)
        session.add(transaction)
        user.reward_balance += amount
        rewards.append(RewardSummary(beneficiary_id=beneficiary_id, amount=amount, level=level, config_version=config.version))
    return rewards


def simulate_payout(reward_type: RewardType, reward_values: list[float], max_depth: int, projected_referrals: int, base_amount: float) -> float:
    per_referral = 0.0
    for level in range(1, max_depth + 1):
        if level - 1 >= len(reward_values):
            break
        if reward_type == RewardType.FIXED:
            per_referral += float(reward_values[level - 1])
        else:
            per_referral += round((base_amount * float(reward_values[level - 1])) / 100.0, 2)
    return round(per_referral * projected_referrals, 2)
