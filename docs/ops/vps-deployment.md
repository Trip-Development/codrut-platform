# VPS Deployment

Production deployment uses the same base Compose topology with the production overlay:

```sh
docker compose -f compose.yaml -f compose.prod.yaml config
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Secrets must be supplied through environment files or GitHub Environment secrets on the VPS, never committed to the repository.

Before using real participant data, verify:

- HTTPS and routing through Traefik.
- Postgres backup and restore.
- Redis persistence expectations.
- Application logs and restart policy.
- Internal staging acceptance from the June release checklist.
