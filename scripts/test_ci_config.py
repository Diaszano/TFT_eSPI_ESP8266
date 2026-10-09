import json
import re
import unittest
from pathlib import Path

from scripts.check_conventional import is_conventional_branch, is_conventional_commit


ROOT = Path(__file__).resolve().parent.parent


class CIConfigTests(unittest.TestCase):
    def test_lint_workflow_uses_valid_python_module_commands(self):
        workflow = (ROOT / ".github/workflows/lint.yml").read_text()
        self.assertNotIn("python -m python -m", workflow)
        self.assertIn("python -m pip install --require-hashes", workflow)

    def test_lint_checks_downloaded_gitleaks_and_working_tree(self):
        workflow = (ROOT / ".github/workflows/lint.yml").read_text()
        self.assertIn('-o "gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"', workflow)
        self.assertIn('tar -xzf "gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" gitleaks', workflow)
        self.assertIn("gitleaks dir . --redact", workflow)

    def test_codeql_context_uses_job_id(self):
        workflow = (ROOT / ".github/workflows/codeql.yml").read_text()
        job = re.search(r"(?ms)^  analyze:\n(.*?)(?=^  [a-z][a-z0-9-]*:|\Z)", workflow)
        self.assertIsNotNone(job)
        self.assertNotRegex(job.group(1), r"(?m)^    name:")

    def test_ruleset_targets_branch_and_default_branch_ref(self):
        ruleset = json.loads((ROOT / ".github/rulesets/main.json").read_text())
        self.assertEqual(ruleset["target"], "branch")
        self.assertEqual(ruleset["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        required_checks = next(rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks")["parameters"]["required_status_checks"]
        self.assertEqual(
            [check["context"] for check in required_checks],
            ["build", "lint", "arduino-lint", "pio-pack", "pr-title", "docs", "analyze"],
        )
        self.assertTrue(all(check["integration_id"] == 15368 for check in required_checks))

    def test_conventional_ruleset_patterns_and_automation_branches(self):
        ruleset = json.loads((ROOT / ".github/rulesets/conventional.json").read_text())
        rules = {rule["type"]: rule["parameters"]["pattern"] for rule in ruleset["rules"]}
        branch_pattern = re.compile(rules["branch_name_pattern"])
        commit_pattern = re.compile(rules["commit_message_pattern"])

        self.assertEqual(ruleset["conditions"]["ref_name"]["include"], ["~ALL"])
        for branch in ("feat/add-display", "fix/st7789-init", "main", "codex/execute-all-plans",
                       "dependabot/github_actions/actions-08422bfd53", "release-please--branches--main"):
            self.assertRegex(branch, branch_pattern)
        for branch in ("feature/add-display", "Feat/add-display", "feat/Add-Display"):
            self.assertNotRegex(branch, branch_pattern)

        for message in ("feat: add display", "fix(st7789): initialize panel", "refactor!: change API"):
            self.assertRegex(message, commit_pattern)
        for message in ("Add display", "Feat: add display", "fix: ", "feat add display"):
            self.assertNotRegex(message, commit_pattern)

    def test_conventional_branch_and_commit_formats(self):
        for branch in ("feat/add-display", "fix/st7789-init", "main", "codex/execute-all-plans",
                       "dependabot/github_actions/actions-08422bfd53", "release-please--branches--main"):
            self.assertTrue(is_conventional_branch(branch), branch)
        for branch in ("feature/add-display", "Feat/add-display", "feat/Add-Display"):
            self.assertFalse(is_conventional_branch(branch), branch)

        for message in ("feat: add display", "fix(st7789): initialize panel", "refactor!: change API"):
            self.assertTrue(is_conventional_commit(message), message)
        for message in ("Add display", "Feat: add display", "fix: ", "feat add display"):
            self.assertFalse(is_conventional_commit(message), message)

    def test_lint_enforces_conventions_on_pull_requests(self):
        workflow = (ROOT / ".github/workflows/lint.yml").read_text()
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("scripts/check_conventional.py", workflow)

    def test_release_please_manifest_has_root_package(self):
        config = json.loads((ROOT / "release-please-config.json").read_text())
        self.assertIn(".", config["packages"])
        self.assertEqual(config["packages"]["."]["release-type"], "simple")

    def test_release_sync_checks_out_same_repository_head_branch(self):
        workflow = (ROOT / ".github/workflows/release-please.yml").read_text()
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", workflow)
        self.assertIn("ref: ${{ github.head_ref }}", workflow)

    def test_docs_concurrency_is_scoped_by_ref(self):
        workflow = (ROOT / ".github/workflows/docs.yml").read_text()
        self.assertRegex(workflow, r"(?m)^  group: .*github\.ref")

    def test_pull_request_title_rechecks_after_edit(self):
        workflow = (ROOT / ".github/workflows/lint.yml").read_text()
        self.assertRegex(workflow, r"(?ms)^  pull_request:\n    types:.*\bedited\b")


if __name__ == "__main__":
    unittest.main()
