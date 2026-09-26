"""Metodele pe care le urmareste poarta 7 a probelor automate. Singurul loc unde stau listele.

Hotararea e a lui Andrei, 19 septembrie 2026, cuvant cu cuvant: „Sandwich iese de peste tot.
ADKAR si OILS ies doar din TEST IN si TEST OUT. Dar raman in quizz-urile intermediare."

- METODE_INTERZISE: o aparitie, in orice mod, e picare.
- METODE_NUMARATE: se numara si se scriu in raport, NU sunt picare — raman in quizurile
  intermediare, cu voia lui Andrei.

Pana la plicul 95 toate trei erau interzise aici, dintr-o intrebare deschisa pusa direct in
poarta: la referinta din 19 septembrie, din 23 de picaturi ale portii 7 la quiz, 15 erau material
permis.

DATORIE: TEST IN si TEST OUT nu exista inca (nici tabel, nici ecran). Cand se construiesc, ADKAR si
OILS sunt interzise ACOLO — si aia e poarta lor. E singurul loc unde partea a doua a hotararii
din 19 septembrie va mai avea efect.
"""

METODE_INTERZISE: tuple[str, ...] = ("SANDWICH",)
METODE_NUMARATE: tuple[str, ...] = ("ADKAR", "OILS")
