"""add explicit guest and registered account types

Revision ID: 0050_identity_account_types
Revises: 0049_user_avatar_palettes
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0050_identity_account_types"
down_revision: str | None = "0049_user_avatar_palettes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

account_type = sa.Enum("guest", "registered", name="useraccounttype")


def upgrade() -> None:
    account_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "account_type",
            account_type,
            server_default="registered",
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET account_type = 'guest'
            WHERE password_hash = 'shadow_account_no_password'
            """
        )
    )
    op.drop_constraint(
        op.f(
            "ck_participant_account_link_audits_participant_account_link_audit_action"
        ),
        "participant_account_link_audits",
        type_="check",
    )
    op.create_check_constraint(
        op.f(
            "ck_participant_account_link_audits_participant_account_link_audit_action"
        ),
        "participant_account_link_audits",
        "action in "
        "('link_matching_email', 'unlink', 'invite_claim', 'registration_claim')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f(
            "ck_participant_account_link_audits_participant_account_link_audit_action"
        ),
        "participant_account_link_audits",
        type_="check",
    )
    op.create_check_constraint(
        op.f(
            "ck_participant_account_link_audits_participant_account_link_audit_action"
        ),
        "participant_account_link_audits",
        "action in ('link_matching_email', 'unlink')",
    )
    op.drop_column("users", "account_type")
    account_type.drop(op.get_bind(), checkfirst=True)
