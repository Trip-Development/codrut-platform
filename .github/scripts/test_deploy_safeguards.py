import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CAPACITY_SCRIPT = REPOSITORY_ROOT / ".github/scripts/check_vps_capacity.sh"
RETENTION_SCRIPT = REPOSITORY_ROOT / ".github/scripts/retain_codrut_images.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class DeploySafeguardTests(unittest.TestCase):
    def _run_capacity(
        self,
        *,
        available_kib: int,
        used_percent: int,
        args: tuple[str, ...],
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            binary_dir = Path(temp_dir)
            _write_executable(
                binary_dir / "df",
                "#!/bin/sh\n"
                "printf '%s\\n' "
                "'Filesystem 1024-blocks Used Available Capacity Mounted on' "
                f"'mock 100000000 1 {available_kib} {used_percent}% /'\n",
            )
            environment = {
                **os.environ,
                "PATH": f"{binary_dir}:{os.environ['PATH']}",
            }
            return subprocess.run(
                [str(CAPACITY_SCRIPT), *args],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

    def test_preflight_rejects_excess_usage_before_pull(self) -> None:
        result = self._run_capacity(
            available_kib=20 * 1024 * 1024,
            used_percent=86,
            args=("preflight", "/", "85", "8"),
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("exceeds 85%", result.stderr)

    def test_preflight_rejects_less_than_eight_gib_free(self) -> None:
        result = self._run_capacity(
            available_kib=(8 * 1024 * 1024) - 1,
            used_percent=50,
            args=("preflight", "/", "85", "8"),
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("below 8GiB", result.stderr)

    def test_scheduled_capacity_warns_at_eighty_and_fails_at_ninety(self) -> None:
        warning = self._run_capacity(
            available_kib=12 * 1024 * 1024,
            used_percent=80,
            args=("scheduled", "/", "80", "90"),
        )
        failure = self._run_capacity(
            available_kib=4 * 1024 * 1024,
            used_percent=90,
            args=("scheduled", "/", "80", "90"),
        )

        self.assertEqual(warning.returncode, 0)
        self.assertIn("CAPACITY_STATUS=warning", warning.stdout)
        self.assertEqual(failure.returncode, 1)
        self.assertIn("CAPACITY_STATUS=failure", failure.stdout)

    def test_retention_removes_only_obsolete_codrut_tags(self) -> None:
        current_backend = (
            "ghcr.io/trip-development/codrut-platform-backend:sha-current"
        )
        previous_backend = (
            "ghcr.io/trip-development/codrut-platform-backend:sha-previous"
        )
        current_frontend = (
            "ghcr.io/trip-development/codrut-platform-frontend:sha-current"
        )
        previous_frontend = (
            "ghcr.io/trip-development/codrut-platform-frontend:sha-previous"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            docker_log = temp_path / "docker.log"
            _write_executable(
                temp_path / "docker",
                "#!/bin/sh\n"
                "printf 'call %s\\n' \"$*\" >> \"$DOCKER_LOG\"\n"
                "case \"$1:$2\" in\n"
                "  image:inspect) exit 0 ;;\n"
                "  image:ls)\n"
                "    printf '%s\\n' \\\n"
                f"      '{current_backend}' \\\n"
                f"      '{previous_backend}' \\\n"
                "      'ghcr.io/trip-development/codrut-platform-backend:sha-old' \\\n"
                f"      '{current_frontend}' \\\n"
                f"      '{previous_frontend}' \\\n"
                "      'ghcr.io/trip-development/codrut-platform-frontend:sha-old' \\\n"
                "      'postgres:17-bookworm'\n"
                "    ;;\n"
                "  image:rm) printf 'rm %s\\n' \"$4\" >> \"$DOCKER_LOG\" ;;\n"
                "  image:prune) printf 'prune\\n' >> \"$DOCKER_LOG\" ;;\n"
                "  *) exit 64 ;;\n"
                "esac\n",
            )
            result = subprocess.run(
                [
                    str(RETENTION_SCRIPT),
                    current_backend,
                    previous_backend,
                    current_frontend,
                    previous_frontend,
                ],
                check=False,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{temp_path}:{os.environ['PATH']}",
                    "DOCKER_LOG": str(docker_log),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            actions = docker_log.read_text(encoding="utf-8")
            self.assertIn("codrut-platform-backend:sha-old", actions)
            self.assertIn("codrut-platform-frontend:sha-old", actions)
            self.assertNotIn("postgres:17-bookworm", actions)
            self.assertNotIn(f"rm {current_backend}", actions)
            self.assertNotIn(f"rm {previous_backend}", actions)
            self.assertIn("prune", actions)

    def test_retention_refuses_non_codrut_repository(self) -> None:
        result = subprocess.run(
            [
                str(RETENTION_SCRIPT),
                "ghcr.io/example/unrelated:current",
                "ghcr.io/example/unrelated:previous",
                "ghcr.io/example/codrut-platform-frontend:current",
                "ghcr.io/example/codrut-platform-frontend:previous",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("outside the Codrut backend repository", result.stderr)

    def test_retention_occurs_only_after_public_readiness(self) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github/workflows/_deploy-vps.yml"
        ).read_text(encoding="utf-8")

        self.assertLess(
            workflow.index("check_vps_capacity.sh preflight"),
            workflow.index('"${compose[@]}" pull'),
        )
        self.assertLess(
            workflow.index("Public health check passed"),
            workflow.index("bash ./retain_codrut_images.sh"),
        )
        self.assertNotIn("docker system prune", workflow)

    def test_deploy_verifies_active_log_rotation_for_every_service(self) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github/workflows/_deploy-vps.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("assert_bounded_log_config()", workflow)
        self.assertIn(
            "for service in traefik frontend backend worker db redis",
            workflow,
        )
        self.assertIn('"$max_size" != "10m"', workflow)
        self.assertIn('"$max_file" != "5"', workflow)

    def test_privacy_bridge_requires_fingerprint_aware_expand_release(self) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github/workflows/_deploy-vps.yml"
        ).read_text(encoding="utf-8")

        guard = workflow.index("pre_migration_revision=")
        migrate = workflow.index('backend alembic upgrade head')
        self.assertLess(guard, migrate)
        self.assertIn("deploy the 0052 expand release first", workflow)
        self.assertIn("hasattr(EmailSuppression, 'email_fingerprint')", workflow)


if __name__ == "__main__":
    unittest.main()
