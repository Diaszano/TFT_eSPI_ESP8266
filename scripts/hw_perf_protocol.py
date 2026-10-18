"""Strict byte parser for PERF,1 records in hardware validation captures."""

import base64
import binascii
import re
import struct
import zlib

from scripts.hw_validation_compare import parse_log


TOKEN = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")
RUN_ID = re.compile(r"[A-Za-z0-9]{1,16}\Z")
CRC = re.compile(r"[0-9a-f]{8}\Z")
U32 = 2**32 - 1
U64 = 2**64 - 1
FIELDS = {"BEGIN": 4, "SAMPLES": 5, "MEM": 6, "END": 4, "ABORT": 3}
STATUSES = {"PASS", "FAIL", "SKIP", "INCONCLUSIVE"}


def _integer(value, maximum=U32):
    if not value or not value.isascii() or not value.isdigit():
        raise ValueError("invalid unsigned integer")
    number = int(value)
    if number > maximum:
        raise ValueError("integer overflow")
    return number


def _token(value, pattern=TOKEN):
    if not pattern.fullmatch(value):
        raise ValueError("invalid token")
    return value


def _new_run(run_id, boot):
    return {"run_id": run_id, "boot": boot, "suite": None, "seed": None,
            "expected_count": None, "profile_id": None, "samples": [],
            "memory": [], "observed_count": None, "elapsed_us": None,
            "firmware_result": "NOT_EXECUTED", "transport_integrity": "INCOMPLETE",
            "errors": [], "records": 0, "terminal": None, "_expected_sequence": 0,
            "_batch": None, "_chunk": None, "_corrupt": False}


