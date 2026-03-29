from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dag_engine import DAGEngine
from app.enums import ClaimRequestStatus, FraudReason, ReferralStatus
from app.events import EventHub
from app.models import ActivityEvent, ClaimRequest, FraudFlag, Referral, User
from app.schemas import ReferralClaimRequest, ReferralClaimResponse
from app.services.fraud import validate_self_referral, validate_user_status, velocity_limiter
from app.services.rewards import create_reward_entries, get_active_reward_config

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"


def build_request_hash(payload: ReferralClaimRequest) -> str:
    raw = f"{payload.child_id}:{payload.parent_id}:{payload.base_amount}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _record_event(session: AsyncSession, hub: EventHub, org_id: str | None, event_type: str, payload: dict) -> None:
    session.add(ActivityEvent(org_id=org_id, event_type=event_type, payload=payload))
    await hub.publish({"org_id": org_id, "event_type": event_type, "payload": payload})


async def _record_fraud(session: AsyncSession, hub: EventHub, org_id: str, user_id: str | None, referral_id: str | None, reason: FraudReason, detail: str) -> None:
    session.add(FraudFlag(org_id=org_id, user_id=user_id, referral_id=referral_id, reason=reason, detail=detail))
    await _record_event(session, hub, org_id, "fraud_flag", {"user_id": user_id, "referral_id": referral_id, "reason": reason.value, "detail": detail})


async def _get_existing_claim(session: AsyncSession, payload: ReferralClaimRequest) -> ClaimRequest | None:
    stmt = select(ClaimRequest).where(ClaimRequest.idempotency_key == payload.idempotency_key)
    return await session.scalar(stmt)


def _response_to_dict(response: ReferralClaimResponse) -> dict:
    return json.loads(response.model_dump_json())


async def process_claim(session: AsyncSession, dag_engine: DAGEngine, hub: EventHub, settings: Settings, payload: ReferralClaimRequest) -> ReferralClaimResponse:
    request_hash = build_request_hash(payload)
    existing_claim = await _get_existing_claim(session, payload)
    if existing_claim is not None:
        if existing_claim.request_hash != request_hash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="idempotency key reused with different payload")
        if existing_claim.response_payload is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="claim is still processing")
        return ReferralClaimResponse.model_validate(existing_claim.response_payload)

    def rejection(reason: FraudReason) -> ReferralClaimResponse:
        return ReferralClaimResponse(status="rejected", reason=reason, rewards=[])

    users = {user.id: user for user in (await session.scalars(select(User).where(User.id.in_([payload.child_id, payload.parent_id])))).all()}
    child = users.get(payload.child_id)
    parent = users.get(payload.parent_id)
    org_id = child.org_id if child else parent.org_id if parent else DEFAULT_ORG_ID

    claim_request = ClaimRequest(org_id=org_id, idempotency_key=payload.idempotency_key, request_hash=request_hash, child_id=payload.child_id, parent_id=payload.parent_id, status=ClaimRequestStatus.PROCESSING)
    session.add(claim_request)
    await session.flush()

    reason = validate_self_referral(payload.child_id, payload.parent_id)
    if reason is not None:
        await _record_fraud(session, hub, org_id, payload.child_id, None, reason, "child and parent cannot be the same")
        response = rejection(reason)
        claim_request.status = ClaimRequestStatus.COMPLETED
        claim_request.response_payload = _response_to_dict(response)
        return response

    existing_pair = await session.scalar(select(Referral).where(Referral.org_id == org_id, Referral.child_id == payload.child_id, Referral.parent_id == payload.parent_id, Referral.status == ReferralStatus.VALID))
    if existing_pair is not None:
        reason = FraudReason.DUPLICATE
        await _record_fraud(session, hub, org_id, payload.child_id, existing_pair.id, reason, "duplicate child parent pair")
        response = rejection(reason)
        claim_request.status = ClaimRequestStatus.COMPLETED
        claim_request.response_payload = _response_to_dict(response)
        return response

    if child is None or parent is None:
        reason = FraudReason.USER_NOT_FOUND
        await _record_fraud(session, hub, org_id, payload.child_id, None, reason, "child or parent does not exist")
        response = rejection(reason)
        claim_request.status = ClaimRequestStatus.COMPLETED
        claim_request.response_payload = _response_to_dict(response)
        return response

    if child.org_id != parent.org_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cross-organisation referrals are not allowed")

    reason = validate_user_status(child.status, parent.status)
    if reason is not None:
        await _record_fraud(session, hub, org_id, payload.child_id, None, reason, "blocked user status")
        response = rejection(reason)
        claim_request.status = ClaimRequestStatus.COMPLETED
        claim_request.response_payload = _response_to_dict(response)
        return response

    existing_referral = await session.scalar(select(Referral).where(Referral.org_id == org_id, Referral.child_id == payload.child_id, Referral.status == ReferralStatus.VALID))
    if existing_referral is not None:
        reason = FraudReason.ALREADY_REFERRED
        await _record_fraud(session, hub, org_id, payload.child_id, existing_referral.id, reason, "child already has a parent")
        response = rejection(reason)
        claim_request.status = ClaimRequestStatus.COMPLETED
        claim_request.response_payload = _response_to_dict(response)
        return response

    if await velocity_limiter.is_limited(payload.parent_id, settings.max_claims_per_minute):
        reason = FraudReason.VELOCITY
        await _record_fraud(session, hub, org_id, payload.parent_id, None, reason, "velocity limit exceeded")
        response = rejection(reason)
        claim_request.status = ClaimRequestStatus.COMPLETED
        claim_request.response_payload = _response_to_dict(response)
        return response

    async with dag_engine.mutation_lock():
        if dag_engine.has_path_unlocked(payload.parent_id, payload.child_id):
            reason = FraudReason.CYCLE
            await _record_fraud(session, hub, org_id, payload.child_id, None, reason, "cycle detected")
            response = rejection(reason)
            claim_request.status = ClaimRequestStatus.COMPLETED
            claim_request.response_payload = _response_to_dict(response)
            return response

        config = await get_active_reward_config(session, org_id)
        referral = Referral(org_id=org_id, child_id=payload.child_id, parent_id=payload.parent_id, status=ReferralStatus.VALID, expires_at=payload.expires_at)
        session.add(referral)

        try:
            await session.flush()
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="referral already exists or child already linked") from exc

        ancestors = [payload.parent_id, *dag_engine.get_ancestors_unlocked(payload.parent_id, config.max_depth - 1)]
        rewards = await create_reward_entries(session, referral, ancestors, config, payload.base_amount)
        dag_engine.add_edge_unlocked(payload.child_id, payload.parent_id)

    response = ReferralClaimResponse(status="accepted", referral_id=referral.id, rewards=rewards)
    claim_request.status = ClaimRequestStatus.COMPLETED
    claim_request.response_payload = _response_to_dict(response)
    await _record_event(session, hub, org_id, "referral_claimed", {"referral_id": referral.id, "child_id": payload.child_id, "parent_id": payload.parent_id})
    for reward in rewards:
        await _record_event(session, hub, org_id, "reward_paid", reward.model_dump())
    await session.flush()
    return response
