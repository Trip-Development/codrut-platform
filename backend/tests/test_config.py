import pytest
from pydantic import SecretStr, ValidationError

from codrut.core.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "env": "production",
        "session_secret": SecretStr("session-secret-with-at-least-32-characters"),
        "task_link_secret": SecretStr("task-link-secret-with-at-least-32-characters"),
        "campaign_asset_signing_secret": SecretStr(
            "campaign-asset-secret-with-at-least-32-characters"
        ),
        "cors_origins": ["https://codrut.example.com"],
        "public_app_url": "https://codrut.example.com",
        "email_provider": "brevo",
        "email_from_address": "no-reply@codrut.ro",
        "email_from_name": "Cody",
        "email_brevo_api_key": SecretStr("brevo-api-key"),
        "email_webhook_token": SecretStr(
            "brevo-webhook-token-with-at-least-32-characters"
        ),
        "email_suppression_fingerprint_secret": SecretStr(
            "suppression-fingerprint-secret-at-least-32-characters"
        ),
    }
    values.update(overrides)
    return Settings(**values)


def test_cors_origins_accept_json_array_env_format() -> None:
    settings = Settings(cors_origins='["https://codrut.andreivacaru.ro","https://codrut.ro"]')

    assert settings.cors_origins == ["https://codrut.andreivacaru.ro", "https://codrut.ro"]


def test_cors_origins_accept_comma_separated_env_format() -> None:
    settings = Settings(cors_origins="https://codrut.andreivacaru.ro,https://codrut.ro")

    assert settings.cors_origins == ["https://codrut.andreivacaru.ro", "https://codrut.ro"]


def test_rate_limit_trusted_proxies_accept_json_ip_and_cidr_env_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CODRUT_RATE_LIMIT_TRUSTED_PROXIES",
        '["10.0.0.2","2001:db8::/64"]',
    )
    settings = Settings(_env_file=None)

    assert settings.rate_limit_trusted_proxies == ["10.0.0.2", "2001:db8::/64"]


def test_rate_limit_trusted_proxies_reject_hostnames() -> None:
    with pytest.raises(ValidationError, match="Invalid trusted proxy IP or network"):
        Settings(rate_limit_trusted_proxies=["traefik"])


def test_campaign_asset_signing_secret_prefers_dedicated_secret() -> None:
    settings = Settings(
        _env_file=None,
        session_secret=SecretStr("session-value"),
        task_link_secret=SecretStr("task-link-value"),
        campaign_asset_signing_secret=SecretStr("campaign-asset-value"),
    )

    assert settings.effective_campaign_asset_signing_secret == "campaign-asset-value"  # noqa: S105


def test_campaign_asset_signing_secret_falls_back_to_task_link_secret() -> None:
    settings = Settings(
        _env_file=None,
        session_secret=SecretStr("session-value"),
        task_link_secret=SecretStr("task-link-value"),
    )

    assert settings.effective_campaign_asset_signing_secret == "task-link-value"  # noqa: S105


def test_campaign_asset_signing_secret_preserves_legacy_session_fallback() -> None:
    settings = Settings(
        _env_file=None,
        session_secret=SecretStr("session-value"),
    )

    assert settings.effective_campaign_asset_signing_secret == "session-value"  # noqa: S105


def test_default_email_sender_name_is_andrei_vacaru(monkeypatch) -> None:
    monkeypatch.delenv("CODRUT_EMAIL_FROM_NAME", raising=False)
    settings = Settings(_env_file=None)

    assert settings.email_from_name == "Andrei Văcaru"


def test_default_email_capacity_covers_launch_delivery() -> None:
    settings = Settings(_env_file=None)

    assert settings.email_daily_send_cap == 2000
    assert settings.email_outbox_batch_size == 100
    assert settings.email_outbox_concurrency == 8
    assert settings.worker_max_jobs == 3
    assert settings.email_brevo_sandbox_enabled is False


