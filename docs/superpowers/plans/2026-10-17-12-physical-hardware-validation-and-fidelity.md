# Superpowers — Plan 12: ESP8266 physical hardware validation and simulator fidelity

> **Execution:** Use `superpowers:executing-plans`; apply TDD to code changes. This plan is authorized for local implementation and verification only. It does not authorize upload, bootloader entry, serial access, reset, or physical tests.

**Goal:** Prepare reproducible, safe evidence that compares the native production-graphics simulator with an actual NodeMCU ESP8266/ST7789 without treating host tests or compilation as hardware validation.
**Design:** `docs/superpowers/specs/2026-10-17-esp8266-physical-hardware-validation-design.md`
**Prerequisites:** Verified Plan 11 base `75cab508b52463f52e7faa455071259d79f33e53`; inspect actual implementation of Plans 01–11 and all local changes first.
**Branch/worktree:** `codex/physical-hardware-validation`, `/home/diaszano/.codex/worktrees/6ad5/simulator-hardware-validation`. Do not modify the primary worktree.
**Environment:** Python 3.14.7 / PlatformIO Core 6.2.0 where available; ESP8266 platform 4.2.1, Arduino framework as resolved by the pinned platform, CMake/CTest, existing host ASan/UBSan. Do not upgrade dependencies to get a build.

## Global constraints

- Read effective `User_Setup.h`, `platformio.ini` equivalents, simulator profile, source code, and tests. Repository settings do not prove actual physical wiring or panel variant.
- Reuse `ValidationCommand`, `ValidationTelemetry`, `ValidationVisualScenes`, existing `B/S/L/M/E30/X` groups, host tests, `hw_validation_compare.py`, and simulator snapshots. Do not duplicate a protocol, scene renderer, or production drawing algorithm.
- Build/test targets may compile, parse saved logs, render host frames, and generate a local H0 report only. They must not enumerate/open serial devices, upload, invoke esptool, reset, toggle DTR/RTS, or start a physical test.
- No test group starts at boot. No automatic resume after reset. E30, L, and X require separate manual approvals if/when physical testing is later authorized.
- Host timings and memory are not ESP8266 measurements. Photos are not exact RGB565 readback. RLE font oracle and S1–S4 manual visual approval stay pending until evidence exists.
- Preserve existing user changes and generated outputs. No destructive Git operations, push, merge, release, or PR.
- A physical action requires the corresponding H1/H2/H3 authorization; this task must stop and ask before H1.

## Audit findings at plan start

- `User_Setup.h` selects ST7789 240×240, MOSI 13, SCLK 14, DC 0, reset 2, backlight 5 active LOW, 40 MHz SPI, CS grounded/no MISO by documented configuration; mode 3 is the driver's ST7789 default. Verify with build/source and have operator confirm the assembled hardware before H1.
- `simulator/profiles/nodemcu-st7789-240x240.json` models 240×320 GRAM and 240×240 visible output with rotations 0–3.
- Existing firmware emits `HWTEST,2`, `RUN`, menu, `READY`; boot does not launch a suite. Commands and cancellation scope are implemented in `ValidationCommand.h`, `Audit_Validation.ino`, and group code. N/Q are contextual, not global.
- The pre-Plan-12 serial harness lacks an operator command to select physical rotations 1–3; add backward-compatible `R0`–`R3` selection and record rotation at each case start in the offline report. This is a confirmed coverage gap, not a configuration change.
- Existing reusable artifacts and actual gate status will be inventoried in Task 1; documentation alone is not evidence of test execution.
- Initial confirmed integration gap: compile-only build has a source-specific output directory, but no single H0 artifact records the exact firmware SHA-256 and explicitly marks upload/physical checks pending. Task 2 adds only that report.

## Review focus

1. No target or script opens a port, uploads, resets, toggles DTR/RTS, or dispatches a physical command.
2. A dirty source tree or absent firmware cannot yield a ready H0 report.
3. Report binds full source revision, exact firmware binary hash, effective source profile, and simulator profile while keeping operator hardware confirmation false/pending.
4. Existing serial grammar and parser semantics remain compatible; N/Q are not misrepresented as global cancellation.
5. No physical test, photo, or measurement is fabricated; no screenshot is treated as exact pixel readback.
6. Standard firmware compiles without `TFT_ESPI_SIMULATOR`; simulator-specific conditional behavior and hardware pins stay unchanged.
7. Plans 01–06 checks are classified from actual implementation and command output, not assumed complete from plans or docs.

---

## Task 1 — Audit Plans 01–11 and establish reproducible host baseline

**Files:** read-only audit of `User_Setup.h`, `test/platformio.ini`, `Makefile`, `scripts/`, `tests/host/`, `extras/hardware/Audit_Validation/`, `simulator/`, `.github/workflows/`, and `docs/superpowers` copies. Add findings to the report section in `extras/hardware/Audit_Validation/TESTES.md` only if current statuses are stale.

**Steps:**

