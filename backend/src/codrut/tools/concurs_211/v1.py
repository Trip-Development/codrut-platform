"""Concursul modelelor, plicul 211: varianta V1 (profesorul fără gândire)."""

from concurs_comun import ruleaza

if __name__ == "__main__":
    ruleaza(
        "V1",
        actor="gemini-3.1-flash-lite",
        evaluator="gemini-3.8-flash",
        gandire_evaluator=0,
    )
