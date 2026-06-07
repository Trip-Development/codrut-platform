from codrut.core.config import Settings


def test_cors_origins_accept_json_array_env_format() -> None:
    settings = Settings(cors_origins='["https://app.codrut.ro","https://codrut.ro"]')

    assert settings.cors_origins == ["https://app.codrut.ro", "https://codrut.ro"]


def test_cors_origins_accept_comma_separated_env_format() -> None:
    settings = Settings(cors_origins="https://app.codrut.ro,https://codrut.ro")

    assert settings.cors_origins == ["https://app.codrut.ro", "https://codrut.ro"]
