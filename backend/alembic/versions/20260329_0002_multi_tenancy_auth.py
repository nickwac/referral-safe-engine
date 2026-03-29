"""add multi tenancy and admin auth schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_0002"
down_revision = "41a33e7b8826"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"


admin_role_enum = postgresql.ENUM("SUPER_ADMIN", "ORG_ADMIN", "MANAGER", "ANALYST", name="adminrole", create_type=False)
org_plan_enum = postgresql.ENUM("FREE", "PRO", "ENTERPRISE", name="orgplan", create_type=False)
org_status_enum = postgresql.ENUM("ACTIVE", "SUSPENDED", "CHURNED", name="orgstatus", create_type=False)
admin_user_status_enum = postgresql.ENUM("ACTIVE", "SUSPENDED", "INVITED", name="adminuserstatus", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    postgresql.ENUM("SUPER_ADMIN", "ORG_ADMIN", "MANAGER", "ANALYST", name="adminrole").create(bind, checkfirst=True)
    postgresql.ENUM("FREE", "PRO", "ENTERPRISE", name="orgplan").create(bind, checkfirst=True)
    postgresql.ENUM("ACTIVE", "SUSPENDED", "CHURNED", name="orgstatus").create(bind, checkfirst=True)
    postgresql.ENUM("ACTIVE", "SUSPENDED", "INVITED", name="adminuserstatus").create(bind, checkfirst=True)

    op.create_table(
        "organisations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True, unique=True),
        sa.Column("plan", org_plan_enum, nullable=False, server_default="FREE"),
        sa.Column("status", org_status_enum, nullable=False, server_default="ACTIVE"),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column("max_depth", sa.Integer(), nullable=True),
        sa.Column("api_rate_limit", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO organisations (id, name, domain, plan, status, created_at, updated_at)
            VALUES (:id, 'System', 'example.com', 'ENTERPRISE', 'ACTIVE', now(), now())
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(id=DEFAULT_ORG_ID)
    )

    for table_name, nullable in [
        ("users", False),
        ("referrals", False),
        ("fraud_flags", False),
        ("reward_configs", False),
        ("reward_transactions", False),
        ("claim_requests", False),
        ("activity_events", True),
    ]:
        op.add_column(table_name, sa.Column("org_id", sa.String(length=36), nullable=True))
        op.execute(sa.text(f"UPDATE {table_name} SET org_id = :org_id WHERE org_id IS NULL").bindparams(org_id=DEFAULT_ORG_ID))
        if not nullable:
            op.alter_column(table_name, "org_id", nullable=False)
        op.create_index(f"ix_{table_name}_org_id", table_name, ["org_id"], unique=False)
        op.create_foreign_key(f"fk_{table_name}_org_id", table_name, "organisations", ["org_id"], ["id"])

    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")
    op.create_unique_constraint("uq_users_org_username", "users", ["org_id", "username"])
    op.create_unique_constraint("uq_users_org_email", "users", ["org_id", "email"])

    op.execute("ALTER TABLE reward_configs DROP CONSTRAINT IF EXISTS reward_configs_version_key")
    op.create_unique_constraint("uq_reward_config_org_version", "reward_configs", ["org_id", "version"])

    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organisations.id"), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("role", admin_role_enum, nullable=False),
        sa.Column("status", admin_user_status_enum, nullable=False, server_default="ACTIVE"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_admin_users_org_id", "admin_users", ["org_id"], unique=False)
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("admin_user_id", sa.String(length=36), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False, unique=True),
        sa.Column("device_hint", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_admin_sessions_admin_user_id", "admin_sessions", ["admin_user_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("actor_id", sa.String(length=36), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_log_org_id", "audit_log", ["org_id"], unique=False)
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"], unique=False)
    op.create_index("ix_audit_log_action", "audit_log", ["action"], unique=False)
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_keys_org_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log")
    op.drop_index("ix_audit_log_org_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_admin_sessions_admin_user_id", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_index("ix_admin_users_email", table_name="admin_users")
    op.drop_index("ix_admin_users_org_id", table_name="admin_users")
    op.drop_table("admin_users")

    op.drop_constraint("uq_reward_config_org_version", "reward_configs", type_="unique")
    op.drop_constraint("uq_users_org_email", "users", type_="unique")
    op.drop_constraint("uq_users_org_username", "users", type_="unique")

    for table_name in ["activity_events", "claim_requests", "reward_transactions", "reward_configs", "fraud_flags", "referrals", "users"]:
        op.drop_constraint(f"fk_{table_name}_org_id", table_name, type_="foreignkey")
        op.drop_index(f"ix_{table_name}_org_id", table_name=table_name)
        op.drop_column(table_name, "org_id")

    op.drop_table("organisations")

    postgresql.ENUM("ACTIVE", "SUSPENDED", "INVITED", name="adminuserstatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM("ACTIVE", "SUSPENDED", "CHURNED", name="orgstatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM("FREE", "PRO", "ENTERPRISE", name="orgplan").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM("SUPER_ADMIN", "ORG_ADMIN", "MANAGER", "ANALYST", name="adminrole").drop(op.get_bind(), checkfirst=True)
