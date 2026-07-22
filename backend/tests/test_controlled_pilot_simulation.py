import pytest

from codrut.core.config import Settings
from codrut.tools.simulate_controlled_pilot import (
    SIMULATION_ACKNOWLEDGEMENT,
    SimulationEmailProvider,
    require_simulation_database,
)


def test_simulation_guard_accepts_only_explicit_synthetic_database() -> None:
    settings = Settings(
        _env_file=None,
        env="development",
        database_url="postgresql+asyncpg://codrut:codrut@db:5432/codrut_pilot_simulation",
    )

    assert (
        require_simulation_database(settings, SIMULATION_ACKNOWLEDGEMENT)
        == "codrut_pilot_simulation"
    )


@pytest.mark.parametrize(
    ("settings", "acknowledgement", "message"),
    [
        (
            Settings.model_construct(
                env="production",
                local_auth_bypass=False,
                database_url="postgresql+asyncpg://codrut:codrut@db:5432/codrut_pilot_simulation",
            ),
            SIMULATION_ACKNOWLEDGEMENT,
            "cannot run in production",
        ),
        (
            Settings(
                _env_file=None,
                env="development",
                database_url="postgresql+asyncpg://codrut:codrut@db:5432/codrut",
            ),
            SIMULATION_ACKNOWLEDGEMENT,
            "must end with",
        ),
        (
            Settings(
                _env_file=None,
                env="development",
                database_url="postgresql+asyncpg://codrut:codrut@db:5432/codrut_pilot_simulation",
            ),
            None,
            "exact synthetic-only acknowledgement",
        ),
    ],
)
def test_simulation_guard_rejects_unsafe_targets(
    settings: Settings,
    acknowledgement: str | None,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        require_simulation_database(settings, acknowledgement)


async def test_simulation_provider_recovers_after_one_transient_failure() -> None:
    from codrut.contracts.emails import EmailAddress, EmailDeliveryStatus, EmailMessage

    email = "pilot-sim@example.com"
    provider = SimulationEmailProvider(fail_once={email})
    message = EmailMessage(
        to=EmailAddress(email),
        subject="Synthetic",
        html_body="<p>Synthetic</p>",
        text_body="Synthetic",
    )

    first = await provider.send(message)
    second = await provider.send(message)

    assert first.status == EmailDeliveryStatus.failed
    assert second.status == EmailDeliveryStatus.accepted
    assert len(provider.accepted_messages) == 1
