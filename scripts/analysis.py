#!/usr/bin/env python3
"""Build and compare owned compiler diagnostics for the pinned ESP8266 target."""

import argparse
import hashlib
import json
import pathlib
import platform
import re
import shlex
import shutil
import subprocess
import sys
from typing import Callable


_WARNING = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):\d+: warning: (?P<message>.*?)(?: \[(?P<check>[^]]+)\])?$"
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
    actual: list[dict], baseline: dict, profile: dict, scope: str = "target"
) -> dict[str, list[dict]]:
    """Compare owned warnings to an exact target/profile baseline."""
    if baseline.get("schema") != 1 or baseline.get("scope") != scope:
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


def map_compile_database(
    entries: list[dict], stage: pathlib.Path, root: pathlib.Path
) -> list[dict]:
    """Map exactly one byte-identical staged library translation unit to the checkout."""
    stage, root = pathlib.Path(stage).resolve(), pathlib.Path(root).resolve()
    candidates = []
    for entry in entries:
        directory = pathlib.Path(entry["directory"])
        if not directory.is_absolute():
            directory = root / directory
        source = pathlib.Path(entry["file"])
        if not source.is_absolute():
            source = directory / source
        try:
            relative = source.resolve().relative_to(stage / "src")
        except ValueError:
            continue
        candidates.append((entry, relative, directory.resolve()))
    if len(candidates) != 1:
        raise ValueError(f"expected one staged library translation unit, found {len(candidates)}")

    entry, relative, directory = candidates[0]
    staged_source, source = stage / "src" / relative, root / "src" / relative
    if (
        not source.is_file()
        or not staged_source.is_file()
        or source.read_bytes() != staged_source.read_bytes()
    ):
        raise ValueError(f"staged library source is missing or stale: {relative}")
    arguments = entry.get("arguments")
    if arguments is None:
        arguments = shlex.split(entry["command"])
    mapped = []
    stage_prefix = str(stage) + "/"
    root_prefix = str(root) + "/"
    for argument in arguments:
        if argument == str(source) or argument == str(staged_source):
            mapped.append(str(source))
        elif argument.startswith(stage_prefix):
            mapped.append(root_prefix + argument[len(stage_prefix):])
        elif argument.startswith("-Ilib/pio-library/"):
            mapped.append("-I" + str(root / argument[len("-Ilib/pio-library/"):]))
        elif argument.startswith("lib/pio-library/"):
            mapped.append(str(root / argument[len("lib/pio-library/"):]))
        else:
            mapped.append(argument)
    if str(source) not in mapped:
        mapped.append(str(source))
    return [{"directory": str(directory), "file": str(source), "arguments": mapped}]


def map_native_compile_database(
    entries: list[dict], project: pathlib.Path, root: pathlib.Path
) -> list[dict]:
    """Map the real pure-color probe entry and reject missing or duplicate TUs."""
    project, root = pathlib.Path(project).resolve(), pathlib.Path(root).resolve()
    source = root / "test/analysis/color_probe.cpp"
    candidates = []
    for entry in entries:
        directory = pathlib.Path(entry["directory"])
        if not directory.is_absolute():
            directory = project / directory
        path = pathlib.Path(entry["file"])
        if not path.is_absolute():
            path = directory / path
        if path.resolve() == (project / "analysis/color_probe.cpp").resolve():
            candidates.append((entry, directory.resolve()))
    if len(candidates) != 1:
        raise ValueError(f"expected one native color probe translation unit, found {len(candidates)}")
    entry, directory = candidates[0]
    if not source.is_file() or (project / "analysis/color_probe.cpp").read_bytes() != source.read_bytes():
        raise ValueError("native analysis probe is missing or stale")
    arguments = entry.get("arguments")
    if arguments is None:
        arguments = shlex.split(entry["command"])
    mapped = []
    for argument in arguments:
        if argument == "analysis/color_probe.cpp" or argument == str(project / "analysis/color_probe.cpp"):
            mapped.append(str(source))
        elif argument == "-I../src":
            mapped.append("-I" + str(root / "src"))
        else:
            mapped.append(argument)
    if str(source) not in mapped:
        mapped.append(str(source))
    return [{"directory": str(directory), "file": str(source), "arguments": mapped}]


