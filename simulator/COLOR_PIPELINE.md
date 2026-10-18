# ST7789 color pipeline and physical check

The graphics API takes logical RGB565 values: red `F800`, green `07E0`, blue
`001F`, cyan `07FF`, magenta `F81F`, yellow `FFE0`, white `FFFF`, black `0000`.
`fillRect`, text, and sprite paths use those values. RAMWR sends the high byte
first (`F8 00` for red). `setSwapBytes(true)` changes the order used to read a
host `uint16_t` image; it does not exchange red and blue channels. S2 needs
that setting and restores its previous value.

The 240×240 setup selects MADCTL `0x08` (BGR) and COLMOD `0x55` (16-bit pixels).
The controller's raw GRAM stores the received word, so red remains `F800` in
`raw_gram_pixel()`. MADCTL bit 3 changes the controller's color output order.
The NodeMCU virtual profile assumes BGR color filters on the attached glass,
matching the setup's BGR selection. Those two order choices cancel at the
display-facing boundary: `visible_pixel()` returns logical RGB565. The test
profile assumes RGB filters, so its BGR MADCTL setting swaps red and blue.
This distinction lets controller tests exercise both MADCTL states without
mislabeling the exported 240×240 frame.

The simulator writes `frame.rgb565` in row-major, **little-endian** canonical
RGB565. `frame.png` expands each channel to RGB888 once. The annotated PNG and
video scale that PNG; H.264 `yuv420p` adds small lossy changes. The MP4 is a
visual guide, never a pixel-exact reference or evidence of panel behavior.

The [ST7789V datasheet](https://dl.espressif.com/dl/schematics/ST7789V_SPEC_V1.0.pdf)
defines MADCTL bit 3 as RGB (`0`) or BGR (`1`) order. It cannot establish the
color-filter order of this particular glass. The simulator's BGR-filter profile
is therefore a configuration assumption, not a measured physical result.

## Operator check

1. Upload the current validation firmware using the normal operator workflow.
   No firmware rebuild is required by this simulator-only correction; use a
   current build if the device has older firmware.
2. Run the existing `Colour_Test` example or a firmware screen with isolated
   `TFT_RED`, `TFT_GREEN`, `TFT_BLUE`, `TFT_CYAN`, `TFT_YELLOW`, white, and black
   regions. Record whether the **red** region looks red and the **blue** region
   looks blue. Photograph the panel with the color labels visible.
3. If red and blue are exchanged, record the observation and compare the same
   test with the documented `TFT_RGB_ORDER` setting. Do not infer physical
   parity from the simulator or MP4 alone.

Physical color fidelity remains **INCONCLUSIVE** until step 2 is observed.
The Font 4 independent golden remains **NO_BASELINE**.
