from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODRUT_", env_file=".env", extra="ignore")

    app_name: str = "Codrut Platform"
    env: str = "development"
    database_url: str = "postgresql+asyncpg://codrut:codrut@localhost:5432/codrut"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: SecretStr = Field(default=SecretStr("local-development-secret"))
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    docs_enabled: bool = True
    email_provider: str = "test"
    email_from_address: str = "no-reply@codrut.local"
    email_from_name: str = "Codrut Platform"
    email_brevo_api_key: SecretStr | None = None
    email_smtp_host: str = "mailpit"
    email_smtp_port: int = 1025
    email_smtp_username: str | None = None
    email_smtp_password: SecretStr | None = None
    email_smtp_starttls: bool = False
    email_test_mode: bool = True
    public_app_url: str = "http://localhost:3000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
