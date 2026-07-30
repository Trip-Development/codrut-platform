import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from verify_release_tree import ReleaseTreeError, verify_release_tree

GIT_BINARY = shutil.which("git")


def _git(repository: Path, *args: str) -> str:
    if GIT_BINARY is None:
        raise RuntimeError("Git is required for release tree tests.")

    return subprocess.run(  # noqa: S603 - test arguments are constants
        [GIT_BINARY, *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class VerifyReleaseTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name)
        _git(self.repository, "init", "--initial-branch=dev")
        _git(self.repository, "config", "user.name", "Release Test")
        _git(self.repository, "config", "user.email", "release-test@example.com")

        (self.repository / "app.txt").write_text("base\n", encoding="utf-8")
        _git(self.repository, "add", "app.txt")
        _git(self.repository, "commit", "-m", "base")
        self.initial_sha = _git(self.repository, "rev-parse", "HEAD")

        (self.repository / "app.txt").write_text("release one\n", encoding="utf-8")
        _git(self.repository, "commit", "-am", "release one")
        self.first_dev_sha = _git(self.repository, "rev-parse", "HEAD")

        _git(self.repository, "switch", "--create", "prod", self.initial_sha)
        _git(self.repository, "merge", "--no-ff", "dev", "-m", "promote release one")
        self.first_prod_sha = _git(self.repository, "rev-parse", "HEAD")

        _git(self.repository, "switch", "dev")
        (self.repository / "app.txt").write_text("release two\n", encoding="utf-8")
        _git(self.repository, "commit", "-am", "release two")
        self.second_dev_sha = _git(self.repository, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_accepts_next_dev_promotion_without_back_merge(self) -> None:
        merge_tree, head_tree = verify_release_tree(
            self.repository,
            self.first_prod_sha,
            self.second_dev_sha,
        )

        self.assertEqual(merge_tree, head_tree)

    def test_rejects_prod_only_content(self) -> None:
        _git(self.repository, "switch", "prod")
        (self.repository / "prod-only.txt").write_text("drift\n", encoding="utf-8")
        _git(self.repository, "add", "prod-only.txt")
        _git(self.repository, "commit", "-m", "prod-only drift")
        drifted_prod_sha = _git(self.repository, "rev-parse", "HEAD")

        with self.assertRaisesRegex(ReleaseTreeError, "not present on dev"):
            verify_release_tree(
                self.repository,
                drifted_prod_sha,
                self.second_dev_sha,
            )

    def test_rejects_non_sha_input(self) -> None:
        with self.assertRaisesRegex(ReleaseTreeError, "full 40-character commit SHA"):
            verify_release_tree(
                self.repository,
                "prod",
                self.second_dev_sha,
            )


if __name__ == "__main__":
    unittest.main()
