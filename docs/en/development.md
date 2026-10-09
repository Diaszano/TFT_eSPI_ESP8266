English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/docs/pt-BR/development.md)

# Development

## Make targets

Use Python 3.14.7 for the development toolchain. Install the pinned and hash-locked tools with `python -m pip install --require-hashes -r scripts/requirements-dev.txt`; the build uses ESP8266 platform 4.2.1 and tracks nested library and example inputs so additions, edits, and deletions invalidate cached builds.

Use clang-format 23.1.2 from the locked requirements. `make format-check` checks maintained C++ and Arduino sources without editing them; run `make format` only when you intend to format those files. Generated font tables, ST7789 initialization data and the font-generation tool are excluded. Include order is preserved. After the dedicated formatting change is merged, configure blame with `git config blame.ignoreRevsFile .git-blame-ignore-revs` using the final merged commit SHA.

Run `make test-native` for the pure color conversion tests. They exercise shared integer conversion helpers only; they do not model the ESP8266 core, PROGMEM, display timing, heap use or rendering. Use `make docs-examples` to compile the first C++ examples from both READMEs and Sprite guides against the staged library. Use a device for display checks.

| Target | Purpose |
| --- | --- |
| `make build` | Compile all curated examples. |
| `make build-<Name>` | Compile one example, such as `make build-Colour_Test`. |
| `make upload EX=<Name> PORT=<port>` | Upload an example to the board. |
| `make uploadfs EX=<Name> PORT=<port>` | Upload an example's filesystem data. |
| `make monitor PORT=<port>` | Open the serial monitor. |
| `make clean` | Remove generated build files. |
| `make docs-check` | Check documentation pairs, links and removed API references. |
| `make docs` | Run the documentation checks and generate the API reference. |
| `make help` | List available targets. |

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
