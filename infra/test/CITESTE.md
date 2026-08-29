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
4. **NU folosește acces administrativ:**  
   Deploy-ul automat folosește o cheie SSH dedicată, îngradită strict (`forced-command` în `/root/.ssh/authorized_keys`), care poate porni doar scriptul `/usr/local/sbin/cody-test-deploy.sh` și nu permite acces la consolă (shell).
5. **NU încarcă memoria serverului:**  
   Toate containerele au limite stricte de memorie (maxim ~1.9 GB în total), lăsând producției peste 5.5 GB RAM liber.

---

## 3. Cum se Pune o Imagine Nouă (Cu Butonul Automatat)

Deploierea și actualizarea casei de probă se fac **automat din GitHub Actions**, fără a fi nevoie de comenzi manuale pe server:

1. Faci modificările în cod și le împingi pe ramura `feat/practice-schema`.
2. Workflow-ul `build-test-image.yml` va construi automat imaginile noi (`test-<SHA>`).
3. Pornești deploy-ul casei de probă:
   - Din interfața GitHub Actions: Rulezi workflow-ul **`Deploy Test (cody-test)`** de pe ramura `feat/practice-schema`.
   - Sau din terminal:
     ```bash
     gh workflow run deploy-test.yml --ref feat/practice-schema
     gh run watch
     ```

---

## 4. Verificarea Stării și Jurnalelor de pe Server (Diagnostic)

Dacă vrei să inspectezi starea direct pe server:
```bash
# Verifică starea containerelor de test
cd /opt/cody-test
docker compose --env-file .env -f compose.test.yaml ps

# Vezi jurnalele în timp real pentru backend
docker compose --env-file .env -f compose.test.yaml logs -f backend

# Vezi jurnalele pentru frontend
docker compose --env-file .env -f compose.test.yaml logs -f frontend
```

---

## 5. Curățenia Finală (Când nu mai e nevoie de Casa de Probă)

Pentru a elibera complet resursele și a șterge baza de date de test:
```bash
cd /opt/cody-test
# Oprește și șterge containerele, rețeaua internă și volumele de test
docker compose --env-file .env -f compose.test.yaml down -v
```
După această comandă, nu rămâne nicio urmă pe serverul de producție.
