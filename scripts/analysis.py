#!/usr/bin/env python3
"""Build and compare owned compiler diagnostics for the pinned ESP8266 target."""

import argparse
import hashlib
import json
import pathlib
import platform
import re
import shutil
import subprocess
import sys
from typing import Callable


_WARNING = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):\d+: warning: (?P<message>.*?)(?: \[(?P<check>-W[^]]+)\])?$"
)
_PROFILE_FIELDS = {"platform", "toolchain", "setup_sha256", "flags"}
_FINDING_FIELDS = {"path", "check", "message", "context_sha256", "line"}


def diagnostic_key(finding: dict[str, str | int]) -> tuple[str, str, str, str]:
    """Identify a diagnostic independently of its current source line."""
    missing = _FINDING_FIELDS - finding.keys()
    if missing:
        raise ValueError(f"diagnostic missing fields: {', '.join(sorted(missing))}")
    return (
        str(finding["path"]),
        str(finding["check"]),
        _normalize(str(finding["message"])),
        str(finding["context_sha256"]),
    )


def compare_findings(
    actual: list[dict], baseline: dict, profile: dict
) -> dict[str, list[dict]]:
    """Compare owned warnings to an exact target/profile baseline."""
    if baseline.get("schema") != 1 or baseline.get("scope") != "target":
        raise ValueError("unsupported diagnostic baseline schema or scope")
    _validate_profile(profile)
    if baseline.get("profile") != profile:
        raise ValueError("diagnostic tool or setup profile does not match baseline")
    expected = baseline.get("findings")
    if not isinstance(expected, list):
        raise ValueError("baseline findings must be a list")
    actual_by_key = _index_findings(actual, baseline=False)
    baseline_by_key = _index_findings(expected, baseline=True)
    keys_actual, keys_base = set(actual_by_key), set(baseline_by_key)
    return {
        "new": [actual_by_key[key] for key in sorted(keys_actual - keys_base)],
        "resolved": [baseline_by_key[key] for key in sorted(keys_base - keys_actual)],
    }


def _index_findings(findings: list[dict], baseline: bool) -> dict[tuple[str, str, str, str], dict]:
    result = {}
    for finding in findings:
        key = diagnostic_key(finding)
        if key in result:
            raise ValueError(f"duplicate diagnostic identity: {key}")
        if baseline and (
            not isinstance(finding.get("owner"), str)
            or not finding["owner"].strip()
            or not isinstance(finding.get("rationale"), str)
            or not finding["rationale"].strip()
        ):
            raise ValueError("baseline findings require owner and rationale")
        result[key] = finding
    return result


def _validate_profile(profile: dict) -> None:
    if not isinstance(profile, dict) or _PROFILE_FIELDS - profile.keys():
        raise ValueError("diagnostic profile is missing tool/setup fields")
    if not isinstance(profile["flags"], list) or not all(
        isinstance(flag, str) and flag for flag in profile["flags"]
    ):
        raise ValueError("diagnostic flags must be a list of strings")
    for field in ("platform", "toolchain", "setup_sha256"):
        if not isinstance(profile[field], str) or not profile[field]:
            raise ValueError(f"diagnostic profile field {field} must be non-empty")


def build_warning_profile(
    root: pathlib.Path,
    examples: list[str],
    flags: list[str],
    run: Callable = subprocess.run,
) -> dict[str, str]:
    """Freshly compile each example into an isolated warning-only directory."""
    if not flags or any(not flag for flag in flags):
        raise ValueError("warning flags must be non-empty")
    root = pathlib.Path(root).resolve()
    output_root = root / ".build/warnings"
    stage = root / ".build/pio-library"
    logs = {}
    for name in examples:
        project = root / "examples" / name
        if not project.is_dir() or not any(project.glob("*.ino")):
            raise ValueError(f"example directory missing sketch: {name}")
        build_dir = output_root / name
        shutil.rmtree(build_dir, ignore_errors=True)
        build_dir.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "pio",
            "ci",
            f"--lib={stage}",
            "--board=nodemcuv2",
            "-O",
            "platform=espressif8266@4.2.1",
            "-O",
            "board_build.filesystem=littlefs",
            "-O",
            f"build_flags={' '.join(flags)}",
            "--build-dir",
            str(build_dir),
            "--keep-build-dir",
            str(project),
        ]
        try:
            result = run(command, capture_output=True, text=True, check=False)
        except OSError as error:
            raise RuntimeError(f"cannot execute PlatformIO for {name}: {error}") from error
        log = (result.stdout or "") + (result.stderr or "")
        (output_root / f"{name}.log").write_text(log)
        if result.returncode:
            raise RuntimeError(f"warning-profile build failed for {name}; see .build/warnings/{name}.log")
        logs[name] = log
    if not logs:
        raise ValueError("warning profile has no examples")
    return logs


