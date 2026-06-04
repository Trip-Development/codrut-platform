"""create_scoring_results

Revision ID: 4102edafb8c7
Revises: 0011_campaign_templates
Create Date: 2026-06-04 10:24:32.559840
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

revision: str = '4102edafb8c7'
down_revision: str | None = '0011_campaign_templates'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('scoring_results',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('assignment_id', sa.Uuid(), nullable=False),
    sa.Column('scores', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('primary_result', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assignment_id'], ['questionnaire_assignments.id'], name=op.f('fk_scoring_results_assignment_id_questionnaire_assignments'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_scoring_results')),
    sa.UniqueConstraint('assignment_id', name='uq_scoring_results_assignment_id')
    )
    op.create_index(op.f('ix_scoring_results_assignment_id'), 'scoring_results', ['assignment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scoring_results_assignment_id'), table_name='scoring_results')
    op.drop_table('scoring_results')
