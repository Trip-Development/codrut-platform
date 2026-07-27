"""persist unique user avatar palettes

Revision ID: 0049_user_avatar_palettes
Revises: 0048_project_recycle_bin
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_user_avatar_palettes"
down_revision: str | None = "0048_project_recycle_bin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AVATAR_PALETTE_SPACE = 55_520_640
AVATAR_PALETTE_DEFAULT = (
    "mod(nextval('user_avatar_palette_key_seq') * 16777619 + 2166136261, 55520640)"
)


def upgrade() -> None:
    op.execute(
        sa.text(
            "CREATE SEQUENCE user_avatar_palette_key_seq "
            f"START WITH 1 MINVALUE 1 MAXVALUE {AVATAR_PALETTE_SPACE} NO CYCLE"
        )
    )
    op.add_column(
        "users",
        sa.Column("avatar_palette_key", sa.BigInteger(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE users SET avatar_palette_key = "
            "mod(nextval('user_avatar_palette_key_seq') * 16777619 + 2166136261, 55520640) "
            "WHERE avatar_palette_key IS NULL"
        )
    )
    op.alter_column(
        "users",
        "avatar_palette_key",
        existing_type=sa.BigInteger(),
        nullable=False,
        server_default=sa.text(AVATAR_PALETTE_DEFAULT),
    )
    op.execute(
        sa.text(
            "ALTER SEQUENCE user_avatar_palette_key_seq "
            "OWNED BY users.avatar_palette_key"
        )
    )
    op.create_unique_constraint(
        op.f("uq_users_avatar_palette_key"),
        "users",
        ["avatar_palette_key"],
    )
    op.create_check_constraint(
        op.f("ck_users_user_avatar_palette_key_range"),
        "users",
        f"avatar_palette_key >= 0 and avatar_palette_key < {AVATAR_PALETTE_SPACE}",
    )


def downgrade() -> None:
    op.execute(
        sa.text("ALTER SEQUENCE user_avatar_palette_key_seq OWNED BY NONE")
    )
    op.drop_constraint(
        op.f("ck_users_user_avatar_palette_key_range"),
        "users",
        type_="check",
    )
    op.drop_constraint(
        op.f("uq_users_avatar_palette_key"),
        "users",
        type_="unique",
    )
    op.drop_column("users", "avatar_palette_key")
    op.execute(sa.text("DROP SEQUENCE user_avatar_palette_key_seq"))
