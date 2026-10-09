#!/usr/bin/env python3
"""Run the repository's pinned clang-format policy on maintained C++ files."""
import argparse
import pathlib
import re
import subprocess
import sys

SUFFIXES = {".c", ".cc", ".cpp", ".h", ".hpp", ".ino", ".inc", ".ipp"}
EXCLUDED = ("src/Fonts/", "src/TFT_Drivers/ST7789_Init.h", "extras/Create_Smooth_Font/")


def selected_files(root: pathlib.Path, paths: list[str] | None = None) -> list[str]:
    root = pathlib.Path(root).resolve()
    if paths is None:
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], check=True, capture_output=True)
        paths = result.stdout.decode().split("\0")
    selected = set()
    for value in paths:
        if not value:
            continue
        path = pathlib.PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"path is outside repository: {value}")
        name = path.as_posix()
        if path.suffix.lower() in SUFFIXES and not any(name.startswith(prefix) or name == prefix for prefix in EXCLUDED):
            selected.add(name)
    return sorted(selected)


def require_version(version_output: str) -> None:
    if not re.search(r"\bclang-format version 23\.1\.2\b", version_output):
        raise ValueError(f"clang-format 23.1.2 is required, found: {version_output.strip()}")


def run_files(root: pathlib.Path, paths: list[str], write: bool, executable: str = "clang-format") -> int:
    version = subprocess.run([executable, "--version"], check=True, capture_output=True, text=True)
    require_version(version.stdout)
    for name in paths:
        path = pathlib.PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() not in SUFFIXES:
            raise ValueError(f"invalid repository source path: {name}")
        source = name if path.suffix.lower() not in {".ino", ".inc", ".ipp"} else str(path.with_suffix(".cpp"))
        mode = ["-i"] if write else ["--dry-run", "--Werror"]
        result = subprocess.run([executable, "--style=file", f"--assume-filename={source}", *mode, name], cwd=root)
        if result.returncode:
            return result.returncode
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    root = pathlib.Path(__file__).resolve().parent.parent
    try:
        return run_files(root, selected_files(root, args.paths or None), args.write)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
