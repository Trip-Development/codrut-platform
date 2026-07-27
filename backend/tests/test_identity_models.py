from sqlalchemy import BigInteger, CheckConstraint, UniqueConstraint

from codrut.core.database import Base
from codrut.modules.identity.models import AVATAR_PALETTE_SPACE


def test_user_avatar_palette_is_persisted_and_unique() -> None:
    table = Base.metadata.tables["users"]
    column = table.columns["avatar_palette_key"]
    unique_columns = {
        tuple(item.name for item in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    checks = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert isinstance(column.type, BigInteger)
    assert column.nullable is False
    assert column.server_default is not None
    assert "user_avatar_palette_key_seq" in str(column.server_default.arg)
    assert ("avatar_palette_key",) in unique_columns
    assert "ck_users_user_avatar_palette_key_range" in checks
    assert AVATAR_PALETTE_SPACE == 360 * 68 * 54 * 42
