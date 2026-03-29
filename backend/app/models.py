from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import (
    AdminRole, AdminUserStatus, ClaimRequestStatus, FraudReason,
    OrgPlan, OrgStatus, ReferralStatus, RewardType, UserStatus,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Organisation(TimestampMixin, Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    plan: Mapped[OrgPlan] = mapped_column(Enum(OrgPlan), default=OrgPlan.FREE, nullable=False)
    status: Mapped[OrgStatus] = mapped_column(Enum(OrgStatus), default=OrgStatus.ACTIVE, nullable=False)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_rate_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    admin_users: Mapped[list["AdminUser"]] = relationship("AdminUser", back_populates="organisation", lazy="noload")


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[AdminRole] = mapped_column(Enum(AdminRole), nullable=False)
    status: Mapped[AdminUserStatus] = mapped_column(Enum(AdminUserStatus), default=AdminUserStatus.ACTIVE, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organisation: Mapped["Organisation | None"] = relationship("Organisation", back_populates="admin_users", lazy="noload")
    sessions: Mapped[list["AdminSession"]] = relationship("AdminSession", back_populates="admin_user", lazy="noload", cascade="all, delete-orphan")


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("admin_users.id"), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    device_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    admin_user: Mapped["AdminUser"] = relationship("AdminUser", back_populates="sessions", lazy="noload")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), ForeignKey("admin_users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("admin_users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    reward_balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "username", name="uq_users_org_username"),
        UniqueConstraint("org_id", "email", name="uq_users_org_email"),
    )


class Referral(TimestampMixin, Base):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("child_id", name="uq_referrals_child_id"),
        UniqueConstraint("child_id", "parent_id", name="uq_referrals_child_parent"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    child_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    parent_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[ReferralStatus] = mapped_column(Enum(ReferralStatus), default=ReferralStatus.VALID, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FraudFlag(Base):
    __tablename__ = "fraud_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    referral_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("referrals.id"), nullable=True, index=True)
    reason: Mapped[FraudReason] = mapped_column(Enum(FraudReason), nullable=False, index=True)
    detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RewardConfig(TimestampMixin, Base):
    __tablename__ = "reward_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_type: Mapped[RewardType] = mapped_column(Enum(RewardType), default=RewardType.FIXED, nullable=False)
    reward_values: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("org_id", "version", name="uq_reward_config_org_version"),)


class RewardTransaction(Base):
    __tablename__ = "reward_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    from_referral_id: Mapped[str] = mapped_column(String(36), ForeignKey("referrals.id"), nullable=False, index=True)
    beneficiary_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ClaimRequest(TimestampMixin, Base):
    __tablename__ = "claim_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    child_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[ClaimRequestStatus] = mapped_column(Enum(ClaimRequestStatus), default=ClaimRequestStatus.PROCESSING, nullable=False)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
