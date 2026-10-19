#!/usr/bin/env python3
"""Compile source-extracted host regressions with sanitizers."""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys
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


def run_scroll(root: pathlib.Path, fuzz: bool = False, fuzz_time: int = 60, timeout: int = 5) -> None:
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

    if fuzz:
        compiler = shutil.which("clang++")
        if not compiler:
            raise RuntimeError("clang++ compiler required for fuzz target")
        # Check if compiler supports -fsanitize=fuzzer
        probe = subprocess.run(
            [compiler, "-fsanitize=fuzzer", "-x", "c++", "-", "-o", "/dev/null"],
            input=b'extern "C" int LLVMFuzzerTestOneInput(const unsigned char*, unsigned long) { return 0; }\n',
            capture_output=True,
        )
        if probe.returncode != 0:
            raise RuntimeError(
                f"clang++ at {compiler} does not support libFuzzer (-fsanitize=fuzzer): {probe.stderr.decode()}"
            )

        build_dir = root / ".build/fuzz/scroll"
        build_dir.mkdir(parents=True, exist_ok=True)
        corpus_dir = root / "tests/host/corpus/scroll"
        corpus_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="tft-fuzz-") as temp:
            source = pathlib.Path(temp) / "fuzz_scroll.cpp"
            binary = pathlib.Path(temp) / "fuzz_scroll"
            source.write_text(generated)
            subprocess.run(
                [
                    compiler,
                    "-std=c++11",
                    "-Wall",
                    "-Wextra",
                    "-DFUZZ_TARGET",
                    "-fsanitize=fuzzer,address,undefined",
                    "-fno-sanitize-recover=all",
                    str(source),
                    "-o",
                    str(binary),
                ],
                check=True,
            )

            cmd = [
                str(binary),
                f"-max_total_time={fuzz_time}",
                f"-timeout={timeout}",
                f"-artifact_prefix={build_dir}/",
                str(build_dir),
                str(corpus_dir),
            ]
            env = dict(subprocess.os.environ)
            env["ASAN_OPTIONS"] = (
                f"{env.get('ASAN_OPTIONS', '')}:detect_leaks=0".lstrip(":")
            )
            subprocess.run(cmd, env=env, check=True)
        print("PASS fuzz-scroll")
        return

    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    with tempfile.TemporaryDirectory(prefix="tft-host-") as temp:
        source = pathlib.Path(temp) / "scroll.cpp"
        binary = pathlib.Path(temp) / "scroll"
        source.write_text(generated)
        subprocess.run(
            [
                compiler,
                "-std=c++11",
                "-Wall",
                "-Wextra",
                "-fsanitize=address,undefined",
                "-fno-sanitize-recover=all",
                str(source),
                "-o",
                str(binary),
            ],
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
        "sprite-clipping": (
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


def run_clipping_case(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    fixture = (root / "tests/host/test_clipping.cpp").read_text()
    marker = "// FUNCTIONS UNDER TEST"
    source = (root / "src/TFT_eSPI.cpp").read_text()
    methods = []
    for signature in (
        "void TFT_eSPI::setViewport(int32_t x, int32_t y, int32_t w, int32_t h, bool vpDatum) {",
        "void TFT_eSPI::drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t color) {",
        "void TFT_eSPI::drawFastVLine(int32_t x, int32_t y, int32_t h, uint32_t color) {",
        "void TFT_eSPI::fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color) {",
        "void TFT_eSPI::drawRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color) {",
    ):
        method, line = extract_method(source, signature)
        methods.append(f'#line {line} "src/TFT_eSPI.cpp"\n{method}')
    if fixture.count(marker) != 1:
        raise ValueError("expected exactly one unique function insertion marker")
    generated = fixture.replace(marker, "\n".join(methods))
    with tempfile.TemporaryDirectory(prefix="tft-clipping-") as temp:
        cpp = pathlib.Path(temp) / "clipping.cpp"
        binary = pathlib.Path(temp) / "clipping"
        cpp.write_text(generated)
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-fsanitize=address,undefined",
                        "-fno-sanitize-recover=all", "-I", str(root / "tests/host"), "-I", str(root / "src"), str(cpp), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS clipping")


def run_image_clipping(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    fixture = (root / "tests/host/test_image_clipping.cpp").read_text()
    source = (root / "src/TFT_eSPI.cpp").read_text()
    method, line = extract_method(
        source,
        "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t* data) {",
    )
    bitmap, bitmap_line = extract_method(
        source,
        "void TFT_eSPI::drawBitmap(int16_t x, int16_t y, const uint8_t* bitmap, int16_t w, int16_t h,\n                          uint16_t color) {",
    )
    generated = fixture.replace("// FUNCTION UNDER TEST", f'#line {line} "src/TFT_eSPI.cpp"\n{method}')
    generated = generated.replace("// BITMAP FUNCTION UNDER TEST", f'#line {bitmap_line} "src/TFT_eSPI.cpp"\n{bitmap}')
    with tempfile.TemporaryDirectory(prefix="tft-image-clipping-") as temp:
        cpp = pathlib.Path(temp) / "case.cpp"
        binary = pathlib.Path(temp) / "case"
        cpp.write_text(generated)
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-fsanitize=address,undefined",
                        "-fno-sanitize-recover=all", "-I", str(root / "tests/host"), str(cpp), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS image-clipping")


def run_text_clipping(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    fixture = (root / "tests/host/test_text_clipping.cpp").read_text()
    source = (root / "src/TFT_eSPI.cpp").read_text()
    methods = []
    for signature in (
        "void TFT_eSPI::fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color) {",
        "int16_t TFT_eSPI::drawChar(uint16_t uniCode, int32_t x, int32_t y, uint8_t font) {",
        "void TFT_eSPI::drawChar(int32_t x, int32_t y, uint16_t c, uint32_t color, uint32_t bg,\n                        uint8_t size) {",
    ):
        method, line = extract_method(source, signature)
        methods.append(f'#line {line} "src/TFT_eSPI.cpp"\n{method}')
    if fixture.count("// FUNCTIONS UNDER TEST") != 1:
        raise ValueError("expected exactly one unique function insertion marker")
    generated = fixture.replace("// FUNCTIONS UNDER TEST", "\n".join(methods))
    with tempfile.TemporaryDirectory(prefix="tft-text-clipping-") as temp:
        cpp = pathlib.Path(temp) / "case.cpp"
        binary = pathlib.Path(temp) / "case"
        cpp.write_text(generated)
        subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Wno-int-to-pointer-cast", "-fsanitize=address,undefined",
                        "-fno-sanitize-recover=all", "-I", str(root / "src"), str(cpp), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS text-clipping fonts 1 and 2")
    print("SKIP text-font-4: no independent host RLE glyph fixture")


def run_extreme_coordinates(root: pathlib.Path, case_id: str = None, fuzz: bool = False,
                             fuzz_time: int = 60, timeout: int = 2) -> None:
    compiler = shutil.which("clang++" if fuzz else "c++")
    if not compiler:
        print("SKIP extreme-coordinate fuzz: clang++ is unavailable" if fuzz else
              "FAIL extreme-coordinates: c++ is unavailable")
        if not fuzz:
            raise RuntimeError("C++ compiler required for host tests")
        return
    fixture = (root / "tests/host/test_extreme_coordinates.cpp").read_text()
    library_source = (root / "src/TFT_eSPI.cpp").read_text()
    methods = []
    for signature in (
        "void TFT_eSPI::setViewport(int32_t x, int32_t y, int32_t w, int32_t h, bool vpDatum) {",
        "void TFT_eSPI::drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t color) {",
        "void TFT_eSPI::fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color) {",
        "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t* data) {",
    ):
        method, line = extract_method(library_source, signature)
        methods.append(f'#line {line} "src/TFT_eSPI.cpp"\n{method}')
    generated = fixture.replace("// FUNCTIONS UNDER TEST", "\n".join(methods))
    if fuzz:
        generated = "#define FUZZ_TARGET\n" + generated
    with tempfile.TemporaryDirectory(prefix="tft-extremes-") as temp:
        cpp = pathlib.Path(temp) / "extremes.cpp"
        binary = pathlib.Path(temp) / "extremes"
        cpp.write_text(generated)
        command = [compiler, "-std=c++11", "-Wall", "-Wextra",
                   "-fsanitize=fuzzer,address,undefined" if fuzz else "-fsanitize=address,undefined",
                   "-fno-sanitize-recover=all", "-I", str(root / "src"), "-I", str(root / "tests/host"), str(cpp), "-o", str(binary)]
        subprocess.run(command, check=True)
        if fuzz:
            corpus = root / "tests/host/corpus/extremes"
            artifact_dir = root / ".build/fuzz/extremes"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run([str(binary), f"-max_total_time={fuzz_time}", f"-timeout={timeout}",
                            f"-artifact_prefix={artifact_dir}/", str(corpus)], check=True)
            print("PASS extreme-coordinate fuzz")
            return
        sys.path.insert(0, str(root))
        from tests.host.extremes_runner import run_case
        cases = re.findall(r'\{"([^\"]+)"', (root / "tests/host/extreme_cases.h").read_text())
        results = [run_case(str(binary), current, timeout_s=timeout)
                   for current in ([case_id] if case_id else cases)]
        for result in results:
            print("{} {} ({:.3f}s)".format(result["status"], result["case_id"], result["duration_s"]))
        if any(result["status"] in ("FAIL", "TIMEOUT") for result in results):
            raise RuntimeError("extreme-coordinate case failed; see .build/fuzz/extremes/*.stderr")


def run_validation_unit(root: pathlib.Path) -> None:
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for validation protocol tests")
    sources = ("test_validation_command.cpp", "test_validation_bench_math.cpp",
               "test_validation_stress_math.cpp", "test_validation_oracle.cpp",
               "test_validation_perf_protocol.cpp", "test_validation_input.cpp",
               "test_validation_frame_math.cpp", "test_validation_frame_workloads.cpp",
               "test_validation_heap_churn.cpp", "test_validation_soak.cpp")
    includes = (root / "extras/hardware/Audit_Validation", root / "tests/host")
    with tempfile.TemporaryDirectory(prefix="tft-validation-unit-") as temp:
        for name in sources:
            source = root / "tests/host" / name
            binary = pathlib.Path(temp) / source.stem
            subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                            *(arg for include in includes for arg in ("-I", str(include))),
                            str(source),
                            *([str(root / "extras/hardware/Audit_Validation/ValidationPerfTelemetry.cpp")]
                              if name == "test_validation_perf_protocol.cpp" else []),
                            *([str(root / "extras/hardware/Audit_Validation/ValidationInput.cpp")]
                              if name in ("test_validation_input.cpp", "test_validation_frame_workloads.cpp") else []),
                            *([str(root / "extras/hardware/Audit_Validation/ValidationPerfTelemetry.cpp"),
                               str(root / "extras/hardware/Audit_Validation/ValidationFramePerf.cpp")]
                              if name == "test_validation_frame_workloads.cpp" else []),
                            *([str(root / "extras/hardware/Audit_Validation/ValidationInput.cpp"),
                               str(root / "extras/hardware/Audit_Validation/ValidationPerfTelemetry.cpp"),
                               str(root / "extras/hardware/Audit_Validation/ValidationMemoryExtended.cpp")]
                              if name == "test_validation_heap_churn.cpp" else []),
                            *([str(root / "extras/hardware/Audit_Validation/ValidationInput.cpp"),
                               str(root / "extras/hardware/Audit_Validation/ValidationPerfTelemetry.cpp"),
                               str(root / "extras/hardware/Audit_Validation/ValidationFramePerf.cpp"),
                               str(root / "extras/hardware/Audit_Validation/ValidationMemoryExtended.cpp"),
                               str(root / "extras/hardware/Audit_Validation/ValidationTelemetry.cpp"),
                               str(root / "extras/hardware/Audit_Validation/ValidationSoak.cpp")]
                              if name == "test_validation_soak.cpp" else []),
                            "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            print("PASS validation-{}".format(source.stem.removeprefix("test_validation_")))


def run_stateful_graphics(root: pathlib.Path) -> None:
    fixture = (root / "tests/host/test_validation_stateful.cpp").read_text()
    source = (root / "src/TFT_eSPI.cpp").read_text()
    signatures = (
        "void TFT_eSPI::setViewport(int32_t x, int32_t y, int32_t w, int32_t h, bool vpDatum) {",
        "void TFT_eSPI::drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t color) {",
        "void TFT_eSPI::fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color) {",
        "void TFT_eSPI::setSwapBytes(bool swap) {",
        "void TFT_eSPI::setTextFont(uint8_t f) {",
    )
    methods = []
    for signature in signatures:
        method, line = extract_method(source, signature)
        methods.append(f'#line {line} "src/TFT_eSPI.cpp"\n{method}')
    generated = fixture.replace("// FUNCTIONS UNDER TEST", "\n".join(methods))
    with tempfile.TemporaryDirectory(prefix="tft-stateful-") as temp:
        source_path = pathlib.Path(temp) / "stateful.cpp"
        binary = pathlib.Path(temp) / "stateful"
        source_path.write_text(generated)
        subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                        "-I", str(root / "src"), "-I", str(root / "tests/host"), str(source_path),
                        "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS stateful-graphics")


RENDER_SIGNATURES = (
    "inline void TFT_eSPI::begin_tft_write(void) {",
    "inline void TFT_eSPI::end_tft_write(void) {",
    "void TFT_eSPI::pushBlock(uint16_t color, uint32_t len) {",
    "void TFT_eSPI::pushPixels(const void* data_in, uint32_t len) {",
    "void TFT_eSPI::pushSwapBytePixels(const void* data_in, uint32_t len) {",
    "void TFT_eSPI::setWindow(int32_t x0, int32_t y0, int32_t x1, int32_t y1) {",
    "void TFT_eSPI::drawPixel(int32_t x, int32_t y, uint32_t color) {",
    "void TFT_eSPI::fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color) {",
    "void TFT_eSPI::drawFastVLine(int32_t x, int32_t y, int32_t h, uint32_t color) {",
    "void TFT_eSPI::drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t color) {",
    "void TFT_eSPI::drawRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color) {",
    "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t* data) {",
    "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint16_t* data,\n",
    "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t* data) {",
    "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t* data,\n",
    "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint8_t* data, bool bpp8,",
    "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint8_t* data, bool bpp8,",
    "void TFT_eSPI::pushImage(int32_t x, int32_t y, int32_t w, int32_t h, uint8_t* data, uint8_t transp,",
    "void TFT_eSPI::drawChar(int32_t x, int32_t y, uint16_t c, uint32_t color, uint32_t bg,",
    "int16_t TFT_eSPI::drawChar(uint16_t uniCode, int32_t x, int32_t y, uint8_t font) {",
)


def run_render_stream(root: pathlib.Path, table: bool = False) -> None:
    """Replay render primitives through a simulated ESP8266 SPI bus and ST7789 controller."""
    compiler = shutil.which("c++")
    if not compiler:
        raise RuntimeError("C++ compiler required for host tests")
    source = (root / "src/TFT_eSPI.cpp").read_text()
    header = (root / "src/TFT_eSPI.h").read_text()
    macros = header[header.index("#define CMD_BITS 8") : header.index("#ifndef tft_Write_16N")]
    macros += re.search(r"^#define DAT8TO32\(P\).*$", header, re.MULTILINE).group(0) + "\n"
    clip = source[source.index("#ifndef SPI_BUSY_CHECK") : source.index("/****", source.index("#define PI_CLIP"))]
    methods = []
    for signature in RENDER_SIGNATURES:
        method, line = extract_method(source, signature)
        method = method.replace("inline void", "void", 1).replace("uint32_t flash_address", "uintptr_t flash_address")
        methods.append(f'#line {line} "src/TFT_eSPI.cpp"\n{method}')
    fixture = (root / "tests/host/test_render_stream.cpp").read_text()
    for marker in ("// HEADER MACROS UNDER TEST", "// FUNCTIONS UNDER TEST"):
        if fixture.count(marker) != 1:
            raise ValueError("expected exactly one unique insertion marker: " + marker)
    generated = fixture.replace("// HEADER MACROS UNDER TEST", macros).replace(
        "// FUNCTIONS UNDER TEST", clip + "\n" + "\n".join(methods)
    )
    with tempfile.TemporaryDirectory(prefix="tft-render-stream-") as temp:
        source_path = pathlib.Path(temp) / "render_stream.cpp"
        binary = pathlib.Path(temp) / "render_stream"
        source_path.write_text(generated)
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra",
             "-fsanitize=address" if table else "-fsanitize=address,undefined",
             "-fno-sanitize-recover=all", "-I", str(root / "src"), str(source_path), "-o", str(binary)],
            check=True,
        )
        subprocess.run([str(binary)] + (["--table"] if table else []), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        choices=("scroll", "font-metrics", "allocations", "glyph-allocation", "font-files", "spi-pixels", "sprite-rotation", "sprite-clipping", "text-clipping", "gfx-initialization", "clipping", "image-clipping", "extreme-coordinates", "validation-unit", "stateful-graphics", "render-stream", "all"),
        default="all",
    )
    parser.add_argument(
        "--fuzz",
        action="store_true",
        help="Run libFuzzer on supported targets (e.g. scroll)",
    )
    parser.add_argument(
        "--fuzz-time",
        type=int,
        default=60,
        help="Fuzzing duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--fuzz-timeout",
        type=int,
        default=5,
        help="Timeout per input in seconds (default: 5)",
    )
    parser.add_argument("--case-id", help="Run one extreme-coordinate case ID")
    parser.add_argument(
        "--table",
        action="store_true",
        help="Print the render-stream table instead of checking",
    )
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[2]
    if args.fuzz and args.case not in ("scroll", "extreme-coordinates"):
        raise ValueError("--fuzz currently supports scroll and extreme-coordinates")
    if args.case in ("scroll", "all"):
        run_scroll(root, fuzz=args.fuzz, fuzz_time=args.fuzz_time, timeout=args.fuzz_timeout)
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
    if args.case in ("sprite-clipping", "all"):
        run_memory_case(root, "sprite-clipping")
    if args.case in ("gfx-initialization", "all"):
        run_memory_case(root, "gfx-initialization")
    if args.case in ("clipping", "all"):
        run_clipping_case(root)
    if args.case in ("image-clipping", "all"):
        run_image_clipping(root)
    if args.case in ("text-clipping", "all"):
        run_text_clipping(root)
    if args.case == "extreme-coordinates":
        run_extreme_coordinates(root, args.case_id, args.fuzz, args.fuzz_time, args.fuzz_timeout)
    if args.case in ("validation-unit", "all"):
        run_validation_unit(root)
    if args.case in ("stateful-graphics", "all"):
        run_stateful_graphics(root)
    if args.case in ("render-stream", "all"):
        run_render_stream(root, table=args.table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
