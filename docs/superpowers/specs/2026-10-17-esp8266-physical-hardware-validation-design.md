# ESP8266 Physical Hardware Validation and ST7789 Simulator Fidelity

**Date:** 2026-10-17
**Status:** implementation design for Plan 12 preparation
**Repository:** `TFT_eSPI_ESP8266`
**Base revision:** `75cab508b52463f52e7faa455071259d79f33e53`

## 1. Purpose

Establish a safe, reproducible process for checking the real NodeMCU ESP8266 and ST7789 panel against the existing production-rendering simulator. Plan 12 separates host evidence, firmware compilation, physical observations, and human approval. A successful simulator or firmware build is never physical-display evidence.

This is a **functional graphics simulator, not an ESP8266 CPU emulator**. The simulator validates production graphics paths and a virtual ST7789 model. It does not model ESP8266 instruction timing, heap behavior, watchdog scheduling, SPI electrical behavior, panel optics, or all controller/module variants.

## 2. Scope and non-goals

### In scope

- Audit and reuse Plans 01–11, especially the `HWTEST,2` serial protocol, S1–S4 shared draw functions, host pixel oracle, `B/L/M/E30/X` validation code, simulator scene registry, profile, snapshots, and offline log comparison.
- Build-only H0 preflight evidence tying a clean source revision and exact firmware binary checksum to the repository's effective profile.
- A physical test matrix covering initialization, orientation, primitives, images/sprites, fonts, shared scenes, timing, heap, and stability.
- Explicit operator checkpoints H0–H3 and evidence/report semantics.
- Simulator-to-hardware comparison with independent provenance and human visual review.

### Non-goals

- No automatic upload, bootloader entry, serial-port selection, serial monitor, DTR/RTS manipulation, reset, reboot, or physical test execution.
- No new graphics renderer, duplicate shared scene implementation, pin changes, board changes, display-driver changes, or dependency upgrades.
- No claim of exact physical GRAM equality from a photograph. The configured module has no MISO/readback path.
- No automatic approval of photographs, snapshots, benchmark baselines, or endurance results.
- No Plan 13 or unrelated simulator feature work.

## 3. Effective profile and assumptions

The repository configuration currently selects `ST7789_DRIVER`, 240×240 visible dimensions, MOSI GPIO13, SCLK GPIO14, DC GPIO0, reset GPIO2, backlight GPIO5 active LOW, 40 MHz SPI, CS tied LOW, and no MISO. The driver defaults to SPI mode 3 for ST7789. The simulator profile models 240×320 GRAM and a visible 240×240 region. Rotation starts at 0.

These are **repository settings**, not proof of the assembled unit. Before H1 the operator must confirm the actual module, board revision, wiring, supply voltage, CS wiring, backlight polarity, SPI mode compatibility, display offsets/orientation, and that the panel is write-only. Do not change configuration to force a match. Record mismatches as a profile difference and stop comparisons until resolved.

## 4. Existing architecture and reuse contract

The hardware sketch remains `extras/hardware/Audit_Validation/Audit_Validation.ino`. Its versioned line protocol is `HWTEST,2`, `RUN,...`, `READY`, `CASE,START`, `CASE,RETURN`, plus `BENCH` and `STRESS` records. Existing commands are `?`, `B`, `S`, `S1`–`S4`, `L`, `M`, `E30`, `X`, `N`, and `Q`. Plan 12 adds the backward-compatible `R0`–`R3` command to select the current display rotation and emit `ROTATION,<n>`; it starts no drawing or stress test. Preserve all existing meanings and parser compatibility.

The boot path initializes the display, creates reusable sprites, draws an informational menu, and emits `READY`; it does not automatically run a benchmark, stress, extreme-coordinate, visual, or endurance suite. `R0`–`R3` permits rotation 0–3 before a selected `S1`–`S4` scene, with the active rotation captured for each case by the offline parser. `N`/`Q` are consumed inside the visual and endurance routines where supported. They are not global cancellation commands. Do not claim cancellation of blocking operations that cannot service serial input.

Reuse:

- `ValidationVisualScenes.cpp` for the same S1–S4 drawing calls on host and firmware.
- `simulator/native/Scenes.cpp`, `simulator/tools/sim.py`, and the selected simulator profile to generate expected RGB565/PNG evidence.
- `scripts/hw_validation_compare.py` for parsing logs, strict status semantics, five-boot benchmark comparison, and sanitized reports.
- Plans 01–06 host tests, command parser, telemetry, bounded `X` allowlist, stress/memory math, and offline CI/build targets.
- Plans 07–11 controller model, production renderer, snapshots, diffs, viewer, and headless checks.

Plan 12 must add only missing integration. Physical serial capture remains operator-controlled. Host tests must use fixtures/fakes and never open a device.

## 5. H0 preflight and authorization gates

