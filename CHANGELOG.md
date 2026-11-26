# Changelog

This project follows [Semantic Versioning](https://semver.org/). While the version is 0.x, the API may still change.

## Unreleased

- Live check with the board's own analog input: `filter2c target-sketch ... --live` and `filter2c check-live-log`, example `LiveCheck40Hz`. First real run on an ESP32-S3 (GPIO2 wired to GPIO1): sample period 1000.0 us with 0.7 us spread, and the filter output equals SciPy on the real readings (2.66e-06 of the peak). Figure drawn from the log by `tools/plot_live_log.py`.
- Fix: `Butterworth40Hz` was missing its own copy of `filter2c.h` and only compiled with the library installed. Every example now carries the header, a test checks it, and the CI builds the examples without the library installed. The example now prints at 921600 baud, because 115200 baud cannot carry 1000 lines per second.

- Real ESP32-S3 results for all four filter types (low-pass, high-pass, ECG band-pass, notch), with the logs in `results/` and tests that check them. Sketches `ESP32SelfTestHighpass`, `ESP32SelfTestEcg` and `ESP32SelfTestNotch`.

- Butterworth high-pass and band-pass (`filter2c butter-highpass`, `filter2c butter-bandpass`, `filter2c.butterworth_highpass`, `filter2c.butterworth_bandpass`), also for `target-sketch`. Checked against SciPy's frequency response and, for the high-pass, against the closed-form gain. The 0.5 to 40 Hz ECG band passes in float32 at 250 and 500 Hz sampling and fails at 1 kHz, which the tool reports.

- CI builds the examples with `arduino-cli` for the ESP32-S3 and the Arduino UNO R4 WiFi, and checks the library with `arduino-lint`. The three examples were also compiled locally for the ESP32-S3.
- `HumNotch50Hz` uses `Serial.print` and picks the analog pin by board, so it builds on boards without `Serial.printf`. Re-run on the ESP32-S3: same result.

- Notch filter (`filter2c notch`, `filter2c.notch`) for removing a single frequency such as 50 Hz mains hum.
- Verification for notch filters: attenuation of a pure tone at the notch frequency, measured on the compiled C code.
- Screen recording (GIF) of the live hum demo in the README.
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
