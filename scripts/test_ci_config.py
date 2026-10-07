import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CIConfigTests(unittest.TestCase):
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