### H0 — build and safety readiness

Before any physical action:

1. Record a clean full source SHA; a dirty tree is not an exact approved source revision.
2. Run host regressions, sanitizers, firmware compile-only tests, documentation checks, and the dedicated validation-sketch build.
3. Record the PlatformIO Core/platform/framework/compiler versions and board environment from actual build output.
4. Produce an H0 report containing firmware path, firmware SHA-256, source SHA, clean/dirty state, effective repository profile, expected boot/protocol behavior, build commands, and the fact that upload is not authorized.
5. Identify the intended serial port manually, but do not enumerate devices or open it from automation. Confirm the operator's upload tool and policy will not toggle DTR/RTS or reset automatically.
6. Operator confirms actual hardware wiring, module voltage, and display profile.

H0 means **build evidence ready for review**, not permission to flash. If the binary is absent, source is dirty, profile is inconsistent, or toolchain/build evidence is incomplete, H0 is BLOCKED.

### H1 — explicit authorization before flashing

Stop and request a separate, explicit operator authorization naming the firmware checksum, physical board/panel, selected manual upload procedure, and intended device. Do not infer this authorization from the Plan 12 request. Require manual confirmation before bootloader entry. If upload cannot avoid automatic DTR/RTS/reset, do not proceed.

### H2 — reboot and observation

After an operator-authorized upload, the operator performs or confirms reboot manually. A separate approval is required before serial observation. Do not reboot, open serial, or claim firmware identity/`READY` without operator-provided evidence.

### H3 — individual physical groups

Before each physical group, present its purpose, expected duration, risks, and stop/cancel behavior. Require a separate approval. E30, L, and X require distinct opt-in; no combined automatic hardware suite is allowed. Cancellation is honored only where the firmware can poll it. A reset, timeout, missing final marker, or lost log is INCONCLUSIVE or FAIL, never PASS.

## 6. Test architecture and evidence

The evidence layers are:

1. **Host functional:** production graphics code under native simulator, independent pixel oracle, ASan/UBSan, deterministic scene/profile/seed, snapshot and diff report.
2. **Firmware compilation:** the actual ESP8266 target and validation sketch compile without enabling `TFT_ESPI_SIMULATOR`; this proves compile compatibility only.
3. **Physical digital telemetry:** serial output captured manually after H2 approval. It proves only what the firmware reports; `CASE,RETURN` means a call returned, not that pixels are correct.
4. **Physical visual review:** operator records observations and, optionally, a photograph. A photo is affected by exposure, white balance, angle, reflections, and the panel; it is not RGB565 readback.
5. **Physical performance/stability:** measurements from the real ESP8266 only, with fixed board, supply, firmware, CPU/SPI settings, Wi-Fi state, and repeated independent boots.

Recommended run directory: `validation/hardware/runs/<run-id>/`, created only for an approved physical run. It may contain `manifest.json`, sanitized `serial.log`, expected `frame.rgb565`/`frame.png`, optional operator-supplied photo, `observations.md`, `report.json`, and `report.md`. Do not commit local identifiers, unsanitized serial data, private photographs, generated binaries, or unapproved goldens by default.

Manifest fields include protocol version, run ID, firmware full source SHA, firmware binary SHA-256, simulator SHA, scenario ID/seed, profile and profile hash, board/panel/operator-confirmed wiring, rotation, CPU/SPI frequencies, Wi-Fi profile, reset reason, command, start/end state, and artifact hashes. Unknown or conflicting required fields make the result INCONCLUSIVE.

## 7. Simulator-to-hardware mapping

| Hardware check | Existing source of commands | Expected host evidence | Physical evidence / limit |
|---|---|---|---|
| Initialization and colors | `Audit_Validation.ino`, `User_Setup.h` | Controller init replay; profile metadata | Human confirms powered panel, backlight, stable idle and primary colors; no readback |
| Rotation/addressing | `R0`–`R3` then `S1` asymmetrical edge scene | Real production path, 0–3 asymmetric simulator output | Four individually approved rotations; record orientation, corner placement, offsets |
| Primitive/clipping | `S1`, `X` bounded cases | Host primitive/clipping oracle and snapshots | Human verifies edges/negative/partial cases; `X` only after separate approval |
| Image/sprite | `S2`, `S3`, `M` | Production image/sprite cases and independent host checks | Confirm only capabilities in compiled profile; record transparency and crop behavior |
| Text/fonts | `S4` and host text cases | Existing supported font references | RLE font without independent golden is SKIP/INCONCLUSIVE; visual observation is not exact pixel proof |
| Shared S1–S4 | `ValidationVisualScenes.cpp` compiled into firmware and simulator | Same draw functions, scene ID/profile/seed | Operator reviews each screen; visual approval is separate from automated status |
| Timing | `B` | No host timing used as hardware baseline | ESP8266 microsecond samples; ≥5 independent boots per revision for comparison; median/p95 |
| Heap/stability | `M`, `L`, optional `E30` | Host memory is not representative | Free heap/max block, allocation recovery, reset/watchdog observations; E30 opt-in |

