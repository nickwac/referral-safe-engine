"""Additional schemas for auth, audit, team management, org management, sessions, and user profile."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.enums import (
    AdminRole, AdminUserStatus, FraudReason, OrgPlan, OrgStatus,
    ReferralStatus, RewardType, UserStatus,
)


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    status: UserStatus = UserStatus.ACTIVE


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: EmailStr
    status: UserStatus
    reward_balance: float
    created_at: datetime


class UserSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    status: UserStatus
    reward_balance: float


class UserListResponse(BaseModel):
    total: int
    items: list[UserRead]


class UserStatusUpdateRequest(BaseModel):
    status: UserStatus
    reason: str = Field(min_length=5, max_length=500)


class ReferralRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    child_id: str
    parent_id: str
    status: ReferralStatus
    created_at: datetime
    expires_at: datetime | None


class UserProfileResponse(BaseModel):
    user: UserRead
    referral_count: int
    fraud_flags: list["FraudFlagRead"]
    recent_transactions: list["RewardTransactionRead"]
    recent_claims: list[ReferralRead]
    audit_entries: list["AuditLogRead"]


class ReferralClaimRequest(BaseModel):
    child_id: str
    parent_id: str
    idempotency_key: str = Field(min_length=8, max_length=128)
    base_amount: float | None = Field(default=None, ge=0)
    expires_at: datetime | None = None


class RewardSummary(BaseModel):
    beneficiary_id: str
    amount: float
    level: int
    config_version: int


class ReferralClaimResponse(BaseModel):
    status: str
    referral_id: str | None = None
    reason: FraudReason | None = None
    rewards: list[RewardSummary] = Field(default_factory=list)


class GraphTreeNode(BaseModel):
    user_id: str
    username: str
    status: UserStatus
    referral_id: str | None = None
    referral_created_at: datetime | None = None
    children: list["GraphTreeNode"] = Field(default_factory=list)


class GraphResponse(BaseModel):
    root_user_id: str
    depth: int
    tree: GraphTreeNode


class RewardTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    from_referral_id: str
    beneficiary_id: str
    amount: float
    level: int
    config_version: int
    created_at: datetime


class RewardHistoryResponse(BaseModel):
    user_id: str
    total_rewards: float
    transactions: list[RewardTransactionRead]


class FraudFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None
    referral_id: str | None
    reason: FraudReason
    detail: str | None
    timestamp: datetime


class FraudFlagListResponse(BaseModel):
    total: int
    items: list[FraudFlagRead]


class FlagUserRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500, description="Reason for flagging this user")


class UnflagUserRequest(BaseModel):
    justification: str = Field(min_length=10, max_length=500, description="Justification for clearing this flag")


class RewardConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    max_depth: int
    reward_type: RewardType
    reward_values: list[float]
    is_active: bool


class RewardConfigUpdate(BaseModel):
    max_depth: int = Field(ge=1, le=10)
    reward_type: RewardType = RewardType.FIXED
    reward_values: list[float]

    @field_validator("reward_values")
    @classmethod
    def validate_reward_values(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("reward_values must not be empty")
        return value


class SimulationRequest(BaseModel):
    reward_type: RewardType
    reward_values: list[float]
    max_depth: int = Field(ge=1, le=10)
    projected_referrals: int = Field(ge=0)
    base_amount: float = Field(default=0, ge=0)


class SimulationResponse(BaseModel):
    projected_referrals: int
    total_projected_payout: float
    reward_type: RewardType


class MetricsResponse(BaseModel):
    total_users: int
    total_referrals: int
    total_rewards_distributed: float
    total_fraud_flags: int
    accepted_claims: int
    rejected_claims: int


class ActivityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    payload: dict
    created_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str | None
    before_state: dict | None
    after_state: dict | None
    ip_address: str | None
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    total: int
    items: list[AuditLogRead]


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: AdminRole
    status: AdminUserStatus
    last_login_at: datetime | None
    created_at: datetime


class AdminSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    admin_user_id: str
    device_hint: str | None
    ip_address: str | None
    last_active_at: datetime
    expires_at: datetime
    revoked: bool
    created_at: datetime
    is_current: bool = False


class AdminSessionListResponse(BaseModel):
    total: int
    items: list[AdminSessionRead]


class TeamListResponse(BaseModel):
    total: int
    items: list[AdminUserRead]


class TeamInviteRequest(BaseModel):
    email: EmailStr
    role: AdminRole = AdminRole.ANALYST


class OrganisationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    domain: str | None
    plan: OrgPlan
    status: OrgStatus
    max_users: int | None
    max_depth: int | None
    api_rate_limit: int | None
    created_at: datetime


class OrganisationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    domain: str | None = Field(default=None, max_length=255)
    plan: OrgPlan = OrgPlan.FREE
    max_users: int | None = Field(default=None, ge=1)
    max_depth: int | None = Field(default=None, ge=1, le=10)
    api_rate_limit: int | None = Field(default=None, ge=1)


class OrganisationListResponse(BaseModel):
    total: int
    items: list[OrganisationRead]


class ErrorResponse(BaseModel):
    detail: str
