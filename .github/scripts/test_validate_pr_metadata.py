import unittest

from validate_pr_metadata import validate_pr_metadata


class ValidatePrMetadataTests(unittest.TestCase):
    def validate(
        self,
        *,
        title: str = "fix(api): handle missing project",
        body: str = "Refs #123",
        labels: tuple[str, ...] = (),
        author: str = "developer",
        head_branch: str = "fix/missing-project",
    ) -> list[str]:
        return validate_pr_metadata(
            title=title,
            body=body,
            labels=labels,
            author=author,
            head_branch=head_branch,
        )

    def test_accepts_human_pr_with_conventional_title_and_issue(self) -> None:
        self.assertEqual(self.validate(), [])

    def test_rejects_invalid_title_even_with_admin_exemption(self) -> None:
        errors = self.validate(title="Update the thing", labels=("admin-exempt",))
        self.assertEqual(len(errors), 1)
        self.assertIn("Conventional Commits", errors[0])

    def test_admin_exemption_only_skips_issue_reference(self) -> None:
        self.assertEqual(self.validate(body="", labels=("admin-exempt",)), [])

    def test_accepts_dependabot_own_branch_without_issue_reference(self) -> None:
        self.assertEqual(
            self.validate(
                title="chore(deps): bump example from 1.0.0 to 1.0.1",
                body="",
                author="dependabot[bot]",
                head_branch="dependabot/pip/backend/example-1.0.1",
            ),
            [],
        )

    def test_rejects_dependabot_identity_on_non_dependabot_branch(self) -> None:
        errors = self.validate(
            body="",
            author="dependabot[bot]",
            head_branch="feature/unrelated",
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("Refs #123", errors[0])

    def test_rejects_dependabot_branch_from_another_author(self) -> None:
        errors = self.validate(
            body="",
            author="developer",
            head_branch="dependabot/pip/backend/example-1.0.1",
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("Refs #123", errors[0])


if __name__ == "__main__":
    unittest.main()
