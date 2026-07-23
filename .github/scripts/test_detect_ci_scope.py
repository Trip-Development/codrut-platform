import unittest
from pathlib import Path

from detect_ci_scope import detect_scope


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class DetectCiScopeTests(unittest.TestCase):
    def test_docs_only_skips_product_checks(self) -> None:
        self.assertEqual(
            detect_scope(["README.md", "docs/operations/runbook.md"]),
            {"backend": False, "frontend": False, "infra": False, "e2e": False},
        )

    def test_frontend_runtime_change_runs_frontend_and_e2e(self) -> None:
        self.assertEqual(
            detect_scope(["frontend/src/app/page.tsx"]),
            {"backend": False, "frontend": True, "infra": False, "e2e": True},
        )

    def test_api_snapshot_runs_both_contract_surfaces_without_e2e(self) -> None:
        self.assertEqual(
            detect_scope(["docs/api/openapi.json"]),
            {"backend": True, "frontend": True, "infra": False, "e2e": False},
        )

    def test_workflow_change_runs_every_check(self) -> None:
        self.assertEqual(
            detect_scope([".github/workflows/app-ci.yml"]),
            {"backend": True, "frontend": True, "infra": True, "e2e": True},
        )

    def test_scope_rule_change_runs_every_check(self) -> None:
        self.assertEqual(
            detect_scope([".github/scripts/detect_ci_scope.py"]),
            {"backend": True, "frontend": True, "infra": True, "e2e": True},
        )

    def test_docker_context_change_runs_every_runtime_check(self) -> None:
        self.assertEqual(
            detect_scope([".dockerignore"]),
            {"backend": True, "frontend": True, "infra": True, "e2e": True},
        )

    def test_backup_change_runs_backend_and_infrastructure_checks(self) -> None:
        self.assertEqual(
            detect_scope(["infra/backup/backup.sh"]),
            {"backend": True, "frontend": False, "infra": True, "e2e": False},
        )

    def test_app_ci_grants_permissions_required_by_reusable_e2e(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github/workflows/app-ci.yml").read_text(
            encoding="utf-8"
        )
        permissions = workflow.split("permissions:", 1)[1].split("concurrency:", 1)[0]

        self.assertIn("contents: read", permissions)
        self.assertIn("packages: read", permissions)


if __name__ == "__main__":
    unittest.main()
