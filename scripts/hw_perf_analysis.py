"""Offline PERF distributions and independent evidence status dimensions."""

import argparse
import hashlib
import json
import math
import os
import statistics
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


def summarize_frame_run(run: dict) -> dict:
    summary = summarize_samples(run["samples"], run["elapsed_us"])
    pixels = run.get("pixels_per_frame")
    if not isinstance(pixels, int) or pixels <= 0:
        raise ValueError("positive pixels_per_frame required")
    cold = run.get("cold_us")
    if cold is not None and not 0 < cold <= 0xffffffff:
        raise ValueError("invalid cold frame")
    summary.update({"cold_us": cold,
                    "pixel_throughput": pixels * len(run["samples"]) * 1_000_000
                    / run["elapsed_us"],
                    "p95_minus_p50_us": summary["p95_us"] - summary["p50_us"],
                    "max_minus_p50_us": summary["max_us"] - summary["p50_us"],
                    "timer_overhead_us": run.get("timer_overhead_us"),
                    "source_type": run.get("source_type", "synthetic")})
    return summary


def baseline_content_hash(runs: list[dict]) -> str:
    canonical = json.dumps(sorted(runs, key=lambda run: run.get("boot_id", "")),
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compare_frame_profiles(baseline_runs: list[dict], candidate_runs: list[dict],
                           approval: dict) -> dict:
    required_profile = {"board", "display", "rotation", "cpu_hz", "spi_hz",
                        "wifi", "scene", "seed", "supply"}
    for runs in (baseline_runs, candidate_runs):
        boots = [run.get("boot_id") for run in runs]
        if (len(runs) < 5 or len(set(boots)) != len(runs) or None in boots
                or len({run.get("firmware_sha") for run in runs}) != 1
                or any(not run.get("firmware_sha") or not run.get("boot_witness")
                       or run.get("source_type") != "physical"
                       or run.get("transport_integrity") != "COMPLETE"
                       or run.get("profile_compatibility") != "COMPATIBLE"
                       or run.get("physical_review") != "APPROVED_BY_OPERATOR"
                       or not required_profile <= set(run.get("profile") or {})
                       for run in runs)):
            return {"status": "INCOMPARABLE", "reason": "insufficient independent physical boots"}
    profiles = [run["profile"] for run in baseline_runs + candidate_runs]
    if any(profile != profiles[0] for profile in profiles[1:]):
        return {"status": "INCOMPARABLE", "reason": "physical profiles differ"}
    try:
        base = [summarize_samples(run["samples"], run["elapsed_us"])
                for run in baseline_runs]
        cand = [summarize_samples(run["samples"], run["elapsed_us"])
                for run in candidate_runs]
    except (KeyError, ValueError):
        return {"status": "INCOMPARABLE", "reason": "invalid frame samples"}
    if any(summary["status"] != "COMPLETE" for summary in base + cand):
        return {"status": "INCOMPARABLE", "reason": "fewer than 1000 valid frames"}
    if (not approval.get("operator") or not approval.get("approved_utc")
            or approval.get("baseline_sha256") != baseline_content_hash(baseline_runs)):
        return {"status": "NO_BASELINE", "reason": "baseline lacks matching approval"}
    base_p99 = statistics.median(summary["p99_us"] for summary in base)
    cand_p99 = statistics.median(summary["p99_us"] for summary in cand)
    effect = 100 * (cand_p99 / base_p99 - 1)
    budget = approval.get("budget_percent")
    status = ("REGRESSION_CANDIDATE" if isinstance(budget, (int, float))
              and effect > budget else "INFORMATIONAL")
    return {"status": status, "baseline_boots": len(base),
            "candidate_boots": len(cand), "baseline_boot_p99_median_us": base_p99,
            "candidate_boot_p99_median_us": cand_p99, "p99_effect_percent": effect,
            "profile": profiles[0]}


def analyze_run(raw: bytes, capture: dict) -> dict:
    parsed = parse_perf(raw)
    run_summaries = []
    for run in parsed["runs"]:
        measurement = None
        integrity = run["transport_integrity"]
        if run["suite"] not in {"TI", "HC", "HP"} and run["samples"] and run["elapsed_us"]:
            try:
                measurement = summarize_samples(run["samples"], run["elapsed_us"])
            except ValueError:
                integrity = "CORRUPT"
        run_summaries.append({"run": run, "measurements": measurement,
                              "firmware_result": run["firmware_result"],
                              "transport_integrity": integrity})
    run = parsed["runs"][0] if parsed["runs"] else None
    source_type = capture.get("source_type", "synthetic")
    results = [item["firmware_result"] for item in run_summaries]
    firmware_result = (next((status for status in ("FAIL", "INCONCLUSIVE", "SKIP")
                             if status in results), "PASS") if results else "NOT_EXECUTED")
    integrities = [item["transport_integrity"] for item in run_summaries]
    integrity = ("CORRUPT" if "CORRUPT" in integrities else
                 "INCOMPLETE" if "INCOMPLETE" in integrities else
                 "COMPLETE" if integrities else "NOT_CAPTURED")
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
    warm = next((item for item in run_summaries
                 if item["measurements"] and not
                 str(item["run"].get("profile_id") or "").endswith("_cold")),
                None)
    measurements = warm["measurements"] if warm else None
    statuses = {"firmware_result": firmware_result,
                "transport_integrity": integrity,
                "profile_compatibility": compatibility,
                "baseline_status": baseline,
                "physical_review": physical_review}
    complete = (firmware_result == "PASS" and integrity == "COMPLETE"
                and compatibility == "COMPATIBLE" and baseline == "APPROVED"
                and physical_review == "APPROVED_BY_OPERATOR"
                and all(item["measurements"] is None
                        or str(item["run"].get("profile_id") or "").endswith("_cold")
                        or item["measurements"]["status"] == "COMPLETE"
                        for item in run_summaries))
    return {**statuses, "overall_status": "PASS" if complete else "INCONCLUSIVE",
            "source_type": source_type, "run": run, "runs": run_summaries,
            "measurements": measurements,
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
