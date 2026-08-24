import unicodedata

RECEIVED_360_MINIMUM_COMPLETED: int = 2
MINIMUM_PRIVACY_THRESHOLD: int = 2

PCM_REPORT_KEYS: set[str] = {
    "pcm_base",
    "phase",
    "pcm_phase",
}

PCM_PROFILES: dict[str, tuple[str, str]] = {
    "harmonizer": ("Armonizator", "#f97316"),
    "thinker": ("Gânditor", "#2563eb"),
    "persister": ("Perseverent", "#7c3aed"),
    "imaginer": ("Imaginator", "#fb923c"),
    "rebel": ("Rebel", "#eab308"),
    "promoter": ("Promotor", "#dc2626"),
}

PCM_ALIASES: dict[str, str] = {
    "armonizator": "harmonizer",
    "harmonizer": "harmonizer",
    "ganditor": "thinker",
    "gânditor": "thinker",
    "thinker": "thinker",
    "perseverent": "persister",
    "persister": "persister",
    "imaginator": "imaginer",
    "imaginer": "imaginer",
    "rebel": "rebel",
    "promotor": "promoter",
    "promoter": "promoter",
}


def normalize_pcm_token(value: str) -> str:
    without_diacritics = "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_diacritics.casefold().split())


def pcm_profile_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = normalize_pcm_token(value).replace("_", " ")
    compact = normalized.replace(" ", "")
    return PCM_ALIASES.get(normalized) or PCM_ALIASES.get(compact)


def format_pcm_label(value: str | None) -> str:
    key = pcm_profile_key(value)
    if key is not None:
        return PCM_PROFILES[key][0]
    if not value:
        return "Necompletată"
    return " ".join(part.capitalize() for part in value.replace("_", " ").split())


def get_pcm_color(value: str | None) -> str | None:
    key = pcm_profile_key(value)
    return PCM_PROFILES[key][1] if key is not None else None
