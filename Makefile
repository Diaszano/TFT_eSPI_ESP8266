.DEFAULT_GOAL := build
.SECONDEXPANSION:
PATH := $(CURDIR)/.venv/bin:$(PATH)

EXAMPLES := $(notdir $(patsubst %/,%,$(wildcard examples/*/)))
REF_EXAMPLE ?= TFT_Print_Test
CHECK_PROFILE ?= default
SIZE_LABEL ?= current
JOBS ?= $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)
VERSION := $(shell mise exec -- python -c "import json;print(json.load(open('library.json'))['version'])")

.PHONY: build $(addprefix build-,$(EXAMPLES)) upload uploadfs monitor clean help docs-check docs-examples docs-api docs setup lint lint-update check-version size-check warnings compiledb compiledb-native tidy tidy-native cppcheck format format-check test-native test-host test-compile test-hw-build test-hw-preflight test-hw-parse test-hw-compare test-host-extremes sim-build sim-test sim-render sim-diff sim-preview sim-visual-video FORCE

SIMULATOR_BUILD ?= .build/simulator/debug
CMAKE ?= $(shell command -v cmake 2>/dev/null || echo /tmp/plan12-cmake-4.4/cmake/data/bin/cmake)
CTEST ?= $(shell command -v ctest 2>/dev/null || echo /tmp/plan12-cmake-4.4/cmake/data/bin/ctest)

sim-build:
	$(CMAKE) -S simulator -B $(SIMULATOR_BUILD) -DCMAKE_BUILD_TYPE=Debug
	$(CMAKE) --build $(SIMULATOR_BUILD) -j$(JOBS)

sim-test: sim-build
	$(CTEST) --test-dir $(SIMULATOR_BUILD) --output-on-failure
	python3 -m unittest simulator.tests.test_snapshots simulator.tests.test_cli simulator.tests.test_viewer simulator.tests.test_reference_images simulator.tests.test_visual_guide -v
	python3 -m unittest scripts.test_simulator_integration -v

sim-render: sim-build
	@test -n "$(SCENE)" -a -n "$(OUT)" || (echo 'Usage: make sim-render SCENE=<scene> OUT=<directory> [SEED=123]' >&2; exit 2)
	python3 simulator/tools/sim.py render --scene "$(SCENE)" --seed "$(or $(SEED),0)" --out "$(OUT)"

sim-diff:
	@test -n "$(EXPECTED)" -a -n "$(ACTUAL)" || (echo 'Usage: make sim-diff EXPECTED=<run> ACTUAL=<run>' >&2; exit 2)
	python3 simulator/tools/sim.py diff --expected "$(EXPECTED)/frame.rgb565" --actual "$(ACTUAL)/frame.rgb565" --out "$(ACTUAL)"

sim-preview:
	@test -n "$(RUN)" || (echo 'Usage: make sim-preview RUN=<rendered-run-directory>' >&2; exit 2)
	python3 simulator/tools/viewer_server.py --run "$(RUN)"

sim-visual-video: sim-build
	python3 simulator/tools/generate_visual_guide.py --out "$(or $(OUT),.build/simulator/renders)"

format:
	python3 scripts/format.py --write

format-check:
	python3 scripts/format.py --check

test-native:
	pio test -d test -e native

test-host:
	python3 tests/host/run.py

test-compile: .build/pio-library/.stamp
	@cd /tmp && pio ci --lib=$(CURDIR)/.build/pio-library --board=nodemcuv2 -O "platform=espressif8266@4.2.1" --build-dir=$(CURDIR)/.build/compile/sprite_ownership --keep-build-dir $(CURDIR)/tests/compile/sprite_ownership
	@cd /tmp && pio ci --lib=$(CURDIR)/.build/pio-library --board=nodemcuv2 -O "platform=espressif8266@4.2.1" -O "build_flags=-DUSER_SETUP_LOADED -DST7789_DRIVER -DTFT_WIDTH=240 -DTFT_HEIGHT=240 -DTFT_MOSI=13 -DTFT_SCLK=14 -DTFT_DC=0 -DTFT_RST=2 -DSPI_FREQUENCY=40000000 -DLOAD_GLCD" --build-dir=$(CURDIR)/.build/compile/minimal_setup --keep-build-dir $(CURDIR)/tests/compile/minimal_setup
	@cd /tmp && pio ci --lib=$(CURDIR)/.build/pio-library --board=nodemcuv2 -O "platform=espressif8266@4.2.1" --build-dir=$(CURDIR)/.build/compile/firmware_memory --keep-build-dir $(CURDIR)/tests/compile/firmware_memory

test-hw-build: test-compile
	python3 scripts/hw_validation_build.py --build-only

.PHONY: test-hw-perf-offline
test-hw-perf-offline:
	python3 -m unittest scripts.test_hw_perf_protocol scripts.test_hw_perf_capture scripts.test_hw_perf_analysis scripts.test_hw_perf_lab

test-hw-preflight: test-hw-build
	python3 scripts/hw_validation_preflight.py

test-hw-parse:
	@test -n "$(LOG)" || (echo 'Usage: make test-hw-parse LOG=path/to.log' >&2; exit 2)
	python3 scripts/hw_validation_compare.py "$(LOG)"

test-hw-compare:
	@test -n "$(BASELINE)" -a -n "$(CANDIDATE)" || (echo 'Usage: make test-hw-compare BASELINE=approved.json CANDIDATE=log-or-directory' >&2; exit 2)
	python3 scripts/hw_validation_compare.py --baseline "$(BASELINE)" --candidate "$(CANDIDATE)"

test-host-extremes:
	python3 tests/host/run.py --case extreme-coordinates

build: .build/source-inventory.txt
	@mkdir -p "$${PLATFORMIO_CORE_DIR:-$$HOME/.platformio}"
	$(MAKE) --no-print-directory -j$(JOBS) $(EXAMPLES:%=.build/%/.ok)

$(addprefix build-,$(EXAMPLES)): build-%: .build/%/.ok

.build/source-inventory.txt: FORCE scripts/build_inputs.py
	@mkdir -p .build
	@python3 scripts/build_inputs.py library > $@.tmp
	@python3 scripts/build_inputs.py examples >> $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp

.build/pio-library/.stamp: .build/source-inventory.txt
	@rm -rf .build/pio-library
	@mkdir -p .build/pio-library
	@cp -R src User_Setup.h User_Setup_Select.h library.json library.properties .build/pio-library/
	@touch $@

.build/%/.ok: .build/source-inventory.txt .build/pio-library/.stamp $$(wildcard examples/$$*/*.ino)
	@rm -rf .build/$*
	@mkdir -p .build/$*
	@if pio ci --lib=$(CURDIR)/.build/pio-library --board=nodemcuv2 -O "platform=espressif8266@4.2.1" -O "board_build.filesystem=littlefs" --build-dir $(CURDIR)/.build/$* --keep-build-dir examples/$* > .build/$*.log 2>&1; then \
		touch $@; echo "OK $*"; \
	else \
		tail -n 30 .build/$*.log; echo "FAIL $*"; exit 1; \
	fi

ifneq ($(filter upload uploadfs,$(MAKECMDGOALS)),)
ifndef EX
$(error EX=<Nome> required)
endif
endif

upload: .build/$(EX)/.ok
	pio run -d .build/$(EX) -t upload $(if $(PORT),--upload-port $(PORT))

uploadfs:
	PLATFORMIO_DATA_DIR=$(CURDIR)/examples/$(EX)/data pio run -d .build/$(EX) -t uploadfs $(if $(PORT),--upload-port $(PORT))

monitor:
	pio device monitor -b 115200 $(if $(PORT),-p $(PORT))

clean:
	rm -rf .build

docs-check:
	python3 -m unittest -q scripts/test_docs_check.py && python3 scripts/docs_check.py

docs-examples: build-Colour_Test
	python3 scripts/check_docs_examples.py

docs-api:
	@mkdir -p .build
	PROJECT_VERSION=$(VERSION) doxygen Doxyfile

docs: docs-check docs-api

setup:
	mise exec -- uv sync --locked --python "$$(mise which python)"
	command -v gitleaks || brew install gitleaks
	mise exec -- uv run -- pre-commit install --hook-type pre-commit --hook-type commit-msg

lint:
	pre-commit run --all-files
	python3 -m unittest -q scripts/test_ci_config.py
	$(MAKE) check-version

lint-update:
	pre-commit autoupdate --freeze

check-version:
	python3 -m unittest -q scripts/test_check_version.py && python3 scripts/check_version.py

size-check: build-$(REF_EXAMPLE)
	@pio run -d .build/$(REF_EXAMPLE) -e nodemcuv2 -t size > .build/$(REF_EXAMPLE)-size.log
	@python3 scripts/size_check.py --elf .build/$(REF_EXAMPLE)/.pio/build/nodemcuv2/firmware.elf --log .build/$(REF_EXAMPLE)-size.log --build-log .build/$(REF_EXAMPLE).log --profile $(CHECK_PROFILE) --baseline scripts/size-baseline.json --label $(SIZE_LABEL)

warnings: .build/pio-library/.stamp
	python3 scripts/analysis.py warnings --all-examples --flags "-Wall -Wextra" --baseline scripts/warnings-baseline.json

compiledb: build-TFT_Print_Test
	pio run -d .build/TFT_Print_Test -e nodemcuv2 -t compiledb
	python3 scripts/analysis.py prepare --project .build/TFT_Print_Test --scope target

compiledb-native:
	pio run -d test -e analysis-native -t compiledb
	python3 scripts/analysis.py prepare --project test --scope native

tidy: compiledb
	python3 scripts/analysis.py tidy --scope target

tidy-native: compiledb-native
	python3 scripts/analysis.py tidy --scope native --baseline scripts/analysis-native-baseline.json

cppcheck: build-TFT_Print_Test
	python3 scripts/analysis.py cppcheck --project .build/TFT_Print_Test

help:
	@printf '%s\n' 'test-hw-build: compile validation sketch only' 'test-hw-preflight: report firmware checksum/profile; no device access' 'test-hw-parse LOG=<path>: parse a saved serial log' 'test-hw-compare BASELINE=<json> CANDIDATE=<log-or-dir>: compare approved runs' 'test-host-extremes: run bounded coordinate safety cases'
	@printf '%s\n' 'sim-build: build native graphics simulator with sanitizers' 'sim-test: run headless native and Python simulator tests' 'sim-render SCENE=<id> OUT=<dir>: render a deterministic simulator scene' 'sim-diff EXPECTED=<dir> ACTUAL=<dir>: compare approved frame artifacts' 'sim-preview RUN=<dir>: start localhost read-only viewer (Ctrl+C to stop)' 'sim-visual-video [OUT=<dir>]: generate and verify S1-S4 validation-guide.mp4'
	@printf '%s\n' 'build: compile all curated examples' 'build-<Nome>: compile one example' 'upload EX=<Nome> [PORT=<port>]: upload one example' 'uploadfs EX=<Nome> [PORT=<port>]: upload example filesystem' 'monitor [PORT=<port>]: open serial monitor' 'clean: remove build files' 'warnings: compare owned compiler warnings across all examples' 'compiledb: prepare the target clang-tidy database' 'compiledb-native: prepare the native pure-logic database' 'tidy: run the target clang-tidy parsing pilot' 'tidy-native: analyze pure color helpers on native' 'cppcheck: run the optional PlatformIO cppcheck pilot' 'test-host: run source-extracted ASan/UBSan host regressions' 'docs-check: validate documentation pairs, links and removed APIs' 'docs-examples: compile README and Sprite guide examples' 'docs-api: generate the Doxygen API reference' 'docs: validate docs and generate the API reference' 'setup: install lint tools and hooks' 'lint: run pre-commit checks and version check' 'lint-update: update pre-commit hook revisions' 'check-version: verify package versions' 'help: show this help'

.PHONY: build-arduino layout-check package-check test-python

build-arduino:
	python3 scripts/arduino_build.py

layout-check: compiledb
	python3 scripts/layout_check.py --root . --project .build/TFT_Print_Test

package-check:
	@mkdir -p .build
	pio pkg pack -o .build/library.tar.gz
	python3 scripts/package_check.py .build/library.tar.gz

test-python:
	python3 -m unittest discover -s scripts -p 'test_*.py' -v
