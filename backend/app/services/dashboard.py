"""Metrics calculation service — org-scoped."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ClaimRequestStatus, ReferralStatus
from app.models import ClaimRequest, FraudFlag, Referral, RewardTransaction, User
from app.schemas import MetricsResponse


async def get_metrics(session: AsyncSession, org_id: str | None = None) -> MetricsResponse:
    def _where(stmt, model):
        if org_id:
            return stmt.where(model.org_id == org_id)
        return stmt

    total_users = int(await session.scalar(_where(select(func.count(User.id)), User)) or 0)
    total_referrals = int(await session.scalar(
        _where(select(func.count(Referral.id)), Referral)
        .where(Referral.status == ReferralStatus.VALID)
    ) or 0)
    total_rewards = float(await session.scalar(
        _where(select(func.coalesce(func.sum(RewardTransaction.amount), 0.0)), RewardTransaction)
    ) or 0.0)
    total_fraud = int(await session.scalar(_where(select(func.count(FraudFlag.id)), FraudFlag)) or 0)
    accepted = int(await session.scalar(
        _where(select(func.count(ClaimRequest.id)), ClaimRequest)
        .where(ClaimRequest.status == ClaimRequestStatus.COMPLETED)
    ) or 0)
    rejected = total_fraud  # One flag per rejection

    return MetricsResponse(
        total_users=total_users,
        total_referrals=total_referrals,
        total_rewards_distributed=round(total_rewards, 2),
        total_fraud_flags=total_fraud,
        accepted_claims=accepted,
        rejected_claims=rejected,
    )
