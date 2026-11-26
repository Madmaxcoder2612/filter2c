# Changelog

This project follows [Semantic Versioning](https://semver.org/). While the version is 0.x, the API may still change.

## 0.1.0 (unreleased)

- Butterworth low-pass design (order 1 to 16) as second-order sections, using SciPy.
- C header generator and a header-only biquad runtime (Direct Form II Transposed, float).
- Verification: stability after rounding to float, and a compile-and-compare check against SciPy.
- Command line tool `filter2c butter-lowpass`.
- Arduino library layout and the `Butterworth40Hz` example.
