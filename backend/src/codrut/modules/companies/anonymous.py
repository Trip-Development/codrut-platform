import secrets

_ANONYMOUS_ADJECTIVES = (
    "Curious",
    "Calm",
    "Bright",
    "Steady",
    "Kind",
    "Clear",
    "Brave",
    "Warm",
    "Wise",
    "Open",
)
_ANONYMOUS_NOUNS = (
    "Soap",
    "Cedar",
    "Comet",
    "Harbor",
    "Lantern",
    "River",
    "Signal",
    "Meadow",
    "Compass",
    "Anchor",
)


def new_anonymous_name() -> str:
    return (
        f"{secrets.choice(_ANONYMOUS_ADJECTIVES)}"
        f"{secrets.choice(_ANONYMOUS_NOUNS)}"
        f"{secrets.randbelow(9000) + 1000}"
    )
