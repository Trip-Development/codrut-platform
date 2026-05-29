# Traefik

Traefik is the edge gateway for local, staging, and production Compose topology.

- In development, Traefik routes `/` to the frontend and `/api/*` to FastAPI while direct ports remain exposed for debugging.
- In production, `compose.prod.yaml` enables HTTPS through Let's Encrypt and routes by `CODRUT_HOST`.
- Application authentication remains inside FastAPI; Traefik is not an auth service.
