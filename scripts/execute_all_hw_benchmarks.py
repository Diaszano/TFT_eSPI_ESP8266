"""Automated hardware benchmark executor for ESP8266 + ST7789."""

import json
import os
import sys
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import serial

from scripts.hw_perf_protocol import parse_perf
from scripts.hw_perf_analysis import summarize_samples, summarize_heap

PORT = "/dev/ttyUSB0"
BAUD = 115200


def open_serial():
    s = serial.Serial(PORT, BAUD, timeout=0.2)
    s.dtr = False
    s.rts = False
    return s


def drain_serial(s, timeout=1.0):
    start = time.time()
    total = 0
    while time.time() - start < timeout:
        chunk = s.read(2048)
        if chunk:
            total += len(chunk)
            start = time.time()  # reset timer if data is still arriving
    return total


def run_command(s, cmd: str, stop_tokens: list[bytes], max_wait_sec: float = 60.0):
    drain_serial(s, timeout=0.5)
    print(f"\n>>> Executando suite: {cmd.strip()} (timeout: {max_wait_sec}s)...", flush=True)
    s.write(cmd.encode("ascii"))
    s.flush()

    raw = b""
    start = time.time()
    last_print = start
    while time.time() - start < max_wait_sec:
        chunk = s.read(2048)
        if chunk:
            raw += chunk
            if any(token in raw for token in stop_tokens):
                time.sleep(0.3)
                raw += s.read(4096)
                break
        if time.time() - last_print > 5.0:
            last_print = time.time()
            elapsed = round(last_print - start, 1)
            print(f"    ... aguardando {cmd.strip()} ({elapsed}s decorridos, {len(raw)} bytes)...", flush=True)

    elapsed_total = round(time.time() - start, 2)
    print(f"    Concluído em {elapsed_total}s ({len(raw)} bytes recebidos).", flush=True)
    return raw


def main():
    s = open_serial()
    drain_serial(s, 1.0)

    results = {}

    try:
        # 1. TI: Telemetry Integrity
        raw_ti = run_command(s, "TI\n", [b"END,TI,"], max_wait_sec=5.0)
        p_ti = parse_perf(raw_ti)
        results["TI"] = {"raw_len": len(raw_ti), "runs": p_ti["runs"], "errors": p_ti["errors"]}

        # 2. HP: Heap Pressure
        raw_hp = run_command(s, "HP\n", [b"END,HP,"], max_wait_sec=10.0)
        p_hp = parse_perf(raw_hp)
        results["HP"] = {"raw_len": len(raw_hp), "runs": p_hp["runs"], "errors": p_hp["errors"]}

        # 3. FP3: Mixed Frame UI
        raw_fp3 = run_command(s, "FP3\n", [b"END,FP3,"], max_wait_sec=20.0)
        # FP3 tem 2 runs: cold e warm
        if raw_fp3.count(b"END,FP3,") < 2:
            time.sleep(3.0)
            raw_fp3 += s.read(8192)
        p_fp3 = parse_perf(raw_fp3)
        results["FP3"] = {"raw_len": len(raw_fp3), "runs": p_fp3["runs"], "errors": p_fp3["errors"]}

        # 4. FP1: Full Frame (Scanline + Fill)
        raw_fp1 = run_command(s, "FP1\n", [b"fp1_fill"], max_wait_sec=70.0)
        # FP1 tem 4 runs
        start_wait = time.time()
        while raw_fp1.count(b"END,FP1,") < 4 and time.time() - start_wait < 30.0:
            chunk = s.read(2048)
            if chunk:
                raw_fp1 += chunk
            else:
                time.sleep(0.2)
        time.sleep(0.5)
        raw_fp1 += s.read(4096)
        p_fp1 = parse_perf(raw_fp1)
        results["FP1"] = {"raw_len": len(raw_fp1), "runs": p_fp1["runs"], "errors": p_fp1["errors"]}

        # 5. FP2: Partial Frame Regions (12 perfis x 2 = 24 runs)
        raw_fp2 = run_command(s, "FP2\n", [b"fp2_120_clip"], max_wait_sec=60.0)
        start_wait = time.time()
        while raw_fp2.count(b"END,FP2,") < 24 and time.time() - start_wait < 30.0:
            chunk = s.read(2048)
            if chunk:
                raw_fp2 += chunk
            else:
                time.sleep(0.2)
        time.sleep(0.5)
        raw_fp2 += s.read(4096)
        p_fp2 = parse_perf(raw_fp2)
        results["FP2"] = {"raw_len": len(raw_fp2), "runs": p_fp2["runs"], "errors": p_fp2["errors"]}

        # 6. HC: Heap Churn (100k cycles)
        raw_hc = run_command(s, "HC\n", [b"END,HC,"], max_wait_sec=35.0)
        p_hc = parse_perf(raw_hc)
        results["HC"] = {"raw_len": len(raw_hc), "runs": p_hc["runs"], "errors": p_hc["errors"]}

        # 7. LW: Wi-Fi Latency
        raw_lw = run_command(s, "LW\n", [b"END,LW,"], max_wait_sec=20.0)
        p_lw = parse_perf(raw_lw)
        results["LW"] = {"raw_len": len(raw_lw), "runs": p_lw["runs"], "errors": p_lw["errors"]}

        # 8. B: Classic Benchmark
        raw_b = run_command(s, "B\n", [b"BENCHMARK_COMPLETE"], max_wait_sec=30.0)
        results["B"] = {"raw_len": len(raw_b), "raw_text": raw_b.decode("latin1", errors="replace")}

    finally:
        s.close()

    output_path = Path("benchmark_results.json")
    # Salvar resumo formatado
    summary = {}
    for suite, res in results.items():
        if "runs" in res:
            suite_summary = []
            for run in res["runs"]:
                entry = {
                    "profile_id": run["profile_id"],
                    "suite": run["suite"],
                    "observed_count": run["observed_count"],
                    "firmware_result": run["firmware_result"],
                    "transport_integrity": run["transport_integrity"],
                }
                if run["samples"] and run["elapsed_us"]:
                    s_stats = summarize_samples(run["samples"], run["elapsed_us"])
                    entry["fps"] = round(s_stats["fps_effective"], 2)
                    entry["p50_us"] = s_stats["p50_us"]
                    entry["p95_us"] = s_stats["p95_us"]
                    entry["p99_us"] = s_stats["p99_us"]
                    entry["min_us"] = s_stats["min_us"]
                    entry["max_us"] = s_stats["max_us"]
                if run["memory"]:
                    h_stats = summarize_heap(run)
                    entry["heap_stats"] = h_stats
                suite_summary.append(entry)
            summary[suite] = {"runs": suite_summary, "error_count": len(res["errors"])}
        else:
            summary[suite] = {"raw_len": res["raw_len"], "text": res.get("raw_text", "")}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n[SUCESSO] Todos os resultados foram gravados em {output_path}!", flush=True)


if __name__ == "__main__":
    main()
