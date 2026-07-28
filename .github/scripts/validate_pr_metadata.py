#!/usr/bin/env python3
"""Validate pull request metadata used by the required policy check."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Collection


TITLE_PATTERN = re.compile(
    r"^(feat|fix|build|docs|chore|ci|refactor|perf|test|revert)"
    r"(\([a-z0-9._/-]+\))?!?: .+"
)
ISSUE_PATTERN = re.compile(
    r"(^|[\s(])"
    r"(close[sd]?|fix(e[sd])?|resolve[sd]?|refs?|references?)"
    r"\s+#[0-9]+([\s,.)]|$)",
    re.IGNORECASE,
)


def validate_pr_metadata(
    *,
    title: str,
    body: str,
    labels: Collection[str],
    author: str,
    head_branch: str,
) -> list[str]:
    errors: list[str] = []

    if not TITLE_PATTERN.match(title):
        errors.append(
            "PR title must follow Conventional Commits, for example: "
            "build(repo): add delivery checks."
        )

    if "admin-exempt" in labels:
        return errors

    if author == "dependabot[bot]" and head_branch.startswith("dependabot/"):
        return errors

    if not ISSUE_PATTERN.search(body):
        errors.append(
            "PR body must include Closes #123 or Refs #123, unless labeled "
            "admin-exempt."
        )

    return errors


def main() -> int:
    try:
        labels = json.loads(os.environ.get("PR_LABELS", "[]"))
    except json.JSONDecodeError as exc:
        print(f"PR_LABELS must be valid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(labels, list) or not all(
        isinstance(label, str) for label in labels
    ):
        print("PR_LABELS must be a JSON array of strings.", file=sys.stderr)
        return 1

    author = os.environ.get("PR_AUTHOR", "")
    head_branch = os.environ.get("HEAD_BRANCH", "")
    errors = validate_pr_metadata(
        title=os.environ.get("PR_TITLE", ""),
        body=os.environ.get("PR_BODY", ""),
        labels=labels,
        author=author,
        head_branch=head_branch,
    )
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    if "admin-exempt" in labels:
        print("Administrative exemption label present.")
    elif author == "dependabot[bot]" and head_branch.startswith("dependabot/"):
        print("Trusted Dependabot update; manual issue reference is not required.")
    else:
        print("Pull request metadata is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
