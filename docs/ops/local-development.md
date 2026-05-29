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
