English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/docs/pt-BR/development.md)

# Development

## Make targets

Use Python 3.14.7 for the development toolchain. Install the pinned and hash-locked tools with `python -m pip install --require-hashes -r scripts/requirements-dev.txt`; the build uses ESP8266 platform 4.2.1 and tracks nested library and example inputs so additions, edits, and deletions invalidate cached builds.

The build and CodeQL workflows compile `Colour_Test` once before their parallel build. This serial first build initializes the shared PlatformIO packages before other examples use them concurrently; the locked PlatformIO core and target versions are part of the checked build profile.

Use clang-format 23.1.2 from the locked requirements. `make format-check` checks maintained C++ and Arduino sources without editing them; run `make format` only when you intend to format those files. Generated font tables, ST7789 initialization data and the font-generation tool are excluded. Include order is preserved. After the dedicated formatting change is merged, configure blame with `git config blame.ignoreRevsFile .git-blame-ignore-revs` using the final merged commit SHA.

Run `make test-native` for the pure color conversion tests. They exercise shared integer conversion helpers only; they do not model the ESP8266 core, PROGMEM, display timing, heap use or rendering. Use `make docs-examples` to compile the first C++ examples from both READMEs and Sprite guides against the staged library. Use a device for display checks.

Run `make warnings` to rebuild all 14 examples in `.build/warnings/` with `-Wall -Wextra`. The owned-warning baseline is reviewed manually; new findings fail, resolved findings are reported for removal, and framework/core warnings are kept in a separate report. Do not edit the baseline automatically.

`make compiledb` prepares the checked Xtensa compile database. `make tidy` runs an opt-in clang-tidy 22.1.8 target parser pilot; current ESP8266 compiler flags and SDK headers produce parse errors, so it is not a required gate. See the [LLVM 22.1.8](https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-22.1.8/clang-tools-extra/docs/clang-tidy/index.rst) and [LLVM 23.1.2](https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-23.1.2/clang-tools-extra/docs/clang-tidy/index.rst) documentation for the pilot and requested documentation versions.

`make cppcheck` is an optional PlatformIO pilot over the staged library source, including its `.inc` fragments. The pilot resolved cppcheck 2.11 (`tool-cppcheck` 1.21100.230717) and reported 24 existing findings to `.build/analysis/cppcheck.json`. It is a report only, has no baseline, and does not run in CI.

`make tidy-native` runs the required clang-tidy 22.1.8 check for the pure color-conversion probe and shared header only. Run `make compiledb-native` to refresh that native database; `.clangd` uses it for the probe. This host scope says nothing about parsing the ESP8266 library target.

| Target | Purpose |
| --- | --- |
| `make build` | Compile all curated examples. |
| `make build-<Name>` | Compile one example, such as `make build-Colour_Test`. |
| `make upload EX=<Name> PORT=<port>` | Upload an example to the board. |
| `make uploadfs EX=<Name> PORT=<port>` | Upload an example's filesystem data. |
| `make monitor PORT=<port>` | Open the serial monitor. |
| `make clean` | Remove generated build files. |
| `make warnings` | Rebuild examples with owned compiler-warning checks. |
| `make compiledb` | Validate and map the target compilation database. |
| `make tidy` | Run the non-gating Xtensa clang-tidy parsing pilot. |
| `make cppcheck` | Run the optional staged-library cppcheck report. |
| `make compiledb-native` | Prepare the native color-probe database. |
| `make tidy-native` | Check the pure color probe and shared header. |
| `make docs-check` | Check documentation pairs, links and removed API references. |
| `make docs` | Run the documentation checks and generate the API reference. |
| `make help` | List available targets. |

### Required checks and test directories

`make build-arduino` requires Arduino CLI 1.3.1 and ESP8266 core 3.1.2 installed locally. It compiles all 14 maintained examples for `esp8266:esp8266:nodemcuv2`, then compiles the sprite-ownership and minimal-setup regressions. It uses this checkout as the library and writes logs to `.build/arduino/`. PlatformIO remains required with `espressif8266@4.2.1`; passing one compiler does not replace the other.

Install the core with:

    arduino-cli core update-index --additional-urls https://arduino.esp8266.com/stable/package_esp8266com_index.json
    arduino-cli core install esp8266:esp8266@3.1.2 --additional-urls https://arduino.esp8266.com/stable/package_esp8266com_index.json

`make test-python` runs script regressions. `make layout-check` validates the checkout and the actual PlatformIO compile database; `make package-check` creates and validates the actual package. CI also requires `make format-check`, Unity, source-extracted ASan/UBSan host tests and native clang-tidy. Formatting is checked without rewriting files.

`test/` holds the PlatformIO project, Unity color tests and the native analysis probe. `tests/` holds host regressions and firmware compile sketches. These directories serve different runtimes; their existence is not duplicate test coverage. Host sanitizers and native analysis do not emulate ESP8266 timing, PROGMEM or the physical display.

Library diagnostics from the compiled copy belong to this repository, including legacy SPIFFS deprecations. New owned diagnostics fail the warning gate. Existing debt requires an individual baseline entry with an owner and a specific rationale; framework findings remain separately reported. Never hide library warnings as vendor output or regenerate the baseline without review.

CI compiles the curated examples with PlatformIO. The documentation workflow checks and builds the docs; its Pages deploy job runs only for pushes to `main`.

`make size-check` fails if static flash or RAM usage grows under a different build profile. Its RAM total covers initialized data, read-only data, and BSS; it does not measure runtime heap use by sprites, fonts, or other allocations.

## Arduino library layout

Arduino and PlatformIO compile `src/TFT_eSPI.cpp` as the library’s only production translation unit. Sprite, smooth-font, driver, and built-in font data files are included fragments; keep them as `.inc` or headers, not separately compiled `.cpp`/`.c` files. The editable `User_Setup.h` stays at the package root.

## Add an example

Create `examples/<Name>/<Name>.ino` with no spaces in `<Name>`. Keep example-specific data inside that directory and ensure the sketch builds with the supported setup. Run `make build-<Name>` before submitting, then `make build` to check the complete curated set.

CI also runs `make test-native` for pure color conversions and `make test-compile` for sprite ownership plus a minimal `LOAD_GLCD`-only setup. These checks do not replace the 14 example builds or physical display checks.

## Documentation changes

Write the English file in `docs/en/` first, add its same-named pt-BR translation in `docs/pt-BR/`, and update the matching README if needed. Run `make docs` to check links and language pairs and generate Doxygen HTML.

The Pages workflow uses Doxygen 1.18.0. Install the same version locally so generated warnings match CI; the workflow downloads the official Linux binary for the pinned `DOXYGEN_VERSION`.
