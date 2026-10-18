"""Bounded passive capture of an already opened binary stream."""

import hashlib
import argparse
import json
import os
import secrets
import select
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")
    os.replace(temporary, path)


def capture_stream(source, destination, max_bytes, max_seconds, metadata, *, clock=time.monotonic):
    """Copy source bytes to a new artifact directory; never own the serial port."""
    if max_bytes <= 0 or max_seconds <= 0:
        raise ValueError("capture limits must be positive")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    metadata = dict(metadata)
    physical = (metadata.get("source_type") == "physical"
                and all(metadata.get(key) for key in
                        ("operator", "boot_witness", "firmware_sha", "profile")))
    session = {"session_id": secrets.token_hex(12),
               "source_type": "physical" if physical else "synthetic",
               "source": metadata.get("source", "stdin"),
               "ownership": metadata.get("ownership", "operator"),
               "operator": metadata.get("operator"),
               "boot_witness": metadata.get("boot_witness"),
               "firmware_sha": metadata.get("firmware_sha"),
               "profile": metadata.get("profile")}
    started_at = _utc()
    start = clock()
    digest = hashlib.sha256()
    byte_count = 0
    reason = None
    temporary = destination / "serial.raw.tmp"
    with temporary.open("xb") as output:
        while True:
            remaining = max_seconds - (clock() - start)
            if remaining <= 0:
                reason = "time_limit"
                break
            if byte_count >= max_bytes:
                reason = "byte_limit"
                break
            try:
                try:
                    descriptor = source.fileno()
                except (AttributeError, OSError):
                    descriptor = None
                if descriptor is not None and not select.select([descriptor], [], [], remaining)[0]:
                    reason = "time_limit"
                    break
                block = (source.read1 if descriptor is not None and hasattr(source, "read1")
                         else source.read)(min(65536, max_bytes - byte_count))
            except Exception as error:
                reason = "read_error:" + type(error).__name__
                break
            if not isinstance(block, bytes):
                reason = "nonbinary_source"
                break
            if not block:
                break
            output.write(block)
            digest.update(block)
            byte_count += len(block)
    os.replace(temporary, destination / "serial.raw")
    capture = {"started_utc": started_at, "ended_utc": _utc(),
               "byte_count": byte_count, "sha256": digest.hexdigest(),
               "truncation_reason": reason, "session_id": session["session_id"],
               "source": session["source"], "ownership": session["ownership"],
               "source_type": session["source_type"], "profile": session["profile"]}
    _atomic_json(destination / "capture.json", capture)
    _atomic_json(destination / "session.json", session)
    return capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--max-bytes", type=int, default=16_000_000)
    parser.add_argument("--max-seconds", type=float, default=3600)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text()) if args.metadata else {}
    result = capture_stream(sys.stdin.buffer, args.destination, args.max_bytes,
                            args.max_seconds, metadata)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
