import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("format", pathlib.Path(__file__).with_name("format.py"))
format = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(format)


class FormatTests(unittest.TestCase):
    def test_version_is_exact(self):
        format.require_version("clang-format version 23.1.2")
        with self.assertRaises(ValueError):
            format.require_version("clang-format version 23.1.3")

    def test_suffix_selection_and_exclusions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            paths = ["examples/X/X.ino", "src/internal/Sprite.inc", "src/Fonts/Font16.inc",
                     "src/TFT_Drivers/ST7789_Init.h", "extras/Create_Smooth_Font/Create_font.pde"]
            self.assertEqual(format.selected_files(root, paths), paths[:2])

    def test_rejects_paths_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            with self.assertRaises(ValueError):
                format.selected_files(root, ["../outside.cpp"])

    def test_filename_with_spaces_is_one_argument(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            path = root / "space name.cpp"
            path.write_text("int main(){return 0;}\n")
            seen = []
            original = subprocess.run
            try:
                subprocess.run = lambda args, **kwargs: seen.extend(args) or subprocess.CompletedProcess(args, 0, "clang-format version 23.1.2\n")
                format.run_files(root, ["space name.cpp"], write=False, executable="clang-format")
            finally:
                subprocess.run = original
            self.assertIn("space name.cpp", seen)


if __name__ == "__main__":
    unittest.main()
