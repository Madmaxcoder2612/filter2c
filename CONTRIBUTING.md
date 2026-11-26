# Contributing

Thanks for looking at filter2c. This is an early alpha, and bug reports, questions and results from other boards are very welcome.

## Run the tests

```bash
python -m pip install -e "python[test]"
python -m pytest
```

You need a C compiler (gcc or clang) for most of the tests, because they compile the generated code and compare it with SciPy.

## Please keep the work original

This project only contains work that its authors wrote themselves, so that its licence is clean. When you contribute:

- Write code, tests and documentation yourself. Do not copy, port or closely paraphrase code from other projects, whatever their licence. Ideas and mathematics are free to use. Source code is not.
- Do not add images, fonts, datasets or text that you did not make or that do not have a clear permissive licence. If you use a library, list its licence in [NOTICE.md](NOTICE.md).
- State how you made a figure or a measurement.

## Adding a filter or a feature

1. Add the design to `python/src/filter2c/design.py` with input checks.
2. Add tests that check the compiled C code against SciPy **and** against something independent of SciPy, such as a closed-form gain.
3. If the filter has a typical use, add a board self-test (`filter2c target-sketch`) and say in the README whether it has been run on a real board. Never claim hardware results that were not measured.
4. Update `README.md` (including limitations) and `CHANGELOG.md`.

## Changing generated files

The files in `examples/` are written by the tool and contain its version number. After changing the tool, run `python tools/regenerate_examples.py`. The tests fail if the committed examples differ from what the tool writes today. `src/filter2c.h` must be identical to `python/src/filter2c/runtime/filter2c.h` and to the copy in every example folder, which the same script takes care of.

## Reporting results from your board

An issue with the output of `filter2c check-board-log` or `filter2c check-live-log` and the name of your board is the most useful thing you can send. Please say which Arduino core version you used.
