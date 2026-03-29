"""initial schema"""

from alembic import op
import sqlalchemy as sa

revision = "20260329_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("status", sa.Enum("ACTIVE", "FLAGGED", "ROOT", "INACTIVE", name="userstatus"), nullable=False),
        sa.Column("reward_balance", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "reward_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("max_depth", sa.Integer(), nullable=False),
        sa.Column("reward_type", sa.Enum("FIXED", "PERCENT", name="rewardtype"), nullable=False),
        sa.Column("reward_values", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "claim_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("child_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.Enum("PROCESSING", "COMPLETED", "FAILED", name="claimrequeststatus"), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_claim_requests_idempotency_key", "claim_requests", ["idempotency_key"])

    op.create_table(
        "referrals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("child_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Enum("VALID", "REJECTED", "EXPIRED", name="referralstatus"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("child_id", name="uq_referrals_child_id"),
        sa.UniqueConstraint("child_id", "parent_id", name="uq_referrals_child_parent"),
    )
    op.create_index("ix_referrals_child_id", "referrals", ["child_id"])
    op.create_index("ix_referrals_parent_id", "referrals", ["parent_id"])

    op.create_table(
        "reward_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("from_referral_id", sa.String(length=36), sa.ForeignKey("referrals.id"), nullable=False),
        sa.Column("beneficiary_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reward_transactions_from_referral_id", "reward_transactions", ["from_referral_id"])
    op.create_index("ix_reward_transactions_beneficiary_id", "reward_transactions", ["beneficiary_id"])

    op.create_table(
        "fraud_flags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("referral_id", sa.String(length=36), sa.ForeignKey("referrals.id"), nullable=True),
        sa.Column("reason", sa.Enum("SELF_REFERRAL", "DUPLICATE", "ALREADY_REFERRED", "VELOCITY", "CYCLE", "USER_BLOCKED", "USER_NOT_FOUND", name="fraudreason"), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fraud_flags_user_id", "fraud_flags", ["user_id"])
    op.create_index("ix_fraud_flags_referral_id", "fraud_flags", ["referral_id"])
    op.create_index("ix_fraud_flags_reason", "fraud_flags", ["reason"])

    op.create_table(
        "activity_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_activity_events_event_type", "activity_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_activity_events_event_type", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_index("ix_fraud_flags_reason", table_name="fraud_flags")
    op.drop_index("ix_fraud_flags_referral_id", table_name="fraud_flags")
    op.drop_index("ix_fraud_flags_user_id", table_name="fraud_flags")
    op.drop_table("fraud_flags")
    op.drop_index("ix_reward_transactions_beneficiary_id", table_name="reward_transactions")
    op.drop_index("ix_reward_transactions_from_referral_id", table_name="reward_transactions")
    op.drop_table("reward_transactions")
    op.drop_index("ix_referrals_parent_id", table_name="referrals")
    op.drop_index("ix_referrals_child_id", table_name="referrals")
    op.drop_table("referrals")
    op.drop_index("ix_claim_requests_idempotency_key", table_name="claim_requests")
    op.drop_table("claim_requests")
    op.drop_table("reward_configs")
    op.drop_table("users")