def prepare_compile_database(project: pathlib.Path, root: pathlib.Path, scope: str) -> pathlib.Path:
    project, root = pathlib.Path(project).resolve(), pathlib.Path(root).resolve()
    database_path = project / "compile_commands.json"
    entries = json.loads(database_path.read_text())
    if scope == "target":
        mapped = map_compile_database(entries, project / "lib/pio-library", root)
    elif scope == "native":
        mapped = map_native_compile_database(entries, project, root)
    else:
        raise ValueError(f"unsupported compilation database scope: {scope}")
    output = root / ".build/analysis/compile_commands.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(mapped, indent=2) + "\n")
    return output


def native_profile(
    root: pathlib.Path, entry: dict, clang_tidy_version: str, checks: str
) -> dict:
    root = pathlib.Path(root).resolve()
    args = entry.get("arguments") or shlex.split(entry["command"])
    compiler = shutil.which(args[0]) or args[0]
    compiler_version = subprocess.run(
        [compiler, "--version"], capture_output=True, text=True, check=False
    )
    if compiler_version.returncode or not compiler_version.stdout.splitlines():
        raise RuntimeError("cannot identify the native compiler from the compile database")
    version_match = re.search(r"(\d+\.\d+\.\d+)$", compiler_version.stdout.splitlines()[0])
    if not version_match:
        raise RuntimeError("native compiler version format is unknown")
    settings = root / "test/platformio.ini"
    config = root / ".clang-tidy"
    flags = [arg.replace(str(root), "$ROOT") for arg in args if arg.startswith(("-D", "-I", "-std"))]
    return {
        "platform": "native@1.2.1",
        "toolchain": f"{pathlib.Path(compiler).name} {version_match.group(1)}",
        "setup_sha256": hashlib.sha256(settings.read_bytes()).hexdigest(),
        "clang_tidy": re.search(r"version ([0-9.]+)", clang_tidy_version).group(1),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "checks_sha256": hashlib.sha256(checks.encode()).hexdigest(),
        "flags": flags,
    }


