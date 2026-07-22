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

## Local Product Preview

Production-like local testing should use real seeded accounts and keep demo fallback disabled.

Set these values in `.env`:

```sh
CODRUT_FRONTEND_DEMO_FALLBACK=false
NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK=false
CODRUT_LOCAL_AUTH_BYPASS=true
CODRUT_SEED_TRAINER_EMAIL=trainer@example.com
CODRUT_SEED_TRAINER_PASSWORD=replace-with-a-long-test-password
CODRUT_SEED_PARTICIPANT_EMAIL=participant@example.com
CODRUT_SEED_PARTICIPANT_PASSWORD=replace-with-a-long-test-password
CODRUT_SEED_COMPANY_NAME=Pilot Codrut
```

For the complete local product preview, migrate and seed persisted sample data:

```sh
just migrate
just seed-local-preview
```

The local preview includes three companies, projects, participants, teams, assignments,
invitation delivery states, submitted results, campaigns, contacts, and email templates. Its
questionnaires are short, invented samples that exercise the production renderer without copying
protected wording, scoring rules, or interpretations into the repository. The synthetic iCARE
sample includes statement-specific participant choices so the real response interaction remains
reviewable. All contact addresses are synthetic `.test` addresses. The command replaces only its
named preview companies and communication records, then resets the local questionnaire samples.
It is safe to run again and always refuses to run when `CODRUT_ENV=production`.

With `CODRUT_LOCAL_AUTH_BYPASS=true`, local routes resolve these real seeded users directly:

- `/trainer/*` uses the configured trainer.
- `/participant/*` uses the configured participant.
- Existing session cookies do not pin the browser to the wrong local role.

No login or account switching is required. Set `CODRUT_LOCAL_AUTH_BYPASS=false` when testing
the real login, logout, session restoration, CSRF, or role-mismatch flows. The backend rejects
this bypass when `CODRUT_ENV=production`, and production Compose forces it off.

Use these accounts when testing authentication explicitly:

```text
Trainer: trainer@example.com
Participant: participant@example.com
Password: replace-with-a-long-test-password
```

For the smaller pilot-only setup, seed the local database from the backend/devcontainer
environment:

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
Mara Ionescu Manager,mara.manager@example.com,,Manager,Bucuresti,Gânditor,Perseverent
Tudor Stan,tudor.member@example.com,Mara Ionescu Manager,Membru echipă,Bucuresti,Empatic,Promotor
Ioana Rusu,ioana.member@example.com,Mara Ionescu Manager,Membru echipă,Bucuresti,Rebel,Imaginator
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
- Reports use the Romanian questionnaire keys for active workflows:
  `lencioni`, `distress_drivers`, and canonical iCARE 360 on `boss_360`.

This path is covered by `test_two_person_roster_generates_manager_member_default_plan`
in `backend/tests/test_company_service.py`.

Run the transactional email smoke from the backend container to prove the
configured provider can send to Mailpit and that Mailpit stores the delivered
plain-text and HTML bodies:

```sh
docker compose -f compose.yaml -f compose.dev.yaml exec -T backend uv run python -m codrut.tools.smoke_mailpit
```

## Demo Fallback

`CODRUT_FRONTEND_DEMO_FALLBACK=true` is only for intentionally browsing the legacy prototype
adapter. Keep it `false` for the local preview and for every backend-connected product check.
