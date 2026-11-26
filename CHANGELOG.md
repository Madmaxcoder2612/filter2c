# Changelog

This project follows [Semantic Versioning](https://semver.org/). While the version is 0.x, the API may still change.

## Unreleased

- Notch filter (`filter2c notch`, `filter2c.notch`) for removing a single frequency such as 50 Hz mains hum.
- Verification for notch filters: attenuation of a pure tone at the notch frequency, measured on the compiled C code.
- Example `HumNotch50Hz`, tried live on an ESP32-S3: the 50 Hz component drops by about 36 dB (read from a screenshot, approximate); the 100 and 150 Hz harmonics stay.
- `target-sketch` now takes the filter type: `target-sketch butter-lowpass ...` or `target-sketch notch ...`. The notch self-test signal contains a tone at the notch frequency.

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
