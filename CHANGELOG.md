# Changelog

This project follows [Semantic Versioning](https://semver.org/). While the version is 0.x, the API may still change.

## 0.1.0 (2026-11-26)

First public version.

### Filters

- Butterworth low-pass, high-pass and band-pass, and a notch filter, designed with SciPy as second-order sections (`filter2c.butterworth_lowpass`, `butterworth_highpass`, `butterworth_bandpass`, `notch`).
- C header generator and a header-only biquad runtime (Direct Form II Transposed, 32-bit float) that works in C99, C++ and Arduino sketches. No dynamic memory, no dependencies.
- Command line tool: `filter2c butter-lowpass`, `butter-highpass`, `butter-bandpass`, `notch`.

### Verification

- Stability check after rounding the coefficients to float.
- `--verify`: the generated header is compiled with a C compiler and compared with SciPy on a test signal. Failures come with a hint when 32-bit float is not precise enough, for example the 0.5 to 40 Hz ECG band at 1 kHz sampling.
- Notch filters: the attenuation of a pure tone at the notch frequency is measured on the compiled C code.
- Tests compare the compiled C code with closed-form Butterworth gains, which are independent of SciPy, and check that a wrong coefficient is caught.

### Checks on a real board

- `filter2c target-sketch <filter>`: writes an ESP32 sketch that runs the filter on a built-in test signal and prints the result and the time per sample. `filter2c check-board-log` compares the board's output with SciPy and with the PC build.
- `filter2c target-sketch <filter> --live` and `filter2c check-live-log`: a live check with the board's own analog input and one jumper wire. It checks the real sample rate, that the input changed, and that the filter output equals SciPy on the real readings.
- Real ESP32-S3 results (240 MHz) for all four filter types, with the logs in `results/` and tests that check them: errors from 2.8e-06 to 6.9e-05 of the output peak, 26 to 46 clock cycles per sample. The live check measured a sample period of 1000.0 us with 0.7 us spread.

### Examples

- `Butterworth40Hz`, `HumNotch50Hz` (removes 50 Hz mains hum from a bare wire on an analog pin), `LiveCheck40Hz`, and the self-test sketches `ESP32SelfTest`, `ESP32SelfTestHighpass`, `ESP32SelfTestEcg` and `ESP32SelfTestNotch`. Every example folder carries its own copy of `filter2c.h`, and a test checks this.

### Continuous integration

- Python tests on 3.10 and 3.12, the generated examples are checked for being up to date, all examples are built with `arduino-cli` for the ESP32-S3 (the two portable ones also for the UNO R4 WiFi) without the library installed, and the library is checked with `arduino-lint`.

### Known limitations

- 32-bit float only. Double precision and fixed-point output are planned.
- Tested on one board, an ESP32-S3. The UNO R4 and a classic ESP32 have not been run.
- Not tested on real ECG data.
