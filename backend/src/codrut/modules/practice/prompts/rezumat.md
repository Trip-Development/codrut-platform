Pe baza conversației de mai jos cu {name} (modul: {opt_text}), scrie exact în formatul următor:

##Concluzie
Un paragraf de 3-4 propoziții — ce s-a întâmplat, ce a învățat {name}. **Dacă a fost modul Role-play sau Verificare Cunoștințe, trece OBLIGATORIU și PUNCTAJUL/SCORUL FINAL obținut.** Adresează-te direct lui {name}.

##Recomandări
• Prima recomandare concretă
• A doua recomandare concretă
• A treia recomandare concretă

---

**LA FINAL**, te rog să adaugi OBLIGATORIU evaluarea cantitativă a competențelor lui {name}, în funcție de răspunsurile sale din conversație, DOAR în format JSON, exact cum urmează:
```json
{{
  "topic": "Un singur cuvânt major despre subiectul blocant din conversatie (ex: Vasile, Epuizare, Sarcini, Feedback)",
  "characters": [
    {{ "name": "Numele complet sau prenumele extrase", "role": "Functia sau rolul din poveste (ex: coleg, manager, prieten)" }}
  ],
  "scores": {{
    "questionsRatio": 8, // Nota 1-10: A dovedit Abilități de Coach (a pus întrebări bune ca să exploreze) sau de Șef (a dat ordine)?
    "assertiveness": 9,  // Nota 1-10: Cât de asertiv a fost per mesaj? A evitat agresivitatea și structurile absolute "trebuie, mereu, niciodată"?
    "sbiFeedback": 5,    // Nota 1-10: Concizie și Feedback. A folosit modelul SBI (specific) sau a umplut conversația de zgomot și a fost vag?
    "conciseness": 7     // Nota 1-10: A fost echilibrat din punct de vedere a cantității textului sau a vorbit prea mult?
  }}
}}
```

Respectă EXACT acest format. Nu adăuga alte structuri extra. Ton: cald, direct, fără jargon. Nu uita blocul JSON la final!

Conversația:
{history}
