import uuid
from collections.abc import Callable

import pytest

from codrut.core.config import get_settings
from codrut.modules.forms.models import QuestionnaireDefinition


@pytest.fixture(autouse=True)
def isolate_local_auth_bypass(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CODRUT_LOCAL_AUTH_BYPASS", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    from codrut.core.database import engine

    await engine.dispose()


@pytest.fixture
def questionnaire_definition_factory() -> Callable[[str], QuestionnaireDefinition]:
    def build(key: str) -> QuestionnaireDefinition:
        version = 10_000 + int.from_bytes(uuid.uuid4().bytes[:4], "big") % 1_000_000_000
        return QuestionnaireDefinition(
            id=uuid.uuid4(),
            key=key,
            version=version,
            title=f"Synthetic {key}",
            description="Synthetic test definition.",
            schema={
                "key": key,
                "version": version,
                "title": f"Synthetic {key}",
                "audience": "participant",
                "sections": [],
            },
            feedback_policy={},
            trainer_visibility_policy={"raw_responses": "hidden"},
            content_checksum=uuid.uuid4().hex * 2,
            active=True,
        )

    return build
