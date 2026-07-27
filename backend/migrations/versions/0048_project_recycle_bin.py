"""add recoverable project lifecycle

Revision ID: 0048_project_recycle_bin
Revises: 0047_account_link_audit
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0048_project_recycle_bin"
down_revision: str | None = "0047_account_link_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    project_status = postgresql.ENUM(
        "draft",
        "active",
        "completed",
        "archived",
        name="companyprojectstatus",
        create_type=False,
    )
    op.add_column(
        "company_projects",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "company_projects",
        sa.Column("archived_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "company_projects",
        sa.Column("archived_from_status", project_status, nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_company_projects_archived_by_user_id_users"),
        "company_projects",
        "users",
        ["archived_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_company_projects_archived_by_user_id"),
        "company_projects",
        ["archived_by_user_id"],
    )

    op.create_table(
        "project_lifecycle_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        # No project FK: permanent deletion must not erase its own audit record.
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("next_status", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action in ('archived', 'restored', 'permanently_deleted')",
            name=op.f("ck_project_lifecycle_events_project_lifecycle_event_action"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_lifecycle_events")),
    )
    for column_name in ("company_id", "project_id", "actor_user_id"):
        op.create_index(
            op.f(f"ix_project_lifecycle_events_{column_name}"),
            "project_lifecycle_events",
            [column_name],
        )


def downgrade() -> None:
    op.drop_table("project_lifecycle_events")
    op.drop_index(
        op.f("ix_company_projects_archived_by_user_id"),
        table_name="company_projects",
    )
    op.drop_constraint(
        op.f("fk_company_projects_archived_by_user_id_users"),
        "company_projects",
        type_="foreignkey",
    )
    op.drop_column("company_projects", "archived_from_status")
    op.drop_column("company_projects", "archived_by_user_id")
    op.drop_column("company_projects", "archived_at")
