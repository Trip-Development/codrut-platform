#!/usr/bin/env python3
"""Verify that a dev-to-prod merge introduces exactly the dev tree."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

GIT_BINARY = shutil.which("git")
COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


class ReleaseTreeError(RuntimeError):
    """Raised when a proposed production merge is not an exact dev promotion."""


def _git(
    repository: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if GIT_BINARY is None:
        raise ReleaseTreeError("Git is required to verify a production release tree.")

    result = subprocess.run(  # noqa: S603 - arguments are validated SHAs or constants
        [GIT_BINARY, *args],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise ReleaseTreeError(detail)
    return result


def verify_release_tree(repository: Path, base_sha: str, head_sha: str) -> tuple[str, str]:
    """Return merge and head tree IDs when the proposed merge exactly matches head."""

    for name, value in (("base", base_sha), ("head", head_sha)):
        if COMMIT_SHA_PATTERN.fullmatch(value) is None:
            raise ReleaseTreeError(f"{name} must be a full 40-character commit SHA.")

    merge_result = _git(repository, "merge-tree", "--write-tree", base_sha, head_sha)
    merge_tree = merge_result.stdout.splitlines()[0].strip()
    head_tree = _git(repository, "rev-parse", f"{head_sha}^{{tree}}").stdout.strip()

    if not merge_tree or merge_tree != head_tree:
        raise ReleaseTreeError(
            "Production contains changes that are not present on dev. "
            f"Proposed merge tree {merge_tree or 'unknown'} does not match dev tree {head_tree}. "
            "Move the production-only change through dev before promoting."
        )

    return merge_tree, head_tree


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_sha", help="Current prod commit")
    parser.add_argument("head_sha", help="Dev commit proposed for promotion")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()

    merge_tree, _ = verify_release_tree(
        args.repository.resolve(),
        args.base_sha,
        args.head_sha,
    )
    print(f"Release merge is an exact dev promotion ({merge_tree}).")


if __name__ == "__main__":
    try:
        main()
    except ReleaseTreeError as error:
        raise SystemExit(str(error)) from error
