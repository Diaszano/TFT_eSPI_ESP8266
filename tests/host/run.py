#!/usr/bin/env python3
"""Compile source-extracted host regressions with sanitizers."""
import argparse
import pathlib
import re
import shutil
import subprocess
import tempfile


def extract_scroll(source: str) -> tuple[str, int]:
    marker = "void TFT_eSprite::scroll(int16_t dx, int16_t dy) {"
    start = source.find(marker)
    if start < 0:
        raise ValueError("scroll implementation marker missing")
    open_brace = source.find("{", start)
    depth = 0
    state = "code"
    i = open_brace
    while i < len(source):
        char = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                state = "line"
                i += 1
            elif char == "/" and nxt == "*":
                state = "block"
                i += 1
            elif char == '"':
                state = "string"
            elif char == "'":
                state = "char"
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[start : i + 1], source.count("\n", 0, start) + 1
        elif state == "line":
            if char == "\n":
                state = "code"
        elif state == "block":
            if char == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state in ("string", "char"):
            if char == "\\":
                i += 1
            elif (state == "string" and char == '"') or (state == "char" and char == "'"):
                state = "code"
        i += 1
    raise ValueError("unterminated scroll implementation")


def run_scroll(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    fixture = (root / "tests/host/test_scroll.cpp").read_text()
    if fixture.count("// FUNCTION UNDER TEST") != 1:
        raise ValueError("expected exactly one unique function insertion marker")
    implementation, line = extract_scroll((root / "src/internal/Sprite.inc").read_text())
    generated = fixture.replace(
        "// FUNCTION UNDER TEST", f'#line {line} "src/internal/Sprite.inc"\n{implementation}'
    )
    with tempfile.TemporaryDirectory(prefix="tft-host-") as temp:
        source = pathlib.Path(temp) / "scroll.cpp"
        binary = pathlib.Path(temp) / "scroll"
        source.write_text(generated)
        subprocess.run(
            [compiler, "-std=c++11", "-Wall", "-Wextra", "-fsanitize=address,undefined",
             "-fno-sanitize-recover=all", str(source), "-o", str(binary)],
            check=True,
        )
        subprocess.run([str(binary)], check=True)
    print("PASS scroll")


def run_font_metrics(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    marker = "void TFT_eSPI::setFreeFont(const GFXfont* f) {"
    source_text = (root / "src/TFT_eSPI.cpp").read_text()
    start = source_text.find(marker)
    if start < 0:
        raise ValueError("FreeFont metrics implementation marker missing")
    open_brace = source_text.find("{", start)
    depth = 0
    end = open_brace
    while end < len(source_text):
        if source_text[end] == "{":
            depth += 1
        elif source_text[end] == "}":
            depth -= 1
            if depth == 0:
                break
        end += 1
    implementation = source_text[start : end + 1]
    fixture = (root / "tests/host/test_font_metrics.cpp").read_text()
    if fixture.count("// FUNCTION UNDER TEST") != 1:
        raise ValueError("expected exactly one unique function insertion marker")
    generated = fixture.replace("// FUNCTION UNDER TEST", implementation)
    with tempfile.TemporaryDirectory(prefix="tft-font-metrics-") as temp:
        source = pathlib.Path(temp) / "metrics.cpp"
        binary = pathlib.Path(temp) / "metrics"
        source.write_text(generated)
        subprocess.run(
            [compiler, "-std=c++11", "-Wall", "-Wextra", "-fsanitize=address,undefined",
             "-fno-sanitize-recover=all", str(source), "-o", str(binary)], check=True
        )
        subprocess.run([str(binary)], check=True)
    print("PASS font-metrics")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("scroll", "font-metrics", "all"), default="all")
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[2]
    if args.case in ("scroll", "all"):
        run_scroll(root)
    if args.case in ("font-metrics", "all"):
        run_font_metrics(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
