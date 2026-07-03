import json
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODRUT_", env_file=".env", extra="ignore")

    app_name: str = "Codruț Platform"
    env: str = "development"
    database_url: str = "postgresql+asyncpg://codrut:codrut@localhost:5432/codrut"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: SecretStr = Field(default=SecretStr("local-development-secret"))
    # Dedicated secret for signing task/invite links. Defaults to session_secret if not set.
    # Set this independently in prod so links survive session secret rotation.
    task_link_secret: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    docs_enabled: bool = True
    email_provider: str = "test"
    email_from_address: str = "no-reply@codrut.local"
    email_from_name: str = "Andrei Văcaru"
    email_brevo_api_key: SecretStr | None = None
    email_smtp_host: str = "mailpit"
    email_smtp_port: int = 1025
    email_smtp_username: str | None = None
    email_smtp_password: SecretStr | None = None
    email_smtp_starttls: bool = False
    email_test_mode: bool = True
    email_daily_send_cap: int = 300
    public_app_url: str = "http://localhost:3000"
    campaign_asset_dir: str = "var/campaign-assets"
    campaign_asset_public_path: str = "/api/campaign-assets"
    campaign_asset_max_bytes: int = 5 * 1024 * 1024

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

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def effective_task_link_secret(self) -> str:
        """The secret used to sign task/invite link tokens."""
        if self.task_link_secret is not None:
            return self.task_link_secret.get_secret_value()
        return self.session_secret.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
