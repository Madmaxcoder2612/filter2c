"""filter2c: design digital filters with SciPy and generate verified C code."""

__version__ = "0.1.0"

from .codegen import generate_header, runtime_header  # noqa: E402
from .design import (  # noqa: E402
    FilterDesign,
    butterworth_bandpass,
    butterworth_highpass,
    butterworth_lowpass,
    notch,
)

__all__ = [
    "FilterDesign",
    "butterworth_bandpass",
    "butterworth_highpass",
    "butterworth_lowpass",
    "notch",
    "generate_header",
    "runtime_header",
    "__version__",
]
