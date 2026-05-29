set dotenv-load := true

compose := "docker compose -f compose.yaml -f compose.dev.yaml"
compose_prod := "docker compose -f compose.yaml -f compose.prod.yaml"

default:
  just --list

dev:
  {{compose}} up --build

down:
  {{compose}} down --remove-orphans

logs:
  {{compose}} logs -f --tail=200

config:
  {{compose}} config

prod-config:
  {{compose_prod}} config

backend-test:
  cd backend && uv run pytest

backend-lint:
  cd backend && uv run ruff check src tests migrations

frontend-test:
  cd frontend && pnpm test

frontend-lint:
  cd frontend && pnpm lint

frontend-typecheck:
  cd frontend && pnpm typecheck

frontend-build:
  cd frontend && pnpm build

migrate:
  cd backend && uv run alembic upgrade head

generate-client:
  cd frontend && pnpm generate-client

smoke:
  {{compose}} up -d --build
  {{compose}} exec backend uv run pytest tests/test_health.py
