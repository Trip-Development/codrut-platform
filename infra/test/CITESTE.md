# Ghid de Utilizare: Casa de Probă (Test Environment)

Acest director conține configurația completă pentru **Casa de Probă** a aplicației Cody (`cody-test`).

---

## 1. Ce este Casa de Probă și de ce există?

Casa de Probă este o copie complet izolată a platformei Cody, care rulează pe același server fizic, dar pe un domeniu separat:
👉 **`https://test.cody.andreivacaru.ro`**

Scopul ei este să permită testarea funcționalităților noi (de exemplu modulul de exerciții interactive `practice`) într-un mediu real de cloud, **fără niciun risc pentru producție** și fără a fi nevoie de un server separat.

---

## 2. Garanții de Siguranță și Izolare (Cele 9 Straturi)

1. **Rețea complet separată (`cody-test_interna`):**  
   Casa de probă **nu mai face parte din rețeaua producției**. Containerele de test nu pot rezolva numele interne de servicii (`db`, `redis`, `backend`, `frontend`) ale producției. Spațiul comun de nume este complet desființat.
2. **Nume unice de servicii și rutare internă (`INTERNAL_API_BASE_URL`):**  
   Serviciile se numesc `testbackend`, `testfrontend`, `testworker`, `testdb`, `testredis`. Chiar și în cazul unei erori de rețea, nu există niciun nume comun care să se poată ciocni cu producția. La randarea paginilor pe server, `testfrontend` folosește `INTERNAL_API_BASE_URL=http://testbackend:8000/api`.
3. **NU atinge baza de date vie:**  
   Casa de probă folosește propriul container PostgreSQL (`testdb`) și propriul volum de stocare (`cody_test_postgres_data`). Nu are acces la baza de date sau volumul producției.
4. **Emailurile pleacă doar către o listă scurtă, numită pe nume:**  
   Până la 31 august 2026 casa de probă nu trimitea absolut niciun email, iar
   plafonul zilnic de `0` oprea trimiterile **înainte** să se scrie ceva în baza
   de date — fără niciun rând în `email_sends` și fără nimic în jurnal. Asta a
   făcut ca o pană să pară „linişte". Acum:
   - **Lista de destinatari permiși** (`CODRUT_EMAIL_ALLOWED_RECIPIENTS`) e gardul
     principal. Când nu e goală, pleacă email **doar** către adresele din ea;
     restul se opresc, fiecare cu motivul scris în rândul lui din `email_sends`
     și în jurnal. Un participant de probă adăugat din greșeală cu adresa lui
     adevărată **nu** primește nimic. Implicit sunt doar adresele lui Andrei.
   - **Plafonul zilnic** e `20` (`CODRUT_EMAIL_DAILY_SEND_CAP`), nu `0`. E o plasă
     de siguranță împotriva unei bucle, nu un zăvor.
   - **Modul Brevo Sandbox** rămâne pornit (`X-Sib-Sandbox: drop`) și **cheia Brevo
     este în continuare invalidă** (`CHEIE-INVALIDA-INTENTIONAT`), deci în
     momentul de față **tot nu ajunge niciun email**. Ca să ajungă, trebuie puse
     amândouă: o cheie Brevo adevărată în `.env` și
     `CODRUT_EMAIL_BREVO_SANDBOX_ENABLED=false`. Nu se schimbă una fără cealaltă,
     și niciodată fără lista de destinatari de mai sus.
   - **Linkul de invitație nu depinde de email.** La training, invitația e o
     invitație la cont: se face contul omului și i se trimite un link prin care
     își pune parola. Linkul apare și în tabel, cu un buton „Copiază link", ca
     trainerul să-l poată da mai departe și cu poșta oprită. Se arată o singură
     dată, la trimitere — în bază nu se păstrează decât amprenta lui, ca la orice
     link de parolă.
5. **NU deschide porturi pe server:**  
   Niciun container de test nu expune porturi publice pe server.
6. **Prioritate Traefik scăzută:**  
   Rutele de probă au prioritatea `1` (`traefik.http.routers.codytest-*.priority: "1"`), astfel încât nu pot umbri nicio rută vie.
7. **Limite stricte de memorie și procesor:**  
   Fiecare serviciu are limită de memorie (total sub 2.5 GB) și limită CPU (`0.5` nuclee pentru `testbackend` și `testfrontend`, `0.25` pentru `testworker`, `testdb`, `testredis`), lăsând producției garantat peste jumătate din resursele mașinii.

---

## 3. Legătura cu Traefik și Comportamentul la Deploy în Producție

Pentru a direcționa traficul către casa de probă fără a atinge rețeaua producției, containerul Traefik este conectat direct la rețeaua internă de test:
```bash
docker network connect cody-test_interna codrut-platform-traefik-1
```
Această comandă **nu repornește Traefik** și nu creează nicio întrerupere pentru producție.

> [!IMPORTANT]
> **Comportament la punerea în producție:** Când producția se recreează în urma unui deploy, Traefik se recreează și pierde legătura cu `cody-test_interna`. În acest caz, se întrerupe **doar casa de probă**, iar producția funcționează normal (direcție de siguranță optimă). Legătura se reface automat la pornirea casei de probă prin scriptul `.claude-comenzi/porneste-casa-de-proba.sh` sau manual prin comanda de mai sus.

---

## 4. Verificarea Stării și Jurnalelor de pe Server (Diagnostic)

Dacă vrei să inspectezi starea direct pe server:
```bash
cd /opt/cody-test
docker compose --env-file .env -f compose.test.yaml ps

# Vezi jurnalele în timp real pentru backend
docker compose --env-file .env -f compose.test.yaml logs -f testbackend

# Vezi jurnalele pentru frontend
docker compose --env-file .env -f compose.test.yaml logs -f testfrontend
```

---

## 5. Curățenia Finală (Când nu mai e nevoie de Casa de Probă)

Pentru a elibera complet resursele și a șterge baza de date de test:
```bash
cd /opt/cody-test
docker compose --env-file .env -f compose.test.yaml down -v
```
După această comandă, nu rămâne nicio urmă pe serverul de producție.
