#!/usr/bin/env python3
"""Compile the hardware validation sketch without touching a serial device."""
import argparse
import pathlib
import shutil
import subprocess


def plan_build(repo_root: pathlib.Path, git_sha: str, dirty: bool) -> tuple[list[str], pathlib.Path]:
    root = pathlib.Path(repo_root).resolve()
    build_dir = root / '.build/hardware' / ('validation-{}-{}'.format(git_sha, 'dirty' if dirty else 'clean'))
    build_flags = 'build_flags=-DVALIDATION_GIT_SHA=\\"{}\\" -DVALIDATION_DIRTY_TREE={}'.format(
        git_sha, 1 if dirty else 0)
    command = [shutil.which('pio') or 'pio', 'ci', '--lib=' + str(root / '.build/pio-library'),
               '--board=nodemcuv2', '-O', 'platform=espressif8266@4.2.1', '-O',
               build_flags,
               '--build-dir=' + str(build_dir), '--keep-build-dir',
               str(root / 'extras/hardware/Audit_Validation')]
    return command, build_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-only', action='store_true', help='compile only; never upload or open serial')
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    sha = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=root,
                         check=True, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain'], cwd=root,
                                check=True, capture_output=True, text=True).stdout)
    command, build_dir = plan_build(root, sha, dirty)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    print('Building {} ({})'.format(sha, 'dirty source' if dirty else 'clean source'))
    subprocess.run(command, cwd='/tmp', check=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
