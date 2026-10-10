import json
import re
import unittest
import yaml
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
            ["build", "arduino-build", "lint", "arduino-lint", "pio-pack", "pr-title", "docs", "analyze"],
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


    def test_required_jobs_run_effective_gates(self):
        workflows = {name: yaml.safe_load((ROOT / f".github/workflows/{name}.yml").read_text())
                     for name in ("build", "lint")}
        def runs(workflow, job):
            return [step["run"] for step in workflows[workflow]["jobs"][job]["steps"] if "run" in step]
        self.assertIn("make layout-check", runs("build", "build"))
        self.assertIn("make warnings", runs("build", "build"))
        self.assertIn("make test-compile", runs("build", "build"))
        self.assertIn("make format-check", runs("lint", "lint"))
        self.assertIn("make test-native", runs("lint", "lint"))
        self.assertIn("make test-host", runs("lint", "lint"))
        self.assertIn("make tidy-native", runs("lint", "lint"))
        self.assertIn("make test-python", runs("lint", "lint"))
        self.assertIn("make package-check", runs("lint", "pio-pack"))
        self.assertIn("make build-arduino", runs("build", "arduino-build"))
        for workflow in workflows.values():
            for job in workflow["jobs"].values():
                self.assertFalse(job.get("continue-on-error", False))
                for step in job["steps"]:
                    self.assertFalse(step.get("continue-on-error", False))

    def test_arduino_download_checks_exact_version_digest_and_core(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/build.yml").read_text())
        job = workflow["jobs"]["arduino-build"]
        self.assertEqual(job["env"]["ARDUINO_CLI_VERSION"], "1.3.1")
        self.assertEqual(job["env"]["ARDUINO_CLI_SHA256"],
                         "376428d7d45be640c00812a71612e1742edc2f5f9ee3742a2d6da7870e079588")
        commands = "\n".join(step.get("run", "") for step in job["steps"])
        self.assertIn("sha256sum -c -", commands)
        self.assertLess(commands.index("sha256sum -c -"), commands.index("tar -xzf"))
        self.assertIn("esp8266:esp8266@3.1.2", commands)
        self.assertEqual(job["permissions"], {"contents": "read"})

    def test_lint_runs_fuzz_smoke(self):
        workflow = (ROOT / ".github/workflows/lint.yml").read_text()
        self.assertIn("python3 tests/host/run.py --case scroll --fuzz", workflow)

    def test_fuzz_workflow_config(self):
        workflow_text = (ROOT / ".github/workflows/fuzz.yml").read_text()
        workflow = yaml.safe_load(workflow_text)
        self.assertEqual(workflow["permissions"], {})
        job = workflow["jobs"]["fuzz"]
        self.assertEqual(job["permissions"], {"contents": "read"})
        steps = job["steps"]
        step_commands = [s.get("run", "") for s in steps]
        self.assertTrue(any("python3 tests/host/run.py --case scroll --fuzz" in cmd for cmd in step_commands))
        self.assertIn("actions/upload-artifact@65c4c4a1ddee5b72f698fdd19549f0f0fb45cf08", workflow_text)
        self.assertIn("schedule:", workflow_text)
        self.assertIn("workflow_dispatch:", workflow_text)


if __name__ == "__main__":
    unittest.main()
