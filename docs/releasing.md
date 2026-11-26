# Releasing filter2c

A release puts one version on PyPI (`pip install filter2c`), on GitHub (a release with the changelog text) and on the Arduino Library Manager. This page is the checklist. Do the one-time setup first, then follow the steps for every release.

## One-time setup (the repository owner)

1. **PyPI and TestPyPI accounts** with two-factor authentication.
2. **Trusted publishing**, so that no password or token is stored anywhere. On each site, add a *pending publisher* for the project name `filter2c`:

   | Field | PyPI | TestPyPI |
   |---|---|---|
   | Owner | `Madmaxcoder2612` | `Madmaxcoder2612` |
   | Repository | `filter2c` | `filter2c` |
   | Workflow file | `release.yml` | `release.yml` |
   | Environment | `pypi` | `testpypi` |

3. **GitHub environments** (repository Settings > Environments): create `pypi` and `testpypi`. On `pypi`, add the owner as a *required reviewer*. Then every real release waits for one explicit approval, even after the tag is pushed.

## Version numbers

The project uses [semantic versioning](https://semver.org/): `0.x.y` while the API may still change, `MAJOR.MINOR.PATCH` after that. The number lives in four places, and a test (`test_release.py`) fails if they disagree. It also appears in every generated example. Do not edit them by hand:

```bash
python tools/bump_version.py 0.2.0
```

This changes the four files, copies the runtime header to the Python package and regenerates the examples. Afterwards add a `## 0.2.0` section to `CHANGELOG.md` (and change "not yet released" in the old one to a date).

## Steps for every release

1. **Main is green.** The latest CI run on `main` passed.
2. **Bump and write the changelog** as above, run `python -m pytest`, and commit "Release X.Y.Z".
3. **Dry run on TestPyPI.** In GitHub: Actions > Release > Run workflow > target `testpypi`. Then, in a clean environment:

   ```bash
   pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple filter2c==X.Y.Z
   filter2c --version
   filter2c butter-lowpass --order 4 --cutoff 40 --fs 1000 --name lp40 -o lp40.h --write-runtime --verify
   ```

4. **Tag.** The workflow refuses a tag that does not match the version in `pyproject.toml` or has no changelog section:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   The workflow builds the package, installs the built wheel in a clean environment and runs it, then waits for approval of the `pypi` environment. After approval it publishes to PyPI and creates the GitHub release with the changelog text.
5. **Check the result:** the project page on pypi.org, and `pip install filter2c` in a clean environment.
6. **Arduino Library Manager.** The first time, the library is added by a pull request to Arduino's `library-registry` repository (add the repository URL to its list; follow the instructions in that repository, which may change). Its checks run `arduino-lint` and verify that the name is free. After that, new versions are picked up from the git tags of the repository, with the version taken from `library.properties`. The CI already runs the same `arduino-lint` check on every push.
7. **After the release:** update the install section and badges in `README.md`.

## Rules

- **Never reuse a version number.** PyPI refuses a second upload of the same version, even after a delete. If something is wrong, release the next patch version. A bad release can be *yanked* on PyPI, which hides it from new installs.
- **A release contains only checked work.** Every claim in the README is backed by a test or a saved log in `results/`. Anything that has not been run on hardware is listed under Limitations.
- **Everything is original work.** See [CONTRIBUTING.md](../CONTRIBUTING.md) and [NOTICE.md](../NOTICE.md).
