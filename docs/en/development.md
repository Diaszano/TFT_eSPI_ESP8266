English | [Português (Brasil)](https://github.com/Diaszano/TFT_eSPI_ESP8266/blob/main/docs/pt-BR/development.md)

# Development

## Make targets

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

## Add an example

Create `examples/<Name>/<Name>.ino` with no spaces in `<Name>`. Keep example-specific data inside that directory and ensure the sketch builds with the supported setup. Run `make build-<Name>` before submitting, then `make build` to check the complete curated set.

## Documentation changes

Write the English file in `docs/en/` first, add its same-named pt-BR translation in `docs/pt-BR/`, and update the matching README if needed. Run `make docs` to check links and language pairs and generate Doxygen HTML.

The Pages workflow uses Doxygen 1.18.0. Install the same version locally so generated warnings match CI; the workflow downloads the official Linux binary for the pinned `DOXYGEN_VERSION`.
