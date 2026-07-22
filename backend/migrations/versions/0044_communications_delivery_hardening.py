"""harden communications delivery ownership and recovery

Revision ID: 0044_communications_hardening
Revises: 0043_result_publication_audit
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_communications_hardening"
down_revision: str | None = "0043_result_publication_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("alter type emailsendstatus add value if not exists 'indeterminate'")
        op.execute("alter type emaileventtype add value if not exists 'indeterminate'")

    op.add_column("email_sends", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column(
        "email_sends",
        sa.Column("provider_idempotency_key", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "email_sends",
        sa.Column("provider_request_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_email_sends_owner_id_users"),
        "email_sends",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_email_sends_owner_id"), "email_sends", ["owner_id"])
    op.create_index(
        op.f("ix_email_sends_provider_idempotency_key"),
        "email_sends",
        ["provider_idempotency_key"],
        unique=True,
    )

    op.execute(
        """
        update email_sends as email_send
        set owner_id = campaign.owner_id
        from campaigns as campaign
        where email_send.campaign_id = campaign.id
          and email_send.owner_id is null
        """
    )

    op.create_table(
        "email_suppressions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("source_email_send_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_email_suppressions_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_email_send_id"],
            ["email_sends.id"],
            name=op.f("fk_email_suppressions_source_email_send_id_email_sends"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_suppressions")),
    )
    op.create_index(op.f("ix_email_suppressions_owner_id"), "email_suppressions", ["owner_id"])
    op.create_index(
        "uq_email_suppressions_owner_normalized_email",
        "email_suppressions",
        ["owner_id", sa.text("lower(email)")],
        unique=True,
    )

    op.create_table(
        "campaign_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("public_url", sa.String(length=2048), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="staged"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('staged', 'attached')",
            name=op.f("ck_campaign_assets_campaign_asset_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_assets_campaign_id_campaigns"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_campaign_assets_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_assets")),
        sa.UniqueConstraint("file_name", name=op.f("uq_campaign_assets_file_name")),
        sa.UniqueConstraint("public_url", name=op.f("uq_campaign_assets_public_url")),
    )
    op.create_index(op.f("ix_campaign_assets_campaign_id"), "campaign_assets", ["campaign_id"])
    op.create_index(op.f("ix_campaign_assets_owner_id"), "campaign_assets", ["owner_id"])

    op.drop_constraint("uq_email_templates_key_version", "email_templates", type_="unique")
    op.create_index(
        "uq_email_templates_owner_key_version",
        "email_templates",
        ["owner_id", "key", "version"],
        unique=True,
        postgresql_where=sa.text("owner_id is not null"),
    )
    op.create_index(
        "uq_email_templates_system_key_version",
        "email_templates",
        ["key", "version"],
        unique=True,
        postgresql_where=sa.text("owner_id is null"),
    )


def downgrade() -> None:
    op.drop_index("uq_email_templates_system_key_version", table_name="email_templates")
    op.drop_index("uq_email_templates_owner_key_version", table_name="email_templates")
    op.create_unique_constraint(
        "uq_email_templates_key_version",
        "email_templates",
        ["key", "version"],
    )
    op.drop_table("campaign_assets")
    op.drop_table("email_suppressions")
    op.drop_index(op.f("ix_email_sends_provider_idempotency_key"), table_name="email_sends")
    op.drop_index(op.f("ix_email_sends_owner_id"), table_name="email_sends")
    op.drop_constraint(op.f("fk_email_sends_owner_id_users"), "email_sends", type_="foreignkey")
    op.drop_column("email_sends", "provider_request_started_at")
    op.drop_column("email_sends", "provider_idempotency_key")
    op.drop_column("email_sends", "owner_id")

    # PostgreSQL enum values are intentionally retained on downgrade.
