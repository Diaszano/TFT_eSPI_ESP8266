"""Run risky coordinate cases in separate, time-limited processes."""
import os
import pathlib
import signal
import subprocess
import time


def run_case(binary: str, case_id: str, timeout_s: float = 2.0) -> dict:
    artifact_dir = pathlib.Path('.build/fuzz/extremes')
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stderr_path = artifact_dir / (case_id + '.stderr')
    started = time.monotonic()
    process = subprocess.Popen([binary, case_id], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=(os.name == 'posix'))
    try:
        _, stderr = process.communicate(timeout=timeout_s)
        stderr_path.write_bytes(stderr)
        status = 'PASS' if process.returncode == 0 else ('SKIP' if process.returncode == 77 else 'FAIL')
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        _, stderr = process.communicate()
        stderr_path.write_bytes(stderr + b'\nTIMEOUT\n')
        status = 'TIMEOUT'
    return {'case_id': case_id, 'status': status, 'returncode': process.returncode,
            'stderr_path': str(stderr_path), 'duration_s': time.monotonic() - started}


def run_suite(binary: str, ids: list[str]) -> list[dict]:
    return [run_case(binary, case_id) for case_id in ids]
