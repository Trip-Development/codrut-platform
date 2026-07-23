#!/usr/bin/env python3
"""Map changed repository paths to the smallest safe CI scope."""

from __future__ import annotations

import sys
from pathlib import PurePosixPath


def _matches(path: str, prefixes: tuple[str, ...], exact: tuple[str, ...] = ()) -> bool:
    return path in exact or path.startswith(prefixes)


def detect_scope(paths: list[str]) -> dict[str, bool]:
    normalized = [str(PurePosixPath(path.strip())) for path in paths if path.strip()]
    workflow_change = any(
        path.startswith((".github/workflows/", ".github/scripts/")) for path in normalized
    )

    backend = workflow_change or any(
        _matches(
            path,
            ("backend/", "infra/backup/"),
            (
                ".dockerignore",
                "compose.backup.yaml",
                "infra/docker/Dockerfile.backend",
                "docs/api/openapi.json",
            ),
        )
        for path in normalized
    )
    frontend = workflow_change or any(
        _matches(
            path,
            ("frontend/",),
            (
                ".dockerignore",
                "infra/docker/Dockerfile.frontend",
                "docs/api/openapi.json",
            ),
        )
        for path in normalized
    )
    infra = workflow_change or any(
        _matches(
            path,
            ("infra/",),
            (
                ".dockerignore",
                "compose.backup.yaml",
                "compose.yaml",
                "compose.dev.yaml",
                "compose.e2e.yaml",
                "compose.prod.yaml",
                ".env.example",
            ),
        )
        for path in normalized
    )

    runtime_change = any(
        _matches(
            path,
            (
                "backend/src/",
                "backend/migrations/",
                "frontend/src/",
                "frontend/app/",
                "frontend/e2e/",
            ),
            (
                "backend/pyproject.toml",
                "backend/uv.lock",
                "frontend/package.json",
                "frontend/pnpm-lock.yaml",
                "frontend/next.config.mjs",
                "frontend/playwright.config.ts",
                ".dockerignore",
                "compose.backup.yaml",
                "compose.yaml",
                "compose.dev.yaml",
                "compose.e2e.yaml",
                "infra/docker/Dockerfile.backend",
                "infra/docker/Dockerfile.frontend",
                ".github/workflows/_e2e-playwright.yml",
            ),
        )
        for path in normalized
    )

    return {
        "backend": backend,
        "frontend": frontend,
        "infra": infra,
        "e2e": workflow_change or runtime_change,
    }


def main() -> None:
    scope = detect_scope(sys.stdin.read().splitlines())
    for name, enabled in scope.items():
        print(f"{name}={str(enabled).lower()}")


if __name__ == "__main__":
    main()
