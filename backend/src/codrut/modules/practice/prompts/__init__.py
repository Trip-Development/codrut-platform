from pathlib import Path
from codrut.modules.practice.models import SessionKind

_PROMPTS_DIR = Path(__file__).parent
COMUN_PROMPT = (_PROMPTS_DIR / "comun.md").read_text(encoding="utf-8").strip()
COACH_PROMPT = (_PROMPTS_DIR / "coach.md").read_text(encoding="utf-8").strip()
ACTOR_PROMPT = (_PROMPTS_DIR / "actor.md").read_text(encoding="utf-8").strip()
EVALUARE_PROMPT = (_PROMPTS_DIR / "evaluare.md").read_text(encoding="utf-8").strip()

CODY_PROMPT_VERSION = "v2.0"
# Backward compatibility default:
CODY_SYSTEM_PROMPT = f"{COMUN_PROMPT}\n\n---\n\n{ACTOR_PROMPT}\n\n---\n\n{EVALUARE_PROMPT}"


def get_system_prompt_for_kind(kind: SessionKind) -> str:
    """Compose the specialized system prompt for the given practice session kind."""
    if kind == SessionKind.roleplay:
        return f"{COMUN_PROMPT}\n\n---\n\n{ACTOR_PROMPT}\n\n---\n\n{EVALUARE_PROMPT}"
    else:
        # coaching, knowledge, research, etc.
        return f"{COMUN_PROMPT}\n\n---\n\n{COACH_PROMPT}"
