# filter2c

Design digital filters in Python with SciPy, and get C code that runs the same filter on a microcontroller, together with proof that the C code does what the design says.

The code generation is the easy part. The point of this project is the **check**: the generated code is compiled, run on a test signal and compared with SciPy, and the tool tells you when 32-bit float is not precise enough for your filter.

> **Early alpha.** Tested on one ESP32-S3 board. Do not use the output in a safety-relevant system without your own verification. The full list of results and limitations is in the [project README on GitHub](https://github.com/Madmaxcoder2612/filter2c#readme).

## Install

```bash
pip install filter2c
```

Needs Python 3.10 or newer. For `--verify` you also need a C compiler (gcc or clang).

## Use it

Make an ECG band-pass filter (0.5 to 40 Hz at 250 Hz sampling), write the C header and check it:

```bash
filter2c butter-bandpass --order 2 --low 0.5 --high 40 --fs 250 --name ecg -o ecg.h --write-runtime --verify
```

Other filters: `butter-lowpass`, `butter-highpass` and `notch` (for example to remove 50 Hz mains hum).

From Python:

```python
from filter2c import butterworth_lowpass, notch, generate_header

design = butterworth_lowpass(order=4, cutoff_hz=40, fs_hz=1000)
header_text = generate_header(design, "lp40")
hum_filter = notch(freq_hz=50, q=30, fs_hz=1000)
```

On the microcontroller, add the two generated headers to your project:

```c
#include "lp40.h"

filter2c_reset(&lp40);                  /* once, before the first sample */
float y = filter2c_process(&lp40, x);   /* once per sample, at exactly 1000 Hz */
```

## What it checks

- The filter stays stable after its coefficients are rounded to 32-bit float.
- The compiled C code matches SciPy on a test signal. For a notch filter it also measures how much of a tone at the notch frequency is removed.
- On a real ESP32 board, `filter2c target-sketch` writes a sketch that runs the filter on the board, and `filter2c check-board-log` checks what the board printed. `--live` does the same with the board's own analog input and one jumper wire.

## Links

- Project page with results, figures and the Arduino library: <https://github.com/Madmaxcoder2612/filter2c>
- Changelog: <https://github.com/Madmaxcoder2612/filter2c/blob/main/CHANGELOG.md>
- Licence: MIT