S1–S4 must use the shared draw functions. If firmware rotation or scenario seed is not configurable under the existing protocol, document that limitation rather than inventing an incompatible command. A physical photo is for manual visual review only; exact physical pixel comparison requires a separately designed and validated readback/capture device.

## 8. Coverage and result semantics

The final matrix distinguishes present implementation, executed host tests, compile evidence, and physical evidence. Expected cases include RGB565 fill; pixels/lines/rectangles/circles; all four edges and negative/partial geometry; RGB565 image and crop; 1/4/8/16-bpp sprites where enabled; palette/transparency/odd widths; supported text modes; RLE fonts; rotations 0–3; shared S1–S4; B timings; M allocation profiles; L stability; E30 endurance; and bounded X cases.

Use only `PASS`, `FAIL`, `SKIP`, `INCONCLUSIVE`, `BLOCKED`, and `VISUAL_REVIEW_REQUIRED` for gate/evidence status. `NO_BASELINE` remains a comparison status, not success. Unsupported profile capabilities remain `SKIP`/`UNSUPPORTED` as the underlying tool reports. Never turn missing evidence, a returned function call, or screenshot similarity into PASS.

## 9. Failure classification

- **Configuration mismatch:** repository setup and assembled device disagree (pins, mode, offsets, dimensions, color order, inversion, supply, or panel variant). Stop matched-profile comparison; preserve both profiles.
- **Production library defect:** supported operation violates the API/controller contract on production code. Add a host regression first; fix production code separately and prove the ordinary hardware build remains compatible.
- **Simulator defect:** simulator output disagrees with the verified production path/controller model under a valid profile. Fix simulator/test logic without masking production behavior.
- **Physical/module behavior:** real display behavior differs while source/profile and command evidence agree; investigate module/controller/assembly and record a physical limitation rather than changing configuration to pass.
- **Unsupported operation:** invalid addresses/buffers or commands outside the documented hardware contract; classify explicitly, do not clamp or run arbitrary inputs.
- **Insufficient evidence:** no physical execution, no independent font oracle, no readback, unknown reset state, incomplete serial log, or missing manual review; report INCONCLUSIVE/BLOCKED/SKIP.

## 10. Safety and data policy

- CI and every default build/test target are headless and offline from hardware.
- No program in Plan 12 selects a serial device, opens USB/UART, uploads firmware, invokes reset/bootloader, toggles modem lines, or sends a hardware test command.
- Upload/reboot/observation/test commands in documentation are manual operator procedures only and cannot be Make prerequisites.
- Never automatically resume after reset or start B/S/L/M/E30/X at boot.
- Never automatically approve visual or performance baselines.
- Keep generated binary, serial log, and photo data local unless the operator explicitly sanitizes and chooses to share it.

## 11. Gates and acceptance

### Preparation gate P12-PREFLIGHT

PASS requires: audited reusable harness and plan coverage; spec and executable plan; exact clean source revision; host/sanitizer checks; native/ESP8266 compile-only checks; validation sketch build; firmware SHA-256 and profile report; and no physical interaction. If toolchain/build is unavailable, BLOCKED with exact command/output.

### H-GATE-1 — physical display functionality

Requires operator-approved flash and reboot, confirmed firmware identity, initialization/backlight, primary colors, primitive/clipping behavior, all four rotations/addressing, and a reviewed physical observation. Build, host render, or photo without operator review is insufficient.

### H-GATE-2 — simulator fidelity

Requires matched source/profile/scenario/seed, shared S1–S4 production calls, expected simulator artifacts, physical observations for all four scenes, human approval, and recorded discrepancies. Without physical readback, this is a reviewed visual fidelity gate, not exact RGB565 equality.

### H-GATE-3 — hardware stability and performance

Requires real ESP8266 B measurements with repeated independent boots, M allocation observations, L stability result, reset/watchdog review, and separately authorized E30 if required. Host timing/heap is not accepted. Incomplete or interrupted runs are not PASS.

Plan12 preparation may be complete while H-GATE-1/2/3 remain BLOCKED pending H1–H3 operator approvals. D5 remote GitHub Actions verification remains separate.

## 12. Plan 12 completion evidence

The final report lists branch/worktree/source SHA; audit inventory and commands actually run; firmware/toolchain/configuration; H0 report and binary checksum; Plan 01–11 reuse and current limitations; per-case coverage and status; any RED/GREEN changes; code review findings; commit SHAs; and explicit unexecuted physical gates. It ends at H1 with the exact firmware path/checksum, board/profile, and manual action requiring operator approval.
