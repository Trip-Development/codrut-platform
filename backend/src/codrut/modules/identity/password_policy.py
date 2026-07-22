PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
CREDENTIAL_POLICY_MESSAGE = "Parola trebuie să aibă cel puțin 12 caractere."

COMMON_PASSWORDS = frozenset(
    {
        "123456789012",
        "administrator",
        "changeme1234",
        "codrut123456",
        "letmeinplease",
        "parola123456",
        "password1234",
        "qwerty123456",
        "qwertyuiop12",
        "welcome12345",
    }
)


def validate_new_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(CREDENTIAL_POLICY_MESSAGE)
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Parola nu poate depăși {PASSWORD_MAX_LENGTH} de caractere.")
    if value.casefold().strip() in COMMON_PASSWORDS:
        raise ValueError("Parola este prea frecventă. Alege o frază mai greu de ghicit.")
    return value
