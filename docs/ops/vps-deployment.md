# VPS Deployment

Production deployment uses the same base Compose topology with the production overlay:

```sh
docker compose -f compose.yaml -f compose.prod.yaml config
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Secrets must be supplied through environment files or GitHub Environment secrets on the VPS, never committed to the repository.

Required GitHub secrets for the `VPS Deployment` workflow:

- `SSH_PRIVATE_KEY`, `HETZNER_VPS_IP`, `SSH_USER`
- `CODRUT_HOST`
- `TRAEFIK_ACME_EMAIL`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `CODRUT_DATABASE_URL`
- `CODRUT_REDIS_URL`
- `CODRUT_SESSION_SECRET`
- `CODRUT_CORS_ORIGINS`
- `CODRUT_PUBLIC_APP_URL`
- `CODRUT_EMAIL_PROVIDER`
- `CODRUT_EMAIL_FROM_ADDRESS`
- `CODRUT_EMAIL_FROM_NAME`
- `CODRUT_EMAIL_BREVO_API_KEY`

For the current single-host Compose deployment, `CODRUT_DATABASE_URL` should use the
same Postgres credentials as the `POSTGRES_*` secrets and host `db`, for example:

```text
postgresql+asyncpg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@db:5432/<POSTGRES_DB>
```

Set `CODRUT_PUBLIC_APP_URL` to the final HTTPS origin, for example:

```text
https://app.example.com
```

Before using real participant data, verify:

- HTTPS and routing through Traefik.
- Postgres backup and restore.
- Redis persistence expectations.
- Application logs and restart policy.
- Internal staging acceptance from the June release checklist.
