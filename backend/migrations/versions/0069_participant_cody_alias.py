"""participant_profiles: codul cu care Cody il stie pe om (`Fox 34`)

Plicul 138. Hotararea lui Andrei, 23 septembrie: spre Google pleaca un cod, nu un nume. Campul e
separat de `anonymous_name` (chestionarele), gol la toata lumea pana la prima sedinta de exersare,
si unic in toata aplicatia.

Revision ID: 0069_participant_cody_alias
Revises: 0068_practice_missing_indexes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0069_participant_cody_alias"
down_revision = "0068_practice_missing_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "participant_profiles",
        sa.Column("cody_alias", sa.String(length=20), nullable=True),
    )
    op.create_unique_constraint(
        "uq_participant_profiles_cody_alias", "participant_profiles", ["cody_alias"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_participant_profiles_cody_alias", "participant_profiles", type_="unique"
    )
    op.drop_column("participant_profiles", "cody_alias")
