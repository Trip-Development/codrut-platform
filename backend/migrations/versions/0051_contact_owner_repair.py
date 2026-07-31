"""repair legacy campaign and contact ownership

Revision ID: 0051_contact_owner_repair
Revises: 0050_identity_account_types
Create Date: 2026-07-30
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0051_contact_owner_repair"
down_revision: str | None = "0050_identity_account_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOGGER = logging.getLogger("alembic.runtime.migration")
LEGACY_OWNER_ENV = "CODRUT_LEGACY_CAMPAIGN_CONTACT_OWNER_ID"


def _ownerless_count(bind: sa.Connection) -> int:
    return int(
        bind.execute(
            sa.text("select count(*) from campaign_recipients where owner_id is null")
        ).scalar_one()
    )


def _ownerless_campaign_count(bind: sa.Connection) -> int:
    return int(
        bind.execute(sa.text("select count(*) from campaigns where owner_id is null")).scalar_one()
    )


def _configured_owner_id() -> UUID | None:
    raw_owner_id = os.getenv(LEGACY_OWNER_ENV, "").strip()
    if not raw_owner_id:
        return None
    try:
        return UUID(raw_owner_id)
    except ValueError as exc:
        raise RuntimeError(f"{LEGACY_OWNER_ENV} must contain a valid UUID.") from exc


def _resolve_legacy_owner_id(bind: sa.Connection) -> UUID:
    configured_owner_id = _configured_owner_id()
    if configured_owner_id is not None:
        owner_ids = [configured_owner_id]
    else:
        owner_ids = [
            UUID(str(owner_id))
            for owner_id in bind.execute(
                sa.text(
                    """
                    select distinct candidate.owner_id
                    from (
                        select owner_id
                        from campaigns
                        where owner_id is not null

                        union

                        select owner_id
                        from email_sends
                        where owner_id is not null
                          and (campaign_id is not null or campaign_recipient_id is not null)
                    ) candidate
                    join users trainer on trainer.id = candidate.owner_id
                    where trainer.role = 'trainer'
                    order by candidate.owner_id
                    """
                )
            ).scalars()
        ]
        if len(owner_ids) != 1:
            raise RuntimeError(
                "Legacy campaign contacts have ambiguous ownership. Set "
                f"{LEGACY_OWNER_ENV} to the intended trainer UUID; "
                f"found {len(owner_ids)} candidate trainers."
            )

    owner_id = owner_ids[0]
    is_trainer = bind.execute(
        sa.text(
            """
            select exists (
                select 1
                from users
                where id = :owner_id
                  and role = 'trainer'
            )
            """
        ),
        {"owner_id": owner_id},
    ).scalar_one()
    if not is_trainer:
        raise RuntimeError(f"{LEGACY_OWNER_ENV} must identify an existing trainer account.")
    return owner_id


def _repair_campaigns(bind: sa.Connection, owner_id: UUID) -> int:
    repaired_count = _ownerless_campaign_count(bind)
    if repaired_count == 0:
        return 0

    bind.execute(
        sa.text(
            """
            update campaigns
            set owner_id = :owner_id
            where owner_id is null
            """
        ),
        {"owner_id": owner_id},
    )
    bind.execute(
        sa.text(
            """
            update email_sends send
            set owner_id = campaign.owner_id
            from campaigns campaign
            where send.campaign_id = campaign.id
              and send.owner_id is null
            """
        )
    )
    return repaired_count


def _repair_contacts(bind: sa.Connection, owner_id: UUID) -> tuple[int, int]:
    conflict_count = int(
        bind.execute(
            sa.text(
                """
                select count(*)
                from campaign_recipients legacy
                join campaign_recipients owned
                  on owned.owner_id = :owner_id
                 and owned.email is not null
                 and lower(owned.email) = lower(legacy.email)
                where legacy.owner_id is null
                  and legacy.email is not null
                """
            ),
            {"owner_id": owner_id},
        ).scalar_one()
    )

    bind.execute(
        sa.text(
            """
            create temporary table campaign_contact_owner_repair
            on commit drop
            as
            with eligible as (
                select
                    recipient.id,
                    recipient.owner_id,
                    recipient.email,
                    recipient.contact_name,
                    recipient.organization_name,
                    recipient.updated_at
                from campaign_recipients recipient
                where recipient.email is not null
                  and (
                      recipient.owner_id is null
                      or recipient.owner_id = :owner_id
                  )
            ),
            ranked as (
                select
                    eligible.id,
                    eligible.owner_id,
                    first_value(eligible.id) over (
                        partition by lower(eligible.email)
                        order by
                            case when eligible.owner_id = :owner_id then 0 else 1 end,
                            case when eligible.contact_name is not null then 0 else 1 end,
                            case when eligible.organization_name is not null then 0 else 1 end,
                            eligible.updated_at desc,
                            eligible.id
                    ) as canonical_id
                from eligible
            )
            select
                ranked.id as duplicate_id,
                ranked.canonical_id,
                canonical.owner_id = :owner_id as matched_existing_owner
            from ranked
            join campaign_recipients canonical on canonical.id = ranked.canonical_id
            where ranked.owner_id is null
            """
        ),
        {"owner_id": owner_id},
    )

    bind.execute(
        sa.text(
            """
            update campaign_recipients canonical
            set
                contact_name = coalesce(canonical.contact_name, merged.contact_name),
                organization_name = coalesce(
                    canonical.organization_name,
                    merged.organization_name
                ),
                source = coalesce(canonical.source, merged.source),
                status = merged.status::campaignrecipientstatus,
                updated_at = greatest(canonical.updated_at, merged.updated_at)
            from (
                with member_ids as (
                    select canonical_id, duplicate_id as member_id
                    from campaign_contact_owner_repair

                    union

                    select canonical_id, canonical_id as member_id
                    from campaign_contact_owner_repair
                )
                select
                    member_ids.canonical_id,
                    max(recipient.contact_name) filter (
                        where recipient.contact_name is not null
                    ) as contact_name,
                    max(recipient.organization_name) filter (
                        where recipient.organization_name is not null
                    ) as organization_name,
                    max(recipient.source) filter (
                        where recipient.source is not null
                    ) as source,
                    case
                        when bool_or(recipient.status = 'unsubscribed')
                            then 'unsubscribed'
                        when bool_or(recipient.status = 'suppressed')
                            then 'suppressed'
                        else 'active'
                    end as status,
                    max(recipient.updated_at) as updated_at
                from member_ids
                join campaign_recipients recipient
                  on recipient.id = member_ids.member_id
                group by member_ids.canonical_id
            ) merged
            where canonical.id = merged.canonical_id
            """
        )
    )

    bind.execute(
        sa.text(
            """
            insert into campaign_recipient_memberships (
                id,
                campaign_id,
                recipient_id,
                source,
                created_at,
                updated_at
            )
            select
                gen_random_uuid(),
                membership.campaign_id,
                mapping.canonical_id,
                membership.source,
                membership.created_at,
                membership.updated_at
            from campaign_recipient_memberships membership
            join campaign_contact_owner_repair mapping
              on mapping.duplicate_id = membership.recipient_id
            where mapping.duplicate_id <> mapping.canonical_id
            on conflict (campaign_id, recipient_id) do nothing
            """
        )
    )
    bind.execute(
        sa.text(
            """
            delete from campaign_recipient_memberships membership
            using campaign_contact_owner_repair mapping
            where membership.recipient_id = mapping.duplicate_id
              and mapping.duplicate_id <> mapping.canonical_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            update email_sends send
            set campaign_recipient_id = mapping.canonical_id
            from campaign_contact_owner_repair mapping
            where send.campaign_recipient_id = mapping.duplicate_id
              and mapping.duplicate_id <> mapping.canonical_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            update campaign_recipient_events event
            set recipient_id = mapping.canonical_id
            from campaign_contact_owner_repair mapping
            where event.recipient_id = mapping.duplicate_id
              and mapping.duplicate_id <> mapping.canonical_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            delete from campaign_recipients recipient
            using campaign_contact_owner_repair mapping
            where recipient.id = mapping.duplicate_id
              and mapping.duplicate_id <> mapping.canonical_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            update campaign_recipients
            set
                owner_id = :owner_id,
                email = lower(email),
                updated_at = now()
            where owner_id is null
            """
        ),
        {"owner_id": owner_id},
    )
    bind.execute(
        sa.text(
            """
            update email_sends send
            set owner_id = recipient.owner_id
            from campaign_recipients recipient
            where send.campaign_recipient_id = recipient.id
              and send.owner_id is null
            """
        )
    )
    repaired_count = int(
        bind.execute(sa.text("select count(*) from campaign_contact_owner_repair")).scalar_one()
    )
    return repaired_count, conflict_count


def _repair_suppression_owners(bind: sa.Connection) -> int:
    mismatch_count = int(
        bind.execute(
            sa.text(
                """
                select count(*)
                from email_suppressions suppression
                join email_sends send on send.id = suppression.source_email_send_id
                where send.owner_id is not null
                  and suppression.owner_id <> send.owner_id
                """
            )
        ).scalar_one()
    )
    if mismatch_count == 0:
        bind.execute(sa.text("update email_suppressions set email = lower(email)"))
        return 0

    bind.execute(
        sa.text(
            """
            insert into email_suppressions (
                id,
                owner_id,
                email,
                reason,
                source_email_send_id,
                created_at,
                updated_at
            )
            select
                gen_random_uuid(),
                send.owner_id,
                lower(suppression.email),
                suppression.reason,
                suppression.source_email_send_id,
                suppression.created_at,
                suppression.updated_at
            from email_suppressions suppression
            join email_sends send on send.id = suppression.source_email_send_id
            where send.owner_id is not null
              and suppression.owner_id <> send.owner_id
            on conflict do nothing
            """
        )
    )
    bind.execute(
        sa.text(
            """
            update email_suppressions target
            set
                reason = case
                    when target.reason = 'unsubscribed'
                      or source.reason = 'unsubscribed'
                        then 'unsubscribed'
                    when target.reason in ('spam', 'hard_bounce', 'blocked', 'invalid_email')
                        then target.reason
                    else source.reason
                end,
                source_email_send_id = coalesce(
                    target.source_email_send_id,
                    source.source_email_send_id
                ),
                updated_at = greatest(target.updated_at, source.updated_at)
            from email_suppressions source
            join email_sends send on send.id = source.source_email_send_id
            where send.owner_id is not null
              and source.owner_id <> send.owner_id
              and target.owner_id = send.owner_id
              and lower(target.email) = lower(source.email)
              and target.id <> source.id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            delete from email_suppressions suppression
            using email_sends send
            where send.id = suppression.source_email_send_id
              and send.owner_id is not null
              and suppression.owner_id <> send.owner_id
            """
        )
    )
    bind.execute(sa.text("update email_suppressions set email = lower(email)"))
    return mismatch_count


def _validate_repair(bind: sa.Connection) -> None:
    bind.execute(
        sa.text(
            """
            do $$
            declare
                ownerless_campaigns integer;
                ownerless_contacts integer;
                cross_owner_memberships integer;
                cross_owner_sends integer;
                suppression_owner_mismatches integer;
            begin
                select count(*) into ownerless_campaigns
                from campaigns
                where owner_id is null;

                select count(*) into ownerless_contacts
                from campaign_recipients
                where owner_id is null;

                select count(*) into cross_owner_memberships
                from campaign_recipient_memberships membership
                join campaigns campaign on campaign.id = membership.campaign_id
                join campaign_recipients recipient
                  on recipient.id = membership.recipient_id
                where campaign.owner_id is null
                   or campaign.owner_id <> recipient.owner_id;

                select count(*) into cross_owner_sends
                from email_sends send
                join campaigns campaign on campaign.id = send.campaign_id
                join campaign_recipients recipient
                  on recipient.id = send.campaign_recipient_id
                where send.owner_id is null
                   or campaign.owner_id is null
                   or send.owner_id <> campaign.owner_id
                   or send.owner_id <> recipient.owner_id;

                select count(*) into suppression_owner_mismatches
                from email_suppressions suppression
                join email_sends send on send.id = suppression.source_email_send_id
                where send.owner_id is not null
                  and suppression.owner_id <> send.owner_id;

                if ownerless_campaigns <> 0
                   or ownerless_contacts <> 0
                   or cross_owner_memberships <> 0
                   or cross_owner_sends <> 0
                   or suppression_owner_mismatches <> 0 then
                    raise exception
                        'campaign contact ownership repair failed: '
                        'campaigns %, contacts %, memberships %, sends %, '
                        'suppressions %',
                        ownerless_campaigns,
                        ownerless_contacts,
                        cross_owner_memberships,
                        cross_owner_sends,
                        suppression_owner_mismatches;
                end if;
            end
            $$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    ownerless_before = _ownerless_count(bind)
    ownerless_campaigns_before = _ownerless_campaign_count(bind)
    LOGGER.info(
        "Campaign ownership dry run: %s ownerless campaigns, %s ownerless contacts.",
        ownerless_campaigns_before,
        ownerless_before,
    )

    repaired_campaigns = 0
    repaired_count = 0
    conflict_count = 0
    owner_id: UUID | None = None
    if ownerless_before or ownerless_campaigns_before:
        owner_id = _resolve_legacy_owner_id(bind)
        repaired_campaigns = _repair_campaigns(bind, owner_id)
    if ownerless_before:
        if owner_id is None:  # pragma: no cover - guarded by the branch above
            raise RuntimeError("Legacy contact owner resolution unexpectedly failed.")
        repaired_count, conflict_count = _repair_contacts(bind, owner_id)

    suppression_repairs = _repair_suppression_owners(bind)
    _validate_repair(bind)

    op.drop_constraint(
        "fk_campaign_recipients_owner_id_users",
        "campaign_recipients",
        type_="foreignkey",
    )
    op.alter_column(
        "campaign_recipients",
        "owner_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_campaign_recipients_owner_id_users",
        "campaign_recipients",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    LOGGER.info(
        "Campaign ownership repaired: owner=%s, campaigns=%s, contacts=%s, "
        "mapped=%s, matching-email conflicts=%s, suppression owners=%s, "
        "remaining contacts=%s.",
        owner_id,
        repaired_campaigns,
        ownerless_before,
        repaired_count,
        conflict_count,
        suppression_repairs,
        _ownerless_count(bind),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Cannot safely undo campaign contact ownership repair after contact "
        "consolidation and history rewiring."
    )
