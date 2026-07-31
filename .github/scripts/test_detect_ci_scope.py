import unittest

from detect_ci_scope import detect_scope


class DetectCiScopeTests(unittest.TestCase):
    def test_docs_only_skips_product_checks(self) -> None:
        self.assertEqual(
            detect_scope(["README.md", "docs/operations/runbook.md"]),
            {
                "backend": False,
                "frontend": False,
                "infra": False,
                "automation": False,
                "database": False,
                "contract": False,
            },
        )

    def test_frontend_runtime_change_runs_only_frontend_checks(self) -> None:
        self.assertEqual(
            detect_scope(["frontend/src/app/page.tsx"]),
            {
                "backend": False,
                "frontend": True,
                "infra": False,
                "automation": False,
                "database": False,
                "contract": False,
            },
        )

    def test_api_snapshot_runs_both_contract_surfaces(self) -> None:
        self.assertEqual(
            detect_scope(["docs/api/openapi.json"]),
            {
                "backend": True,
                "frontend": True,
                "infra": False,
                "automation": False,
                "database": False,
                "contract": True,
            },
        )

    def test_backend_source_change_checks_the_public_api_contract(self) -> None:
        scope = detect_scope(["backend/src/codrut/main.py"])

        self.assertTrue(scope["backend"])
        self.assertTrue(scope["contract"])

    def test_workflow_change_runs_only_automation_checks(self) -> None:
        self.assertEqual(
            detect_scope([".github/workflows/app-ci.yml"]),
            {
                "backend": False,
                "frontend": False,
                "infra": False,
                "automation": True,
                "database": False,
                "contract": False,
            },
        )

    def test_scope_rule_change_runs_only_automation_checks(self) -> None:
        self.assertEqual(
            detect_scope([".github/scripts/detect_ci_scope.py"]),
            {
                "backend": False,
                "frontend": False,
                "infra": False,
                "automation": True,
                "database": False,
                "contract": False,
            },
        )

    def test_docker_context_change_runs_build_surface_checks(self) -> None:
        self.assertEqual(
            detect_scope([".dockerignore"]),
            {
                "backend": True,
                "frontend": True,
                "infra": True,
                "automation": False,
                "database": False,
                "contract": False,
            },
        )

    def test_backup_change_runs_backend_and_infrastructure_checks(self) -> None:
        self.assertEqual(
            detect_scope(["infra/backup/backup.sh"]),
            {
                "backend": True,
                "frontend": False,
                "infra": True,
                "automation": False,
                "database": False,
                "contract": False,
            },
        )

    def test_database_change_enables_database_checks(self) -> None:
        self.assertEqual(
            detect_scope(["backend/migrations/versions/0057_example.py"]),
            {
                "backend": True,
                "frontend": False,
                "infra": False,
                "automation": False,
                "database": True,
                "contract": False,
            },
        )

    def test_service_change_does_not_run_public_contract_check(self) -> None:
        scope = detect_scope(["backend/src/codrut/modules/scoring/service.py"])

        self.assertTrue(scope["backend"])
        self.assertFalse(scope["contract"])

    def test_router_schema_and_shared_contract_changes_run_public_contract_check(
        self,
    ) -> None:
        router = detect_scope(["backend/src/codrut/modules/scoring/router.py"])
        schemas = detect_scope(["backend/src/codrut/modules/scoring/schemas.py"])
        shared_contract = detect_scope(["backend/src/codrut/contracts/emails.py"])

        self.assertTrue(router["contract"])
        self.assertTrue(schemas["contract"])
        self.assertTrue(shared_contract["contract"])


if __name__ == "__main__":
    unittest.main()
