import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class ReleasePolicyTests(unittest.TestCase):
    def test_next_version_is_not_forced(self):
        config = json.loads((ROOT / "release-please-config.json").read_text())
        self.assertNotIn("release-as", config["packages"]["."])

    def test_metadata_test_accepts_future_consistent_versions(self):
        for version in ("1.0.1", "2.0.0"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                (root / "scripts").mkdir()
                for name in ("library.json", "library.properties", ".release-please-manifest.json", "keywords.txt"):
                    shutil.copyfile(ROOT / name, root / name)
                for name in ("test_package_check.py", "package_check.py", "check_version.py"):
                    shutil.copyfile(ROOT / "scripts" / name, root / "scripts" / name)
                manifest = json.loads((root / "library.json").read_text())
                old = manifest["version"]
                manifest["version"] = version
                (root / "library.json").write_text(json.dumps(manifest))
                properties = (root / "library.properties").read_text().replace(f"version={old}\n", f"version={version}\n")
                (root / "library.properties").write_text(properties)
                (root / ".release-please-manifest.json").write_text(json.dumps({".": version}))
                result = subprocess.run([sys.executable, "-m", "unittest", "scripts/test_package_check.py", "-q"], cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = subprocess.run([sys.executable, "scripts/check_version.py"], cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"version OK {version}", result.stdout)
                (root / ".release-please-manifest.json").write_text(json.dumps({".": "0.0.0"}))
                result = subprocess.run([sys.executable, "scripts/check_version.py"], cwd=root, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
