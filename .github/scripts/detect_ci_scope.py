#!/usr/bin/env python3
"""Map changed repository paths to the smallest safe CI scope."""

from __future__ import annotations

import sys
from pathlib import PurePosixPath


def _matches(path: str, prefixes: tuple[str, ...], exact: tuple[str, ...] = ()) -> bool:
    return path in exact or path.startswith(prefixes)


def detect_scope(paths: list[str]) -> dict[str, bool]:
    normalized = [str(PurePosixPath(path.strip())) for path in paths if path.strip()]
    automation = any(
        path.startswith((".github/workflows/", ".github/scripts/")) for path in normalized
    )

    backend = any(
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
    frontend = any(
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
    infra = any(
        _matches(
            path,
            ("infra/",),
            (
                ".dockerignore",
                "compose.backup.yaml",
                "compose.yaml",
                "compose.dev.yaml",
                "compose.prod.yaml",
                ".env.example",
            ),
        )
        for path in normalized
    )

    database = any(
        _matches(
            path,
            (
                "backend/migrations/",
            ),
            (
                "backend/alembic.ini",
                "backend/src/codrut/core/database.py",
            ),
        )
        or path.endswith("/models.py")
        for path in normalized
    )

    contract = any(
        path in {
            "backend/pyproject.toml",
            "backend/uv.lock",
            "docs/api/openapi.json",
            "frontend/src/api/generated/schema.d.ts",
        }
        or path == "backend/src/codrut/main.py"
        or path.startswith("backend/src/codrut/api/")
        or path.startswith("backend/src/codrut/contracts/")
        or path.endswith(("/router.py", "/schemas.py"))
        for path in normalized
    )

    return {
        "backend": backend,
        "frontend": frontend,
        "infra": infra,
        "automation": automation,
        "database": database,
        "contract": contract,
    }


def main() -> None:
    scope = detect_scope(sys.stdin.read().splitlines())
    for name, enabled in scope.items():
        print(f"{name}={str(enabled).lower()}")


if __name__ == "__main__":
    main()
