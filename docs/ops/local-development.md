# Local Development

Use Docker Compose as the source of truth and `just` as the command contract.

```sh
cp .env.example .env
just dev
```

Useful endpoints:

- Frontend direct: <http://localhost:3000>
- Backend direct: <http://localhost:8000/api/health/live>
- Traefik edge: <http://localhost>
- Traefik dashboard: <http://localhost:8080>
- Mailpit: <http://localhost:8025>

The devcontainer attaches to the `backend` service and uses the same Compose files as normal local development.

## Pilot Test Accounts

Production-like local testing should use real seeded accounts and keep demo fallback disabled.

Set these values in `.env`:

```sh
CODRUT_FRONTEND_DEMO_FALLBACK=false
NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK=false
CODRUT_SEED_TRAINER_EMAIL=trainer@example.com
CODRUT_SEED_TRAINER_PASSWORD=replace-with-a-long-test-password
CODRUT_SEED_COMPANY_NAME=Pilot Codrut
```

Then seed the local database from the backend/devcontainer environment:

```sh
uv run python -m codrut.tools.seed_pilot
```

The seed command creates or updates the trainer account and makes it owner of the configured pilot company. It refuses to run in production unless `CODRUT_SEED_ALLOW_PRODUCTION=true` is explicitly set; do not use that override for normal pilot testing.

## Core Workflow Smoke

For a quick trainer workflow check, create a fake company and import a three-row
roster with these exact headers:

```text
Name,email,Reports To,Position,Location,PCM Bază,PCM Fază
```

Example rows:

```text
Vlad Soimu Manager,vlad.soimu2@gmail.com,,Manager,Bucuresti,Gânditor,Perseverent
Vlad Soimu Membru,vlad.soimu@yahoo.com,Vlad Soimu Manager,Membru echipă,Bucuresti,Empatic,Promotor
Ilinca Member,ilincacrb4825@gmail.com,Vlad Soimu Manager,Membru echipă,Bucuresti,Rebel,Imaginator
```

The same workbook is generated locally at
`/Users/vladul/Downloads/codrut-roster-test-pcm.xlsx` during the current smoke
setup.

Expected behavior:

- The manager imports as `leadership`; the member imports as `member`.
- Importing the roster does not send access automatically.
- The default assignment plan includes Lencioni for leadership and the manager
  team, Distress Drivers for the manager only, and iCARE 360 for the manager
  from self plus direct-report feedback.
- Saving the plan is duplicate-safe; regenerating and saving again should not
  create extra assignments.
- `Generează linkuri securizate` creates links without sending email.
- `Trimite invitații email` sends through the configured provider; in local dev,
  verify delivery in Mailpit at <http://localhost:8025>.
- Permanent participant accounts are redirected to the combined PCM base/phase
  task when either value is missing; the account page should link to the
  persisted PCM assignment, not to an assignment-less questionnaire route.
- Trainer invitation rows show active secure links with a green status dot and
  their expiry date. Participant secure-link pages do not display expiry dates.
- Managers receive account setup emails and then use the participant dashboard.
  Members receive secure form links and see form-only pages.
- Reports aggregate both Romanian and English questionnaire keys into the same
  Lencioni and Distress Drivers buckets, plus canonical Romanian iCARE 360 on
  `boss_360`.

This path is covered by `test_two_person_roster_generates_manager_member_default_plan`
in `backend/tests/test_company_service.py`.

Run the transactional email smoke from the backend container to prove the
configured provider can send to Mailpit and that Mailpit stores the delivered
plain-text and HTML bodies:

```sh
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend uv run python -m codrut.tools.smoke_mailpit
```

## Demo Fallback

`CODRUT_FRONTEND_DEMO_FALLBACK=true` is only for intentionally browsing seeded prototype/demo surfaces. Keep it `false` when checking whether frontend routes are genuinely connected to backend auth and data.
