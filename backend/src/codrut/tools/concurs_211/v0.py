"""Concursul modelelor, plicul 211: varianta V0 (ce e pe live azi)."""

from concurs_comun import ruleaza

if __name__ == "__main__":
    ruleaza(
        "V0",
        actor="gemini-3.1-flash-lite",
        evaluator="gemini-3.8-flash",
        gandire_evaluator=1024,
    )
