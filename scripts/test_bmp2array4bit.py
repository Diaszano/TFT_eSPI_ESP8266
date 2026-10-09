import pathlib
import re
import struct
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).parents[1] / "Tools/bmp2array4bit/bmp2array4bit.py"


def bmp(width=3, height=2, rows=(b"\x12\x30", b"\x45\x60"), *, colors=16, bpp=4, compression=0):
    stride = ((width * bpp + 31) // 32) * 4
    padded = b"".join(row.ljust(stride, b"\0") for row in rows)
    palette_count = colors or 16
    offset = 14 + 40 + palette_count * 4
    file_size = offset + len(padded)
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, offset)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height, 1, bpp, compression, len(padded), 0, 0, colors, 0)
    palette = bytes(palette_count * 4)
    return file_header + dib + palette + padded


class BmpConverterTests(unittest.TestCase):
    def run_cli(self, data, output_name="out.c"):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = pathlib.Path(temp.name)
        source, output = root / "input.bmp", root / output_name
        source.write_bytes(data)
        result = subprocess.run(["python3", str(SCRIPT), str(source), "-o", str(output)], capture_output=True, text=True)
        return result, output

    def test_odd_width_rows_keep_padded_bytes_and_vertical_order(self):
        result, output = self.run_cli(bmp())
        self.assertEqual(result.returncode, 0, result.stderr)
        body = re.search(r"myGraphic\[\d+\].*?=\s*\{(.*?)\};", output.read_text(), re.S).group(1)
        self.assertEqual(re.findall(r"0x[0-9a-fA-F]{2}", body), ["0x45", "0x60", "0x12", "0x30"])

    def test_default_palette_has_sixteen_entries_and_output_compiles(self):
        result, output = self.run_cli(bmp(4, 2, (b"\x12\x34", b"\x56\x78"), colors=0))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = output.read_text()
        self.assertIn("palette[16]", text)
        source = output.with_suffix(".cpp")
        source.write_text("#include <cstdint>\n#define PROGMEM\n" + text + "\nint main(){return sizeof(myGraphic)==4?0:1;}\n")
        subprocess.run(["c++", "-std=c++11", str(source), "-o", str(source.with_suffix(""))], check=True)
        subprocess.run([str(source.with_suffix(""))], check=True)

    def test_single_pixel_rows_are_kept(self):
        result, output = self.run_cli(bmp(1, 2, (b"\x10", b"\x20")))
        self.assertEqual(result.returncode, 0, result.stderr)
        body = re.search(r"myGraphic\[\d+\].*?=\s*\{(.*?)\};", output.read_text(), re.S).group(1)
        self.assertEqual(re.findall(r"0x[0-9a-fA-F]{2}", body), ["0x20", "0x10"])

    def test_rejects_invalid_input_without_truncating_existing_output(self):
        valid = bmp()
        invalid = [valid[:55], bmp(compression=1), bmp(bpp=8), bmp(height=-2), bmp(colors=17)]
        for data in invalid:
            with self.subTest(length=len(data)):
                result, output = self.run_cli(data)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_invalid_input_preserves_existing_output(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = pathlib.Path(temp.name); source = root / "bad.bmp"; output = root / "existing.c"
        source.write_bytes(bmp(compression=1)); output.write_bytes(b"sentinel")
        result = subprocess.run(["python3", str(SCRIPT), str(source), "-o", str(output)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), b"sentinel")


if __name__ == "__main__":
    unittest.main()
