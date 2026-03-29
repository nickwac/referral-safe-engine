"""Dashboard routes - metrics, activity, reward config, simulation, seed, and WebSocket stream."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import decode_token
from app.database import get_db_session
from app.dependencies import get_current_admin, get_event_hub
from app.events import EventHub
from app.models import ActivityEvent, RewardConfig
from app.schemas import (
    ActivityEventRead,
    MetricsResponse,
    RewardConfigRead,
    RewardConfigUpdate,
    SimulationRequest,
    SimulationResponse,
)
from app.services.dashboard import get_metrics
from app.services.rewards import simulate_payout
from seed import ensure_reward_backfill, seed

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/metrics", response_model=MetricsResponse)
async def dashboard_metrics(
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> MetricsResponse:
    return await get_metrics(session, org_id=admin.org_id)


@router.get("/dashboard/activity", response_model=list[ActivityEventRead])
async def dashboard_activity(
    limit: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> list[ActivityEventRead]:
    stmt = (
        select(ActivityEvent)
        .where((ActivityEvent.org_id == admin.org_id) | (ActivityEvent.org_id.is_(None)))
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
    )
    events = (await session.scalars(stmt)).all()
    return [ActivityEventRead.model_validate(e) for e in events]


@router.get("/reward/config", response_model=RewardConfigRead)
async def get_reward_config(
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> RewardConfigRead:
    config = await session.scalar(
        select(RewardConfig)
        .where(RewardConfig.org_id == admin.org_id, RewardConfig.is_active.is_(True))
        .order_by(RewardConfig.version.desc())
    )
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="active reward config not found")
    return RewardConfigRead.model_validate(config)


@router.put("/reward/config", response_model=RewardConfigRead)
async def update_reward_config(
    payload: RewardConfigUpdate,
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> RewardConfigRead:
    current = await session.scalar(
        select(RewardConfig)
        .where(RewardConfig.org_id == admin.org_id, RewardConfig.is_active.is_(True))
        .order_by(RewardConfig.version.desc())
    )
    next_version = 1 if current is None else current.version + 1
    async with session.begin():
        if current is not None:
            await session.execute(update(RewardConfig).where(RewardConfig.id == current.id).values(is_active=False))
        config = RewardConfig(
            org_id=admin.org_id,
            version=next_version,
            max_depth=payload.max_depth,
            reward_type=payload.reward_type,
            reward_values=payload.reward_values,
            is_active=True,
        )
        session.add(config)
    await session.refresh(config)
    return RewardConfigRead.model_validate(config)


@router.post("/simulate", response_model=SimulationResponse)
async def simulate_rewards(
    payload: SimulationRequest,
    admin=Depends(get_current_admin),
) -> SimulationResponse:
    total = simulate_payout(payload.reward_type, payload.reward_values, payload.max_depth, payload.projected_referrals, payload.base_amount)
    return SimulationResponse(projected_referrals=payload.projected_referrals, total_projected_payout=total, reward_type=payload.reward_type)


@router.post("/seed")
async def seed_data(
    session: AsyncSession = Depends(get_db_session),
    admin=Depends(get_current_admin),
) -> dict[str, str]:
    await seed()
    async with session.begin():
        await ensure_reward_backfill(session, admin.org_id)
    return {"status": "seeded"}


@router.websocket("/dashboard/stream")
async def dashboard_stream(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    try:
        payload = decode_token(token)
    except JWTError:
        await websocket.close(code=4401)
        return

    if payload.get("type") != "access":
        await websocket.close(code=4401)
        return

    org_id = payload.get("org_id")
    await websocket.accept()
    hub: EventHub = get_event_hub()
    queue = await hub.subscribe()
    try:
        while True:
            event = await queue.get()
            if event.get("org_id") not in {None, org_id}:
                continue
            await websocket.send_json(event)
    except WebSocketDisconnect:
        hub.unsubscribe(queue)
