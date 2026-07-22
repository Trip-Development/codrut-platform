"""isolate campaign contacts by owner

Revision ID: 0035_contact_owner_isolation
Revises: 0034_invite_session_link
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035_contact_owner_isolation"
down_revision: str | None = "0034_invite_session_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_campaign_recipients_email",
        "campaign_recipients",
        type_="unique",
    )

    # Preserve cross-owner campaign history by creating an owner-local contact
    # before tenant-scoped reads stop exposing the shared source contact.
    op.execute(
        """
        create temporary table campaign_recipient_owner_clones
        on commit drop
        as
        with owner_pairs as (
            select distinct
                membership.recipient_id as source_recipient_id,
                campaign.owner_id as target_owner_id
            from campaign_recipient_memberships membership
            join campaigns campaign on campaign.id = membership.campaign_id
            join campaign_recipients recipient on recipient.id = membership.recipient_id
            where campaign.owner_id is not null
              and recipient.owner_id is distinct from campaign.owner_id

            union

            select distinct
                send.campaign_recipient_id as source_recipient_id,
                campaign.owner_id as target_owner_id
            from email_sends send
            join campaigns campaign on campaign.id = send.campaign_id
            join campaign_recipients recipient on recipient.id = send.campaign_recipient_id
            where send.campaign_recipient_id is not null
              and campaign.owner_id is not null
              and recipient.owner_id is distinct from campaign.owner_id
        )
        select
            source_recipient_id,
            target_owner_id,
            gen_random_uuid() as clone_recipient_id
        from owner_pairs
        """
    )
    op.execute(
        """
        insert into campaign_recipients (
            id,
            owner_id,
            email,
            contact_name,
            organization_name,
            segment,
            source,
            status,
            created_at,
            updated_at
        )
        select
            clone.clone_recipient_id,
            clone.target_owner_id,
            source.email,
            source.contact_name,
            source.organization_name,
            source.segment,
            source.source,
            source.status,
            source.created_at,
            source.updated_at
        from campaign_recipient_owner_clones clone
        join campaign_recipients source on source.id = clone.source_recipient_id
        """
    )
    op.execute(
        """
        insert into campaign_recipient_events (
            id,
            recipient_id,
            event_type,
            variant_key,
            occurred_at,
            created_at,
            updated_at
        )
        select
            gen_random_uuid(),
            clone.clone_recipient_id,
            event.event_type,
            event.variant_key,
            event.occurred_at,
            event.created_at,
            event.updated_at
        from campaign_recipient_owner_clones clone
        join campaign_recipient_events event
          on event.recipient_id = clone.source_recipient_id
        """
    )
    op.execute(
        """
        update campaign_recipient_memberships membership
        set recipient_id = clone.clone_recipient_id
        from campaigns campaign, campaign_recipient_owner_clones clone
        where campaign.id = membership.campaign_id
          and clone.source_recipient_id = membership.recipient_id
          and clone.target_owner_id = campaign.owner_id
        """
    )
    op.execute(
        """
        update email_sends send
        set campaign_recipient_id = clone.clone_recipient_id
        from campaigns campaign, campaign_recipient_owner_clones clone
        where campaign.id = send.campaign_id
          and clone.source_recipient_id = send.campaign_recipient_id
          and clone.target_owner_id = campaign.owner_id
        """
    )

    # The old constraint was case-sensitive. Merge only contacts that collide
    # within one owner after normalization, retaining suppression state and data.
    op.execute(
        """
        create temporary table campaign_recipient_deduplication
        on commit drop
        as
        select
            recipient.id as duplicate_recipient_id,
            first_value(recipient.id) over (
                partition by recipient.owner_id, lower(recipient.email)
                order by
                    (recipient.contact_name is not null) desc,
                    (recipient.organization_name is not null) desc,
                    recipient.updated_at desc,
                    recipient.id
            ) as canonical_recipient_id
        from campaign_recipients recipient
        where recipient.email is not null
        """
    )
    op.execute(
        """
        update campaign_recipients canonical
        set
            contact_name = coalesce(canonical.contact_name, merged.contact_name),
            organization_name = coalesce(
                canonical.organization_name,
                merged.organization_name
            ),
            source = coalesce(canonical.source, merged.source),
            status = merged.status
        from (
            select
                mapping.canonical_recipient_id,
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
                    when bool_or(recipient.status = 'unsubscribed') then 'unsubscribed'
                    when bool_or(recipient.status = 'suppressed') then 'suppressed'
                    else 'active'
                end::campaignrecipientstatus as status
            from campaign_recipient_deduplication mapping
            join campaign_recipients recipient
              on recipient.id = mapping.duplicate_recipient_id
            group by mapping.canonical_recipient_id
        ) merged
        where canonical.id = merged.canonical_recipient_id
        """
    )
    op.execute(
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
            mapping.canonical_recipient_id,
            membership.source,
            membership.created_at,
            membership.updated_at
        from campaign_recipient_memberships membership
        join campaign_recipient_deduplication mapping
          on mapping.duplicate_recipient_id = membership.recipient_id
        where mapping.duplicate_recipient_id <> mapping.canonical_recipient_id
        on conflict (campaign_id, recipient_id) do nothing
        """
    )
    op.execute(
        """
        delete from campaign_recipient_memberships membership
        using campaign_recipient_deduplication mapping
        where membership.recipient_id = mapping.duplicate_recipient_id
          and mapping.duplicate_recipient_id <> mapping.canonical_recipient_id
        """
    )
    op.execute(
        """
        update email_sends send
        set campaign_recipient_id = mapping.canonical_recipient_id
        from campaign_recipient_deduplication mapping
        where send.campaign_recipient_id = mapping.duplicate_recipient_id
          and mapping.duplicate_recipient_id <> mapping.canonical_recipient_id
        """
    )
    op.execute(
        """
        update campaign_recipient_events event
        set recipient_id = mapping.canonical_recipient_id
        from campaign_recipient_deduplication mapping
        where event.recipient_id = mapping.duplicate_recipient_id
          and mapping.duplicate_recipient_id <> mapping.canonical_recipient_id
        """
    )
    op.execute(
        """
        delete from campaign_recipients recipient
        using campaign_recipient_deduplication mapping
        where recipient.id = mapping.duplicate_recipient_id
          and mapping.duplicate_recipient_id <> mapping.canonical_recipient_id
        """
    )
    op.execute(
        """
        update campaign_recipients
        set email = lower(email)
        where email is not null
          and email <> lower(email)
        """
    )
    op.create_index(
        "uq_campaign_recipients_owner_normalized_email",
        "campaign_recipients",
        ["owner_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email is not null"),
    )


def downgrade() -> None:
    duplicate_email = op.get_bind().execute(
        sa.text(
            """
            select lower(email)
            from campaign_recipients
            where email is not null
            group by lower(email)
            having count(*) > 1
            limit 1
            """
        )
    ).scalar_one_or_none()
    if duplicate_email is not None:
        raise RuntimeError(
            "Cannot restore global campaign contact email uniqueness while "
            "multiple owners use the same normalized email."
        )

    op.drop_index(
        "uq_campaign_recipients_owner_normalized_email",
        table_name="campaign_recipients",
    )
    op.create_unique_constraint(
        "uq_campaign_recipients_email",
        "campaign_recipients",
        ["email"],
    )
