#!/usr/bin/env bash

set -euo pipefail

output_path="${1:-previous-images.env}"
rollback_environment_path="${2:-.env.rollback}"

if [[ ! -f .env ]]; then
  existing_containers="$(
    docker ps -a \
      --filter "label=com.docker.compose.project=codrut-platform" \
      --format '{{.ID}}'
  )"
  if [[ -n "$existing_containers" ]]; then
    echo "Cannot capture rollback environment: .env is missing while Codrut containers exist." >&2
    exit 1
  fi
  : >"$output_path"
  exit 0
fi

compose_project="$(
  awk -F= '$1 == "COMPOSE_PROJECT_NAME" { print $2 }' .env
)"
compose_project="${compose_project:-codrut-platform}"

running_image() {
  local service="$1"
  local -a container_ids

  container_ids=()
  while IFS= read -r container_id; do
    if [[ -n "$container_id" ]]; then
      container_ids+=("$container_id")
    fi
  done < <(
    docker ps -a \
      --filter "label=com.docker.compose.project=${compose_project}" \
      --filter "label=com.docker.compose.service=${service}" \
      --format '{{.ID}}'
  )
  if [[ "${#container_ids[@]}" -ne 1 ]]; then
    echo "Cannot capture rollback image: expected one ${service} service container." >&2
    exit 1
  fi

  docker inspect --format '{{.Config.Image}}' "${container_ids[0]}"
}

backend_image="$(running_image backend)"
worker_image="$(running_image worker)"
frontend_image="$(running_image frontend)"

if [[ "$worker_image" != "$backend_image" ]]; then
  echo "Cannot capture rollback images: backend and worker refs differ." >&2
  exit 1
fi

docker image inspect "$backend_image" "$frontend_image" >/dev/null

temporary_path="${output_path}.next"
rollback_temporary_path="${rollback_environment_path}.next"
umask 077
{
  printf 'BACKEND_IMAGE=%s\n' "$backend_image"
  printf 'FRONTEND_IMAGE=%s\n' "$frontend_image"
} >"$temporary_path"

backend_written=false
frontend_written=false
while IFS= read -r line || [[ -n "$line" ]]; do
  case "$line" in
    BACKEND_IMAGE=*)
      printf 'BACKEND_IMAGE=%s\n' "$backend_image"
      backend_written=true
      ;;
    FRONTEND_IMAGE=*)
      printf 'FRONTEND_IMAGE=%s\n' "$frontend_image"
      frontend_written=true
      ;;
    *)
      printf '%s\n' "$line"
      ;;
  esac
done <.env >"$rollback_temporary_path"

if [[ "$backend_written" != "true" ]]; then
  printf 'BACKEND_IMAGE=%s\n' "$backend_image" >>"$rollback_temporary_path"
fi
if [[ "$frontend_written" != "true" ]]; then
  printf 'FRONTEND_IMAGE=%s\n' "$frontend_image" >>"$rollback_temporary_path"
fi

chmod 0600 "$rollback_temporary_path"
mv "$rollback_temporary_path" "$rollback_environment_path"
mv "$temporary_path" "$output_path"
