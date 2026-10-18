# S1–S4 color comparison

The old MP4 discrepancy was reproduced in its lossless source. The virtual
controller held SPI red `F8 00` as raw GRAM `F800`, but `visible_pixel()`
exposed `001F` under MADCTL `08`. The old `frame.rgb565` and PNG therefore
contained blue at a location labeled red. The video faithfully encoded that
PNG. The same path changed cyan `07FF` to yellow `FFE0`. This was a simulator
panel-presentation error for the configured BGR-filter profile, with an oracle
that repeated the error. Physical filter order remains to be observed.

| Scene and pixel | Intended API RGB565 | Old raw/PNG | New raw RGB565 | New PNG RGB888 | Decoded MP4 RGB888 |
| --- | ---: | --- | ---: | --- | --- |
| S1 cyan rectangle `(5,5)` | `07FF` | `FFE0` / yellow | `07FF` | `0,255,255` | `0,255,255` |
| S1 red H-line `(50,24)` | `F800` | `001F` / blue | `F800` | `255,0,0` | `247,1,2` |
| S1 blue V-line `(24,50)` | `001F` | `F800` / red | `001F` | `0,0,255` | `0,0,254` |
| S2 red checker `(0,40)` | `F800` | `001F` / blue | `F800` | `255,0,0` | `234,9,0` |
| S2 green checker `(1,40)` | `07E0` | `07E0` / green | `07E0` | `0,255,0` | `15,246,2` |
| S3 cyan pivot `(35,71)` | `07FF` | `FFE0` / yellow | `07FF` | `0,255,255` | `0,255,255` |
| S4 red stripe `(8,48)` | `F800` | `001F` / blue | `F800` | `255,0,0` | `255,0,0` |
| S4 blue stripe `(16,48)` | `001F` | `F800` / red | `001F` | `0,0,255` | `0,0,255` |

The MP4 samples come from FFmpeg-decoded scene frames at the center of the
4× display pixels. Their small differences from the source are H.264 chroma
and quantization effects. Source PNG and raw values agree exactly. S1–S4
geometry, clipping, sprite rotation, font 1/2, color probes, deterministic
generation, and annotation placement are checked by the simulator suite.
Font 4 independent golden approval and real panel color fidelity remain open.
