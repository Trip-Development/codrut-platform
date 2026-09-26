"""Regresia plicului 92, 3a: transcrierea furnizorului local nu mai cade cu NameError.

`generation_provider.py` folosea `Decimal` la rulare, in transcrierea furnizorului local, fara
sa-l importe. Pe proba si pe productie ruleaza Vertex, deci nu se vedea; pe o masina de lucru
fara Vertex, primul mesaj vorbit dadea NameError.
"""

from decimal import Decimal

import pytest

from codrut.core.config import Settings
from codrut.modules.practice.generation_provider import LocalGenerationProvider


@pytest.mark.asyncio
async def test_transcrierea_locala_intoarce_textul_si_costul() -> None:
    furnizor = LocalGenerationProvider(Settings(generation_provider="local"))

    text, usage, cost = await furnizor.transcribe_audio(b"RIFFsunet")

    assert text
    assert usage.prompt_tokens > 0
    assert cost == Decimal("0.000040")
