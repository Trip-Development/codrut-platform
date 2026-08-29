from pathlib import Path

_PROMPT_PATH = Path(__file__).parent / "cody-v1.md"
CODY_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8").strip()
CODY_PROMPT_VERSION = "v1.1"
