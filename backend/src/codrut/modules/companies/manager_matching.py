import unicodedata

TOP_LEVEL_MANAGER_VALUES = {
    "direct manager",
    "radacina",
    "root",
    "top",
    "top level",
    "nivel superior",
    "fara manager",
    "fara sef",
    "line manager",
    "manager",
    "manager direct",
    "none",
    "n/a",
    "na",
    "sef",
    "seful direct",
    "superior",
    "superior direct",
    "-",
    "\u2014",
}


def clean_manager_reference(value: str | None) -> str | None:
    cleaned = value.strip() if value is not None else ""
    if not cleaned:
        return None
    normalized = normalize_manager_token(cleaned)
    return None if normalized in TOP_LEVEL_MANAGER_VALUES or cleaned.isdigit() else cleaned


def is_external_matrix_manager_label(value: str | None) -> bool:
    if not value:
        return False
    tokens = normalize_manager_token(value).replace("-", " ").split()
    return "matrix" in tokens


def manager_reference_key(value: str | None) -> str:
    if not value:
        return ""
    without_diacritics = "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )
    return "".join(char for char in without_diacritics.casefold() if char.isalnum())


def normalize_manager_token(value: str) -> str:
    without_diacritics = "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_diacritics.casefold().split())
