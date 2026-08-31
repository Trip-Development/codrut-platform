#!/usr/bin/env bash
#
# Punerea in proba (cody-proba). Se instaleaza la /usr/local/sbin/cody-test-deploy.sh
# si e comanda fortata a cheii inguste de punere, deci nu se poate cere altceva de la
# distanta: doar `deploy <sha> <utilizator>`.
#
# Pana la plicul 36 fisierul asta traia DOAR pe server, neversionat, iar punerea muta
# numai imaginile. Fisierul de configurare `compose.test.yaml` se cara cu mana, asa ca
# serverul putea ramane in urma depozitului fara ca cineva sa observe. Acum scriptul
# aduce singur configurarea, la aceeasi comitere cu imaginile.
#
# Dupa orice schimbare aici, se copiaza pe server:
#     scp infra/test/cody-test-deploy.sh cody-proba:/tmp/d.sh
#     ssh cody-proba 'sudo install -m 750 /tmp/d.sh /usr/local/sbin/cody-test-deploy.sh'
set -euo pipefail

DIR="/opt/cody-test"
if [[ ! -d "$DIR" ]]; then
  echo "Error: Directory $DIR does not exist." >&2
  exit 1
fi

NOU=""
curata() {
  docker logout ghcr.io >/dev/null 2>&1 || true
  [[ -n "$NOU" ]] && rm -f "$NOU"
  return 0
}
trap curata EXIT

# Parse and validate SSH_ORIGINAL_COMMAND
ORIGINAL_CMD="${SSH_ORIGINAL_COMMAND:-}"

if [[ -z "$ORIGINAL_CMD" ]]; then
  echo "Error: No command provided." >&2
  exit 1
fi

# Expected: deploy <sha> <utilizator>
read -r ACTION TARGET_SHA ACTOR REST_ARGS <<< "$ORIGINAL_CMD"

if [[ "$ACTION" != "deploy" || -n "${REST_ARGS:-}" ]]; then
  echo "Error: Unauthorized command attempted: $ORIGINAL_CMD" >&2
  exit 1
fi

if [[ ! "$TARGET_SHA" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "Error: Invalid SHA format (must be 40 hex chars): $TARGET_SHA" >&2
  exit 1
fi

if [[ ! "$ACTOR" =~ ^[A-Za-z0-9_-]{1,39}$ ]]; then
  echo "Error: Invalid actor username format: $ACTOR" >&2
  exit 1
fi

# Read GitHub token from stdin (handle trailing newline or EOF gracefully)
GITHUB_TOKEN=""
if ! IFS= read -r GITHUB_TOKEN && [[ -z "$GITHUB_TOKEN" ]]; then
  echo "Error: Failed to read GitHub token from stdin." >&2
  exit 1
fi

if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "Error: Empty GitHub token received." >&2
  exit 1
fi

echo "=== [Cody Test Deploy] Authenticating to GHCR as $ACTOR ==="
printf "%s\n" "$GITHUB_TOKEN" | docker login ghcr.io -u "$ACTOR" --password-stdin

echo "=== [Cody Test Deploy] Updating image tags in $DIR/.env ==="
BACKEND_IMG="ghcr.io/trip-development/codrut-platform-backend:test-${TARGET_SHA}"
FRONTEND_IMG="ghcr.io/trip-development/codrut-platform-frontend:test-${TARGET_SHA}"

sed -i "s|^BACKEND_IMAGE=.*|BACKEND_IMAGE=${BACKEND_IMG}|" "$DIR/.env"
sed -i "s|^FRONTEND_IMAGE=.*|FRONTEND_IMAGE=${FRONTEND_IMG}|" "$DIR/.env"

echo "=== [Cody Test Deploy] Fetching compose.test.yaml at ${TARGET_SHA} ==="
COMPOSE="$DIR/compose.test.yaml"
NOU="$(mktemp)"
COD=$(curl -sS -o "$NOU" -w "%{http_code}" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/Trip-Development/codrut-platform/contents/infra/test/compose.test.yaml?ref=${TARGET_SHA}" \
  || echo 000)

if [[ "$COD" != "200" || ! -s "$NOU" ]]; then
  echo "Warning: could not fetch compose.test.yaml (HTTP ${COD}). Keeping the file already on the server." >&2
elif cmp -s "$NOU" "$COMPOSE"; then
  echo "compose.test.yaml is already up to date."
else
  COPIE="${COMPOSE}.inainte-de-$(date -u +%Y-%m-%dT%H%M%SZ)"
  cp -a "$COMPOSE" "$COPIE"
  cp "$NOU" "$COMPOSE"
  # Un fisier stricat ar opri casa de proba, deci se verifica inainte sa ramana pus.
  if ! docker compose --env-file "$DIR/.env" -f "$COMPOSE" config >/dev/null 2>&1; then
    echo "Error: fetched compose.test.yaml is invalid; restoring the previous one." >&2
    cp -a "$COPIE" "$COMPOSE"
    exit 1
  fi
  echo "compose.test.yaml updated. Backup: ${COPIE}"
fi

cd "$DIR"

echo "=== [Cody Test Deploy] Pulling test images ==="
PULLED=0
for i in {1..30}; do
  if docker compose --env-file .env -f compose.test.yaml pull; then
    PULLED=1
    break
  fi
  echo "Pull failed (image may still be building). Retrying in 10s ($i/30)..."
  sleep 10
done

if [[ $PULLED -ne 1 ]]; then
  echo "Error: Failed to pull test images after 30 attempts." >&2
  exit 1
fi

echo "=== [Cody Test Deploy] Starting testdb and testredis ==="
docker compose --env-file .env -f compose.test.yaml up -d testdb testredis

echo "=== [Cody Test Deploy] Waiting for databases to become healthy ==="
MAX_WAIT=120
WAITED=0
while true; do
  STATUS=$(docker compose --env-file .env -f compose.test.yaml ps --format "{{.Service}}: {{.Health}}" 2>/dev/null || true)
  if [[ "$STATUS" =~ "testdb: healthy" && "$STATUS" =~ "testredis: healthy" ]]; then
    echo "Databases are healthy after ${WAITED}s."
    break
  fi
  if [[ $WAITED -ge $MAX_WAIT ]]; then
    echo "Error: Databases did not become healthy within ${MAX_WAIT}s. Status: $STATUS" >&2
    exit 1
  fi
  sleep 3
  WAITED=$((WAITED + 3))
done

echo "=== [Cody Test Deploy] Running database migrations ==="
docker compose --env-file .env -f compose.test.yaml run --rm -T testbackend alembic upgrade head

echo "=== [Cody Test Deploy] Starting all services ==="
docker compose --env-file .env -f compose.test.yaml up -d

echo "=== [Cody Test Deploy] Final Container Status ==="
docker compose --env-file .env -f compose.test.yaml ps

echo "=== [Cody Test Deploy] Completed Successfully ==="
