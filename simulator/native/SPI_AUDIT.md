# SPI transport audit — ESP8266 ST7789 profile

Scope: production sources at `78a58c91` (Plan 07 worktree base), profile in
`User_Setup.h` (ST7789, 240×240, ESP8266 hardware SPI). This is an inventory,
not evidence that a host seam exists yet. The later transport implementation
must intercept every row marked `host requirement` or fail closed.

## Direct ESP8266 registers

| Register | Production use | Classification for host seam |
| --- | --- | --- |
| `SPI1U` | `TFT_eSPI.h:94,96`; switch bus write/read mode | Intercept configuration; reads are unsupported and must raise structured error |
| `SPI1U1` | `TFT_eSPI.h:201,210,219,225,234,243,252`; `TFT_eSPI.cpp:63,94,110,131,160,186,223`; transfer bit lengths | Intercept transfer width; validate supported byte-aligned lengths |
| `SPI1CMD` | header write macros and `TFT_eSPI.cpp` fast paths; starts transfer and polls `SPIBUSY` | Intercept start/poll; preserve order and reject nested/incomplete transfer |
| `SPI1W0` | scalar macros, first word of burst paths, receive register | Intercept outgoing words; receive/read access is unsupported |
| `SPI1W1` | `TFT_eSPI.cpp:72,142,161,200`; wide color/pixel bursts | Intercept in register order |
| `SPI1W2` | `TFT_eSPI.cpp:73,143,162,201`; wide color/pixel bursts | Intercept in register order |
| `SPI1W3` | `TFT_eSPI.cpp:74,144,163,202`; wide color/pixel bursts | Intercept in register order |
| `SPI1W4` | `TFT_eSPI.cpp:76,145,164,203`; wide color/pixel bursts | Intercept in register order |
| `SPI1W5` | `TFT_eSPI.cpp:77,146,165,204`; wide color/pixel bursts | Intercept in register order |
| `SPI1W6` | `TFT_eSPI.cpp:78,147,166,205`; wide color/pixel bursts | Intercept in register order |
| `SPI1W7` | `TFT_eSPI.cpp:79,148,167,206`; wide color/pixel bursts | Intercept in register order |
| `SPI1W8` | `TFT_eSPI.cpp:82`; `pushBlock` 512-bit burst | Intercept in register order |
| `SPI1W9` | `TFT_eSPI.cpp:83`; `pushBlock` 512-bit burst | Intercept in register order |
| `SPI1W10` | `TFT_eSPI.cpp:84`; `pushBlock` 512-bit burst | Intercept in register order |
| `SPI1W11` | `TFT_eSPI.cpp:85`; `pushBlock` 512-bit burst | Intercept in register order |
| `SPI1W12` | `TFT_eSPI.cpp:88`; `pushBlock` 512-bit burst | Intercept in register order |
| `SPI1W13` | `TFT_eSPI.cpp:89`; `pushBlock` 512-bit burst | Intercept in register order |
| `SPI1W14` | `TFT_eSPI.cpp:90`; `pushBlock` 512-bit burst | Intercept in register order |
| `SPI1W15` | `TFT_eSPI.cpp:91`; `pushBlock` 512-bit burst | Intercept in register order |

## API and control paths

| Path | Production location / role | Classification for host seam |
| --- | --- | --- |
| `tft_Write_8`, `tft_Write_16`, `tft_Write_16N`, `tft_Write_16S`, `tft_Write_32`, `tft_Write_32C`, `tft_Write_32D` | `TFT_eSPI.h:200–255`; command, scalar data, byte-swapped range/pixel words | Intercepted individually; retain exact byte order and blocking/nonblocking semantics |
| `DC_C`, `DC_D` | `TFT_eSPI.h:124–134`; command/data selection (no-op on profiles without DC) | Map to D/C event; no-op only when profile says no physical pin |
| `CS_L`, `CS_H`, `T_CS_L`, `T_CS_H` | `TFT_eSPI.h:143–166`; TFT/touch chip select | Track TFT CS; touch CS is outside this display simulator and must fail if used |
| `pushBlock` | `TFT_eSPI.cpp:53–112`; repeated color via macros and direct `SPI1W0`–`W15` burst | Intercept scalar and wide burst paths, including final odd pixel |
| `pushPixels` | `TFT_eSPI.cpp:121–174`; native 16-bit pixel arrays in 8-word batches | Intercept all words and partial tail |
| `pushSwapBytePixels` | `TFT_eSPI.cpp:180–237`; byte-swapped pixel arrays in 8-word batches | Intercept all words and partial tail |
| `setWindow` | `TFT_eSPI.cpp:3099–3113`; CASET/PASET/RAMWR sequence | Observe only the bytes emitted by production code; controller semantics belong to Plan 08 |
| `writecommand`, `writedata` | `TFT_eSPI.cpp:1009–1066` and init headers | Observe D/C and output bytes; unsupported reads fail explicitly |
| `startWrite`, `endWrite` | public transaction API and internal drawing paths | Preserve transaction nesting/order; no implicit pixel inference |
| direct SPI reads / `SPI1W0` receive | `TFT_eSPI.cpp` readback helpers and `TFT_eSPI.h` read macros | Unsupported in initial host profile; deterministic `UNSUPPORTED_READ`, never return fabricated data |
| `TFT_eSprite::setWindow` | `src/internal/Sprite.inc:1156+`; memory-only sprite window | No SPI itself; delegated push operations reach `_tft` transport |

## Required coverage before D0

- Commands and D/C data through every `tft_Write_*` macro.
- Burst writes through all direct registers, including `pushBlock`, `pushPixels`
  and `pushSwapBytePixels`, with full and partial batches.
- CS and transaction boundaries, clipping-generated windows, and no hidden
  direct `SPI1*` access outside this table.
- Unsupported controller reads and touch SPI produce explicit structured
  errors. Reset/rotation init writes are captured; controller interpretation
  is deferred to Plan 08.
- This inventory is not a claim that the existing transport has been tested;
  it is the fail-closed checklist for the simulator seam.
