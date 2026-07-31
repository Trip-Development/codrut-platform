#!/usr/bin/env bash

set -euo pipefail

expected_backend_image="${1:?expected backend image is required}"
expected_frontend_image="${2:?expected frontend image is required}"
compose=(docker compose --env-file .env -f compose.yaml -f compose.prod.yaml)

assert_service_image() {
  local service="$1"
  local expected_image="$2"
  local container_id
  local actual_image

  container_id="$("${compose[@]}" ps -q "$service")"
  if [[ -z "$container_id" ]]; then
    echo "${service} is not running." >&2
    exit 1
  fi

  actual_image="$(docker inspect --format '{{.Config.Image}}' "$container_id")"
  if [[ "$actual_image" != "$expected_image" ]]; then
    echo "${service} uses ${actual_image}; expected ${expected_image}." >&2
    exit 1
  fi
}

assert_service_image backend "$expected_backend_image"
assert_service_image worker "$expected_backend_image"
assert_service_image frontend "$expected_frontend_image"
