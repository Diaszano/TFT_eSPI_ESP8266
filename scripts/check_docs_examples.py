#!/usr/bin/env python3
"""Compile the first Arduino example in each user-facing language guide."""
import argparse
import pathlib
import re
import subprocess
import sys
import tempfile

DOCS = ("README.md", "README.pt-BR.md", "docs/en/sprites.md", "docs/pt-BR/sprites.md")
_CPP = re.compile(r"```(?:cpp|c\+\+)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def first_cpp_block(path: pathlib.Path) -> str:
    match = _CPP.search(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"missing C++ example in {path}")
    return match.group(1)


def check(root: pathlib.Path, pio: str = "pio") -> None:
    root = pathlib.Path(root).resolve()
    stage = root / ".build/pio-library"
    if not stage.is_dir():
        raise ValueError(f"missing staged library: {stage}; run make build-Colour_Test first")
    snippets = [(name, first_cpp_block(root / name)) for name in DOCS]
    with tempfile.TemporaryDirectory(prefix="tft-doc-examples-") as temp:
        work = pathlib.Path(temp)
        for index, (name, code) in enumerate(snippets):
            project = work / f"example-{index}"
            project.mkdir()
            if name.startswith("docs/"):
                code = "#include <Arduino.h>\n#include <TFT_eSPI.h>\nTFT_eSPI tft;\nvoid setup() {\n" + code + "\n}\nvoid loop() {}\n"
            (project / "documented.ino").write_text(code, encoding="utf-8")
            subprocess.run(
                [pio, "ci", f"--lib={stage}", "--board=nodemcuv2", "-O", "platform=espressif8266@4.2.1",
                 "--build-dir", str(work / f"build-{index}"), "--keep-build-dir", str(project)],
                cwd=work,
                check=True,
            )
            print(f"PASS {name}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent.parent)
    parser.add_argument("--pio", default="pio")
    args = parser.parse_args(argv)
    try:
        check(args.root, args.pio)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
