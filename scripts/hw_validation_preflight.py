"""Create a local, build-only hardware-validation preflight report."""

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile


MAX_FIRMWARE_BYTES = 8 * 1024 * 1024
PROFILE_PATH = pathlib.Path("simulator/profiles/nodemcu-st7789-240x240.json")


def _defines(path):
    defines = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*#define\s+(\w+)(?:\s+(.+?))?\s*$", line)
        if match:
            defines[match.group(1)] = (match.group(2) or "").strip()
    return defines


def _number(defines, name):
    value = defines.get(name)
    if value is None or not re.fullmatch(r"\d+", value):
        raise ValueError("invalid or missing {} in User_Setup.h".format(name))
    return int(value)


def _hardware_output_root(root):
    build_root = (root / ".build").resolve()
    hardware_root = (root / ".build/hardware").resolve()
    if not build_root.is_relative_to(root) or not hardware_root.is_relative_to(build_root):
        raise ValueError(".build/hardware resolved outside the repository build directory")
    return hardware_root


def build_report(repo_root, firmware_path, source_sha, dirty, source_sha_short=None,
                 build_info=None):
    root = pathlib.Path(repo_root).resolve()
    sha = str(source_sha).lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("source SHA must be a full 40-character Git SHA")

    source_sha_short = source_sha_short or sha[:8]
    if not re.fullmatch(r"[0-9a-f]+", source_sha_short) or not sha.startswith(source_sha_short):
        raise ValueError("short source SHA must be a prefix of the full source SHA")
    if not isinstance(build_info, dict) or any(not build_info.get(key) for key in
            ("command", "python", "platformio", "platform", "framework", "compiler")):
        raise ValueError("complete build toolchain metadata is required")
    state = "dirty" if dirty else "clean"
    hardware_root = _hardware_output_root(root)
    build_root = hardware_root / "validation-{}-{}".format(source_sha_short, state)
    if not build_root.resolve().is_relative_to(hardware_root):
        raise ValueError("hardware build directory escaped .build/hardware")
    expected = build_root / ".pio/build/nodemcuv2/firmware.bin"
    firmware = pathlib.Path(firmware_path)
    if not firmware.is_absolute():
        firmware = root / firmware
    firmware = firmware.resolve()
    if firmware != expected.resolve() or not firmware.is_relative_to(hardware_root):
        raise ValueError("firmware must be the expected build artifact under .build/hardware")
    if not firmware.is_file():
        raise ValueError("firmware artifact is missing: {}".format(firmware.relative_to(root)))
    size = firmware.stat().st_size
    if size == 0 or size > MAX_FIRMWARE_BYTES:
        raise ValueError("firmware size is empty or exceeds the 8 MiB safety limit")

    setup_path = root / "User_Setup.h"
    setup = _defines(setup_path)
    profile_path = root / PROFILE_PATH
    try:
        simulator_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid simulator profile: {}".format(exc)) from exc
    if (not isinstance(simulator_profile, dict) or simulator_profile.get("schema_version") != 1
            or simulator_profile.get("pixel_format") != "RGB565"
            or not isinstance(simulator_profile.get("visible"), dict)
            or not isinstance(simulator_profile.get("gram"), dict)):
        raise ValueError("invalid simulator profile: expected an object with visible dimensions")

    width, height = _number(setup, "TFT_WIDTH"), _number(setup, "TFT_HEIGHT")
    visible = simulator_profile["visible"]
    gram = simulator_profile["gram"]
    offsets = (visible.get("offset_x", 0), visible.get("offset_y", 0))
    if ("ST7789_DRIVER" not in setup or setup.get("ST7789_DRIVER")
            or simulator_profile.get("controller") != "ST7789"
            or simulator_profile.get("board") != "nodemcuv2"
            or visible.get("width") != width or visible.get("height") != height
            or any(type(offset) is not int or offset < 0 for offset in offsets)
            or any(type(gram.get(key)) is not int or gram[key] <= 0
                   for key in ("width", "height"))
            or offsets[0] + width > gram["width"]
            or offsets[1] + height > gram["height"]
            or simulator_profile.get("supported_rotations") != [0, 1, 2, 3]):
        raise ValueError("repository setup and simulator display profile do not match")

    source_profile = {
        "board": "nodemcuv2",
        "controller": "ST7789",
        "visible": {"width": width, "height": height},
        "mosi": _number(setup, "TFT_MOSI"),
        "sclk": _number(setup, "TFT_SCLK"),
        "dc": _number(setup, "TFT_DC"),
        "reset": _number(setup, "TFT_RST"),
        "backlight": _number(setup, "TFT_BL"),
        "backlight_active": setup.get("TFT_BACKLIGHT_ON", "unspecified"),
        "spi_hz": _number(setup, "SPI_FREQUENCY"),
        "spi_mode": setup.get("TFT_SPI_MODE", "SPI_MODE3 (library default)"),
        "chip_select": "not defined; documented as tied to GND",
        "miso": "not defined; no display readback",
        "rgb_order": setup.get("TFT_RGB_ORDER", "library default"),
        "inversion": "enabled" if "TFT_INVERSION_ON" in setup else "disabled",
    }
    binary_hash = hashlib.sha256(firmware.read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "status": "BLOCKED" if dirty else "READY_FOR_MANUAL_REVIEW",
        "source_sha": sha,
        "source_sha_short": source_sha_short,
        "source_tree_dirty": bool(dirty),
        "build": build_info,
        "board": "nodemcuv2",
        "firmware_path": firmware.relative_to(root).as_posix(),
        "firmware_size_bytes": size,
        "firmware_sha256": binary_hash,
        "profile": source_profile,
        "simulator_profile": simulator_profile,
        "expected_boot": ["HWTEST,2", "RUN", "menu", "READY"],
        "serial_protocol": ["?", "B", "S", "S1-S4", "L", "M", "E30", "X", "N", "Q"],
        "upload_authorized": False,
        "serial_port_selected": False,
        "operator_hardware_confirmed": False,
        "physical_tests": "NOT_EXECUTED",
        "next_checkpoint": "H1: explicit operator authorization is required before any upload",
    }


