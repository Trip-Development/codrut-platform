from codrut.core.config import Settings


def test_cors_origins_accept_json_array_env_format() -> None:
    settings = Settings(cors_origins='["https://codrut.andreivacaru.ro","https://codrut.ro"]')

    assert settings.cors_origins == ["https://codrut.andreivacaru.ro", "https://codrut.ro"]


def test_cors_origins_accept_comma_separated_env_format() -> None:
    settings = Settings(cors_origins="https://codrut.andreivacaru.ro,https://codrut.ro")

    assert settings.cors_origins == ["https://codrut.andreivacaru.ro", "https://codrut.ro"]


def test_default_email_sender_name_is_andrei_vacaru(monkeypatch) -> None:
    monkeypatch.delenv("CODRUT_EMAIL_FROM_NAME", raising=False)
    settings = Settings(_env_file=None)

    assert settings.email_from_name == "Andrei Vacaru"
