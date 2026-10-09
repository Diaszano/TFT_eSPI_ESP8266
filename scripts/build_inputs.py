#!/usr/bin/env python3
"""List library and example files that affect staged PlatformIO builds."""
import pathlib
import sys


def library_files(root: pathlib.Path) -> list[str]:
    root = pathlib.Path(root)
    source = root / "src"
    roots = [source if source.is_dir() else root]
    files = []
    for path in roots[0].glob("TFT_eSPI.*"):
        if path.is_file():
            files.append(path)
    for path in roots[0].glob("User_Setup*.h"):
        if path.is_file():
            files.append(path)
    for name in ("TFT_Drivers", "Extensions", "Fonts", "User_Setups"):
        folder = roots[0] / name
        if folder.is_dir():
            files.extend(path for path in folder.rglob("*") if path.is_file())
    for name in ("Makefile", "library.json", "library.properties", "keywords.txt", "license.txt", "scripts/requirements-dev.in", "scripts/requirements-dev.txt"):
        path = root / name
        if path.is_file():
            files.append(path)
    return sorted(path.relative_to(root).as_posix() for path in files)


def example_files(root: pathlib.Path) -> list[str]:
    root = pathlib.Path(root)
    folder = root / "examples"
    return sorted(path.relative_to(root).as_posix() for path in folder.rglob("*") if path.is_file()) if folder.is_dir() else []


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    files = {"library": library_files, "examples": example_files}[sys.argv[1]](root)
    print("\n".join(files))


if __name__ == "__main__":
    main()