1. Record branch, worktree, HEAD, dirty state, ignored build outputs, and primary-worktree status. Inspect `git diff` and untracked files in both relevant worktrees; never overwrite either.
2. Inventory each Plan 01–11 deliverable as implemented, host-tested with fresh command output, compile-tested, physically executed, incomplete, or unsupported. Read relevant original plans/specs from the primary copy without modifying it.
3. Trace actual serial commands, startup behavior, cancellation polling, telemetry fields, and bounded X cases. Confirm profile constants from source and note physical assumptions that cannot be source-verified.
4. Run baseline commands that do not touch hardware: `make sim-build`, `make sim-test`, `make test-host`, `make test-host-extremes`, `make docs-check`. Run native/firmware compile commands only after confirming the executable Make recipes are compile-only.
5. Record CTest count, Python test counts, sanitizer flags, tool versions, compile outcomes, SKIPs, and blockers. Baseline failures are diagnosed before code changes.

**Expected:** An evidence inventory differentiating code presence, test execution, compile evidence, and physical evidence. No hardware claim follows from host/compile output.

**Commit:** `docs(hardware): inventory Plan 12 validation prerequisites` (combine with final docs commit if there is no durable source change).

## Task 2 — Add H0 build artifact report (TDD)

**Files:**

- Create `scripts/hw_validation_preflight.py`.
- Create `scripts/test_hw_validation_preflight.py`.
- Modify `Makefile` to expose `test-hw-preflight` without changing existing target behavior.
- Modify `extras/hardware/Audit_Validation/README.md` and `TESTES.md` with exact host-only commands and H0/H1 boundary.
- Modify `simulator/README.md` to list the new build-only evidence target.

**Interface:** `python3 scripts/hw_validation_preflight.py` locates the build artifact corresponding to the current full source SHA/clean state, then emits `preflight.json` and `preflight.md` under `.build/hardware/preflight-<short-sha>-<clean|dirty>/`. The report hashes the exact `firmware.bin` and records effective `User_Setup.h`, simulator profile, `nodemcuv2`, repository source revision, dirty state, expected boot/protocol and required manual checks. It records `upload_authorized: false`, `serial_port_selected: false`, and all physical observations as pending. A dirty source, missing/empty firmware, wrong build/profile path, or mismatched dimensions/driver returns a nonzero result and a BLOCKED report or clear error; it never says physical PASS.

**TDD:**

1. Add tests using temporary fixture roots and fake firmware bytes. Cover exact SHA-256, source/profile values, clean vs dirty status, missing/empty/wrong-path firmware, malformed/mismatched profile, and explicit false authorization fields. No real PlatformIO/device command in unit tests.
2. Run `python3 -m unittest scripts.test_hw_validation_preflight -v`; confirm RED due to missing module/behavior (not missing toolchain).
3. Implement the smallest stdlib report builder and CLI. Constrain report output to the repository's `.build/hardware` directory. Do not include absolute home paths or serial identifiers.
4. Run focused tests GREEN, a malformed-profile negative case, then integration against a real compile-only firmware artifact in Task 4.
5. Add `make test-hw-preflight` as an explicit build-and-report target. It may depend on `test-hw-build`; it must not depend on upload/monitor/reset/device detection.

**Expected:** A deterministic local H0 report with binary SHA-256 and pending physical authorization. A build report is not permission to flash.

**Commit:** `feat(validation): report checksum-bound hardware preflight`.

## Task 3 — Reconcile physical evidence matrix and operator runbook

**Files:**

- Modify `extras/hardware/Audit_Validation/README.md` and `TESTES.md`.
- Modify `simulator/README.md` only if needed to accurately link fidelity coverage and limitations.
- Optional new template `validation/hardware/README.md`; do not commit a fake run or sample physical evidence.

**Steps:**

1. Test the documented command/protocol statuses against `ValidationCommand.h`, sketch dispatch, group implementations, and `hw_validation_compare.py`.
2. Add a traceability matrix for initialization/backlight, rotations 0–3, corner markers, primitive clipping, image crop, 1/4/8/16-bpp sprite capabilities, palettes/transparency/odd widths, fonts/RLE, S1–S4, B timing, M heap profiles, L, E30, and bounded X.
3. For every row specify reusable host command/oracle, required operator action, expected telemetry/artifact, result vocabulary, and limitations. Mark unsupported capabilities SKIP; mark absent independent font oracle INCONCLUSIVE/SKIP; mark visual scenes VISUAL_REVIEW_REQUIRED until signed human review.
4. Document the run manifest and evidence directory, sanitation, no-readback photo rules, five independent boots for benchmark comparisons, reset/lost-log handling, and exact H0–H3 approvals.
5. Add/update a docs contract test if the existing coverage does not assert these safety boundaries. Test that no documented offline target is presented as a physical test and no default command flashes hardware.

**Expected:** A usable operator runbook that does not imply this work performed hardware tests or authorizes upload.

**Commit:** `docs(validation): document physical test matrix and authorization gates`.

## Task 3a — Select and report hardware display rotation (TDD)

