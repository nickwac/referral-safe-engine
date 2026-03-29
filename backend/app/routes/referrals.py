from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dag_engine import DAGEngine
from app.database import get_db_session
from app.dependencies import get_app_settings, get_dag_engine, get_event_hub
from app.events import EventHub
from app.schemas import ReferralClaimRequest, ReferralClaimResponse
from app.services.claims import process_claim

router = APIRouter(prefix="/referral", tags=["referrals"])


@router.post("/claim", response_model=ReferralClaimResponse)
async def claim_referral(
    payload: ReferralClaimRequest,
    session: AsyncSession = Depends(get_db_session),
    dag_engine: DAGEngine = Depends(get_dag_engine),
    hub: EventHub = Depends(get_event_hub),
    settings: Settings = Depends(get_app_settings),
) -> ReferralClaimResponse:
    async with session.begin():
        return await process_claim(session, dag_engine, hub, settings, payload)
