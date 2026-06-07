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

## Demo Fallback

`CODRUT_FRONTEND_DEMO_FALLBACK=true` is only for intentionally browsing seeded prototype/demo surfaces. Keep it `false` when checking whether frontend routes are genuinely connected to backend auth and data.
