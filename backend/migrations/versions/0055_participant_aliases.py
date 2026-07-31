"""make participant aliases cryptographic and unique

Revision ID: 0055_participant_aliases
Revises: 0054_identity_consent_submission
Create Date: 2026-07-30
"""

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055_participant_aliases"
down_revision: str | None = "0054_identity_consent_submission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADJECTIVES = (
    "Albastru",
    "Calm",
    "Curajos",
    "Deschis",
    "Limpede",
    "Linistit",
    "Senin",
    "Statornic",
    "Verde",
    "Viu",
)
_TREES = (
    "Artar",
    "Brad",
    "Cedru",
    "Fag",
    "Frasin",
    "Mesteacan",
    "Pin",
    "Plop",
    "Salcie",
    "Stejar",
)
_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ALIAS_FUNCTION = "ensure_unique_participant_alias"
ALIAS_TRIGGER = "trg_participant_profiles_unique_alias"


def _crockford_suffix(value: int) -> str:
    characters: list[str] = []
    for _index in range(6):
        characters.append(_CROCKFORD_BASE32[value & 31])
        value >>= 5
    return "".join(reversed(characters))


def _replacement_alias(profile_id: str, attempt: int) -> str:
    digest = hashlib.blake2s(
        f"{profile_id}:{attempt}".encode(),
        digest_size=8,
    ).digest()
    suffix_value = int.from_bytes(digest[:4], "big") % (32**6)
    return (
        f"{_TREES[digest[4] % len(_TREES)]}-"
        f"{_ADJECTIVES[digest[5] % len(_ADJECTIVES)]}-"
        f"{_crockford_suffix(suffix_value)}"
    )


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, anonymous_name
            FROM participant_profiles
            WHERE anonymous_name IS NOT NULL
            ORDER BY created_at, id
            """
        )
    ).mappings()
    used_names: set[str] = set()
    for row in rows:
        current_name = str(row["anonymous_name"])
        if current_name not in used_names:
            used_names.add(current_name)
            continue

        profile_id = str(row["id"])
        for attempt in range(4096):
            replacement = _replacement_alias(profile_id, attempt)
            if replacement in used_names:
                continue
            bind.execute(
                sa.text(
                    """
                    UPDATE participant_profiles
                    SET anonymous_name = :anonymous_name
                    WHERE id = :profile_id
                    """
                ),
                {
                    "anonymous_name": replacement,
                    "profile_id": row["id"],
                },
            )
            used_names.add(replacement)
            break
        else:
            raise RuntimeError("Could not backfill a unique participant alias.")

    # The previous rollback image uses a much smaller collision-unaware alias
    # pool. Keep it safe against the new uniqueness contract by deterministically
    # widening only colliding writes during the rollback window.
    op.execute(
        """
        create or replace function ensure_unique_participant_alias()
        returns trigger
        language plpgsql
        as $$
        declare
            alias_base text;
            alias_attempt integer := 0;
            alias_candidate text;
        begin
            if new.anonymous_name is null then
                return new;
            end if;

            -- The retained rollback image checks no uniqueness itself. Serialize
            -- identical legacy candidates so concurrent writes cannot both pass
            -- the existence check and then race on the unique constraint.
            perform pg_advisory_xact_lock(
                hashtextextended(new.anonymous_name, 0)
            );
            if not exists (
                select 1
                from participant_profiles existing
                where existing.anonymous_name = new.anonymous_name
                  and existing.id is distinct from new.id
            ) then
                return new;
            end if;

            alias_base := left(new.anonymous_name, 66);
            loop
                alias_candidate := alias_base || '-' ||
                    upper(substr(md5(new.id::text || ':' || alias_attempt::text), 1, 12));
                exit when not exists (
                    select 1
                    from participant_profiles existing
                    where existing.anonymous_name = alias_candidate
                      and existing.id is distinct from new.id
                );
                alias_attempt := alias_attempt + 1;
                if alias_attempt >= 4096 then
                    raise exception 'Could not allocate a unique participant alias';
                end if;
            end loop;
            new.anonymous_name := alias_candidate;
            return new;
        end;
        $$
        """
    )
    op.execute(
        """
        create trigger trg_participant_profiles_unique_alias
        before insert or update of anonymous_name on participant_profiles
        for each row execute function ensure_unique_participant_alias()
        """
    )
    op.create_unique_constraint(
        "uq_participant_profiles_anonymous_name",
        "participant_profiles",
        ["anonymous_name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_participant_profiles_anonymous_name",
        "participant_profiles",
        type_="unique",
    )
    op.execute(f"drop trigger if exists {ALIAS_TRIGGER} on participant_profiles")
    op.execute(f"drop function if exists {ALIAS_FUNCTION}()")
