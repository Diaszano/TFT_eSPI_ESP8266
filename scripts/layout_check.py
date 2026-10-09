#!/usr/bin/env python3
"""Verify the Arduino src layout and the staged PlatformIO object inventory."""
import argparse
import json
import pathlib
import sys

_SOURCE_SUFFIXES = {".c", ".cc", ".cpp"}
_SETUP_FORWARDER = '// Keep the editable Arduino installation setup at the package root.\n#include "../User_Setup.h"\n'


def compiled_sources(root: pathlib.Path) -> list[str]:
    root = pathlib.Path(root)
    source = root / "src"
    scope = source if source.is_dir() else root
    return sorted(path.relative_to(root).as_posix() for path in scope.rglob("*") if path.is_file() and path.suffix.lower() in _SOURCE_SUFFIXES)


def verify_fragments(root: pathlib.Path) -> None:
    root = pathlib.Path(root)
    sources = compiled_sources(root)
    if sources != ["src/TFT_eSPI.cpp"]:
        raise ValueError(f"expected only src/TFT_eSPI.cpp to compile, found {sources}")
    font_c = sorted((root / "src/Fonts").rglob("*.c")) if (root / "src/Fonts").is_dir() else []
    if font_c:
        raise ValueError(f"font data must be included fragments, not C translation units: {font_c}")
    for relative in ("User_Setup.h", "User_Setup_Select.h", "src/User_Setup.h", "src/User_Setup_Select.h"):
        if not (root / relative).is_file():
            raise ValueError(f"required setup entry is missing: {relative}")
    if (root / "src/User_Setup.h").read_text() != _SETUP_FORWARDER:
        raise ValueError("src/User_Setup.h must forward directly to the editable root setup")
    if 'src/User_Setup_Select.h' not in (root / "User_Setup_Select.h").read_text():
        raise ValueError("root selector must forward to src/User_Setup_Select.h")
    core = (root / "src/TFT_eSPI.cpp").read_text()
    for include in ('#include "internal/Sprite.inc"', '#include "internal/Smooth_font.inc"'):
        if include not in core:
            raise ValueError(f"core is missing included implementation fragment: {include}")
    if "AA_graphics.cpp" in core:
        raise ValueError("missing AA_GRAPHICS implementation must remain a no-op")
    for relative in ("src/internal/Sprite.inc", "src/internal/Smooth_font.inc"):
        if not (root / relative).is_file():
            raise ValueError(f"included implementation fragment is missing: {relative}")
    try:
        manifest = json.loads((root / "library.json").read_text())
        build = manifest["build"]
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as error:
        raise ValueError("library.json has no valid src build configuration") from error
    expected = {"srcDir": "src", "includeDir": "src", "srcFilter": ["-<*>", "+<TFT_eSPI.cpp>"]}
    if build != expected:
        raise ValueError(f"library.json build configuration must be {expected}")


def verify_project(root: pathlib.Path, project: pathlib.Path) -> None:
    root, project = pathlib.Path(root), pathlib.Path(project)
    verify_fragments(root)
    database = project / "compile_commands.json"
    if not database.is_file():
        raise ValueError(f"missing generated compilation database: {database}")
    try:
        entries = json.loads(database.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid compilation database: {database}") from error
    library_entries = [entry for entry in entries if "/lib/pio-library/" in entry.get("file", "/") or entry.get("file", "").startswith("lib/pio-library/")]
    expected_source = "lib/pio-library/src/TFT_eSPI.cpp"
    if len(library_entries) != 1 or not library_entries[0]["file"].replace("\\", "/").endswith(expected_source):
        raise ValueError(f"expected one compiled library source {expected_source}, found {[entry.get('file') for entry in library_entries]}")
    output = library_entries[0].get("output", "").replace("\\", "/")
    if not output.endswith("/TFT_eSPI.cpp.o"):
        raise ValueError(f"unexpected core object path: {output}")
    if any("Sprite.cpp.o" in entry.get("output", "") or "Smooth_font.cpp.o" in entry.get("output", "") for entry in entries):
        raise ValueError("included fragments were compiled as independent objects")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=pathlib.Path)
    parser.add_argument("--project", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        verify_project(args.root, args.project)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print("layout OK: one production translation unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
