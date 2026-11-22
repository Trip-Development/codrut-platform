"""Face perechea de chei VAPID a notificării zilnice — plicul 252, §2.7.

`python -m codrut.tools.chei_notificare` scrie EXACT două rânduri și nimic altceva. Ieșirea
merge direct într-un fișier (`>> .env` pe serverul de probă), niciodată pe ecran. Fără
argumente, fără rețea, fără bază.
"""

from __future__ import annotations

import sys

from codrut.modules.practice.web_push import pereche_noua


def main() -> None:
    privata, publica = pereche_noua()
    sys.stdout.write(
        f"CODRUT_PUSH_VAPID_PRIVATE_KEY={privata}\nCODRUT_PUSH_VAPID_PUBLIC_KEY={publica}\n"
    )


if __name__ == "__main__":
    main()