def write_report(repo_root, report):
    root = pathlib.Path(repo_root).resolve()
    hardware_root = _hardware_output_root(root)
    output = hardware_root / "preflight-{}-{}".format(
        report["source_sha_short"], "dirty" if report["source_tree_dirty"] else "clean")
    output = output.resolve()
    if not output.is_relative_to(hardware_root):
        raise ValueError("preflight output escaped .build/hardware")
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "preflight.json"
    markdown_path = output / "preflight.md"
    _atomic_write(json_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    profile = report["profile"]
    _atomic_write(markdown_path,
        "# Hardware validation preflight\n\n"
        "**Status:** {}  \n**Source SHA:** `{}`  \n**Firmware:** `{}`  \n"
        "**Firmware SHA-256:** `{}`  \n**Size:** {} bytes  \n"
        "**Board/profile:** {} / {}×{} ST7789  \n"
        "**Build:** Python {}; PlatformIO {}; ESP8266 platform {}; Arduino framework {}; Xtensa compiler {}  \n"
        "**Build command:** `{}`  \n"
        "**SPI:** {} Hz, {}  \n**Pins:** MOSI {}, SCLK {}, DC {}, reset {}, backlight {} ({})\n\n"
        "## Expected behavior\n\n"
        "Boot initializes the display, emits `HWTEST,2`, `RUN`, the menu, and `READY`. "
        "No validation suite starts automatically.\n\n"
        "## Authorization boundary\n\n"
        "**NOT AUTHORIZED:** no serial port is selected; upload, bootloader entry, reset, "
        "serial observation, and physical tests have not been approved or performed. "
        "Confirm the assembled board, panel, wiring, voltage, and upload procedure manually. "
        "H1 requires separate explicit operator authorization.\n\n"
        "Physical status: `{}`. This report proves a source-bound build artifact only; "
        "it does not prove display or hardware behavior.\n".format(
            report["status"], report["source_sha"], report["firmware_path"],
            report["firmware_sha256"], report["firmware_size_bytes"], report["board"],
            profile["visible"]["width"], profile["visible"]["height"],
            report["build"]["python"], report["build"]["platformio"],
            report["build"]["platform"], report["build"]["framework"],
            report["build"]["compiler"], " ".join(report["build"]["command"]),
            profile["spi_hz"],
            profile["spi_mode"], profile["mosi"], profile["sclk"], profile["dc"],
            profile["reset"], profile["backlight"], profile["backlight_active"],
            report["physical_tests"]),
    )
    return json_path, markdown_path


def _atomic_write(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix=".preflight-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _package_version(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))["version"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read installed tool version from {}".format(path)) from exc


def collect_build_info(command):
    pio = shutil.which("pio")
    if not pio:
        raise ValueError("PlatformIO executable is not available on PATH")
    pio_version = subprocess.run([pio, "--version"], check=True, capture_output=True,
                                 text=True).stdout.strip()
    core = pathlib.Path(os.environ.get(
        "PLATFORMIO_CORE_DIR", str(pathlib.Path.home() / ".platformio"))).resolve()
    packages = core / "packages"
    platform = _package_version(core / "platforms/espressif8266/platform.json")
    framework = _package_version(packages / "framework-arduinoespressif8266/package.json")
    compiler_package = packages / "toolchain-xtensa"
    compiler_package_version = _package_version(compiler_package / "package.json")
    compiler = compiler_package / "bin/xtensa-lx106-elf-g++"
    compiler_version = subprocess.run([str(compiler), "--version"], check=True,
                                       capture_output=True, text=True).stdout.splitlines()[0]
    return {"command": list(command), "python": sys.version.split()[0],
            "platformio": pio_version, "platform": platform,
            "framework": framework,
            "compiler": "{} ({})".format(compiler_version, compiler_package_version)}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    source_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                                capture_output=True, text=True).stdout.strip()
    source_sha_short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                                      check=True, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True,
                                capture_output=True, text=True).stdout)
    firmware = (root / ".build/hardware" / "validation-{}-{}".format(
        source_sha_short, "dirty" if dirty else "clean") /
        ".pio/build/nodemcuv2/firmware.bin")
    try:
        command = ["make", "test-hw-preflight", "(includes test-hw-build; no upload or serial access)"]
        build_info = collect_build_info(command)
        report = build_report(root, firmware, source_sha, dirty, source_sha_short, build_info)
        json_path, markdown_path = write_report(root, report)
    except (OSError, ValueError) as exc:
        print("Hardware preflight blocked: {}".format(exc), file=sys.stderr)
        return 1
    print("{}: {}".format(report["status"], markdown_path.relative_to(root)))
    print("Firmware SHA-256: {}".format(report["firmware_sha256"]))
    print("Machine-readable report: {}".format(json_path.relative_to(root)))
    return 0 if not dirty else 1


if __name__ == "__main__":
    raise SystemExit(main())
