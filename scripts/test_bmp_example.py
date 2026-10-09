import importlib.util
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bmp_host_runner", ROOT / "tests/host/run.py")
host_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host_runner)


class BmpExampleTests(unittest.TestCase):
    def test_real_parser_crops_and_rejects_invalid_input(self):
        compiler = shutil.which("c++")
        self.assertIsNotNone(compiler, "C++ compiler required for BMP regression")
        path = "examples/TFT_SPIFFS_BMP/TFT_SPIFFS_BMP.ino"
        source = (ROOT / path).read_text()
        methods = []
        signatures = (
            ("uint16_t bmpRead16(const uint8_t* data) {", "uint32_t bmpRead32(const uint8_t* data) {")
            if "uint16_t bmpRead16(" in source else
            ("uint16_t read16(fs::File& f) {", "uint32_t read32(fs::File& f) {")
        )
        for signature in (*signatures, "void drawBmp(const char* filename, int16_t x, int16_t y) {"):
            method, line = host_runner.extract_method(source, signature)
            methods.append(f'#line {line} "{path}"\n{method}')
        fixture = (ROOT / "tests/host/test_bmp_example.cpp").read_text()
        self.assertEqual(fixture.count("// FUNCTIONS UNDER TEST"), 1)
        generated = fixture.replace("// FUNCTIONS UNDER TEST", "\n".join(methods))
        with tempfile.TemporaryDirectory(prefix="tft-bmp-") as temp:
            cpp = pathlib.Path(temp) / "bmp.cpp"
            binary = pathlib.Path(temp) / "bmp"
            cpp.write_text(generated)
            subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra",
                            "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                            str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
