# Ghid de Utilizare: Casa de Probă (Test Environment)

Acest director conține configurația completă pentru **Casa de Probă** a aplicației Cody (`cody-test`).

---

## 1. Ce este Casa de Probă și de ce există?

Casa de Probă este o copie complet izolată a platformei Cody, care rulează pe același server fizic, dar pe un domeniu separat:
👉 **`https://test.cody.andreivacaru.ro`**

Scopul ei este să permită testarea funcționalităților noi (de exemplu modulul de exerciții interactive `practice`) într-un mediu real de cloud, **fără niciun risc pentru producție** și fără a fi nevoie de un server separat.

---

## 2. Garanții de Siguranță (Ce NU face Casa de Probă)

1. **NU atinge baza de date vie:**  
   Casa de probă folosește propriul container PostgreSQL (`testdb`) și propriul volum de stocare (`cody_test_postgres_data`) pe discul rădăcină. Nu are acces la volumul de 10 GB al producției.
2. **NU trimite emailuri reale:**  
   Este configurată cu triplă protecție:
   - Modul Brevo Sandbox este forțat (`X-Sib-Sandbox: drop`).
   - Cheia Brevo API este setată intenționat ca invalidă (`CHEIE-INVALIDA-INTENTIONAT`).
   - Limita zilnică de trimitere este setată pe 0 (`CODRUT_EMAIL_DAILY_SEND_CAP=0`).
   Niciun email nu poate pleca către cei 235 de participanți din producție.
3. **NU deschide porturi pe server:**  
   Containerele nu expun porturi în rețea. Tot traficul intră securizat prin proxy-ul Traefik deja existent, folosind reguli cu nume distincte (`codytest-api`, `codytest-frontend`).
4. **NU încarcă memoria serverului:**  
   Toate containerele au limite stricte de memorie (maxim ~1.9 GB în total), lăsând producției peste 5.5 GB RAM liber.

---

## 3. Comenzi de Rulare (Pas cu Pas)

> **Important:** Toate comenzile de mai jos se rulează din directorul unde este salvat `compose.test.yaml` pe server.

### A. Pornirea stivei de test
```bash
# 1. Trage imaginile construite din GitHub
docker compose --env-file .env -f compose.test.yaml pull

# 2. Pornește serviciile în fundal
docker compose --env-file .env -f compose.test.yaml up -d

# 3. Aplică migrarea bazei de date pe baza de test
docker compose --env-file .env -f compose.test.yaml exec backend alembic upgrade head
```

### B. Verificarea stării și jurnalelor
```bash
# Verifică starea containerelor de test
docker compose --env-file .env -f compose.test.yaml ps

# Vezi jurnalele în timp real pentru backend
docker compose --env-file .env -f compose.test.yaml logs -f backend

# Vezi jurnalele pentru frontend
docker compose --env-file .env -f compose.test.yaml logs -f frontend
```

### C. Oprirea temporară
```bash
docker compose --env-file .env -f compose.test.yaml stop
```

---

## 4. Cum se Pune o Imagine Nouă (După o Modificare)

Când împingi un nou commit pe ramura `feat/practice-schema`, GitHub Actions va construi automat o imagine nouă cu eticheta `test-<SHA>`.

Pentru a actualiza casa de probă:
1. Deschide `.env` pe server și actualizează:
   ```text
   BACKEND_IMAGE=ghcr.io/trip-development/codrut-platform-backend:test-<NOUL_SHA>
   FRONTEND_IMAGE=ghcr.io/trip-development/codrut-platform-frontend:test-<NOUL_SHA>
   ```
2. Rulează comenzile:
   ```bash
   docker compose --env-file .env -f compose.test.yaml pull
   docker compose --env-file .env -f compose.test.yaml up -d
   docker compose --env-file .env -f compose.test.yaml exec backend alembic upgrade head
   ```

---

## 5. Curățenia Finală (Când nu mai e nevoie de Casa de Probă)

Pentru a elibera complet resursele și a șterge baza de date de test:
```bash
# Oprește și șterge containerele, rețeaua internă și volumele de test
docker compose --env-file .env -f compose.test.yaml down -v
```
După această comandă, nu rămâne nicio urmă pe serverul de producție.
