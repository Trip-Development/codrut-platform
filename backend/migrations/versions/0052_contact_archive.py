"""add contact archive and protected suppression retention

Revision ID: 0052_contact_archive
Revises: 0051_contact_owner_repair
Create Date: 2026-07-30
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0052_contact_archive"
down_revision: str | None = "0051_contact_owner_repair"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUPPRESSION_SECRET_ENV = "CODRUT_EMAIL_SUPPRESSION_FINGERPRINT_SECRET"  # noqa: S105
SUPPRESSION_REVIEW_DAYS_ENV = "CODRUT_EMAIL_SUPPRESSION_REVIEW_DAYS"
campaign_recipient_status = postgresql.ENUM(
    "active",
    "suppressed",
    "unsubscribed",
    name="campaignrecipientstatus",
    create_type=False,
)


def _suppression_secret(row_count: int) -> str:
    secret = os.getenv(SUPPRESSION_SECRET_ENV, "").strip()
    if row_count == 0:
        return secret
    if len(secret) < 32:
        raise RuntimeError(
            f"{SUPPRESSION_SECRET_ENV} must be configured with at least 32 characters "
            "before migrating existing email suppressions."
        )
    return secret


def _suppression_review_days() -> int:
    raw_value = os.getenv(SUPPRESSION_REVIEW_DAYS_ENV, "365").strip()
    try:
        review_days = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{SUPPRESSION_REVIEW_DAYS_ENV} must be an integer.") from exc
    if not 30 <= review_days <= 3650:
        raise RuntimeError(
            f"{SUPPRESSION_REVIEW_DAYS_ENV} must be between 30 and 3650."
        )
    return review_days


def _fingerprint(*, owner_id: UUID, email: str, secret: str) -> str:
    normalized_email = email.strip().casefold()
    message = f"codrut-email-suppression:v1:{owner_id}:{normalized_email}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def _migrate_suppressions(bind: sa.Connection) -> None:
    suppressions = list(
        bind.execute(
            sa.text("select id, owner_id, email from email_suppressions order by id")
        ).mappings()
    )
    secret = _suppression_secret(len(suppressions))
    review_after = datetime.now(UTC) + timedelta(days=_suppression_review_days())
    for suppression in suppressions:
        bind.execute(
            sa.text(
                """
                update email_suppressions
                set email_fingerprint = :fingerprint,
                    review_after = :review_after
                where id = :suppression_id
                """
            ),
            {
                "fingerprint": _fingerprint(
                    owner_id=UUID(str(suppression["owner_id"])),
                    email=str(suppression["email"]),
                    secret=secret,
                ),
                "review_after": review_after,
                "suppression_id": suppression["id"],
            },
        )


def upgrade() -> None:
    bind = op.get_bind()

    duplicate_provider_message_ids = int(
        bind.execute(
            sa.text(
                """
                select count(*)
                from (
                    select provider_message_id
                    from email_sends
                    where provider_message_id is not null
                    group by provider_message_id
                    having count(*) > 1
                ) duplicates
                """
            )
        ).scalar_one()
    )
    if duplicate_provider_message_ids:
        raise RuntimeError(
            "Cannot enable replay-safe contact erasure while duplicate provider "
            f"message IDs exist: {duplicate_provider_message_ids} duplicate groups."
        )
    op.create_index(
        "uq_email_sends_provider_message_id",
        "email_sends",
        ["provider_message_id"],
        unique=True,
        postgresql_where=sa.text("provider_message_id is not null"),
    )

    op.add_column(
        "campaign_recipients",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campaign_recipients",
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campaign_recipients",
        sa.Column("status_before_archive", campaign_recipient_status, nullable=True),
    )
    op.create_index(
        op.f("ix_campaign_recipients_archived_at"),
        "campaign_recipients",
        ["archived_at"],
    )
    op.create_index(
        op.f("ix_campaign_recipients_purge_after"),
        "campaign_recipients",
        ["purge_after"],
    )
    op.create_check_constraint(
        op.f("ck_campaign_recipients_campaign_recipient_archive_window"),
        "campaign_recipients",
        "(archived_at is null and purge_after is null) or "
        "(archived_at is not null and purge_after is not null "
        "and purge_after >= archived_at)",
    )

    op.add_column(
        "email_suppressions",
        sa.Column("email_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "email_suppressions",
        sa.Column("review_after", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "email_suppressions",
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    _migrate_suppressions(bind)
    op.create_index(
        "uq_email_suppressions_owner_fingerprint",
        "email_suppressions",
        ["owner_id", "email_fingerprint"],
        unique=True,
    )

    op.add_column(
        "campaign_recipient_events",
        sa.Column("owner_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "campaign_recipient_events",
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        """
        update campaign_recipient_events event
        set owner_id = recipient.owner_id
        from campaign_recipients recipient
        where recipient.id = event.recipient_id
        """
    )
    op.execute(
        """
        update campaign_recipient_events event
        set campaign_id = campaign.id
        from campaigns campaign
        where event.campaign_id is null
          and campaign.id::text = lower(event.variant_key)
          and campaign.owner_id = event.owner_id
        """
    )
    op.execute(
        """
        update campaign_recipient_events event
        set campaign_id = membership_scope.campaign_id
        from (
            select
                membership.recipient_id,
                campaign.owner_id,
                min(membership.campaign_id::text)::uuid as campaign_id
            from campaign_recipient_memberships membership
            join campaigns campaign on campaign.id = membership.campaign_id
            group by membership.recipient_id, campaign.owner_id
            having count(distinct membership.campaign_id) = 1
        ) membership_scope
        where event.campaign_id is null
          and membership_scope.recipient_id = event.recipient_id
          and membership_scope.owner_id = event.owner_id
        """
    )
    op.execute(
        """
        update campaign_recipient_events event
        set campaign_id = latest_send.campaign_id
        from (
            select distinct on (send.campaign_recipient_id, send.owner_id)
                send.campaign_recipient_id,
                send.owner_id,
                send.campaign_id
            from email_sends send
            join campaigns campaign on campaign.id = send.campaign_id
            where send.campaign_recipient_id is not null
              and send.campaign_id is not null
              and send.owner_id is not null
              and campaign.owner_id = send.owner_id
            order by
                send.campaign_recipient_id,
                send.owner_id,
                send.created_at desc,
                send.id desc
        ) latest_send
        where event.campaign_id is null
          and latest_send.campaign_recipient_id = event.recipient_id
          and latest_send.owner_id = event.owner_id
        """
    )
    missing_event_owners = int(
        bind.execute(
            sa.text(
                "select count(*) from campaign_recipient_events where owner_id is null"
            )
        ).scalar_one()
    )
    if missing_event_owners:
        raise RuntimeError(
            "Campaign recipient event ownership backfill left "
            f"{missing_event_owners} rows unresolved."
        )

    op.drop_constraint(
        op.f("fk_campaign_recipient_events_recipient_id_campaign_recipients"),
        "campaign_recipient_events",
        type_="foreignkey",
    )
    op.alter_column(
        "campaign_recipient_events",
        "recipient_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.create_foreign_key(
        op.f("fk_campaign_recipient_events_recipient_id_campaign_recipients"),
        "campaign_recipient_events",
        "campaign_recipients",
        ["recipient_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_campaign_recipient_events_owner_id_users"),
        "campaign_recipient_events",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_campaign_recipient_events_campaign_id_campaigns"),
        "campaign_recipient_events",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_campaign_recipient_events_owner_id"),
        "campaign_recipient_events",
        ["owner_id"],
    )
    op.create_index(
        op.f("ix_campaign_recipient_events_campaign_id"),
        "campaign_recipient_events",
        ["campaign_id"],
    )

    op.create_table(
        "campaign_contact_tombstones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("former_recipient_id", sa.Uuid(), nullable=False),
        sa.Column("email_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("do_not_contact_reason", sa.String(length=64), nullable=True),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_campaign_contact_tombstones_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_contact_tombstones")),
        sa.UniqueConstraint(
            "owner_id",
            "former_recipient_id",
            name=op.f("uq_campaign_contact_tombstones_owner_former_recipient"),
        ),
    )
    op.create_index(
        op.f("ix_campaign_contact_tombstones_owner_id"),
        "campaign_contact_tombstones",
        ["owner_id"],
    )
    op.create_index(
        op.f("ix_campaign_contact_tombstones_former_recipient_id"),
        "campaign_contact_tombstones",
        ["former_recipient_id"],
    )
    op.create_index(
        "ix_campaign_contact_tombstones_owner_email_fingerprint",
        "campaign_contact_tombstones",
        ["owner_id", "email_fingerprint"],
    )
    op.create_index(
        op.f("ix_campaign_contact_tombstones_review_after"),
        "campaign_contact_tombstones",
        ["review_after"],
    )

    op.create_table(
        "campaign_delivery_tombstones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_tombstone_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column(
            "provider_message_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["contact_tombstone_id"],
            ["campaign_contact_tombstones.id"],
            name=op.f(
                "fk_campaign_delivery_tombstones_contact_tombstone_id_"
                "campaign_contact_tombstones"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_delivery_tombstones_campaign_id_campaigns"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_delivery_tombstones")),
        sa.UniqueConstraint(
            "provider_message_fingerprint",
            name=op.f(
                "uq_campaign_delivery_tombstones_provider_message_fingerprint"
            ),
        ),
    )
    op.create_index(
        op.f("ix_campaign_delivery_tombstones_contact_tombstone_id"),
        "campaign_delivery_tombstones",
        ["contact_tombstone_id"],
    )
    op.create_index(
        op.f("ix_campaign_delivery_tombstones_campaign_id"),
        "campaign_delivery_tombstones",
        ["campaign_id"],
    )
    op.create_index(
        op.f("ix_campaign_delivery_tombstones_expires_at"),
        "campaign_delivery_tombstones",
        ["expires_at"],
    )

    op.create_table(
        "campaign_delivery_event_tombstones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_tombstone_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider_event_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["delivery_tombstone_id"],
            ["campaign_delivery_tombstones.id"],
            name=op.f(
                "fk_campaign_delivery_event_tombstones_delivery_tombstone_id_"
                "campaign_delivery_tombstones"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_campaign_delivery_event_tombstones"),
        ),
        sa.UniqueConstraint(
            "provider_event_fingerprint",
            name=op.f("uq_delivery_event_tombstone_provider_fingerprint"),
        ),
    )
    op.create_index(
        op.f("ix_campaign_delivery_event_tombstones_delivery_tombstone_id"),
        "campaign_delivery_event_tombstones",
        ["delivery_tombstone_id"],
    )

    op.create_table(
        "email_suppression_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("suppression_id", sa.Uuid(), nullable=True),
        sa.Column("tombstone_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reviewer", sa.String(length=64), nullable=False),
        sa.Column("basis", sa.String(length=255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_email_suppression_reviews_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["suppression_id"],
            ["email_suppressions.id"],
            name=op.f(
                "fk_email_suppression_reviews_suppression_id_email_suppressions"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tombstone_id"],
            ["campaign_contact_tombstones.id"],
            name=op.f(
                "fk_email_suppression_reviews_tombstone_id_"
                "campaign_contact_tombstones"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_suppression_reviews")),
    )
    op.create_index(
        op.f("ix_email_suppression_reviews_owner_id"),
        "email_suppression_reviews",
        ["owner_id"],
    )
    op.create_index(
        op.f("ix_email_suppression_reviews_suppression_id"),
        "email_suppression_reviews",
        ["suppression_id"],
    )
    op.create_index(
        op.f("ix_email_suppression_reviews_tombstone_id"),
        "email_suppression_reviews",
        ["tombstone_id"],
    )

    op.create_table(
        "campaign_contact_aggregates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("scope_key", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("metric", sa.String(length=80), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
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
            name=op.f("fk_campaign_contact_aggregates_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_contact_aggregates")),
        sa.UniqueConstraint(
            "owner_id",
            "scope_key",
            "metric",
            name=op.f("uq_campaign_contact_aggregates_owner_scope_metric"),
        ),
    )
    op.create_index(
        op.f("ix_campaign_contact_aggregates_owner_id"),
        "campaign_contact_aggregates",
        ["owner_id"],
    )
    op.create_index(
        op.f("ix_campaign_contact_aggregates_campaign_id"),
        "campaign_contact_aggregates",
        ["campaign_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    incompatible_counts = {
        "archived contacts": int(
            bind.execute(
                sa.text(
                    "select count(*) from campaign_recipients "
                    "where archived_at is not null"
                )
            ).scalar_one()
        ),
        "detached campaign events": int(
            bind.execute(
                sa.text(
                    "select count(*) from campaign_recipient_events "
                    "where recipient_id is null"
                )
            ).scalar_one()
        ),
        "contact tombstones": int(
            bind.execute(
                sa.text("select count(*) from campaign_contact_tombstones")
            ).scalar_one()
        ),
        "retained contact aggregates": int(
            bind.execute(
                sa.text("select count(*) from campaign_contact_aggregates")
            ).scalar_one()
        ),
        "suppression review audits": int(
            bind.execute(
                sa.text("select count(*) from email_suppression_reviews")
            ).scalar_one()
        ),
    }
    incompatible = {
        label: count for label, count in incompatible_counts.items() if count
    }
    if incompatible:
        details = ", ".join(
            f"{label}={count}" for label, count in incompatible.items()
        )
        raise RuntimeError(
            "Cannot roll back contact archive expansion after new lifecycle data "
            f"has been created: {details}."
        )

    op.drop_index(
        op.f("ix_campaign_contact_aggregates_campaign_id"),
        table_name="campaign_contact_aggregates",
    )
    op.drop_index(
        op.f("ix_campaign_contact_aggregates_owner_id"),
        table_name="campaign_contact_aggregates",
    )
    op.drop_table("campaign_contact_aggregates")

    op.drop_index(
        op.f("ix_email_suppression_reviews_tombstone_id"),
        table_name="email_suppression_reviews",
    )
    op.drop_index(
        op.f("ix_email_suppression_reviews_suppression_id"),
        table_name="email_suppression_reviews",
    )
    op.drop_index(
        op.f("ix_email_suppression_reviews_owner_id"),
        table_name="email_suppression_reviews",
    )
    op.drop_table("email_suppression_reviews")

    op.drop_index(
        op.f("ix_campaign_delivery_event_tombstones_delivery_tombstone_id"),
        table_name="campaign_delivery_event_tombstones",
    )
    op.drop_table("campaign_delivery_event_tombstones")

    op.drop_index(
        op.f("ix_campaign_delivery_tombstones_expires_at"),
        table_name="campaign_delivery_tombstones",
    )
    op.drop_index(
        op.f("ix_campaign_delivery_tombstones_campaign_id"),
        table_name="campaign_delivery_tombstones",
    )
    op.drop_index(
        op.f("ix_campaign_delivery_tombstones_contact_tombstone_id"),
        table_name="campaign_delivery_tombstones",
    )
    op.drop_table("campaign_delivery_tombstones")

    op.drop_index(
        op.f("ix_campaign_contact_tombstones_review_after"),
        table_name="campaign_contact_tombstones",
    )
    op.drop_index(
        "ix_campaign_contact_tombstones_owner_email_fingerprint",
        table_name="campaign_contact_tombstones",
    )
    op.drop_index(
        op.f("ix_campaign_contact_tombstones_former_recipient_id"),
        table_name="campaign_contact_tombstones",
    )
    op.drop_index(
        op.f("ix_campaign_contact_tombstones_owner_id"),
        table_name="campaign_contact_tombstones",
    )
    op.drop_table("campaign_contact_tombstones")

    op.drop_index(
        op.f("ix_campaign_recipient_events_campaign_id"),
        table_name="campaign_recipient_events",
    )
    op.drop_index(
        op.f("ix_campaign_recipient_events_owner_id"),
        table_name="campaign_recipient_events",
    )
    op.drop_constraint(
        op.f("fk_campaign_recipient_events_campaign_id_campaigns"),
        "campaign_recipient_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_campaign_recipient_events_owner_id_users"),
        "campaign_recipient_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_campaign_recipient_events_recipient_id_campaign_recipients"),
        "campaign_recipient_events",
        type_="foreignkey",
    )
    op.alter_column(
        "campaign_recipient_events",
        "recipient_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        op.f("fk_campaign_recipient_events_recipient_id_campaign_recipients"),
        "campaign_recipient_events",
        "campaign_recipients",
        ["recipient_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("campaign_recipient_events", "campaign_id")
    op.drop_column("campaign_recipient_events", "owner_id")

    op.drop_index(
        "uq_email_suppressions_owner_fingerprint",
        table_name="email_suppressions",
    )
    op.drop_column("email_suppressions", "last_reviewed_at")
    op.drop_column("email_suppressions", "review_after")
    op.drop_column("email_suppressions", "email_fingerprint")

    op.drop_constraint(
        op.f("ck_campaign_recipients_campaign_recipient_archive_window"),
        "campaign_recipients",
        type_="check",
    )
    op.drop_column("campaign_recipients", "status_before_archive")
    op.drop_index(
        op.f("ix_campaign_recipients_purge_after"),
        table_name="campaign_recipients",
    )
    op.drop_index(
        op.f("ix_campaign_recipients_archived_at"),
        table_name="campaign_recipients",
    )
    op.drop_column("campaign_recipients", "purge_after")
    op.drop_column("campaign_recipients", "archived_at")
    op.drop_index(
        "uq_email_sends_provider_message_id",
        table_name="email_sends",
    )
