#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 4 ]]; then
  echo "Usage: retain_codrut_images.sh CURRENT_BACKEND PREVIOUS_BACKEND CURRENT_FRONTEND PREVIOUS_FRONTEND" >&2
  exit 2
fi

current_backend="$1"
previous_backend="$2"
current_frontend="$3"
previous_frontend="$4"

repository_from_ref() {
  local ref="$1"
  local final_component

  if [[ -z "$ref" || "$ref" == *@* ]]; then
    echo "Image refs must be non-empty tag refs; received ${ref:-empty}." >&2
    return 1
  fi
  final_component="${ref##*/}"
  if [[ "$final_component" != *:* ]]; then
    echo "Image ref must include an explicit tag: ${ref}." >&2
    return 1
  fi
  printf '%s\n' "${ref%:*}"
}

backend_repository="$(repository_from_ref "$current_backend")"
frontend_repository="$(repository_from_ref "$current_frontend")"

if [[ "$backend_repository" != */codrut-platform-backend && "$backend_repository" != "codrut-platform-backend" ]]; then
  echo "Refusing retention outside the Codrut backend repository: ${backend_repository}." >&2
  exit 1
fi
if [[ "$frontend_repository" != */codrut-platform-frontend && "$frontend_repository" != "codrut-platform-frontend" ]]; then
  echo "Refusing retention outside the Codrut frontend repository: ${frontend_repository}." >&2
  exit 1
fi
if [[ "$backend_repository" == "$frontend_repository" ]]; then
  echo "Backend and frontend repositories must be distinct." >&2
  exit 1
fi

if [[ -z "$previous_backend" || -z "$previous_frontend" ]]; then
  echo "Skipping image retention because both previous rollback refs are not yet available."
  exit 0
fi

if [[ "$(repository_from_ref "$previous_backend")" != "$backend_repository" ]]; then
  echo "Previous backend ref is not in ${backend_repository}: ${previous_backend}." >&2
  exit 1
fi
if [[ "$(repository_from_ref "$previous_frontend")" != "$frontend_repository" ]]; then
  echo "Previous frontend ref is not in ${frontend_repository}: ${previous_frontend}." >&2
  exit 1
fi

retained_refs=(
  "$current_backend"
  "$previous_backend"
  "$current_frontend"
  "$previous_frontend"
)

is_retained() {
  local candidate="$1"
  local retained_ref
  for retained_ref in "${retained_refs[@]}"; do
    if [[ "$candidate" == "$retained_ref" ]]; then
      return 0
    fi
  done
  return 1
}

for ref in "${retained_refs[@]}"; do
  if ! docker image inspect "$ref" >/dev/null 2>&1; then
    echo "Rollback retention blocked: required image is unavailable locally: ${ref}." >&2
    exit 1
  fi
done

removed=0
while IFS= read -r ref; do
  [[ -n "$ref" && "$ref" != *":<none>" ]] || continue
  repository="${ref%:*}"
  if [[ "$repository" != "$backend_repository" && "$repository" != "$frontend_repository" ]]; then
    continue
  fi
  if is_retained "$ref"; then
    continue
  fi
  docker image rm -- "$ref"
  removed=$((removed + 1))
done < <(docker image ls --format '{{.Repository}}:{{.Tag}}')

docker image prune --force

for ref in "${retained_refs[@]}"; do
  docker image inspect "$ref" >/dev/null
done

echo "Retained current and rollback Codrut image refs; removed ${removed} obsolete tag(s)."