def test_worker_concurrency_cannot_exceed_database_pool_capacity() -> None:
    with pytest.raises(ValidationError, match="Worker concurrency can exceed"):
        Settings(
            _env_file=None,
            db_pool_size=5,
            db_max_overflow=5,
            email_outbox_concurrency=9,
            worker_max_jobs=3,
        )


def test_worker_concurrency_may_exactly_fill_database_pool_capacity() -> None:
    settings = Settings(
        _env_file=None,
        db_pool_size=5,
        db_max_overflow=5,
        email_outbox_concurrency=8,
        worker_max_jobs=3,
    )

    assert settings.email_outbox_concurrency + settings.worker_max_jobs - 1 == (
        settings.db_pool_size + settings.db_max_overflow
    )


def test_default_ip_rate_limit_ceiling_covers_shared_network_launches() -> None:
    settings = Settings(_env_file=None)

    assert settings.rate_limit_max_requests == 120
    assert settings.rate_limit_ip_max_requests == 2000


def test_database_pool_defaults_are_bounded_for_four_api_workers() -> None:
    settings = Settings(_env_file=None)

    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 5
    assert settings.db_pool_timeout_seconds == 10


def test_email_sender_identity_values_are_trimmed() -> None:
    settings = Settings(
        _env_file=None,
        email_from_address="  sender@example.com  ",
        email_from_name="  Cody  ",
        email_legal_address="  Strada Exemplu 1  ",
    )

    assert settings.email_from_address == "sender@example.com"
    assert settings.email_from_name == "Cody"
    assert settings.email_legal_address == "Strada Exemplu 1"


@pytest.mark.parametrize(
    "field_name",
    ["email_from_address", "email_from_name", "email_legal_address"],
)
def test_email_sender_identity_values_cannot_be_blank(field_name: str) -> None:
    with pytest.raises(ValidationError, match="cannot be empty"):
        Settings(_env_file=None, **{field_name: "   "})


def test_production_rejects_local_sender_address() -> None:
    with pytest.raises(ValidationError, match="sender address must be valid"):
        production_settings(
            email_from_address="no-reply@codrut.local",
        )


def test_production_accepts_configured_sender_identity() -> None:
    settings = production_settings()

    assert settings.email_from_address == "no-reply@codrut.ro"


@pytest.mark.parametrize("token", [None, SecretStr(""), SecretStr("too-short")])
def test_production_requires_strong_brevo_webhook_token(token: SecretStr | None) -> None:
    with pytest.raises(ValidationError, match="email-webhook secret"):
        production_settings(email_webhook_token=token)


def test_production_requires_brevo_provider() -> None:
    with pytest.raises(ValidationError, match="provider must be Brevo"):
        production_settings(email_provider="mailpit")


@pytest.mark.parametrize(
    ("field_name", "message"),
    [
        ("session_secret", "session secret"),
        ("task_link_secret", "task-link secret"),
        ("campaign_asset_signing_secret", "campaign-asset secret"),
        ("email_webhook_token", "email-webhook secret"),
    ],
)
def test_production_requires_independent_strong_secrets(field_name: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        production_settings(**{field_name: SecretStr("too-short")})


def test_production_requires_distinct_secrets() -> None:
    shared_secret = SecretStr("shared-secret-with-at-least-32-characters")
    with pytest.raises(ValidationError, match="must be distinct"):
        production_settings(session_secret=shared_secret, task_link_secret=shared_secret)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("public_app_url", "http://codrut.example.com", "public app URL"),
        ("cors_origins", ["http://codrut.example.com"], "CORS origins"),
    ],
)
def test_production_requires_https_origins(field_name: str, value: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        production_settings(**{field_name: value})


def test_production_requires_brevo_api_key() -> None:
    with pytest.raises(ValidationError, match="requires an API key"):
        production_settings(email_brevo_api_key=None)


def test_local_auth_bypass_is_available_in_development() -> None:
    settings = Settings(_env_file=None, env="development", local_auth_bypass=True)

    assert settings.local_auth_bypass is True


def test_local_auth_bypass_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="cannot be enabled in production"):
        production_settings(local_auth_bypass=True)
