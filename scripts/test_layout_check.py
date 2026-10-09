import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import layout_check


class LayoutTests(unittest.TestCase):
    def write_layout(self):
        (self.root / "src/internal").mkdir(parents=True, exist_ok=True)
        (self.root / "src/TFT_eSPI.cpp").write_text('#include "internal/Sprite.inc"\n#ifdef SMOOTH_FONT\n#include "internal/Smooth_font.inc"\n#endif\n')
        for name in ("src/internal/Sprite.inc", "src/internal/Smooth_font.inc", "src/TFT_eSPI.h", "src/User_Setup_Select.h"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// fixture\n")
        (self.root / "User_Setup.h").write_text("// canonical\n")
        (self.root / "User_Setup_Select.h").write_text('#include "src/User_Setup_Select.h"\n')
        (self.root / "src/User_Setup.h").write_text('// Keep the editable Arduino installation setup at the package root.\n#include "../User_Setup.h"\n')
        (self.root / "library.json").write_text('{"build":{"srcDir":"src","includeDir":"src","srcFilter":["-<*>","+<TFT_eSPI.cpp>"]}}\n')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_only_core_is_compiled(self):
        for name in ("src/TFT_eSPI.cpp", "examples/Example/helper.cpp", "Tools/tool.cpp"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// fixture\n")
        self.assertEqual(layout_check.compiled_sources(self.root), ["src/TFT_eSPI.cpp"])

    def test_font_fragments_do_not_keep_c_suffix(self):
        fonts = self.root / "src/Fonts"
        fonts.mkdir(parents=True)
        (fonts / "Font16.c").write_text("data\n")
        with self.assertRaises(ValueError):
            layout_check.verify_fragments(self.root)

    def test_forwarding_preserves_root(self):
        self.write_layout()
        self.assertIsNone(layout_check.verify_fragments(self.root))

    def test_project_inventory_matches_platformio_object_mapping(self):
        self.write_layout()
        project = self.root / ".build/Example"
        project.mkdir(parents=True)
        entry = {"file": "lib/pio-library/src/TFT_eSPI.cpp", "output": ".pio/build/nodemcuv2/libf87/pio-library/TFT_eSPI.cpp.o"}
        (project / "compile_commands.json").write_text(json.dumps([entry]))
        self.assertIsNone(layout_check.verify_project(self.root, project))

    def test_rejects_autonomous_fragment_source(self):
        self.write_layout()
        (self.root / "src/internal").mkdir(exist_ok=True)
        (self.root / "src/internal/Sprite.cpp").write_text("// unsafe separate TU\n")
        with self.assertRaises(ValueError):
            layout_check.verify_fragments(self.root)


if __name__ == "__main__":
    unittest.main()
