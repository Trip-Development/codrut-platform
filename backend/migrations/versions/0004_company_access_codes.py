"""create company access codes

Revision ID: 0004_company_access_codes
Revises: 0003_participant_reports_to_name
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_company_access_codes"
down_revision: str | None = "0003_participant_reports_to_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_access_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_access_codes_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_access_codes")),
    )
    op.create_index(
        op.f("ix_company_access_codes_code_hash"),
        "company_access_codes",
        ["code_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_company_access_codes_company_id"),
        "company_access_codes",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_company_access_codes_company_id"), table_name="company_access_codes")
    op.drop_index(op.f("ix_company_access_codes_code_hash"), table_name="company_access_codes")
    op.drop_table("company_access_codes")
