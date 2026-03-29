import os
from uuid import uuid4

import pytest_asyncio

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:1234@localhost:5432/referral_engine_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DEBUG"] = "false"

from app.database import Base, SessionLocal, engine
from app.enums import RewardType, UserStatus
from app.models import RewardConfig, User


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        session.add(RewardConfig(version=1, max_depth=3, reward_type=RewardType.FIXED, reward_values=[10.0, 5.0, 2.0], is_active=True))
        await session.commit()

    yield

    await engine.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def seeded_users():
    async with SessionLocal() as session:
        root = User(id=str(uuid4()), username="root", email="root@example.com", status=UserStatus.ROOT)
        parent = User(id=str(uuid4()), username="parent", email="parent@example.com", status=UserStatus.ACTIVE)
        child = User(id=str(uuid4()), username="child", email="child@example.com", status=UserStatus.ACTIVE)
        session.add_all([root, parent, child])
        await session.commit()
        return {"root": root, "parent": parent, "child": child}
