import importlib.util
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from scripts.test_bmp2array4bit import bmp

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("palette_converter", ROOT / "Tools/bmp2array4bit/bmp2array4bit.py")
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)
spec = importlib.util.spec_from_file_location("palette_host_runner", ROOT / "tests/host/run.py")
host_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host_runner)


class PaletteConversionTests(unittest.TestCase):
    def test_rejects_unknown_indices_in_high_and_low_nibbles(self):
        for row in (b"\x20", b"\x02", b"\xf0", b"\x0f"):
            with self.subTest(row=row):
                with self.assertRaisesRegex(ValueError, "pixel index"):
                    converter.convert(bmp(2, 1, (row,), colors=2))

    def test_ignores_odd_width_tail_nibble_and_bmp_padding(self):
        generated = converter.convert(bmp(1, 1, (b"\x1f\xff\xff\xff",), colors=2))
        self.assertIn("palette[16]", generated)
        self.assertIn("myGraphic[1]", generated)
        self.assertIn("0x1f", generated)

    def test_generated_short_palette_is_safe_for_default_create_palette(self):
        compiler = shutil.which("c++")
        self.assertIsNotNone(compiler, "C++ compiler required for palette integration")
        source = (ROOT / "src/internal/Sprite.inc").read_text()
        method, line = host_runner.extract_method(
            source, "void TFT_eSprite::createPalette(const uint16_t colorMap[], uint8_t colors) {"
        )
        generated = converter.convert(bmp(3, 2, (b"\x10\x1f", b"\x01\x0f"), colors=2))
        fixture = """#include <cassert>
#include <cstdint>
#include <cstdlib>
#define PROGMEM
#define pgm_read_word(pointer) (*(pointer))
static const uint16_t default_4bit_palette[16] = {};
class TFT_eSprite {
 public:
  bool _created = true;
  uint16_t* _colorMap = nullptr;
  void createPalette(const uint16_t colorMap[], uint8_t colors = 16);
  ~TFT_eSprite() { std::free(_colorMap); }
};
""" + f'#line {line} "src/internal/Sprite.inc"\n' + method + "\n" + generated + """
int main() {
  static_assert(sizeof(palette) / sizeof(palette[0]) == 16, "full palette required");
  static_assert(sizeof(myGraphic) == 4, "odd width packed rows retained");
  TFT_eSprite sprite;
  sprite.createPalette(palette);
  assert(sprite._colorMap);
  for (unsigned index = 0; index < 16; ++index) assert(sprite._colorMap[index] == palette[index]);
  for (unsigned index = 2; index < 16; ++index) assert(palette[index] == 0);
  assert(myGraphic[0] == 0x01 && myGraphic[1] == 0x0f);
  assert(myGraphic[2] == 0x10 && myGraphic[3] == 0x1f);
}
"""
        with tempfile.TemporaryDirectory(prefix="tft-palette-") as temp:
            cpp = pathlib.Path(temp) / "palette.cpp"
            binary = pathlib.Path(temp) / "palette"
            cpp.write_text(fixture)
            subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra",
                            "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                            str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_bad_palette_index_preserves_cli_output(self):
        with tempfile.TemporaryDirectory(prefix="tft-palette-output-") as temp:
            source = pathlib.Path(temp) / "invalid.bmp"
            output = pathlib.Path(temp) / "saved.c"
            source.write_bytes(bmp(1, 1, (b"\xf0",), colors=2))
            output.write_text("sentinel")
            self.assertEqual(converter.main([str(source), "-o", str(output)]), 1)
            self.assertEqual(output.read_text(), "sentinel")


if __name__ == "__main__":
    unittest.main()
