import pytest

from app.config import get_settings
from app.dag_engine import DAGEngine
from app.database import SessionLocal
from app.enums import FraudReason
from app.events import EventHub
from app.schemas import ReferralClaimRequest
from app.services.claims import process_claim


@pytest.mark.asyncio
async def test_process_claim_accepts_and_pays_rewards(seeded_users):
    dag_engine = DAGEngine()
    await dag_engine.rebuild_from_edges([(seeded_users["parent"].id, seeded_users["root"].id)])
    settings = get_settings()
    hub = EventHub()

    async with SessionLocal() as session:
        payload = ReferralClaimRequest(
            child_id=seeded_users["child"].id,
            parent_id=seeded_users["parent"].id,
            idempotency_key="claim-accept-001",
        )
        async with session.begin():
            response = await process_claim(session, dag_engine, hub, settings, payload)

    assert response.status == "accepted"
    assert [reward.amount for reward in response.rewards] == [10.0, 5.0]


@pytest.mark.asyncio
async def test_process_claim_rejects_cycle(seeded_users):
    dag_engine = DAGEngine()
    await dag_engine.rebuild_from_edges([
        (seeded_users["parent"].id, seeded_users["child"].id),
        (seeded_users["child"].id, seeded_users["root"].id),
    ])
    settings = get_settings()
    hub = EventHub()

    async with SessionLocal() as session:
        payload = ReferralClaimRequest(
            child_id=seeded_users["root"].id,
            parent_id=seeded_users["parent"].id,
            idempotency_key="claim-cycle-001",
        )
        async with session.begin():
            response = await process_claim(session, dag_engine, hub, settings, payload)

    assert response.status == "rejected"
    assert response.reason == FraudReason.CYCLE


@pytest.mark.asyncio
async def test_process_claim_is_idempotent(seeded_users):
    dag_engine = DAGEngine()
    await dag_engine.rebuild_from_edges([(seeded_users["parent"].id, seeded_users["root"].id)])
    settings = get_settings()
    hub = EventHub()
    payload = ReferralClaimRequest(
        child_id=seeded_users["child"].id,
        parent_id=seeded_users["parent"].id,
        idempotency_key="claim-idempotent-001",
    )

    async with SessionLocal() as session:
        async with session.begin():
            first = await process_claim(session, dag_engine, hub, settings, payload)

    async with SessionLocal() as session:
        async with session.begin():
            second = await process_claim(session, dag_engine, hub, settings, payload)

    assert first.model_dump() == second.model_dump()
