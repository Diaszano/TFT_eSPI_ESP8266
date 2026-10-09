#!/usr/bin/env python3
"""Compile the maintained examples and compile regressions with Arduino CLI."""
import pathlib
import re
import shutil
import subprocess
import sys

CLI_VERSION = "1.3.1"
CORE_VERSION = "3.1.2"
FQBN = "esp8266:esp8266:nodemcuv2"
MINIMAL_FLAGS = " ".join((
    "-DUSER_SETUP_LOADED", "-DST7789_DRIVER", "-DTFT_WIDTH=240",
    "-DTFT_HEIGHT=240", "-DTFT_MOSI=13", "-DTFT_SCLK=14", "-DTFT_DC=0",
    "-DTFT_RST=2", "-DSPI_FREQUENCY=40000000", "-DLOAD_GLCD",
))


def compile_examples(root: pathlib.Path, cli: str = "arduino-cli", run=subprocess.run) -> None:
    root = pathlib.Path(root).resolve()
    version = run([cli, "version"], check=True, capture_output=True, text=True).stdout
    if not re.search(r"\bVersion:\s+" + re.escape(CLI_VERSION) + r"(?=\s|$)", version):
        raise ValueError(f"Arduino CLI {CLI_VERSION} is required: {version.strip()}")
    cores = run([cli, "core", "list"], check=True, capture_output=True, text=True).stdout
    if not re.search(r"^esp8266:esp8266\s+" + re.escape(CORE_VERSION) + r"\s", cores, re.MULTILINE):
        raise ValueError(f"ESP8266 core {CORE_VERSION} is required")
    examples = sorted(path for path in (root / "examples").iterdir()
                      if path.is_dir() and (path / f"{path.name}.ino").is_file())
    if len(examples) != 14:
        raise ValueError(f"expected 14 maintained examples, found {len(examples)}")
    output = root / ".build/arduino"
    output.mkdir(parents=True, exist_ok=True)

    def compile_one(sketch: pathlib.Path, name: str, flags: str = "") -> None:
        command = [cli, "compile", "--fqbn", FQBN, "--library", str(root),
                   "--warnings", "all", "--clean", "--build-path", str(output / name)]
        if flags:
            command.extend(["--build-property", f"compiler.cpp.extra_flags={flags}"])
        command.append(str(sketch))
        with (output / f"{name}.log").open("w", encoding="utf-8") as log:
            result = run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            print((output / f"{name}.log").read_text(), file=sys.stderr)
            raise RuntimeError(f"Arduino compile failed: {name}")
        print((output / f"{name}.log").read_text(), end="")
        print(f"PASS Arduino {name}")

    for example in examples:
        compile_one(example, example.name)
    for name in ("sprite_ownership", "minimal_setup", "firmware_memory"):
        sketch = output / "sketches" / name
        sketch.mkdir(parents=True, exist_ok=True)
        (sketch / f"{name}.ino").write_text("// Entry point is in the copied C++ regression.\n")
        shutil.copyfile(root / f"tests/compile/{name}/{name}.cpp", sketch / f"{name}.cpp")
        compile_one(sketch, name, MINIMAL_FLAGS if name == "minimal_setup" else "")


def main() -> int:
    try:
        compile_examples(pathlib.Path(__file__).resolve().parents[1])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
