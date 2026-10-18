import json
import tempfile
import pathlib
import io
from unittest.mock import Mock
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
VIEWER = ROOT / "simulator/viewer"


class ViewerTests(unittest.TestCase):
    def test_shell_has_required_controls_and_simulation_warning(self):
        html = (VIEWER / "index.html").read_text()
        css = (VIEWER / "style.css").read_text()
        self.assertIn("SIMULATED — NOT PHYSICAL DISPLAY", html)
        self.assertIn('id="prev-frame"', html)
        self.assertIn('id="next-frame"', html)
        self.assertIn('id="scene-list"', html)
        self.assertIn('id="zoom"', html)
        self.assertIn("image-rendering:pixelated", css)

    def test_navigation_boundaries_zoom_coordinates_and_rgb565(self):
        js = VIEWER / "viewer.js"
        script = r'''const v=require(process.argv[1]);
const assert=require('node:assert/strict');
assert.equal(v.frameIndex(-1, 3), 0); assert.equal(v.frameIndex(8, 3), 2);
assert.equal(v.frameIndex(0, 0), -1); assert.equal(v.zoomValue('4x'), 4);
assert.deepEqual(v.mapPixel(19, 34, 2, 240, 240), {x:9,y:17});
for(const z of [1,2,4,8]) assert.deepEqual(v.mapPixel(5*z,7*z,z,240,240), {x:5,y:7});
assert.equal(v.rgb565(0xF800), '#ff0000');
assert.equal(v.rgb565(0x07E0), '#00ff00');
assert.equal(v.rgb565(0x001F), '#0000ff');
assert.equal(v.rgb565At(Uint8Array.from([0,248]),0), 0xF800);
assert.equal(v.displayStatus({status:'NO_BASELINE'}, {status:'RENDERED'}), 'NO_BASELINE');
assert.equal(v.displayStatus(null, {status:'SKIP'}), 'SKIP');
assert.equal(v.displayStatus({status:'PASS',actual_frame_sha256:'abc',actual_profile_hash:'p'}, {status:'RENDERED'}, 'def','p'), 'INCONCLUSIVE');
assert.equal(v.displayStatus({status:'PASS',actual_frame_sha256:'abc',actual_profile_hash:'p'}, {status:'RENDERED'}, 'abc','p'), 'PASS');'''
        run = subprocess.run(["node", "-e", script, str(js)], text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_malformed_metadata_is_not_inserted_as_html(self):
        js = (VIEWER / "viewer.js").read_text()
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)

    def test_image_blobs_are_awaited_before_object_url_creation(self):
        js = (VIEWER / "viewer.js").read_text()
        self.assertGreaterEqual(js.count("URL.createObjectURL(await r.blob())"), 2)

    def test_manifest_contract_rejects_hardware_and_malformed_profiles(self):
        js = VIEWER / "viewer.js"
        script = r'''const v=require(process.argv[1]);
const p={pixel_format:'RGB565',visible:{width:240,height:240},gram:{width:240,height:320},supported_rotations:[0,1,2,3]};
const m={schema_version:1,scene_id:'edge_rect',seed:123,rotation:0,source_sha:'a'.repeat(40),
simulator_version:'0.1',profile:p,profile_hash:'b'.repeat(64),frame_sha256:'c'.repeat(64),
hardware:false,simulated_timing:false,simulated_memory:false};
if(!v.validManifest(m)) process.exit(1); m.hardware=true; if(v.validManifest(m)) process.exit(2);'''
        run = subprocess.run(["node", "-e", script, str(js)], text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_comparison_values_use_plan10_report_schema(self):
        js = VIEWER / "viewer.js"
        script = r'''const v=require(process.argv[1]), assert=require('node:assert/strict');
const r={first_difference:{x:4,y:8,expected_rgb565:'0xF800',actual_rgb565:'0x001F'}};
assert.deepEqual(v.differenceAt(r,4,8), {expected:'0xF800',actual:'0x001F'});
assert.equal(v.differenceAt(r,4,9), null);'''
        run = subprocess.run(["node", "-e", script, str(js)], text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_server_restricts_paths_methods_and_symlinks(self):
        from simulator.tools.viewer_server import resolve_resource, discover_runs, ALLOWED_METHODS, BIND_ADDRESS
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp); (root / "frame.png").write_bytes(b"png")
            self.assertEqual(BIND_ADDRESS, "127.0.0.1")
            self.assertEqual(ALLOWED_METHODS, {"GET", "HEAD"})
            self.assertEqual(resolve_resource(root, "/frame.png").read_bytes(), b"png")
            for path in ("/../README.md", "/%2e%2e/%2e%2e/secrets.h", "/%252e%252e/etc/passwd", "/etc/passwd"):
                with self.assertRaises((ValueError, FileNotFoundError)):
                    resolve_resource(root, path)
            outside = root.parent / (root.name + "-outside")
            outside.write_text("secret")
            try:
                (root / "escape.json").symlink_to(outside)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    resolve_resource(root, "/escape.json")
            finally:
                outside.unlink()

    def test_server_catalog_only_exposes_valid_neighbor_runs(self):
        from simulator.tools.viewer_server import discover_runs
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for run_id in ("first", "second"):
                directory = root / run_id; directory.mkdir()
                (directory / "manifest.json").write_text(json.dumps({"schema_version": 1, "hardware": False, "scene_id": "edge_rect"}))
                (directory / "result.json").write_text(json.dumps({"schema_version": 1, "status": "RENDERED"}))
            private = root / "notes"; private.mkdir(); (private / "manifest.json").write_text("secret")
            self.assertEqual([run[0] for run in discover_runs(root / "first")], ["first", "second"])

    def test_server_run_limit_keeps_explicitly_selected_run(self):
        from simulator.tools.viewer_server import discover_runs, MAX_RUNS
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for index in range(MAX_RUNS + 1):
                directory = root / ("run{:03d}".format(index)); directory.mkdir()
                (directory / "manifest.json").write_text(json.dumps({"schema_version": 1, "hardware": False, "scene_id": "edge_rect"}))
                (directory / "result.json").write_text(json.dumps({"schema_version": 1, "status": "RENDERED"}))
            runs = discover_runs(root / "run100")
            self.assertEqual(len(runs), MAX_RUNS)
            self.assertIn("run100", [entry[0] for entry in runs])

    def test_server_gets_only_valid_explicit_artifacts_and_missing_files_404(self):
        from simulator.tools.viewer_server import create_handler
        with tempfile.TemporaryDirectory() as temp:
            run = pathlib.Path(temp) / "run"; run.mkdir()
            (run / "manifest.json").write_text(json.dumps({"schema_version": 1, "hardware": False, "scene_id": "edge_rect"}))
            (run / "result.json").write_text(json.dumps({"schema_version": 1, "status": "RENDERED"}))
            (run / "frame.png").write_bytes(b"png")
            handler_type = create_handler(run)
            def request(path):
                handler = object.__new__(handler_type)
                handler.path, handler.command, handler.wfile = path, "GET", io.BytesIO()
                handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
                handler.do_GET()
                return handler.send_response.call_args.args[0], handler.wfile.getvalue()
            self.assertEqual(request("/runs/run/frame.png"), (200, b"png"))
            self.assertEqual(request("/runs/run/source.cpp")[0], 404)
            (run / "frame.png").unlink()
            self.assertEqual(request("/runs/run/frame.png")[0], 404)
            self.assertEqual(request("/runs/run/diff.png")[0], 404)

    def test_http_write_methods_return_405_without_opening_a_socket(self):
        from simulator.tools.viewer_server import create_handler
        with tempfile.TemporaryDirectory() as temp:
            run = pathlib.Path(temp) / "run"; run.mkdir()
            (run / "manifest.json").write_text(json.dumps({"schema_version": 1, "hardware": False, "scene_id": "s"}))
            (run / "result.json").write_text(json.dumps({"schema_version": 1, "status": "RENDERED"}))
            handler_type = create_handler(run)
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                handler = object.__new__(handler_type)
                handler.command, handler.wfile = method, io.BytesIO()
                handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
                getattr(handler, "do_" + method)()
                self.assertEqual(handler.send_response.call_args.args[0], 405)
                self.assertEqual(handler.wfile.getvalue(), b"method not allowed")


if __name__ == "__main__":
    unittest.main()
