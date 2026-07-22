"""add protected content metadata and pin questionnaire assignments

Revision ID: 0037_protected_content_boundary
Revises: 0036_email_send_payload_lease
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037_protected_content_boundary"
down_revision: str | None = "0036_email_send_payload_lease"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questionnaire_definitions",
        sa.Column("private_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "questionnaire_definitions",
        sa.Column(
            "feedback_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "questionnaire_definitions",
        sa.Column(
            "trainer_visibility_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "questionnaire_definitions",
        sa.Column("package_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "questionnaire_definitions",
        sa.Column("content_checksum", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "questionnaire_definitions",
        sa.Column(
            "system_managed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "protected_content_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.String(length=160), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("questionnaire_count", sa.Integer(), nullable=False),
        sa.Column("template_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_id"),
    )

    op.add_column(
        "email_templates",
        sa.Column("package_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "email_templates",
        sa.Column("content_checksum", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "email_templates",
        sa.Column(
            "system_managed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "questionnaire_assignments",
        sa.Column("questionnaire_definition_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_questionnaire_assignments_questionnaire_definition_id"),
        "questionnaire_assignments",
        ["questionnaire_definition_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_questionnaire_assignments_definition",
        "questionnaire_assignments",
        "questionnaire_definitions",
        ["questionnaire_definition_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Pin rows with a response to the exact definition version used for that response.
    op.execute(
        sa.text(
            """
            UPDATE questionnaire_assignments assignment
            SET questionnaire_definition_id = definition.id
            FROM questionnaire_responses response
            JOIN questionnaire_definitions definition
              ON definition.key = response.questionnaire_key
             AND definition.version = response.questionnaire_version
            WHERE response.assignment_id = assignment.id
              AND response.questionnaire_key = assignment.questionnaire_key
              AND assignment.questionnaire_definition_id IS NULL
            """
        )
    )

    # The previous application resolved unanswered assignments through the key's
    # single active definition. Freeze that existing behavior while retaining all
    # historical versions for assignments whose responses identify an exact version.
    op.execute(
        sa.text(
            """
            WITH unique_active_definitions AS (
                SELECT key, min(id::text)::uuid AS definition_id
                FROM questionnaire_definitions
                WHERE active IS TRUE
                GROUP BY key
                HAVING count(*) = 1
            )
            UPDATE questionnaire_assignments assignment
            SET questionnaire_definition_id = unique_active_definitions.definition_id
            FROM unique_active_definitions
            WHERE assignment.questionnaire_key = unique_active_definitions.key
              AND assignment.questionnaire_definition_id IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM questionnaire_responses response
                  WHERE response.assignment_id = assignment.id
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                unresolved_count bigint;
                sample_assignment uuid;
            BEGIN
                SELECT count(*), min(id::text)::uuid
                INTO unresolved_count, sample_assignment
                FROM questionnaire_assignments
                WHERE questionnaire_definition_id IS NULL;

                IF unresolved_count > 0 THEN
                    RAISE EXCEPTION
                        'Cannot safely pin % legacy questionnaire assignments; sample assignment %',
                        unresolved_count,
                        sample_assignment;
                END IF;
            END
            $$
            """
        )
    )

    # The previous application version does not write questionnaire_definition_id.
    # Keep rolling deployment compatible while still rejecting an ambiguous active version.
    op.execute(
        sa.text(
            """
            CREATE FUNCTION pin_questionnaire_assignment_definition()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                pinned_definition_id uuid;
            BEGIN
                IF NEW.questionnaire_definition_id IS NULL THEN
                    SELECT min(id::text)::uuid
                    INTO pinned_definition_id
                    FROM questionnaire_definitions
                    WHERE key = NEW.questionnaire_key
                      AND active IS TRUE
                    HAVING count(*) = 1;

                    IF pinned_definition_id IS NULL THEN
                        RAISE EXCEPTION
                            'No unique active definition for questionnaire key %',
                            NEW.questionnaire_key;
                    END IF;
                    NEW.questionnaire_definition_id := pinned_definition_id;
                ELSIF NOT EXISTS (
                    SELECT 1
                    FROM questionnaire_definitions
                    WHERE id = NEW.questionnaire_definition_id
                      AND key = NEW.questionnaire_key
                ) THEN
                    RAISE EXCEPTION
                        'Pinned definition does not match questionnaire key %',
                        NEW.questionnaire_key;
                END IF;
                RETURN NEW;
            END
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_pin_questionnaire_assignment_definition
            BEFORE INSERT OR UPDATE OF questionnaire_key, questionnaire_definition_id
            ON questionnaire_assignments
            FOR EACH ROW
            EXECUTE FUNCTION pin_questionnaire_assignment_definition()
            """
        )
    )
    op.alter_column(
        "questionnaire_assignments",
        "questionnaire_definition_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_pin_questionnaire_assignment_definition "
            "ON questionnaire_assignments"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS pin_questionnaire_assignment_definition()"))
    op.drop_constraint(
        "fk_questionnaire_assignments_definition",
        "questionnaire_assignments",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_questionnaire_assignments_questionnaire_definition_id"),
        table_name="questionnaire_assignments",
    )
    op.drop_column("questionnaire_assignments", "questionnaire_definition_id")
    op.drop_column("email_templates", "system_managed")
    op.drop_column("email_templates", "content_checksum")
    op.drop_column("email_templates", "package_id")
    op.drop_table("protected_content_imports")
    op.drop_column("questionnaire_definitions", "system_managed")
    op.drop_column("questionnaire_definitions", "content_checksum")
    op.drop_column("questionnaire_definitions", "package_id")
    op.drop_column("questionnaire_definitions", "trainer_visibility_policy")
    op.drop_column("questionnaire_definitions", "feedback_policy")
    op.drop_column("questionnaire_definitions", "private_config")
