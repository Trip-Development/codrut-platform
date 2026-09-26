"""Scenariile probelor automate — plicul 82.

Replicile omului sunt FIXE: aceleasi la fiecare rulare, ca doua rulari sa se poata compara.
Nu se schimba intre masuratori fara sa se spuna in raportul masuratorii.

Fiecare pas are un fel, iar portile se aplica dupa fel:
- `salut`: replica cu care Cody deschide sesiunea (omul n-a scris nimic inca);
- `pornire`: omul accepta; la role-play Cody pune scena, la quiz prima intrebare;
- `joc`: o replica din scena — se puncteaza;
- `raspuns`: un raspuns la quiz sau o replica de coaching — nu e „replica din joc";
- `despartire`: formula de final — NU se puncteaza.

Replicile de role-play sunt generale dinadins: scena o alege modelul, deci o replica prea
precisa n-ar avea sens in orice scena. Doua sunt slabe, ca sa apara note sub 9.
"""

from dataclasses import dataclass

# Numele „adevarat" al omului simulat — plicul 138: NU pleaca niciodata spre model. Poarta de
# nume a uneltii il cauta in tot ce pleaca. E inventat si usor de cautat, si nu seamana cu niciun
# personaj din scena (pana la 138 era „Mihai Ionescu", dar „Mihai Șerban" e personaj, deci poarta
# de nume ar fi sunat din senin).
PARTICIPANT = "Ionela Zăvoianu-Testescu"
# Ce pleaca in locul numelui, ca in aplicatie: codul omului. Primul lui cuvant („Fox") joaca
# rolul prenumelui in porti — poarta 4 verifica si regula „personajul nu poarta numele omului".
COD_PARTICIPANT = "Fox 34"
# Functia „adevarata" a omului simulat — plicul 142: NU pleaca spre model. Unealta o pune
# dinadins in profilul de rol, ca aplicatia de dinainte de 142; daca vreodata ar pleca, poarta de
# nume o prinde.
FUNCTIE_PARTICIPANT = "Director Regional Mărgineanu Sud"

COMPETENTE_PROIECT = [
    "Ascultare activă",
    "Exprimarea asertivă a nevoilor și limitelor",
    "Gestionarea reacțiilor celorlalți",
    "Gestionarea propriilor reacții emoționale",
    "Verificarea înțelegerii și a alinierii",
    "Rezolvarea colaborativă a conflictelor",
    "Feedback constructiv",
]


@dataclass(frozen=True)
class Pas:
    text: str | None  # None = Cody deschide sesiunea, omul n-a scris nimic
    fel: str


SCENARII: dict[str, tuple[Pas, ...]] = {
    "roleplay": (
        Pas(None, "salut"),
        Pas("Da, hai.", "pornire"),
        Pas("Înțeleg ce spui. Ce anume te-a deranjat cel mai tare?", "joc"),
        Pas("Păi nu e vina mea, eu am făcut ce mi s-a cerut.", "joc"),
        Pas(
            "Când se întâmplă asta, eu rămân fără timp pentru restul echipei. "
            "Aș vrea să stabilim împreună un termen clar.",
            "joc",
        ),
        Pas("Bine, dar tu nu mi-ai spus niciodată ce aștepți de la mine.", "joc"),
        Pas("Mulțumesc, zi faină!", "despartire"),
    ),
    "knowledge": (
        Pas(None, "salut"),
        Pas("Da, hai.", "pornire"),
        *(Pas(litera, "raspuns") for litera in ("B", "A", "C", "B", "D", "A", "C", "B", "A", "D")),
    ),
    "coaching": (
        Pas(None, "salut"),
        Pas("Bine, mulțumesc. Am o situație la muncă.", "pornire"),
        Pas("Am un coleg care întârzie mereu cu partea lui din proiect.", "raspuns"),
        Pas("Nu știu. Poate îi e greu să spună că nu are timp.", "raspuns"),
        Pas("Aș putea să vorbesc cu el mâine dimineață, între patru ochi.", "raspuns"),
        Pas("Mulțumesc, mi-a fost de folos.", "despartire"),
    ),
}