def parse_warnings(
    log: str, root: pathlib.Path, stage: pathlib.Path, example: str
) -> tuple[list[dict], list[dict]]:
    """Map repository-owned GCC diagnostics and retain vendor diagnostics separately."""
    root, stage = pathlib.Path(root).resolve(), pathlib.Path(stage).resolve()
    owned, third_party = [], []
    for raw_line in log.splitlines():
        match = _WARNING.match(raw_line.strip())
        if not match:
            continue
        diagnostic_path = pathlib.Path(match["path"])
        line = int(match["line"])
        mapped = _map_owned_path(diagnostic_path, root, stage, example)
        finding = {
            "path": mapped[0] if mapped else str(diagnostic_path),
            "check": match["check"] or "compiler-warning",
            "message": _normalize(match["message"]),
            "context_sha256": _context_hash(mapped[1], line) if mapped else "",
            "line": line,
        }
        (owned if mapped else third_party).append(finding)
    return owned, third_party


def _map_owned_path(
    path: pathlib.Path, root: pathlib.Path, stage: pathlib.Path, example: str
) -> tuple[str, pathlib.Path] | None:
    try:
        resolved = path.resolve()
        return "src/" + resolved.relative_to(stage / "src").as_posix(), root / "src" / resolved.relative_to(stage / "src")
    except ValueError:
        pass
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(root / "examples")
        source = root / "examples" / relative
        return "examples/" + relative.as_posix(), source
    except ValueError:
        pass
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(root / ".build/warnings" / example / "src")
        generated_name = relative.name.removesuffix(".cpp")
        candidate = root / "examples" / example / generated_name
        if candidate.is_file():
            rel = candidate.relative_to(root)
            return rel.as_posix(), candidate
    except ValueError:
        pass
    return None


def _context_hash(path: pathlib.Path, line: int) -> str:
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError as error:
        raise ValueError(f"cannot read owned warning source {path}: {error}") from error
    first = max(0, line - 3)
    last = min(len(lines), line + 2)
    context = "\n".join(value.strip() for value in lines[first:last] if value.strip())
    return hashlib.sha256(context.encode()).hexdigest()


def _normalize(value: str) -> str:
    return " ".join(value.split())


def _deduplicate(findings: list[dict]) -> list[dict]:
    unique = {}
    for finding in findings:
        unique[diagnostic_key(finding)] = finding
    return [unique[key] for key in sorted(unique)]


def _warning_profile(root: pathlib.Path, flags: list[str], log: str) -> dict:
    platform_match = re.search(r"PLATFORM: .*?\(([^)]+)\)", log)
    framework_match = re.search(r"framework-arduinoespressif8266 @ ([^\s]+)", log)
    toolchain_match = re.search(r"toolchain-xtensa @ ([^\s]+) \(([^)]+)\)", log)
    if not (platform_match and framework_match and toolchain_match):
        raise ValueError("warning build log is missing target tool versions")
    import platformio

    setup_hash = hashlib.sha256((root / "User_Setup.h").read_bytes()).hexdigest()
    return {
        "platform": platform_match.group(1),
        "framework": framework_match.group(1),
        "toolchain": toolchain_match.group(1),
        "compiler": toolchain_match.group(2),
        "platformio": platformio.__version__,
        "python": platform.python_version(),
        "setup_sha256": setup_hash,
        "flags": flags,
    }


def warnings(root: pathlib.Path, baseline_path: pathlib.Path, flags: list[str]) -> int:
    root = pathlib.Path(root).resolve()
    examples_root = root / "examples"
    examples = sorted(
        entry.name for entry in examples_root.iterdir() if entry.is_dir() and any(entry.glob("*.ino"))
    )
    logs = build_warning_profile(root, examples, flags)
    profile = _warning_profile(root, flags, next(iter(logs.values())))
    owned, vendor = [], []
    stage = root / ".build/pio-library"
    for name, log in logs.items():
        owned_log, vendor_log = parse_warnings(log, root, stage, name)
        owned.extend(owned_log)
        vendor.extend(vendor_log)
    owned, vendor = _deduplicate(owned), _deduplicate(vendor)
    baseline = json.loads(pathlib.Path(baseline_path).read_text())
    result = compare_findings(owned, baseline, profile)
    report_root = root / ".build/warnings"
    (report_root / "vendor.json").write_text(json.dumps(vendor, indent=2) + "\n")
    report = {"profile": profile, **result}
    (report_root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"owned warnings: {len(owned)}; new: {len(result['new'])}; resolved: {len(result['resolved'])}")
    print(f"vendor warnings: {len(vendor)} (report: .build/warnings/vendor.json)")
    if result["resolved"]:
        print("resolved baseline entries should be removed before merge", file=sys.stderr)
    return 1 if result["new"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    warning_parser = subparsers.add_parser("warnings", help="build and compare GCC warnings")
    warning_parser.add_argument("--all-examples", action="store_true", required=True)
    warning_parser.add_argument("--flags", required=True)
    warning_parser.add_argument("--baseline", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.command == "warnings":
        try:
            flags = args.flags.split()
            root = pathlib.Path(__file__).resolve().parents[1]
            return warnings(root, args.baseline, flags)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            print(f"analysis: {error}", file=sys.stderr)
            return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