def run_tidy(
    root: pathlib.Path,
    scope: str = "target",
    baseline_path: pathlib.Path | None = None,
    executable: str = "clang-tidy",
) -> int:
    root = pathlib.Path(root).resolve()
    database = root / ".build/analysis/compile_commands.json"
    entries = json.loads(database.read_text())
    executable_path = shutil.which(executable)
    if not executable_path:
        raise RuntimeError("clang-tidy 22.1.8 is required for the target pilot")
    version = subprocess.run(
        [executable_path, "--version"], capture_output=True, text=True, check=False
    )
    if version.returncode or "22.1.8" not in version.stdout + version.stderr:
        raise RuntimeError("target pilot requires clang-tidy 22.1.8")
    config = root / ".clang-tidy"
    subprocess.run([executable_path, "--verify-config", f"--config-file={config}"], check=True)
    checks = subprocess.run(
        [executable_path, "--list-checks", f"--config-file={config}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if checks.returncode:
        raise RuntimeError("cannot enumerate clang-tidy checks")
    source = entries[0]["file"]
    result = subprocess.run(
        [
            executable_path,
            "-p",
            str(database.parent),
            f"--config-file={config}",
            "--warnings-as-errors=clang-diagnostic-error",
            source,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    report = root / ".build/analysis/tidy.log"
    report.write_text(output)
    if result.returncode or tidy_has_parse_error(output):
        print(output.rstrip(), file=sys.stderr)
        return 1
    if scope == "native":
        findings, vendor = parse_warnings(output, root, root / "src", "")
        if baseline_path is None:
            raise ValueError("native tidy requires a reviewed native baseline")
        profile = native_profile(
            root, entries[0], version.stdout + version.stderr, checks.stdout + checks.stderr
        )
        baseline = json.loads(pathlib.Path(baseline_path).read_text())
        result = compare_findings(findings, baseline, profile, scope="native")
        (root / ".build/analysis/native-report.json").write_text(
            json.dumps(
                {"scope": "native", "profile": profile, "findings": findings, "vendor": vendor, **result},
                indent=2,
            )
            + "\n"
        )
        if result["new"] or result["resolved"]:
            print(f"native findings: {len(findings)}; new: {len(result['new'])}; resolved: {len(result['resolved'])}")
            return 1
    return 0


def tidy_has_parse_error(output: str) -> bool:
    return "[clang-diagnostic-error]" in output or "Found compiler error(s)." in output


def run_cppcheck(
    project: pathlib.Path,
    root: pathlib.Path,
    run: Callable = subprocess.run,
) -> int:
    project, root = pathlib.Path(project).resolve(), pathlib.Path(root).resolve()
    if not (project / "lib/pio-library/src/TFT_eSPI.cpp").is_file():
        raise ValueError("generated project does not contain the staged library source")
    analysis_dir = root / ".build/analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    config = project / ".pio-analysis.ini"
    config.write_text(
        (project / "platformio.ini").read_text().rstrip() + "\ncheck_tool = cppcheck\n"
    )
    command = [
        "pio",
        "check",
        "--project-dir",
        str(project),
        "--project-conf",
        str(config),
        "--environment",
        "nodemcuv2",
        "--src-filters",
        "+<lib/pio-library/>",
        "--flags",
        "cppcheck: --enable=warning,performance,portability --std=c++11",
        "--json-output",
    ]
    result = run(command, capture_output=True, text=True, check=False)
    report = result.stdout or ""
    try:
        start = report.index("[")
        defects = json.JSONDecoder().raw_decode(report[start:])[0]
        report = json.dumps(defects, indent=2) + "\n"
    except (ValueError, json.JSONDecodeError):
        (analysis_dir / "cppcheck.log").write_text(report + (result.stderr or ""))
        if result.returncode == 0:
            raise ValueError("PlatformIO cppcheck output did not contain JSON")
    else:
        (analysis_dir / "cppcheck.json").write_text(report)
    if result.returncode:
        print((report + (result.stderr or "")).rstrip(), file=sys.stderr)
    return result.returncode


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
    for source_root in (stage / "src", root / "src"):
        try:
            resolved = path.resolve()
            relative = resolved.relative_to(source_root)
            return "src/" + relative.as_posix(), root / "src" / relative
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
        relative = resolved.relative_to(root / "test")
        source = root / "test" / relative
        return "test/" + relative.as_posix(), source
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
    prepare_parser = subparsers.add_parser(
        "prepare", help="validate and map a target compilation database"
    )
    prepare_parser.add_argument("--project", type=pathlib.Path, required=True)
    prepare_parser.add_argument("--scope", choices=["target", "native"], required=True)
    tidy_parser = subparsers.add_parser("tidy", help="run the pinned target parsing pilot")
    tidy_parser.add_argument("--scope", choices=["target", "native"], required=True)
    tidy_parser.add_argument("--baseline", type=pathlib.Path)
    cppcheck_parser = subparsers.add_parser(
        "cppcheck", help="run optional cppcheck on staged library"
    )
    cppcheck_parser.add_argument("--project", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "warnings":
            flags = args.flags.split()
            root = pathlib.Path(__file__).resolve().parents[1]
            return warnings(root, args.baseline, flags)
        if args.command == "prepare":
            root = pathlib.Path(__file__).resolve().parents[1]
            print(prepare_compile_database(args.project, root, args.scope))
            return 0
        if args.command == "tidy":
            root = pathlib.Path(__file__).resolve().parents[1]
            return run_tidy(root, args.scope, args.baseline)
        if args.command == "cppcheck":
            root = pathlib.Path(__file__).resolve().parents[1]
            return run_cppcheck(args.project, root)
    except (
        OSError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        print(f"analysis: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
