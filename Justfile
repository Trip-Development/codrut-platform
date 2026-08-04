set dotenv-load := true

compose := "docker compose -f compose.yaml -f compose.dev.yaml"
compose_prod := "docker compose -f compose.yaml -f compose.prod.yaml"
backend_workdir := "/workspace/backend"
frontend_workdir := "/workspace/frontend"
container_openapi_url := "http://backend:8000/api/openapi.json"

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
  {{compose}} run --rm --user vscode --workdir {{backend_workdir}} backend uv run pytest

backend-coverage:
  {{compose}} run --rm --user vscode --workdir {{backend_workdir}} backend uv run pytest --cov=codrut --cov-branch --cov-report=term-missing:skip-covered --cov-report=json:coverage.json

backend-test-host:
  cd backend && uv run pytest

backend-lint:
  {{compose}} run --rm --user vscode --workdir {{backend_workdir}} backend uv run ruff check src tests migrations

backend-lint-host:
  cd backend && uv run ruff check src tests migrations

frontend-test:
  {{compose}} run --rm --no-deps --user node --workdir {{frontend_workdir}} frontend pnpm test

frontend-coverage:
  {{compose}} run --rm --no-deps --user node --workdir {{frontend_workdir}} frontend pnpm test:coverage

frontend-test-host:
  cd frontend && pnpm test

frontend-lint:
  {{compose}} run --rm --no-deps --user node --workdir {{frontend_workdir}} frontend pnpm lint

frontend-lint-host:
  cd frontend && pnpm lint

frontend-typecheck:
  {{compose}} run --rm --no-deps --user node --workdir {{frontend_workdir}} frontend pnpm typecheck

frontend-typecheck-host:
  cd frontend && pnpm typecheck

frontend-build:
  mkdir -p frontend/.next-build
  {{compose}} run --rm --no-deps --user node --volume ./frontend/.next-build:{{frontend_workdir}}/.next --workdir {{frontend_workdir}} frontend pnpm build

frontend-build-host:
  cd frontend && pnpm build

migrate:
  {{compose}} run --rm --user vscode --workdir {{backend_workdir}} backend uv run alembic upgrade head

migrate-host:
  cd backend && uv run alembic upgrade head

seed-local-preview:
  {{compose}} exec -T --workdir {{backend_workdir}} backend uv run python -m codrut.tools.seed_local_preview

generate-client:
  {{compose}} run --rm --user node --workdir {{frontend_workdir}} frontend sh -lc 'OPENAPI_URL={{container_openapi_url}} pnpm generate-client'

generate-client-host:
  cd frontend && pnpm generate-client

export-openapi:
  {{compose}} run --rm --user vscode --workdir {{backend_workdir}} backend uv run python -m codrut.tools.export_openapi --output /workspace/docs/api/openapi.json

openapi-snapshot-check:
  {{compose}} run --rm --user vscode --workdir {{backend_workdir}} backend uv run python -m codrut.tools.export_openapi --check --output /workspace/docs/api/openapi.json

openapi-check:
  {{compose}} run --rm --user node --workdir {{frontend_workdir}} frontend sh -lc 'pnpm exec openapi-typescript {{container_openapi_url}} -o /tmp/codrut-openapi-schema.d.ts'

smoke:
  {{compose}} up -d --build
  {{compose}} exec -T backend sh -lc 'cd {{backend_workdir}} && uv run pytest tests/test_health.py'
