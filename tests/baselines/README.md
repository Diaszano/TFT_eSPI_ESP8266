# Hardware benchmark baselines

Only human-reviewed captures from real devices belong here. Synthetic fixtures
are tests and must never be listed as performance evidence.

A baseline revision and a candidate each need at least five independent boots
with matching board, display driver and dimensions, rotation, CPU frequency,
SPI frequency, Wi-Fi state, and build flags. Keep the raw serial log for each
boot with its SHA and run ID. Do not commit a baseline while any required
scenario or round is missing. `REGRESSION_CANDIDATE` is a review signal, not an
automatic release failure.
