import re

import pytest

from codrut.modules.companies import anonymous


def test_new_anonymous_name_uses_friendly_tree_and_crockford_suffix() -> None:
    value = anonymous.new_anonymous_name()

    assert re.fullmatch(
        r"[A-Za-z]+-[A-Za-z]+-[0-9A-HJKMNP-TV-Z]{6}",
        value,
    )
    assert not set(value.rsplit("-", 1)[1]) & {"I", "L", "O", "U"}


@pytest.mark.asyncio
async def test_alias_allocation_retries_collisions_with_a_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated = iter(
        [
            "Stejar-Albastru-7K4P9X",
            "Stejar-Albastru-7K4P9X",
            "Cedru-Senin-92M6TR",
        ]
    )
    monkeypatch.setattr(anonymous, "new_anonymous_name", lambda: next(generated))
    checked: list[str] = []

    async def is_taken(candidate: str) -> bool:
        checked.append(candidate)
        return candidate == "Stejar-Albastru-7K4P9X"

    allocated = await anonymous.allocate_anonymous_name(
        is_taken,
        max_attempts=3,
    )

    assert allocated == "Cedru-Senin-92M6TR"
    assert checked == [
        "Stejar-Albastru-7K4P9X",
        "Stejar-Albastru-7K4P9X",
        "Cedru-Senin-92M6TR",
    ]


@pytest.mark.asyncio
async def test_alias_allocation_fails_after_the_configured_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        anonymous,
        "new_anonymous_name",
        lambda: "Stejar-Albastru-7K4P9X",
    )

    async def is_taken(_candidate: str) -> bool:
        return True

    with pytest.raises(RuntimeError, match="unique anonymous name"):
        await anonymous.allocate_anonymous_name(is_taken, max_attempts=2)
