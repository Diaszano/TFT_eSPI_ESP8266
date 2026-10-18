"""Offline validator for external optical, tearing, and power measurements."""

import json
from pathlib import Path


def validate_lab_session(perf_summary: dict, manifest: dict, readings: list[dict] | None) -> dict:
    if not isinstance(perf_summary, dict) or not isinstance(manifest, dict):
        raise ValueError("perf_summary and manifest must be dicts")

    # If no readings provided, external metrics are UNAVAILABLE
    if readings is None or len(readings) == 0:
        return {
            "status": "COMPLETE",
            "optical": "UNAVAILABLE",
            "power": "UNAVAILABLE",
            "reason": "no external instrument readings provided"
        }

    # Reject non-physical captures
    if perf_summary.get("source_type") != "physical":
        return {
            "status": "INCOMPARABLE",
            "optical": "INCOMPARABLE",
            "power": "INCOMPARABLE",
            "reason": "synthetic or non-physical capture cannot be attached to lab evidence"
        }

    # Check profile match
    perf_prof = perf_summary.get("profile") or {}
    manifest_prof = manifest.get("profile") or {}
    if perf_prof != manifest_prof:
        return {
            "status": "INCOMPARABLE",
            "optical": "INCOMPARABLE",
            "power": "INCOMPARABLE",
            "reason": "profile mismatch between manifest and perf capture"
        }

    # Check time interval
    start_utc = manifest.get("capture_utc_start")
    end_utc = manifest.get("capture_utc_end")
    if not start_utc or not end_utc:
        return {
            "status": "INCOMPARABLE",
            "optical": "INCOMPARABLE",
            "power": "INCOMPARABLE",
            "reason": "missing capture_utc_start or capture_utc_end in manifest"
        }

    # Check reading timestamps
    last_ts = None
    for r in readings:
        ts = r.get("timestamp_utc")
        if not ts:
            return {"status": "INCOMPARABLE", "reason": "missing timestamp_utc in reading"}
        if ts < start_utc or ts > end_utc:
            return {
                "status": "INCOMPARABLE",
                "optical": "INCOMPARABLE",
                "power": "INCOMPARABLE",
                "reason": "reading timestamp outside capture interval"
            }
        if last_ts is not None and ts < last_ts:
            return {
                "status": "INCOMPARABLE",
                "reason": "nonmonotonic timestamps"
            }
        last_ts = ts

    # Process optical readings
    optical_readings = [r for r in readings if r.get("channel") == "optical"]
    optical = "UNAVAILABLE"
    if optical_readings:
        valid_units = {"lux", "V", "counts", "state"}
        if any(r.get("unit") not in valid_units for r in optical_readings):
            optical = {"status": "INCOMPARABLE", "reason": "invalid optical units"}
        else:
            values = [r["value"] for r in optical_readings]
            optical = {
                "status": "COMPLETE",
                "sample_count": len(optical_readings),
                "min": min(values),
                "max": max(values),
                "unit": optical_readings[0]["unit"]
            }

    # Process power (voltage & current)
    voltage_readings = {r["timestamp_utc"]: r for r in readings if r.get("channel") == "voltage"}
    current_readings = {r["timestamp_utc"]: r for r in readings if r.get("channel") == "current"}
    power = "UNAVAILABLE"

    if voltage_readings or current_readings:
        calibration = manifest.get("calibration") or {}
        v_factor = calibration.get("voltage_factor")
        i_factor = calibration.get("current_factor")

        if v_factor is None or i_factor is None:
            power = {"status": "INCOMPARABLE", "watts": "UNAVAILABLE", "reason": "missing calibration factor"}
        else:
            # Check units
            v_units_ok = all(r.get("unit") in {"V", "mV"} for r in voltage_readings.values())
            i_units_ok = all(r.get("unit") in {"A", "mA"} for r in current_readings.values())
            if not v_units_ok or not i_units_ok:
                power = {"status": "INCOMPARABLE", "watts": "UNAVAILABLE", "reason": "invalid voltage/current units"}
            else:
                # Find paired timestamps
                common_ts = sorted(set(voltage_readings.keys()) & set(current_readings.keys()))
                if not common_ts:
                    power = {"status": "INCOMPARABLE", "watts": "UNAVAILABLE", "reason": "no paired V/I samples"}
                else:
                    watt_samples = []
                    for ts in common_ts:
                        vr = voltage_readings[ts]
                        ir = current_readings[ts]
                        v = vr["value"] * v_factor * (0.001 if vr["unit"] == "mV" else 1.0)
                        i = ir["value"] * i_factor * (0.001 if ir["unit"] == "mA" else 1.0)
                        watt_samples.append(v * i)
                    power = {
                        "status": "COMPLETE",
                        "sample_count": len(watt_samples),
                        "mean_watts": sum(watt_samples) / len(watt_samples),
                        "max_watts": max(watt_samples),
                        "min_watts": min(watt_samples)
                    }

    return {
        "status": "COMPLETE",
        "optical": optical,
        "power": power,
        "manifest": manifest
    }


def write_lab_summary(directory: Path, summary: dict):
    path = directory / "lab-summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
