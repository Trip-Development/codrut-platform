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
4. **NU trimite emailuri reale:**  
   Este configurată cu triplă protecție:
   - Modul Brevo Sandbox este forțat (`X-Sib-Sandbox: drop`).
   - Cheia Brevo API este setată intenționat ca invalidă (`CHEIE-INVALIDA-INTENTIONAT`).
   - Limita zilnică de trimitere este setată pe 0 (`CODRUT_EMAIL_DAILY_SEND_CAP=0`).
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