def parse_perf(raw: bytes) -> dict:
    """Parse raw serial bytes; never repair, decode with replacement, or infer samples."""
    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes")
    runs = []
    errors = []
    active = {}
    boot = -1
    legacy_lines = []
    latest = None
    lines = raw.split(b"\n")
    for lineno, piece in enumerate(lines[:-1] if raw.endswith(b"\n") else lines, 1):
        encoded = piece + (b"\n" if lineno <= len(lines) - 1 else b"")
        if encoded == b"HWTEST,2\n" or encoded == b"HWTEST,2\r\n":
            boot += 1
            active = {}
            latest = None
        if not encoded.startswith(b"PERF,"):
            if encoded.startswith(b"HWTEST,2") or (boot >= 0 and encoded.isascii()):
                legacy_lines.append(encoded.decode("ascii", errors="strict"))
            elif latest is not None and encoded.strip(b"\r\n"):
                latest["_corrupt"] = True
                latest["errors"].append("non-ASCII or stray data")
                errors.append({"line": lineno, "error": "non-ASCII or stray data"})
            continue
        run = None
        try:
            if not encoded.endswith(b"\n"):
                raise ValueError("unterminated line")
            if len(encoded) > 192:
                raise ValueError("oversized line")
            content = encoded[:-1].removesuffix(b"\r")
            if not content.isascii() or any(byte < 32 or byte > 126 for byte in content):
                raise ValueError("non-ASCII record")
            parts = content.decode("ascii").split(",")
            if len(parts) < 7 or parts[0] != "PERF" or parts[1] != "1":
                raise ValueError("unsupported PERF version")
            run_id = _token(parts[2], RUN_ID)
            key = (boot, run_id)
            run = active.get(key)
            if run is None:
                run = _new_run(run_id, boot)
                active[key] = run
                runs.append(run)
            latest = run
            sequence = _integer(parts[3])
            kind = parts[4]
            if kind not in FIELDS or len(parts) != FIELDS[kind] + 6:
                raise ValueError("unknown kind or wrong field count")
            if not CRC.fullmatch(parts[-1]):
                raise ValueError("invalid CRC format")
            body = content.rsplit(b",", 1)[0]
            if zlib.crc32(body) != int(parts[-1], 16):
                raise ValueError("CRC mismatch")
            if sequence != run["_expected_sequence"]:
                run["errors"].append("sequence discontinuity")
            run["_expected_sequence"] = sequence + 1
            if run["terminal"] is not None:
                raise ValueError("record after terminal")
            fields = parts[5:-1]
            suite = _token(fields[0])
            if kind == "BEGIN":
                if run["suite"] is not None or sequence != 0:
                    raise ValueError("duplicate or noninitial BEGIN")
                run["suite"] = suite
                run["seed"] = _integer(fields[1])
                run["expected_count"] = _integer(fields[2])
                run["profile_id"] = _token(fields[3])
            elif run["suite"] != suite:
                raise ValueError("missing BEGIN or suite mismatch")
            elif kind == "SAMPLES":
                batch = _integer(fields[1])
                chunk = _integer(fields[2])
                count = _integer(fields[3])
                if not 1 <= count <= 16:
                    raise ValueError("invalid sample count")
                try:
                    binary = base64.b64decode(fields[4], validate=True)
                except (binascii.Error, ValueError) as error:
                    raise ValueError("invalid Base64") from error
                if len(binary) != count * 4 or base64.b64encode(binary).decode("ascii") != fields[4]:
                    raise ValueError("Base64 byte count or padding mismatch")
                values = struct.unpack(f"<{count}I", binary)
                if suite.startswith(("FP", "FM", "LW")) and any(value == 0 for value in values):
                    raise ValueError("zero frame duration")
                if run["_batch"] is None:
                    if (batch, chunk) != (0, 0):
                        raise ValueError("batch must start at zero")
                elif batch == run["_batch"]:
                    if chunk != run["_chunk"] + 1 or chunk >= 8:
                        raise ValueError("chunk discontinuity")
                elif batch != run["_batch"] + 1 or chunk != 0:
                    raise ValueError("batch discontinuity")
                run["_batch"], run["_chunk"] = batch, chunk
                run["samples"].extend(values)
            elif kind == "MEM":
                checkpoint, free, largest, minimum, failures = (
                    _integer(value) for value in fields[1:])
                if largest > free:
                    raise ValueError("largest block exceeds free heap")
                run["memory"].append({"checkpoint": checkpoint, "free_heap": free,
                                      "largest_block": largest, "min_heap": minimum,
                                      "failures": failures})
            elif kind == "END":
                run["observed_count"] = _integer(fields[1])
                run["elapsed_us"] = _integer(fields[2], U64)
                run["firmware_result"] = _token(fields[3])
                if run["firmware_result"] not in STATUSES:
                    raise ValueError("invalid terminal status")
                run["terminal"] = "END"
            else:
                run["observed_count"] = _integer(fields[1])
                _token(fields[2])
                run["firmware_result"] = "INCONCLUSIVE"
                run["terminal"] = "ABORT"
            run["records"] += 1
        except (ValueError, UnicodeError) as error:
            errors.append({"line": lineno, "error": str(error)})
            if run is not None:
                run["_corrupt"] = True
                run["errors"].append(str(error))

    for run in runs:
        frame = run["suite"] not in {"HC", "HP"}
        skipped = run["firmware_result"] == "SKIP" and run["observed_count"] == 0
        if (run["terminal"] == "END" and frame and not skipped
                and "sequence discontinuity" not in run["errors"] and (
                run["observed_count"] != len(run["samples"])
                or (run["expected_count"] and run["expected_count"] != len(run["samples"])))):
            run["_corrupt"] = True
            run["errors"].append("terminal sample count mismatch")
        complete = (run["terminal"] == "END" and not run["errors"]
                    and (skipped or (
                        (not frame or run["observed_count"] == len(run["samples"]))
                        and (not frame or run["expected_count"] == 0
                             or run["expected_count"] == len(run["samples"])))))
        if run["_corrupt"]:
            run["transport_integrity"] = "CORRUPT"
        elif complete:
            run["transport_integrity"] = "COMPLETE"
        else:
            run["transport_integrity"] = "INCOMPLETE"
        for private in ("_expected_sequence", "_batch", "_chunk", "_corrupt"):
            del run[private]
    legacy = parse_log(legacy_lines) if legacy_lines else None
    return {"runs": runs, "errors": errors, "legacy": legacy}
