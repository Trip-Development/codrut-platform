"""practice_consents: acordul la prima intrare in exersare

Plicul 139. Niciun om nu vorbeste cu Cody pana nu a vazut si a bifat acordul. Se tine minte cine,
pe ce proiect, cand si pentru ce text (amprenta lui).

Revision ID: 0070_practice_consent
Revises: 0069_participant_cody_alias
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0070_practice_consent"
down_revision = "0069_participant_cody_alias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "practice_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["participant_profile_id"], ["participant_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["company_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "participant_profile_id", "project_id", "text_hash",
            name="uq_practice_consents_profile_project_text",
        ),
    )
    op.create_index(
        "ix_practice_consents_participant_profile_id", "practice_consents",
        ["participant_profile_id"],
    )
    op.create_index("ix_practice_consents_project_id", "practice_consents", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_practice_consents_project_id", table_name="practice_consents")
    op.drop_index("ix_practice_consents_participant_profile_id", table_name="practice_consents")
    op.drop_table("practice_consents")
