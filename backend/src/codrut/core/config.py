import json
from functools import lru_cache
from ipaddress import ip_network
from typing import Literal
from urllib.parse import urlsplit

from email_validator import EmailNotValidError, validate_email
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODRUT_", env_file=".env", extra="ignore")

    app_name: str = "Cody Platform"
    env: str = "development"
    database_url: str = "postgresql+asyncpg://codrut:codrut@localhost:5432/codrut"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: SecretStr = Field(default=SecretStr("local-development-secret"))
    # Dedicated secret for signing task/invite links. Defaults to session_secret if not set.
    # Set this independently in prod so links survive session secret rotation.
    task_link_secret: SecretStr | None = None
    # Dedicated secret for campaign asset ownership markers. Defaults to the effective
    # task-link secret so existing deployments are not tied directly to session rotation.
    campaign_asset_signing_secret: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    docs_enabled: bool = True
    email_provider: str = "test"
    email_from_address: str = "no-reply@codrut.local"
    email_from_name: str = "Andrei Văcaru"
    email_legal_address: str = "Cody"
    email_brevo_api_key: SecretStr | None = None
    email_webhook_token: SecretStr | None = None
    email_smtp_host: str = "mailpit"
    email_smtp_port: int = 1025
    email_smtp_username: str | None = None
    email_smtp_password: SecretStr | None = None
    email_smtp_starttls: bool = False
    email_test_mode: bool = True
    email_daily_send_cap: int = Field(default=750, ge=0)
    readiness_timeout_seconds: float = Field(default=3.0, ge=0.25, le=30.0)
    worker_heartbeat_key: str = "codrut:worker:heartbeat"
    worker_heartbeat_ttl_seconds: int = Field(default=30, ge=10, le=300)
    outbox_backlog_max_pending: int = Field(default=5000, ge=1, le=1_000_000)
    outbox_backlog_max_age_seconds: int = Field(default=1800, ge=60, le=86_400)
    public_app_url: str = "http://localhost:3000"
    campaign_asset_dir: str = "var/campaign-assets"
    campaign_asset_public_path: str = "/api/campaign-assets"
    campaign_asset_max_bytes: int = 5 * 1024 * 1024
    campaign_asset_max_width: int = Field(default=4096, ge=1, le=16_384)
    campaign_asset_max_height: int = Field(default=4096, ge=1, le=16_384)
    campaign_asset_max_pixels: int = Field(default=16_000_000, ge=1, le=100_000_000)
    api_request_max_bytes: int = 8 * 1024 * 1024
    security_headers_enabled: bool = True
    security_hsts_max_age_seconds: int = 31_536_000
    rate_limit_enabled: bool = False
    rate_limit_backend: Literal["noop", "redis"] = "noop"
    rate_limit_max_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_trusted_proxies: list[str] = Field(default_factory=list)
    password_breach_check_enabled: bool = False
    password_breach_timeout_seconds: float = Field(default=1.5, ge=0.25, le=5.0)
    password_breach_api_url: str = "https://api.pwnedpasswords.com/range"  # noqa: S105
    local_auth_bypass: bool = False
    local_auth_trainer_email: str = "trainer@example.com"
    local_auth_participant_email: str = "participant@example.com"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("email_from_address", "email_from_name", "email_legal_address")
    @classmethod
    def normalize_email_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Email sender identity values cannot be empty.")
        return normalized

    @field_validator("rate_limit_trusted_proxies", mode="before")
    @classmethod
    def parse_rate_limit_trusted_proxies(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            parsed = json.loads(stripped)
            if not isinstance(parsed, list):
                raise ValueError("Trusted proxies must be a JSON array.")
            if not all(isinstance(proxy, str) for proxy in parsed):
                raise ValueError("Trusted proxy entries must be strings.")
            value = [proxy.strip() for proxy in parsed if proxy.strip()]

        for proxy in value:
            if not isinstance(proxy, str):
                raise ValueError("Trusted proxy entries must be strings.")
            try:
                ip_network(proxy, strict=False)
            except ValueError as exc:
                raise ValueError(f"Invalid trusted proxy IP or network: {proxy}") from exc
        return value

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if not self.is_production:
            return self
        if self.local_auth_bypass:
            raise ValueError("Local authentication bypass cannot be enabled in production.")
        if self.email_provider != "brevo":
            raise ValueError("Production email provider must be Brevo.")

        secrets = {
            "session": self.session_secret.get_secret_value().strip(),
            "task-link": (
                self.task_link_secret.get_secret_value().strip()
                if self.task_link_secret
                else ""
            ),
            "campaign-asset": (
                self.campaign_asset_signing_secret.get_secret_value().strip()
                if self.campaign_asset_signing_secret
                else ""
            ),
            "email-webhook": (
                self.email_webhook_token.get_secret_value().strip()
                if self.email_webhook_token
                else ""
            ),
        }
        for purpose, secret in secrets.items():
            if len(secret) < 32:
                raise ValueError(
                    f"Production {purpose} secret must be independently configured "
                    "with at least 32 characters."
                )
        if len(set(secrets.values())) != len(secrets):
            raise ValueError("Production signing secrets must be distinct.")

        public_url = urlsplit(self.public_app_url)
        if public_url.scheme != "https" or not public_url.hostname:
            raise ValueError("Production public app URL must be an absolute HTTPS URL.")
        for origin in self.cors_origins:
            parsed_origin = urlsplit(origin)
            if parsed_origin.scheme != "https" or not parsed_origin.hostname:
                raise ValueError("Production CORS origins must be absolute HTTPS origins.")

        try:
            validate_email(self.email_from_address, check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValueError("Production email sender address must be valid.") from exc
        brevo_api_key = (
            self.email_brevo_api_key.get_secret_value().strip()
            if self.email_brevo_api_key is not None
            else ""
        )
        if not brevo_api_key:
            raise ValueError("Production Brevo delivery requires an API key.")
        return self

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def effective_task_link_secret(self) -> str:
        """The secret used to sign task/invite link tokens."""
        if self.task_link_secret is not None:
            return self.task_link_secret.get_secret_value()
        return self.session_secret.get_secret_value()

    @property
    def effective_campaign_asset_signing_secret(self) -> str:
        """The secret used to derive campaign asset ownership markers."""
        if self.campaign_asset_signing_secret is not None:
            return self.campaign_asset_signing_secret.get_secret_value()
        return self.effective_task_link_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
