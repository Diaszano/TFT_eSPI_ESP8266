#!/usr/bin/env python3
"""Compile source-extracted host regressions with sanitizers."""
import argparse
import pathlib
import re
import shutil
import subprocess
import tempfile


def extract_method(source: str, marker: str) -> tuple[str, int]:
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
    implementation, line = extract_method(
        (root / "src/internal/Sprite.inc").read_text(),
        "void TFT_eSprite::scroll(int16_t dx, int16_t dy) {",
    )
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


def run_allocations(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    fixture = (root / "tests/host/test_allocations.cpp").read_text()
    marker = "// FUNCTION UNDER TEST"
    if fixture.count(marker) != 1:
        raise ValueError("expected exactly one unique function insertion marker")
    implementation, line = extract_method(
        (root / "src/internal/Smooth_font.inc").read_text(),
        "bool TFT_eSPI::loadMetrics(void) {",
    )
    source = (root / "src/internal/Smooth_font.inc").read_text()
    cleanup, cleanup_line = extract_method(source, "void TFT_eSPI::unloadFont(void) {")
    sprite_source = (root / "src/internal/Sprite.inc").read_text()
    sprite_methods = []
    for signature in (
        "void* TFT_eSprite::createSprite(int16_t w, int16_t h, uint8_t frames) {",
        "void* TFT_eSprite::callocSprite(int16_t w, int16_t h, uint8_t frames) {",
        "void TFT_eSprite::createPalette(uint16_t colorMap[], uint8_t colors) {",
        "void TFT_eSprite::createPalette(const uint16_t colorMap[], uint8_t colors) {",
        "void TFT_eSprite::deleteSprite(void) {",
    ):
        method, method_line = extract_method(sprite_source, signature)
        sprite_methods.append(f'#line {method_line} "src/internal/Sprite.inc"\n{method}')
    generated = fixture.replace(
        marker,
        f'#line {line} "src/internal/Smooth_font.inc"\n{implementation}\n'
        f'#line {cleanup_line} "src/internal/Smooth_font.inc"\n{cleanup}\n'
        + "\n".join(sprite_methods),
    )
    with tempfile.TemporaryDirectory(prefix="tft-allocations-") as temp:
        source = pathlib.Path(temp) / "allocations.cpp"
        binary = pathlib.Path(temp) / "allocations"
        source.write_text(generated)
        subprocess.run(
            [compiler, "-std=c++11", "-Wall", "-Wextra", "-fsanitize=address,undefined",
             "-fno-sanitize-recover=all", "-I", str(root / "tests/host"), str(source), "-o",
             str(binary)], check=True
        )
        subprocess.run([str(binary)], check=True)
    print("PASS allocations")


def run_glyph_allocation(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    source = (root / "src/internal/Smooth_font.inc").read_text()
    implementation, line = extract_method(source, "void TFT_eSPI::drawGlyph(uint16_t code) {")
    cleanup, cleanup_line = extract_method(source, "void TFT_eSPI::unloadFont(void) {")
    fixture = (root / "tests/host/test_glyph_allocation.cpp").read_text()
    marker = "// FUNCTION UNDER TEST"
    if fixture.count(marker) != 1:
        raise ValueError("expected exactly one unique function insertion marker")
    generated = fixture.replace(
        marker,
        f'#define FONT_FS_AVAILABLE\n#line {cleanup_line} "src/internal/Smooth_font.inc"\n'
        f"{cleanup}\n#line {line} \"src/internal/Smooth_font.inc\"\n{implementation}",
    )
    with tempfile.TemporaryDirectory(prefix="tft-glyph-allocation-") as temp:
        source_path = pathlib.Path(temp) / "glyph.cpp"
        binary = pathlib.Path(temp) / "glyph"
        source_path.write_text(generated)
        subprocess.run(
            [compiler, "-std=c++11", "-Wall", "-Wextra", "-fsanitize=address,undefined",
             "-fno-sanitize-recover=all", str(source_path), "-o", str(binary)], check=True
        )
        subprocess.run([str(binary)], check=True)
    print("PASS glyph-allocation")


def run_font_files(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    fixture = (root / "tests/host/test_font_files.cpp").read_text()
    marker = "// FUNCTIONS UNDER TEST"
    if fixture.count(marker) != 1:
        raise ValueError("expected exactly one unique function insertion marker")
    source = (root / "src/internal/Smooth_font.inc").read_text()
    methods = []
    for signature in (
        "void TFT_eSPI::loadFont(const uint8_t array[]) {",
        "void TFT_eSPI::loadFont(String fontName, bool flash) {",
        "bool TFT_eSPI::loadMetrics(void) {",
        "void TFT_eSPI::unloadFont(void) {",
        "bool TFT_eSPI::readInt32(uint32_t& val) {",
        "void TFT_eSPI::drawGlyph(uint16_t code) {",
    ):
        method, line = extract_method(source, signature)
        methods.append(f'#define FONT_FS_AVAILABLE\n#line {line} "src/internal/Smooth_font.inc"\n{method}')
    sprite_method, sprite_line = extract_method(
        (root / "src/internal/Sprite.inc").read_text(),
        "void TFT_eSprite::drawGlyph(uint16_t code) {",
    )
    methods.append(f'#line {sprite_line} "src/internal/Sprite.inc"\n{sprite_method}')
    for path, signature in (
        ("src/TFT_eSPI.cpp", "int16_t TFT_eSPI::drawString(const char* string, int32_t poX, int32_t poY, uint8_t font) {"),
        ("src/internal/Smooth_font.inc", "void TFT_eSPI::showFont(uint32_t td) {"),
        ("src/internal/Sprite.inc", "void TFT_eSprite::printToSprite(char* cbuffer, uint16_t len)"),
        ("src/internal/Sprite.inc", "int16_t TFT_eSprite::printToSprite(int16_t x, int16_t y, uint16_t index) {"),
    ):
        method, line = extract_method((root / path).read_text(), signature)
        methods.append(f'#line {line} "{path}"\n{method}')
    generated = fixture.replace(marker, "#define SMOOTH_FONT\n" + "\n".join(methods))
    with tempfile.TemporaryDirectory(prefix="tft-font-files-") as temp:
        source_path = pathlib.Path(temp) / "font_files.cpp"
        binary = pathlib.Path(temp) / "font_files"
        source_path.write_text(generated)
        subprocess.run(
            [compiler, "-std=c++11", "-Wall", "-Wextra", "-fsanitize=address,undefined",
             "-fno-sanitize-recover=all", "-I", str(root / "tests/host"), str(source_path),
             "-o", str(binary)], check=True
        )
        subprocess.run([str(binary)], check=True)
    print("PASS font-files")


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


def run_memory_case(root: pathlib.Path, case: str) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    signatures = {
        "spi-pixels": (("src/TFT_eSPI.cpp", "void TFT_eSPI::pushSwapBytePixels(const void* data_in, uint32_t len) {"),),
        "sprite-rotation": (
            ("src/internal/Sprite.inc", "uint16_t TFT_eSprite::readPixelValue(int32_t x, int32_t y) {"),
            ("src/internal/Sprite.inc", "uint16_t TFT_eSprite::readPixel(int32_t x, int32_t y) {"),
            ("src/internal/Sprite.inc", "void TFT_eSprite::drawPixel(int32_t x, int32_t y, uint32_t color) {"),
            ("src/internal/Sprite.inc", "void TFT_eSprite::setRotation(uint8_t r) {"),
        ),
        "gfx-initialization": (
            ("src/TFT_eSPI.cpp", "int16_t TFT_eSPI::fontHeight(uint8_t font) {"),
            ("src/TFT_eSPI.cpp", "int16_t TFT_eSPI::textWidth(const char* string, uint8_t font) {"),
            ("src/TFT_eSPI.cpp", "int16_t TFT_eSPI::drawString(const char* string, int32_t poX, int32_t poY, uint8_t font) {"),
        ),
    }
    fixture = (root / "tests/host" / ("test_" + case.replace("-", "_") + ".cpp")).read_text()
    marker = "// FUNCTIONS UNDER TEST"
    if fixture.count(marker) != 1:
        raise ValueError("expected exactly one unique function insertion marker")
    methods = []
    for path, signature in signatures[case]:
        method, line = extract_method((root / path).read_text(), signature)
        methods.append(f'#line {line} "{path}"\n{method}')
    if case == "spi-pixels":
        macro = re.search(r"^#define DAT8TO32\(P\).*$", (root / "src/TFT_eSPI.h").read_text(), re.MULTILINE)
        if not macro:
            raise ValueError("pixel conversion macro missing")
        fixture = fixture.replace("// DAT8TO32 UNDER TEST", macro.group(0))
    if case == "gfx-initialization":
        declaration = re.search(r"^\s*GFXfont\* gfxFont[^\n]*", (root / "src/TFT_eSPI.h").read_text(), re.MULTILINE)
        if not declaration:
            raise ValueError("FreeFont member declaration missing")
        fixture = fixture.replace("// MEMBER UNDER TEST", declaration.group(0))
    generated = fixture.replace(marker, "\n".join(methods))
    with tempfile.TemporaryDirectory(prefix="tft-" + case + "-") as temp:
        source = pathlib.Path(temp) / "case.cpp"
        binary = pathlib.Path(temp) / "case"
        source.write_text(generated)
        subprocess.run(
            [compiler, "-std=c++11", "-Wall", "-Wextra", "-fsanitize=address,undefined",
             "-fno-sanitize-recover=all", "-I", str(root / "tests/host"), str(source), "-o", str(binary)],
            check=True,
        )
        subprocess.run([str(binary)], check=True)
    print("PASS " + case)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        choices=("scroll", "font-metrics", "allocations", "glyph-allocation", "font-files", "spi-pixels", "sprite-rotation", "all"),
        default="all",
    )
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[2]
    if args.case in ("scroll", "all"):
        run_scroll(root)
    if args.case in ("font-metrics", "all"):
        run_font_metrics(root)
    if args.case in ("allocations", "all"):
        run_allocations(root)
    if args.case in ("glyph-allocation", "all"):
        run_glyph_allocation(root)
    if args.case in ("font-files", "spi-pixels", "all"):
        run_font_files(root)
    if args.case in ("spi-pixels", "all"):
        run_memory_case(root, "spi-pixels")
    if args.case in ("sprite-rotation", "all"):
        run_memory_case(root, "sprite-rotation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
