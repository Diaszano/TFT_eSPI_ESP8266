"""Offline PERF distributions and independent evidence status dimensions."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from scripts.hw_perf_protocol import parse_perf


def elapsed_u32(end, start):
    return (end - start) & 0xffffffff


def summarize_samples(samples: list[int], elapsed_us: int) -> dict:
    if not samples or not 0 < elapsed_us <= 2**64 - 1 or any(
            not isinstance(value, int) or not 1 <= value <= 0xffffffff for value in samples):
        raise ValueError("samples and elapsed time must be positive uint32 measurements")
    if sum(samples) > elapsed_us:
        raise ValueError("sample duration exceeds elapsed window")
    ordered = sorted(samples)
    count = len(ordered)

    def nearest_rank(percent):
        return ordered[math.ceil(count * percent) - 1]

    return {"sample_count": count, "min_us": ordered[0],
            "p50_us": nearest_rank(.50), "p95_us": nearest_rank(.95),
            "p99_us": nearest_rank(.99), "max_us": ordered[-1],
            "fps_effective": count * 1_000_000 / elapsed_us,
            "deadline_miss_60": sum(value > 16_667 for value in ordered),
            "deadline_miss_30": sum(value > 33_333 for value in ordered),
            "quantile_method": "sorted nearest rank",
            "status": "COMPLETE" if count >= 1000 else "INCOMPLETE"}


def analyze_run(raw: bytes, capture: dict) -> dict:
    parsed = parse_perf(raw)
    run = parsed["runs"][0] if parsed["runs"] else None
    source_type = capture.get("source_type", "synthetic")
    firmware_result = run["firmware_result"] if run else "NOT_EXECUTED"
    integrity = run["transport_integrity"] if run else "NOT_CAPTURED"
    if (capture.get("truncation_reason")
            or capture.get("byte_count", len(raw)) != len(raw)):
        integrity = "INCOMPLETE"
    if capture.get("sha256") and capture["sha256"] != hashlib.sha256(raw).hexdigest():
        integrity = "CORRUPT"
    profile = capture.get("profile")
    legacy = parsed.get("legacy") or {}
    metadata = legacy.get("metadata", {})
    compatibility = "UNKNOWN"
    if profile and metadata:
        compatibility = ("COMPATIBLE" if all(
            metadata.get(key) == value for key, value in profile.items())
            else "INCOMPATIBLE")
    physical_review = ("APPROVED_BY_OPERATOR" if source_type == "physical"
                       and capture.get("operator_approved") else
                       "VISUAL_REVIEW_REQUIRED" if source_type == "physical"
                       else "NOT_APPLICABLE")
    baseline = capture.get("baseline_status", "NO_BASELINE")
    if baseline not in {"APPROVED", "NO_BASELINE", "INCOMPARABLE"}:
        baseline = "INCOMPARABLE"
    measurements = None
    if run and run["suite"] not in {"TI", "HC", "HP"} and run["samples"] and run["elapsed_us"]:
        measurements = summarize_samples(run["samples"], run["elapsed_us"])
    statuses = {"firmware_result": firmware_result,
                "transport_integrity": integrity,
                "profile_compatibility": compatibility,
                "baseline_status": baseline,
                "physical_review": physical_review}
    complete = (firmware_result == "PASS" and integrity == "COMPLETE"
                and compatibility == "COMPATIBLE" and baseline == "APPROVED"
                and physical_review == "APPROVED_BY_OPERATOR"
                and (measurements is None or measurements["status"] == "COMPLETE"))
    return {**statuses, "overall_status": "PASS" if complete else "INCONCLUSIVE",
            "source_type": source_type, "run": run, "measurements": measurements,
            "parser_errors": parsed["errors"], "raw_sha256": hashlib.sha256(raw).hexdigest()}


def _atomic_new(path, content):
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="") as output:
        output.write(content)
    os.replace(temporary, path)


def write_analysis(destination, raw: bytes, capture: dict) -> dict:
    """Write immutable derived artifacts alongside a captured serial.raw."""
    destination = Path(destination)
    result = analyze_run(raw, capture)
    parsed = parse_perf(raw)
    _atomic_new(destination / "parsed.json", json.dumps(parsed, indent=2, sort_keys=True) + "\n")
    rows = ["run_id,suite,frame_index,duration_us"]
    for run in parsed["runs"]:
        rows.extend(f'{run["run_id"]},{run["suite"]},{i},{value}'
                    for i, value in enumerate(run["samples"]))
    _atomic_new(destination / "measurements.csv", "\n".join(rows) + "\n")
    _atomic_new(destination / "summary.json", json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = (f'# PERF run\n\nSource: {result["source_type"]}\n\n'
              f'Firmware: {result["firmware_result"]}\n\n'
              f'Transport: {result["transport_integrity"]}\n\n'
              f'Overall: {result["overall_status"]}\n')
    _atomic_new(destination / "report.md", report)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_directory", type=Path)
    args = parser.parse_args()
    directory = args.capture_directory
    capture = json.loads((directory / "capture.json").read_text())
    capture.update(json.loads((directory / "session.json").read_text()))
    result = write_analysis(directory, (directory / "serial.raw").read_bytes(), capture)
    print(json.dumps({key: result[key] for key in
                      ("firmware_result", "transport_integrity", "overall_status")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
