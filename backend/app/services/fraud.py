from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.enums import FraudReason, UserStatus

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None


class InMemoryVelocityLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, deque[datetime]] = defaultdict(deque)

    async def is_limited(self, user_id: str, max_claims_per_minute: int) -> bool:
        now = datetime.now(timezone.utc)
        bucket = self._requests[user_id]
        cutoff = now - timedelta(minutes=1)
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_claims_per_minute:
            return True
        bucket.append(now)
        return False


class RedisVelocityLimiter:
    def __init__(self, redis_url: str) -> None:
        self.client = redis.from_url(redis_url, decode_responses=True)

    async def is_limited(self, user_id: str, max_claims_per_minute: int) -> bool:
        key = f"referral-velocity:{user_id}"
        now = datetime.now(timezone.utc)
        now_score = now.timestamp()
        cutoff = now_score - 60
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.zremrangebyscore(key, 0, cutoff)
            await pipe.zcard(key)
            await pipe.zadd(key, {str(now_score): now_score})
            await pipe.expire(key, 120)
            result = await pipe.execute()
        current_count = int(result[1])
        return current_count >= max_claims_per_minute


settings = get_settings()
velocity_limiter = RedisVelocityLimiter(settings.redis_url) if settings.redis_url and redis is not None else InMemoryVelocityLimiter()


def validate_user_status(child_status: UserStatus, parent_status: UserStatus) -> FraudReason | None:
    blocked = {UserStatus.FLAGGED, UserStatus.INACTIVE}
    if child_status in blocked or parent_status in blocked:
        return FraudReason.USER_BLOCKED
    return None


def validate_self_referral(child_id: str, parent_id: str) -> FraudReason | None:
    if child_id == parent_id:
        return FraudReason.SELF_REFERRAL
    return None
