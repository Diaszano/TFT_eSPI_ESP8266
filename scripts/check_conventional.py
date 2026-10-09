#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RULESET_PATH = ROOT / ".github/rulesets/conventional.json"


def _load_patterns():
    if RULESET_PATH.exists():
        data = json.loads(RULESET_PATH.read_text())
        rules = {rule["type"]: rule["parameters"]["pattern"] for rule in data.get("rules", [])}
        return re.compile(rules["branch_name_pattern"]), re.compile(rules["commit_message_pattern"])
    branch = re.compile(
        r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)/[a-z0-9]+(-[a-z0-9]+)*$"
        r"|^(main|codex/execute-all-plans|release-please--branches--main|dependabot/[a-z0-9._/-]+)$"
    )
    commit = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?!?: .+")
    return branch, commit


BRANCH, COMMIT = _load_patterns()


def is_conventional_branch(branch):
    return bool(BRANCH.fullmatch(branch))


def is_conventional_commit(message):
    return bool(COMMIT.fullmatch(message))


def main(branch, base, head):
    valid = True
    if not is_conventional_branch(branch):
        print(f"Invalid branch name: {branch}", file=sys.stderr)
        valid = False

    result = subprocess.run(
        ["git", "log", "--format=%s", f"{base}..{head}"],
        check=True,
        capture_output=True,
        text=True,
    )
    for message in result.stdout.splitlines():
        if not is_conventional_commit(message):
            print(f"Invalid commit message: {message}", file=sys.stderr)
            valid = False
    return 0 if valid else 1


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: check_conventional.py BRANCH BASE_SHA HEAD_SHA")
    raise SystemExit(main(*sys.argv[1:]))
