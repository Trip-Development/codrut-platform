import secrets
from collections.abc import Awaitable, Callable, Collection

_ANONYMOUS_ADJECTIVES = (
    "Albastru",
    "Calm",
    "Curajos",
    "Deschis",
    "Limpede",
    "Linistit",
    "Senin",
    "Statornic",
    "Verde",
    "Viu",
)
_ANONYMOUS_TREES = (
    "Artar",
    "Brad",
    "Cedru",
    "Fag",
    "Frasin",
    "Mesteacan",
    "Pin",
    "Plop",
    "Salcie",
    "Stejar",
)
_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ANONYMOUS_NAME_ALLOCATION_ATTEMPTS = 16


def new_anonymous_name() -> str:
    suffix = "".join(secrets.choice(_CROCKFORD_BASE32) for _ in range(6))
    return (
        f"{secrets.choice(_ANONYMOUS_TREES)}-"
        f"{secrets.choice(_ANONYMOUS_ADJECTIVES)}-"
        f"{suffix}"
    )


async def allocate_anonymous_name(
    is_taken: Callable[[str], Awaitable[bool]],
    *,
    reserved: Collection[str] = (),
    max_attempts: int = ANONYMOUS_NAME_ALLOCATION_ATTEMPTS,
) -> str:
    if max_attempts < 1:
        raise ValueError("Anonymous name allocation requires at least one attempt.")

    reserved_names = set(reserved)
    for _attempt in range(max_attempts):
        candidate = new_anonymous_name()
        if candidate in reserved_names or await is_taken(candidate):
            continue
        return candidate
    raise RuntimeError("Could not allocate a unique anonymous name.")
