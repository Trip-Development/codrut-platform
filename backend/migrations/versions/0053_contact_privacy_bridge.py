"""backfill the contact privacy bridge without closing the rollback window

Revision ID: 0053_contact_privacy_bridge
Revises: 0052_contact_archive
Create Date: 2026-07-30

This release must remain compatible with the retained pre-contract,
fingerprint-aware archive application image. It therefore backfills the expand
fields but deliberately keeps the real-email compatibility column, its unique
index, and the nullable fingerprint/review/event-owner columns.

The destructive fingerprint-only contract (scrubbing or dropping ``email`` and
making the expand fields non-null) belongs in a later release, after this
dual-read/dual-write application has become the retained rollback image.
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

revision: str = "0053_contact_privacy_bridge"
down_revision: str | None = "0052_contact_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUPPRESSION_SECRET_ENV = "CODRUT_EMAIL_SUPPRESSION_FINGERPRINT_SECRET"  # noqa: S105
SUPPRESSION_REVIEW_DAYS_ENV = "CODRUT_EMAIL_SUPPRESSION_REVIEW_DAYS"


def _suppression_secret(row_count: int) -> str:
    secret = os.getenv(SUPPRESSION_SECRET_ENV, "").strip()
    if row_count == 0:
        return secret
    if len(secret) < 32:
        raise RuntimeError(
            f"{SUPPRESSION_SECRET_ENV} must be configured with at least 32 characters "
            "before backfilling email suppressions."
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


def _backfill_late_suppressions(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                select id, owner_id, email
                from email_suppressions
                where email_fingerprint is null or review_after is null
                order by id
                """
            )
        ).mappings()
    )
    secret = _suppression_secret(len(rows))
    review_after = datetime.now(UTC) + timedelta(days=_suppression_review_days())
    for row in rows:
        values: dict[str, object] = {
            "suppression_id": row["id"],
            "review_after": review_after,
        }
        if row["email"] is not None:
            values["fingerprint"] = _fingerprint(
                owner_id=UUID(str(row["owner_id"])),
                email=str(row["email"]),
                secret=secret,
            )
        bind.execute(
            sa.text(
                """
                update email_suppressions
                set email_fingerprint = coalesce(email_fingerprint, :fingerprint),
                    review_after = coalesce(review_after, :review_after)
                where id = :suppression_id
                """
            ),
            {"fingerprint": values.get("fingerprint"), **values},
        )


def upgrade() -> None:
    bind = op.get_bind()
    _backfill_late_suppressions(bind)

    unresolved_suppressions = int(
        bind.execute(
            sa.text(
                """
                select count(*)
                from email_suppressions
                where email_fingerprint is null or review_after is null
                """
            )
        ).scalar_one()
    )
    if unresolved_suppressions:
        raise RuntimeError(
            "Contact privacy contract left "
            f"{unresolved_suppressions} suppressions unresolved."
        )
    unresolved_event_owners = int(
        bind.execute(
            sa.text(
                "select count(*) from campaign_recipient_events where owner_id is null"
            )
        ).scalar_one()
    )
    if unresolved_event_owners:
        raise RuntimeError(
            "Contact privacy contract left "
            f"{unresolved_event_owners} campaign event owners unresolved."
        )

    # Do not contract the schema here. The retained production image reads and
    # writes ``email`` and does not provide the new expand fields. A later
    # migration may enforce the fingerprint-only contract only after this
    # application is itself the rollback image.


def downgrade() -> None:
    # Upgrade only backfills data in columns owned by 0052. Keeping those values
    # makes downgrade/re-upgrade idempotent and preserves suppression coverage.
    pass
