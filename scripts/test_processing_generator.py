import importlib.util
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "extras/Create_Smooth_Font/Create_font/Create_font.pde"
HEADER = ROOT / "extras/Create_Smooth_Font/Create_font/FontFiles/Final-Frontier28.h"
spec = importlib.util.spec_from_file_location("processing_host_runner", ROOT / "tests/host/run.py")
host_runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host_runner)


class ProcessingGeneratorTests(unittest.TestCase):
    def test_identifier_and_font_selection_use_actual_java_helpers(self):
        javac, java = shutil.which("javac"), shutil.which("java")
        self.assertIsNotNone(javac, "JDK required for Processing helper regression")
        self.assertIsNotNone(java, "Java required for Processing helper regression")
        source = GENERATOR.read_text()
        methods = []
        for signature in ("String fontIdentifier(String name, int size) {",
                          "String selectFontName(int number, String[] fonts, String fallback) {"):
            method, _ = host_runner.extract_method(source, signature)
            methods.append(method)
        fixture = "public class ProcessingGeneratorProbe {\n" + "\n".join(methods) + """
  String str(int value) { return Integer.toString(value); }
  void require(boolean value) { if (!value) throw new AssertionError(); }
  void run() {
    require(fontIdentifier("Final-Frontier", 28).equals("Final_Frontier28"));
    require(fontIdentifier("9 font", 12).equals("font_9_font12"));
    require(fontIdentifier("", 18).equals("font_18"));
    require(fontIdentifier("NotoSansBold", 15).equals("NotoSansBold15"));
    String[] fonts = {"First", "Last"};
    require(selectFontName(-1, fonts, "Fallback").equals("Fallback"));
    require(selectFontName(0, fonts, "Fallback").equals("First"));
    require(selectFontName(1, fonts, "Fallback").equals("Last"));
    for (int number : new int[] {-2, 2, Integer.MAX_VALUE}) {
      boolean rejected = false;
      try { selectFontName(number, fonts, "Fallback"); }
      catch (IllegalArgumentException error) { rejected = true; }
      require(rejected);
    }
    boolean rejected = false;
    try { selectFontName(0, new String[0], "Fallback"); }
    catch (IllegalArgumentException error) { rejected = true; }
    require(rejected);
  }
  public static void main(String[] args) { new ProcessingGeneratorProbe().run(); }
}
"""
        with tempfile.TemporaryDirectory(prefix="tft-processing-java-") as temp:
            path = pathlib.Path(temp) / "ProcessingGeneratorProbe.java"
            path.write_text(fixture)
            subprocess.run([javac, str(path)], check=True)
            subprocess.run([java, "-cp", temp, "ProcessingGeneratorProbe"], check=True)

    def test_generator_wires_helpers_and_shipped_header_compiles(self):
        source = GENERATOR.read_text()
        setup, _ = host_runner.extract_method(source, "void setup() {")
        self.assertIn("fontName = selectFontName(fontNumber, fontList, fontName);", setup)
        self.assertIn('fontIdentifier(fontName, fontSize) + "[] PROGMEM = {"', setup)
        compiler = shutil.which("c++")
        self.assertIsNotNone(compiler, "C++ compiler required for generated header regression")
        with tempfile.TemporaryDirectory(prefix="tft-processing-header-") as temp:
            root = pathlib.Path(temp)
            (root / "pgmspace.h").write_text("#pragma once\n#define PROGMEM\n")
            cpp = root / "font.cpp"
            cpp.write_text('#include <cstdint>\n' + f'#include "{HEADER}"\n' +
                           'static_assert(sizeof(Final_Frontier28) > 24, "font data required");\n' +
                           'int main() { return Final_Frontier28[7] == 11 ? 0 : 1; }\n')
            binary = root / "font"
            subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-I", temp,
                            str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
