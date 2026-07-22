import pytest

from codrut.core.config import Settings
from codrut.core.database import build_database_engine


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("environment", "expected_hide_parameters"),
    [("development", False), ("production", True)],
)
async def test_database_engine_hides_parameters_only_in_production(
    environment: str,
    expected_hide_parameters: bool,
) -> None:
    settings = (
        Settings.model_construct(env=environment)
        if environment == "production"
        else Settings(env=environment)
    )
    engine = build_database_engine(settings)

    try:
        assert engine.sync_engine.hide_parameters is expected_hide_parameters
    finally:
        await engine.dispose()
