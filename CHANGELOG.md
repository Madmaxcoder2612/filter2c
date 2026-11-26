# Changelog

This project follows [Semantic Versioning](https://semver.org/). While the version is 0.x, the API may still change.

## Unreleased

- `filter2c target-sketch`: writes an ESP32 sketch that runs the filter on the board and prints the result and the time per sample.
- `filter2c check-board-log`: compares the board's printed output with SciPy and with the PC build.
- Example `ESP32SelfTest`.
- First real hardware result: ESP32-S3 at 240 MHz matches SciPy to 2.8e-06 of the peak, 43 cycles per sample (`results/esp32-s3-board-log.txt`).

## 0.1.0 (unreleased)

- Butterworth low-pass design (order 1 to 16) as second-order sections, using SciPy.
- C header generator and a header-only biquad runtime (Direct Form II Transposed, float).
- Verification: stability after rounding to float, and a compile-and-compare check against SciPy.
- Command line tool `filter2c butter-lowpass`.
- Arduino library layout and the `Butterworth40Hz` example.
