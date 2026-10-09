#!/usr/bin/env python3
"""Fail closed when the reference firmware grows or its measurement profile changes."""
import argparse
import configparser
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

REQUIRED = {".irom0.text", ".text", ".data", ".rodata", ".bss"}
PROFILE_KEYS = {"board", "platform", "framework", "toolchain", "python", "platformio", "build_flags", "setup_sha256"}


def parse_sections(output: str) -> dict[str, int]:
    sections: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if not fields or not fields[0].startswith(".") or "/" in fields[0] or fields[0].endswith(":"):
            continue
        if len(fields) < 3:
            raise ValueError(f"malformed section row: {line}")
        try:
            size = int(fields[1])
        except ValueError as error:
            raise ValueError(f"malformed section size: {line}") from error
        if size < 0 or fields[0] in sections:
            raise ValueError(f"invalid or duplicate section: {line}")
        sections[fields[0]] = size
    if not REQUIRED.issubset(sections):
        raise ValueError(f"missing required sections: {sorted(REQUIRED - sections.keys())}")
    return sections


def resource_totals(sections: dict[str, int]) -> dict[str, int]:
    if not REQUIRED.issubset(sections):
        raise ValueError(f"missing required sections: {sorted(REQUIRED - sections.keys())}")
    flash = sum(sections[name] for name in (".irom0.text", ".text", ".text1", ".data", ".rodata") if name in sections)
    ram = sum(sections[name] for name in (".data", ".rodata", ".bss"))
    return {"flash": flash, "ram": ram}


def compare_resources(actual: dict[str, int], baseline: dict[str, int], actual_profile: dict, baseline_profile: dict) -> dict[str, int]:
    if actual_profile != baseline_profile:
        raise ValueError("measurement profile differs from baseline")
    if set(actual) != {"flash", "ram"} or set(baseline) != {"flash", "ram"}:
        raise ValueError("resource records must contain only flash and ram")
    if any(type(value) is not int or value < 0 for records in (actual, baseline) for value in records.values()):
        raise ValueError("resource sizes must be non-negative integers")
    delta = {name: actual[name] - baseline[name] for name in ("flash", "ram")}
    if any(value > 0 for value in delta.values()):
        raise ValueError(f"resource increase: {delta}")
    return delta


def _used_bytes(log: str) -> dict[str, int]:
    result = {}
    for name in ("RAM", "Flash"):
        matches = re.findall(rf"^{name}:.*?\(used ([0-9]+) bytes", log, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(f"expected one {name} usage report, found {len(matches)}")
        result[name.lower()] = int(matches[0])
    return result


def _profile(root: pathlib.Path, build_log: str, project: pathlib.Path) -> dict:
    config = configparser.ConfigParser()
    if not config.read(project / "platformio.ini") or "env:nodemcuv2" not in config:
        raise ValueError("missing nodemcuv2 project configuration")
    section = config["env:nodemcuv2"]
    platform = re.search(r"^PLATFORM:\s+[^\n(]+\(([^)]+)\)", build_log, re.MULTILINE)
    framework = re.search(r"^\s*- framework-arduinoespressif8266 @ ([^\s]+)", build_log, re.MULTILINE)
    toolchain = re.search(r"^\s*- toolchain-xtensa @ ([^\s]+)", build_log, re.MULTILINE)
    if not all((platform, framework, toolchain)):
        raise ValueError("build log does not identify platform, framework, and toolchain")
    import platformio

    setup = (root / "User_Setup.h").read_bytes()
    return {
        "board": section.get("board", ""),
        "platform": platform.group(1),
        "framework": framework.group(1),
        "toolchain": toolchain.group(1),
        "python": sys.version.split()[0],
        "platformio": platformio.__version__,
        "build_flags": dict(sorted(section.items())),
        "setup_sha256": hashlib.sha256(setup).hexdigest(),
    }


def _size_program() -> pathlib.Path:
    core = pathlib.Path(os.environ.get("PLATFORMIO_CORE_DIR", pathlib.Path.home() / ".platformio"))
    paths = list((core / "packages/toolchain-xtensa/bin").glob("xtensa-lx106-elf-size"))
    if len(paths) != 1:
        raise ValueError("ESP8266 toolchain size program is unavailable or ambiguous")
    return paths[0]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=pathlib.Path)
    parser.add_argument("--log", required=True, type=pathlib.Path)
    parser.add_argument("--build-log", required=True, type=pathlib.Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--baseline", required=True, type=pathlib.Path)
    parser.add_argument("--label", required=True)
    args = parser.parse_args(argv)
    root = pathlib.Path.cwd()
    try:
        if not args.elf.is_file() or not args.log.is_file() or not args.build_log.is_file():
            raise ValueError("requested ELF or size/build report is missing")
        pio_report = args.log.read_text()
        if "[SUCCESS]" not in pio_report or "firmware.elf" not in pio_report:
            raise ValueError("requested -t size report is missing or unsuccessful")
        build_report = args.build_log.read_text()
        summary = _used_bytes(build_report)
        profile = _profile(root, build_report, args.elf.parent.parent.parent.parent)
        if set(profile) != PROFILE_KEYS:
            raise ValueError("internal profile schema mismatch")
        sections_output = subprocess.run([str(_size_program()), "-A", "-d", str(args.elf)], check=True, capture_output=True, text=True).stdout
        sections_path = root / ".build" / f"{args.elf.parent.parent.parent.parent.name}-sections.log"
        sections_path.parent.mkdir(parents=True, exist_ok=True)
        sections_path.write_text(sections_output)
        actual = resource_totals(parse_sections(sections_output))
        if actual != summary:
            raise ValueError(f"section totals {actual} disagree with build report {summary}")
        baseline_data = json.loads(args.baseline.read_text())
        if baseline_data.get("schema") != 1 or set(baseline_data.get("profile", {})) != PROFILE_KEYS:
            raise ValueError("baseline schema/profile is invalid")
        delta = compare_resources(actual, baseline_data["resources"], profile, baseline_data["profile"])
        print(f"{args.profile}/{args.label}: flash={actual['flash']} ({delta['flash']:+d}), ram={actual['ram']} ({delta['ram']:+d})")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
