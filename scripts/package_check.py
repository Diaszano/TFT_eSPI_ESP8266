#!/usr/bin/env python3
"""Validate the required files and safe member names in a packed library."""
import argparse
import json
import pathlib
import re
import tarfile
from pathlib import PurePosixPath

_DATA = {
    "examples/Font_Demo_1/data/NotoSansBold15.vlw",
    "examples/Font_Demo_1/data/NotoSansBold36.vlw",
    "examples/TFT_SPIFFS_BMP/data/parrot.bmp",
}
_TOOL_ARTIFACTS = {".git", ".venv", ".superpowers", ".build", ".pio"}


def validate_members(names: set[str], src_layout: bool) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or re.match(r"^[A-Za-z]:", name):
            raise ValueError(f"unsafe archive member path: {name}")
        if path.parts and path.parts[0] in _TOOL_ARTIFACTS:
            raise ValueError(f"tooling artifact in package: {name}")
    required = {
        "User_Setup.h", "User_Setup_Select.h", "library.json", "library.properties", "license.txt",
        "examples/TFT_Print_Test/TFT_Print_Test.ino", *_DATA,
    }
    required.add("src/Fonts/GFXFF/license.txt" if src_layout else "Fonts/GFXFF/license.txt")
    required.update({"src/TFT_eSPI.h", "src/TFT_eSPI.cpp", "src/User_Setup.h", "src/User_Setup_Select.h"} if src_layout else {"TFT_eSPI.h", "TFT_eSPI.cpp"})
    missing = required - names
    if missing:
        raise ValueError(f"package is missing required members: {sorted(missing)}")


def validate_archive(archive: pathlib.Path, src_layout: bool | None = None) -> None:
    with tarfile.open(archive, "r:*") as package:
        names = {member.name for member in package.getmembers()}
        if src_layout is None:
            try:
                manifest = json.load(package.extractfile("library.json"))
            except (KeyError, TypeError, json.JSONDecodeError) as error:
                raise ValueError("package library.json is missing or invalid") from error
            src_layout = manifest.get("build", {}).get("srcDir") == "src"
        validate_members(names, src_layout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=pathlib.Path)
    args = parser.parse_args()
    try:
        validate_archive(args.archive)
    except (OSError, tarfile.TarError, ValueError) as error:
        parser.error(str(error))
    print(f"package OK: {args.archive}")


if __name__ == "__main__":
    main()
