from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update

from app.config import get_settings
from app.dag_engine import dag_engine
from app.database import SessionLocal
from app.enums import ReferralStatus, RewardType
from app.models import Referral, RewardConfig
from app.routes import admin, auth, dashboard, fraud, referrals, users
from seed import DEFAULT_ORG_ID

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with SessionLocal() as session:
        await session.execute(
            update(Referral)
            .where(Referral.expires_at.is_not(None), Referral.expires_at < datetime.now(timezone.utc), Referral.status == ReferralStatus.VALID)
            .values(status=ReferralStatus.EXPIRED)
        )
        await session.commit()

        referral_edges = (
            await session.execute(
                select(Referral.child_id, Referral.parent_id)
                .where(Referral.status == ReferralStatus.VALID)
                .where((Referral.expires_at.is_(None)) | (Referral.expires_at > datetime.now(timezone.utc)))
            )
        ).all()
        await dag_engine.rebuild_from_edges([(row[0], row[1]) for row in referral_edges])

        existing_config = await session.scalar(
            select(RewardConfig).where(RewardConfig.org_id == DEFAULT_ORG_ID, RewardConfig.is_active.is_(True))
        )
        if existing_config is None:
            session.add(
                RewardConfig(
                    org_id=DEFAULT_ORG_ID,
                    version=1,
                    max_depth=settings.reward_max_depth,
                    reward_type=RewardType.FIXED,
                    reward_values=settings.reward_amount_list,
                    is_active=True,
                )
            )
            await session.commit()
    yield


app = FastAPI(title=settings.api_title, debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(referrals.router)
app.include_router(users.router)
app.include_router(fraud.router)
app.include_router(dashboard.router)
app.include_router(admin.router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
