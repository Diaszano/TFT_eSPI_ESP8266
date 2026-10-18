import hashlib
import json
import pathlib
import tempfile
import unittest

from scripts.hw_validation_preflight import build_report, write_report


SHA = "75cab508b52463f52e7faa455071259d79f33e53"


class HardwarePreflightTests(unittest.TestCase):
    BUILD_INFO = {"command": ["make", "test-hw-build"], "python": "3.14.7",
                  "platformio": "PlatformIO Core, version 6.2.0", "platform": "4.2.1",
                  "framework": "3.30102.0", "compiler": "Xtensa GCC fixture"}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "User_Setup.h").write_text(
            "#define ST7789_DRIVER\n#define TFT_WIDTH 240\n#define TFT_HEIGHT 240\n"
            "#define TFT_MOSI 13\n#define TFT_SCLK 14\n#define TFT_DC 0\n"
            "#define TFT_RST 2\n#define TFT_BL 5\n#define TFT_BACKLIGHT_ON LOW\n"
            "#define SPI_FREQUENCY 40000000\n",
            encoding="utf-8",
        )
        profile_dir = self.root / "simulator/profiles"
        profile_dir.mkdir(parents=True)
        (profile_dir / "nodemcu-st7789-240x240.json").write_text(
            json.dumps({"schema_version": 1, "board": "nodemcuv2", "controller": "ST7789",
                        "visible": {"width": 240, "height": 240, "offset_x": 0, "offset_y": 0},
                        "gram": {"width": 240, "height": 320}, "pixel_format": "RGB565",
                        "supported_rotations": [0, 1, 2, 3]}),
            encoding="utf-8",
        )
        self.build = self.root / ".build/hardware" / f"validation-{SHA[:8]}-clean"
        self.firmware = self.build / ".pio/build/nodemcuv2/firmware.bin"
        self.firmware.parent.mkdir(parents=True)
        self.binary = b"fixture firmware, not executable"
        self.firmware.write_bytes(self.binary)

    def tearDown(self):
        self.temp.cleanup()

    def test_report_binds_exact_binary_to_source_and_profile(self):
        report = build_report(self.root, self.firmware, SHA, dirty=False,
                              source_sha_short=SHA[:8], build_info=self.BUILD_INFO)
        self.assertEqual(report["firmware_sha256"], hashlib.sha256(self.binary).hexdigest())
        self.assertEqual(report["source_sha"], SHA)
        self.assertEqual(report["source_sha_short"], SHA[:8])
        self.assertEqual(report["build"]["platformio"], "PlatformIO Core, version 6.2.0")
        self.assertEqual(report["profile"]["board"], "nodemcuv2")
        self.assertEqual(report["profile"]["visible"], {"width": 240, "height": 240})
        self.assertEqual(report["simulator_profile"]["gram"], {"width": 240, "height": 320})
        self.assertEqual(report["status"], "READY_FOR_MANUAL_REVIEW")
        self.assertFalse(report["upload_authorized"])
        self.assertFalse(report["serial_port_selected"])
        self.assertEqual(report["physical_tests"], "NOT_EXECUTED")

    def test_dirty_source_is_blocked_and_never_authorizes_upload(self):
        dirty_firmware = self.root / ".build/hardware" / f"validation-{SHA[:8]}-dirty/.pio/build/nodemcuv2/firmware.bin"
        dirty_firmware.parent.mkdir(parents=True)
        dirty_firmware.write_bytes(self.binary)
        report = build_report(self.root, dirty_firmware, SHA, dirty=True,
                              build_info=self.BUILD_INFO)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["upload_authorized"])

    def test_missing_firmware_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "firmware"):
            build_report(self.root, self.firmware.with_name("missing.bin"), SHA, dirty=False, build_info=self.BUILD_INFO)

    def test_empty_firmware_is_rejected(self):
        self.firmware.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "size"):
            build_report(self.root, self.firmware, SHA, dirty=False, build_info=self.BUILD_INFO)

    def test_firmware_outside_expected_build_is_rejected(self):
        outside = self.root / "firmware.bin"
        outside.write_bytes(self.binary)
        with self.assertRaisesRegex(ValueError, "expected build"):
            build_report(self.root, outside, SHA, dirty=False, build_info=self.BUILD_INFO)

    def test_symlinked_build_root_cannot_escape_hardware_directory(self):
        if not hasattr(pathlib.Path, "symlink_to"):
            self.skipTest("symlinks are unavailable")
        hardware = self.root / ".build/hardware"
        external = self.root / "external"
        external.mkdir()
        import shutil
        shutil.rmtree(hardware)
        hardware.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "outside"):
            build_report(self.root, self.firmware, SHA, dirty=False, build_info=self.BUILD_INFO)

    def test_mismatched_display_profile_is_rejected(self):
        path = self.root / "simulator/profiles/nodemcu-st7789-240x240.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["visible"]["width"] = 320
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "profile"):
            build_report(self.root, self.firmware, SHA, dirty=False, build_info=self.BUILD_INFO)

    def test_malformed_profile_is_rejected(self):
        path = self.root / "simulator/profiles/nodemcu-st7789-240x240.json"
        path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "profile"):
            build_report(self.root, self.firmware, SHA, dirty=False, build_info=self.BUILD_INFO)

    def test_visible_region_outside_gram_is_rejected(self):
        path = self.root / "simulator/profiles/nodemcu-st7789-240x240.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["visible"]["offset_y"] = 100
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "profile"):
            build_report(self.root, self.firmware, SHA, dirty=False, build_info=self.BUILD_INFO)

    def test_report_files_are_written_under_build_directory(self):
        report = build_report(self.root, self.firmware, SHA, dirty=False,
                              build_info=self.BUILD_INFO)
        json_path, markdown_path = write_report(self.root, report)
        self.assertTrue(json_path.is_relative_to(self.root / ".build/hardware"))
        self.assertTrue(markdown_path.is_relative_to(self.root / ".build/hardware"))
        self.assertEqual(json.loads(json_path.read_text())["firmware_sha256"], report["firmware_sha256"])
        self.assertIn("NOT AUTHORIZED", markdown_path.read_text())
        self.assertIn("PlatformIO Core, version 6.2.0", markdown_path.read_text())

    def test_report_replaces_symlink_without_writing_outside_build_directory(self):
        report = build_report(self.root, self.firmware, SHA, dirty=False,
                              build_info=self.BUILD_INFO)
        output = self.root / ".build/hardware" / f"preflight-{SHA[:8]}-clean"
        output.mkdir(parents=True, exist_ok=True)
        outside = self.root / "outside.json"
        outside.write_text("preserve", encoding="utf-8")
        (output / "preflight.json").symlink_to(outside)

        json_path, _ = write_report(self.root, report)

        self.assertEqual(outside.read_text(encoding="utf-8"), "preserve")
        self.assertFalse(json_path.is_symlink())
        self.assertEqual(json.loads(json_path.read_text())["source_sha"], SHA)

    def test_missing_toolchain_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "toolchain metadata"):
            build_report(self.root, self.firmware, SHA, dirty=False)

    def test_nonmatching_short_sha_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "prefix"):
            build_report(self.root, self.firmware, SHA, dirty=False, source_sha_short="deadbeef",
                         build_info=self.BUILD_INFO)


if __name__ == "__main__":
    unittest.main()
