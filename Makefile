.DEFAULT_GOAL := build
.SECONDEXPANSION:

EXAMPLES := $(notdir $(patsubst %/,%,$(wildcard examples/*/)))
JOBS ?= $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)
PIO_CI_FLAGS = --lib=. --board=nodemcuv2 -O "lib_deps=bitbank2/PNGdec" -O "board_build.filesystem=littlefs"
LIB_SRC = $(wildcard TFT_eSPI.* User_Setup*.h TFT_Drivers/* Extensions/* Fonts/*.h User_Setups/*)

.PHONY: build $(addprefix build-,$(EXAMPLES)) upload uploadfs monitor clean help

build:
	$(MAKE) --no-print-directory -j$(JOBS) $(EXAMPLES:%=.build/%/.ok)

$(addprefix build-,$(EXAMPLES)): build-%: .build/%/.ok

.build/pio-library/.stamp: $(LIB_SRC) $(wildcard Fonts/*.c Fonts/GFXFF/*.h) library.json library.properties
	@rm -rf .build/pio-library
	@mkdir -p .build/pio-library
	@cp -R TFT_eSPI.* User_Setup*.h TFT_Drivers Extensions Fonts User_Setups library.json library.properties .build/pio-library/
	@touch $@

.build/%/.ok: $(LIB_SRC) .build/pio-library/.stamp $$(wildcard examples/$$*/*.ino)
	@rm -rf .build/$*
	@mkdir -p .build/$*
	@if pio ci --lib=$(CURDIR)/.build/pio-library --board=nodemcuv2 -O "lib_deps=bitbank2/PNGdec" -O "board_build.filesystem=littlefs" --build-dir $(CURDIR)/.build/$* --keep-build-dir examples/$* > .build/$*.log 2>&1; then \
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

help:
	@printf '%s\n' 'build: compile all curated examples' 'build-<Nome>: compile one example' 'upload EX=<Nome> [PORT=<port>]: upload one example' 'uploadfs EX=<Nome> [PORT=<port>]: upload example filesystem' 'monitor [PORT=<port>]: open serial monitor' 'clean: remove build files' 'help: show this help'
