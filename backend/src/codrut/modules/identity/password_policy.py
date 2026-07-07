PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
CREDENTIAL_POLICY_MESSAGE = (
    "Parola trebuie să aibă cel puțin 8 caractere și să includă "
    "o literă mare, o literă mică, o cifră și un caracter special."
)


def validate_new_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(CREDENTIAL_POLICY_MESSAGE)
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Parola nu poate depăși {PASSWORD_MAX_LENGTH} de caractere.")
    if not any(character.isupper() for character in value):
        raise ValueError(CREDENTIAL_POLICY_MESSAGE)
    if not any(character.islower() for character in value):
        raise ValueError(CREDENTIAL_POLICY_MESSAGE)
    if not any(character.isdigit() for character in value):
        raise ValueError(CREDENTIAL_POLICY_MESSAGE)
    if not any(not character.isalnum() and not character.isspace() for character in value):
        raise ValueError(CREDENTIAL_POLICY_MESSAGE)
    return value
