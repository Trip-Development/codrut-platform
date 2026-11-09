"""Concursul modelelor, plicul 211: varianta V2 (profesorul pe 3.5-flash-lite)."""

from concurs_comun import ruleaza

if __name__ == "__main__":
    ruleaza(
        "V2",
        actor="gemini-3.1-flash-lite",
        evaluator="gemini-3.5-flash-lite",
        gandire_evaluator=1024,
    )
