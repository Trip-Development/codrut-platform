"""persist campaign recipient memberships

Revision ID: 0030_campaign_memberships
Revises: 0029_clear_campaign_contacts
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_campaign_memberships"
down_revision: str | None = "0029_clear_campaign_contacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("create extension if not exists pgcrypto")
    op.add_column(
        "campaigns",
        sa.Column(
            "recipient_memberships_initialized",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_table(
        "campaign_recipient_memberships",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
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
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_crm_campaign_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["campaign_recipients.id"],
            name="fk_crm_recipient_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaign_recipient_memberships"),
        sa.UniqueConstraint(
            "campaign_id",
            "recipient_id",
            name="uq_campaign_recipient_memberships_campaign_recipient",
        ),
    )
    op.create_index(
        "ix_campaign_recipient_memberships_campaign_id",
        "campaign_recipient_memberships",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_recipient_memberships_recipient_id",
        "campaign_recipient_memberships",
        ["recipient_id"],
        unique=False,
    )

    op.execute(
        """
        insert into campaign_recipient_memberships (
            campaign_id,
            recipient_id,
            source,
            created_at,
            updated_at
        )
        select distinct
            es.campaign_id,
            es.campaign_recipient_id,
            'send_history',
            now(),
            now()
        from email_sends es
        join campaigns c on c.id = es.campaign_id
        join campaign_recipients cr on cr.id = es.campaign_recipient_id
        where es.campaign_id is not null
          and es.campaign_recipient_id is not null
        on conflict (campaign_id, recipient_id) do nothing
        """
    )
    op.execute(
        """
        insert into campaign_recipient_memberships (
            campaign_id,
            recipient_id,
            source,
            created_at,
            updated_at
        )
        select distinct
            es.campaign_id,
            cr.id,
            'send_email_match',
            now(),
            now()
        from email_sends es
        join campaigns c on c.id = es.campaign_id
        join campaign_recipients cr
          on cr.email is not null
         and lower(cr.email) = lower(es.recipient_email)
         and (c.owner_id is null or cr.owner_id is null or c.owner_id = cr.owner_id)
        where es.campaign_id is not null
          and es.campaign_recipient_id is null
        on conflict (campaign_id, recipient_id) do nothing
        """
    )
    op.execute(
        """
        insert into campaign_recipient_memberships (
            campaign_id,
            recipient_id,
            source,
            created_at,
            updated_at
        )
        select distinct
            c.id,
            cr.id,
            'segment_backfill',
            now(),
            now()
        from campaigns c
        join campaign_recipients cr
          on cr.segment = c.segment
         and cr.status = 'active'
         and cr.email is not null
         and (c.owner_id is null or cr.owner_id is null or c.owner_id = cr.owner_id)
        where c.status in ('draft', 'ready')
          and not exists (
              select 1 from email_sends es where es.campaign_id = c.id
          )
        on conflict (campaign_id, recipient_id) do nothing
        """
    )
    op.execute(
        """
        update campaigns c
        set recipient_memberships_initialized = true
        where exists (
            select 1
            from campaign_recipient_memberships crm
            where crm.campaign_id = c.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_recipient_memberships_recipient_id",
        table_name="campaign_recipient_memberships",
    )
    op.drop_index(
        "ix_campaign_recipient_memberships_campaign_id",
        table_name="campaign_recipient_memberships",
    )
    op.drop_table("campaign_recipient_memberships")
    op.drop_column("campaigns", "recipient_memberships_initialized")