**Files:** `extras/hardware/Audit_Validation/ValidationCommand.h`, `Audit_Validation.ino`, `tests/host/test_validation_command.cpp`, `scripts/hw_validation_compare.py`, `scripts/test_hw_validation_compare.py`, `extras/hardware/Audit_Validation/README.md`, `TESTES.md`.

1. Add parser tests for `R0`–`R3`, malformed `R4`/`R10`, and old command behavior; run the focused native parser test and confirm RED.
2. Add parser-log tests proving each `CASE,START` captures the most recently selected rotation and malformed rotation records make the run INCONCLUSIVE; run focused Python tests and confirm RED.
3. Implement only `R0`–`R3`: call `tft.setRotation(n)`, emit `ROTATION,n`, and start no suite. Keep N/Q scoped as before.
4. Extend the offline log parser/report so each case includes its rotation. Existing HWTEST,2 logs without ROTATION remain compatible and use the RUN rotation field.
5. Run focused tests GREEN, all host/parser tests, and the ESP8266 compile-only build. Document that physical rotation still awaits H1/H3 approval.

**Expected:** Each orientation can be selected manually, rendered with shared S1–S4 code, and paired with the corresponding simulator `--rotation` frame without adding an automated hardware runner.

**Commit:** `feat(validation): select and report ST7789 test rotation`.

## Task 4 — Run the complete hardware-independent preflight

**Files:** generated outputs only under ignored `.build/`; no checked-in binaries, logs, or photos.

**Commands:**

```bash
git diff --check
make sim-build
make sim-test
make test-host
make test-host-extremes
make test-native
make test-compile
make test-hw-build
make test-hw-preflight
make docs-check
python3 -m unittest scripts.test_hw_validation_preflight -v
python3 -m unittest scripts.test_hw_validation_compare -v
make test-host  # includes the native validation-command parser tests
```

Run each command only after confirming its recipe is host/build-only. For PlatformIO use the documented isolated environment and record PIO Core, platform, framework, compiler, board and exit status. Check that simulator test targets retain ASan/UBSan and that no test opens a viewer or hardware port.

**Steps:**

1. Verify the source revision is clean and all task commits are reviewed; then build the validation sketch from that exact revision.
2. Inspect the produced firmware path and verify its report SHA-256 independently with `sha256sum` (or Python hashlib). Ensure profile data agrees with `User_Setup.h` and the simulator JSON.
3. Inspect Make recipes, CI workflows, and process logs for upload, esptool, serial monitor, USB/UART, DTR/RTS, bootloader, reset, or physical test commands. These must not be executed.
4. Rerun affected suites after any fix. Preserve failures; do not weaken gates.
5. Conduct final code review for correctness, report integrity, path handling, protocol compatibility, and safety.

**Expected:** All locally executable checks pass or have exact, actionable BLOCKED reasons. P12-PREFLIGHT cannot PASS if a mandatory build is unexecuted or failed.

**Commit:** `test(validation): verify Plan 12 host and compile-only preflight` only if the project convention requires test changes; otherwise keep evidence in the final report/build output.

## Task 5 — Stop at H1 and request explicit operator authorization

**No source code or hardware command is part of this task.**

1. Present H0 report path, full source SHA, firmware path and SHA-256, profile, build/toolchain versions, expected boot output, and exact test command menu.
2. State that serial port remains unselected and no upload, bootloader entry, reset, reboot, serial observation, or test has occurred.
3. Request explicit manual authorization before any flashing. Authorization must identify the exact checksum, board/panel, operator-selected serial port and upload procedure, and confirm no automatic DTR/RTS/reset.
4. Do not interpret silence or a previous broad Plan 12 request as approval. Stop after the request.

## Gate criteria

| Gate | Required evidence | Preparation-stage expectation |
|---|---|---|
| P12-PREFLIGHT | Clean source, host/sanitizer suites, compile-only ESP8266 and sketch builds, H0 checksum/profile report, no hardware side effects | PASS only with actual command output |
| H-GATE-1 | Authorized execution, init/backlight/color/primitive/rotation visual evidence | BLOCKED pending H1–H3 and actual observations |
| H-GATE-2 | Matched profile/scenarios, S1–S4 physical review and discrepancy log | VISUAL_REVIEW_REQUIRED / BLOCKED; no photos currently exist |
| H-GATE-3 | Real ESP8266 timing, heap, reset/watchdog, stability and any approved E30 | BLOCKED; host/compile evidence does not count |
| D5 remote CI | Exact HEAD successful GitHub Actions run | Report separately; local workflow checks are not remote CI |

## Completion and commits

Plan 12 preparation is complete only when specification/plan, audit, H0 report, operator matrix, local tests, review and local commits are complete and the process stops at H1. Full physical validation requires later approvals and evidence; it is not a condition for preparation completion.

Suggested local commits, reviewed and scoped:

1. `feat(validation): report checksum-bound hardware preflight` — preflight script/tests and Make integration.
2. `docs(validation): document physical test matrix and authorization gates` — spec/plan and operator documentation.

Do not commit generated firmware, serial logs, private photos, unapproved snapshots, or unrelated primary-worktree files. Do not push, merge, release, or create a pull request.
