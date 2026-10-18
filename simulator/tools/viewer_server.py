#!/usr/bin/env python3
"""Read-only, loopback-only server for selected simulator output directories."""
import argparse
import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

BIND_ADDRESS = "127.0.0.1"
ALLOWED_METHODS = {"GET", "HEAD"}
ASSET_NAMES = {"/": "index.html", "/index.html": "index.html",
               "/viewer.js": "viewer.js", "/style.css": "style.css"}
RUN_FILES = {"frame.png": 8 * 1024 * 1024, "frame.rgb565": 115200,
             "manifest.json": 64 * 1024, "result.json": 64 * 1024,
             "diff.png": 8 *  1024 * 1024, "report.json": 64 * 1024,
             "report.md": 64 * 1024, "expected.png": 8 * 1024 * 1024}
MAX_RUNS = 100
RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


def resolve_resource(root, request_path):
    """Resolve one relative URL below root, rejecting encoded traversal and links."""
    path = urlsplit(request_path).path
    for _ in range(2):
        path = unquote(path, errors="strict")
    if "\\" in path or "\x00" in path or "%" in path:
        raise ValueError("invalid encoded path")
    parts = path.split("/")
    if any(part in (".", "..") for part in parts):
        raise ValueError("path traversal rejected")
    root = Path(root).resolve(strict=True)
    target = root.joinpath(*(part for part in parts if part))
    if target.is_symlink():
        raise ValueError("symlinks are not served")
    target = target.resolve(strict=True)
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("resource is outside the permitted root")
    return target


def discover_runs(run_dir):
    """Return only direct child directories with bounded simulator manifests."""
    selected = Path(run_dir).absolute()
    if selected.is_symlink():
        raise ValueError("RUN cannot be a symlink")
    selected = selected.resolve(strict=True)
    if not selected.is_dir():
        raise ValueError("RUN must be a directory")
    entries = []
    for directory in sorted(selected.parent.iterdir(), key=lambda p: (p != selected, p.name)):
        if not RUN_ID.fullmatch(directory.name) or directory.is_symlink() or not directory.is_dir():
            continue
        manifest, result = directory / "manifest.json", directory / "result.json"
        if manifest.is_symlink() or result.is_symlink() or not manifest.is_file() or not result.is_file():
            continue
        try:
            if manifest.stat().st_size > 64 * 1024 or result.stat().st_size > 64 * 1024:
                continue
            m = json.loads(manifest.read_text(encoding="utf-8"))
            r = json.loads(result.read_text(encoding="utf-8"))
            if (m.get("schema_version") == 1 and m.get("hardware") is False and
                    isinstance(m.get("scene_id"), str) and isinstance(r.get("status"), str)):
                entries.append((directory.name, directory, m, r))
        except (ValueError, OSError, AttributeError):
            continue
        if len(entries) >= MAX_RUNS:
            break
    if not any(item[1] == selected for item in entries):
        raise ValueError("RUN does not contain valid simulator results")
    return entries


def create_handler(run_dir):
    selected = Path(run_dir).absolute()
    if selected.is_symlink():
        raise ValueError("RUN cannot be a symlink")
    selected = selected.resolve(strict=True)
    run_entries = discover_runs(selected)
    allowed_runs = {item[0]: item[1] for item in run_entries}
    asset_root = Path(__file__).resolve().parents[1] / "viewer"

    class ViewerHandler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            pass

        def _send(self, status, body=b"", content_type="text/plain; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none'")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_POST(self): self._send(405, b"method not allowed")
        def do_PUT(self): self._send(405, b"method not allowed")
        def do_PATCH(self): self._send(405, b"method not allowed")
        def do_DELETE(self): self._send(405, b"method not allowed")

        def do_GET(self): self._serve()
        def do_HEAD(self): self._serve()

        def _serve(self):
            try:
                path = urlsplit(self.path).path
                if path == "/api/runs":
                    entries = [{"id": run_id, "scene_id": manifest["scene_id"],
                                "status": result["status"]}
                               for run_id, _directory, manifest, result in run_entries]
                    body = json.dumps({"schema_version": 1, "runs": entries}, separators=(",", ":")).encode()
                    self._send(200, body, "application/json")
                    return
                if path in ASSET_NAMES:
                    target = resolve_resource(asset_root, "/" + ASSET_NAMES[path])
                    mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                else:
                    parts = path.strip("/").split("/")
                    if len(parts) != 3 or parts[0] != "runs" or parts[1] not in allowed_runs or parts[2] not in RUN_FILES:
                        self._send(404, b"not found"); return
                    target = resolve_resource(allowed_runs[parts[1]], "/" + parts[2])
                    if target.stat().st_size > RUN_FILES[parts[2]]:
                        self._send(413, b"artifact exceeds size limit"); return
                    mime = {"frame.png": "image/png", "diff.png": "image/png", "expected.png": "image/png",
                            "frame.rgb565": "application/octet-stream", "manifest.json": "application/json",
                            "result.json": "application/json", "report.json": "application/json",
                            "report.md": "text/plain; charset=utf-8"}[parts[2]]
                self._send(200, target.read_bytes(), mime)
            except (OSError, ValueError, UnicodeError):
                self._send(404, b"not found")

    return ViewerHandler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="explicit simulator output directory")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    server = ThreadingHTTPServer((BIND_ADDRESS, args.port), create_handler(args.run))
    print("Simulator viewer: http://{}:{}/ (Ctrl+C to stop)".format(*server.server_address), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
