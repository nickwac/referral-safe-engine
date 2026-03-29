from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    FLAGGED = "flagged"
    ROOT = "root"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"


class ReferralStatus(str, Enum):
    VALID = "valid"
    REJECTED = "rejected"
    EXPIRED = "expired"


class FraudReason(str, Enum):
    SELF_REFERRAL = "self_referral"
    DUPLICATE = "duplicate"
    ALREADY_REFERRED = "already_referred"
    VELOCITY = "velocity"
    CYCLE = "cycle"
    USER_BLOCKED = "user_blocked"
    USER_NOT_FOUND = "user_not_found"


class ClaimRequestStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RewardType(str, Enum):
    FIXED = "fixed"
    PERCENT = "percent"


# ── Auth / Identity Enums ──────────────────────────────────────────────────────

class AdminRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    MANAGER = "manager"
    ANALYST = "analyst"


class OrgPlan(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class OrgStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CHURNED = "churned"


class AdminUserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INVITED = "invited"
