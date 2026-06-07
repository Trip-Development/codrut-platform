"""create company participant admin model

Revision ID: 0002_company_participant_admin
Revises: 0001_identity_sessions
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_company_participant_admin"
down_revision: str | None = "0001_identity_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


company_membership_role = postgresql.ENUM(
    "owner",
    "trainer",
    "participant",
    name="companymembershiprole",
    create_type=False,
)


def upgrade() -> None:
    company_membership_role.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        sa.UniqueConstraint("name", name=op.f("uq_companies_name")),
    )

    op.create_table(
        "company_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", company_membership_role, nullable=False),
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
            name=op.f("fk_company_memberships_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_company_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_memberships")),
        sa.UniqueConstraint(
            "company_id",
            "user_id",
            name=op.f("uq_company_memberships_company_id"),
        ),
    )
    op.create_index(
        op.f("ix_company_memberships_company_id"),
        "company_memberships",
        ["company_id"],
    )
    op.create_index(op.f("ix_company_memberships_user_id"), "company_memberships", ["user_id"])

    op.create_table(
        "participant_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("position", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("role_group", sa.String(length=255), nullable=True),
        sa.Column("pcm_profile", sa.String(length=255), nullable=True),
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
            name=op.f("fk_participant_profiles_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_participant_profiles_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_participant_profiles")),
        sa.UniqueConstraint(
            "company_id",
            "email",
            name=op.f("uq_participant_profiles_company_id"),
        ),
        sa.UniqueConstraint(
            "company_id",
            "id",
            name=op.f("uq_participant_profiles_company_id_id"),
        ),
        sa.UniqueConstraint("user_id", name=op.f("uq_participant_profiles_user_id")),
    )
    op.create_index(
        op.f("ix_participant_profiles_company_id"),
        "participant_profiles",
        ["company_id"],
    )
    op.create_index(op.f("ix_participant_profiles_user_id"), "participant_profiles", ["user_id"])

    op.create_table(
        "participant_reporting_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("participant_profile_id", sa.Uuid(), nullable=False),
        sa.Column("manager_profile_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "participant_profile_id <> manager_profile_id",
            name=op.f("ck_participant_reporting_relationships_participant_reporting_not_self"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_participant_reporting_relationships_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "manager_profile_id"],
            ["participant_profiles.company_id", "participant_profiles.id"],
            name=op.f("fk_participant_reporting_relationships_company_id_participant_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "participant_profile_id"],
            ["participant_profiles.company_id", "participant_profiles.id"],
            name=op.f(
                "fk_participant_reporting_relationships_company_id_participant_profile"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_participant_reporting_relationships")),
        sa.UniqueConstraint(
            "participant_profile_id",
            name=op.f("uq_participant_reporting_relationships_participant_profile_id"),
        ),
    )
    op.create_index(
        op.f("ix_participant_reporting_relationships_company_id"),
        "participant_reporting_relationships",
        ["company_id"],
    )
    op.create_index(
        op.f("ix_participant_reporting_relationships_manager_profile_id"),
        "participant_reporting_relationships",
        ["manager_profile_id"],
    )
    op.create_index(
        op.f("ix_participant_reporting_relationships_participant_profile_id"),
        "participant_reporting_relationships",
        ["participant_profile_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_participant_reporting_relationships_participant_profile_id"),
        table_name="participant_reporting_relationships",
    )
    op.drop_index(
        op.f("ix_participant_reporting_relationships_manager_profile_id"),
        table_name="participant_reporting_relationships",
    )
    op.drop_index(
        op.f("ix_participant_reporting_relationships_company_id"),
        table_name="participant_reporting_relationships",
    )
    op.drop_table("participant_reporting_relationships")
    op.drop_index(op.f("ix_participant_profiles_user_id"), table_name="participant_profiles")
    op.drop_index(op.f("ix_participant_profiles_company_id"), table_name="participant_profiles")
    op.drop_table("participant_profiles")
    op.drop_index(op.f("ix_company_memberships_user_id"), table_name="company_memberships")
    op.drop_index(op.f("ix_company_memberships_company_id"), table_name="company_memberships")
    op.drop_table("company_memberships")
    op.drop_table("companies")
    company_membership_role.drop(op.get_bind(), checkfirst=True)
