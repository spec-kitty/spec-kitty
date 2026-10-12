# Quickstart: running the acceptance-jvm scenarios locally

> The runner is **nightly-only in CI** (no per-PR JDK cost). This is how a maintainer runs it by
> hand. It is a black box: it builds the wheel, installs it into a throwaway venv, and drives the
> `spec-kitty` CLI as an external process — it never imports Python.

## Prerequisites

- **JDK 25** on `PATH` (the version the nightly uses; mirrors the `contracts/` toolchain bumped to 25).
- **Python + `uv`** (to build the wheel under test).
- The **pinned Gradle** — installed the same way CI does, via the shared installer:

  ```bash
  python contracts/tools/install_tools.py \
    --pins acceptance-jvm/tools/pins.json \
    --dest "$PWD/.tooltmp" --only gradle
  export PATH="$PWD/.tooltmp/gradle/bin:$PATH"   # install_tools appends this in CI via $GITHUB_PATH
  ```

  The installer refuses to unpack Gradle unless the downloaded bytes match the pinned sha256.

## Run the scenarios

```bash
cd acceptance-jvm

# Gating set (what the nightly gates on): everything that is not @wip and not @manual
gradle test --no-daemon -Dcucumber.filter.tags="not @wip and not @manual"

# The @wip set (the nightly's separate, non-gating run)
gradle test --no-daemon -Dcucumber.filter.tags="@wip"
```

The build builds the wheel (`uv build`) and installs it into a temp venv itself; you do not install
`spec-kitty` globally. Each scenario gets its own temp git repo and a fully redirected environment,
so a run never touches your real `~/.spec-kitty` or `$HOME`.

## Results

After a run, results are under `acceptance-jvm/build/`:

- Cucumber JSON + JUnit XML (consumed by the nightly upload),
- Allure results (`allure-cucumber7-jvm`), uploaded for the spec-kitty-qa acceptance nightly.

## Regenerating the dependency verification metadata

When JVM dependencies change, regenerate (never hand-edit) the pinned metadata:

```bash
cd acceptance-jvm
gradle --write-verification-metadata sha256 test --no-daemon
```

Commit the regenerated `acceptance-jvm/gradle/verification-metadata.xml`. The shared
`contracts/tools/gradle_pin_check.py` (generalized by this mission) cross-checks that the Gradle
version used by the build, the metadata, and the nightly workflow all match `acceptance-jvm/tools/pins.json`
— a mismatch fails `GRADLE_PIN_MISMATCH`.

## Adding a scenario

1. Add a `.feature` under `tests/scenarios/<area>/`.
2. Bind any new steps through the `SpecKittyDriver` port (never import Python; never call internal Java).
3. Leave it **bound + untagged** to run in the gating nightly, or tag `@manual` for a heavy/on-demand
   scenario (excluded from the gating run), or `@wip` while its steps are incomplete.
4. The new `tests/scenarios/**` path must be git-tracked (the ci-router `scenarios` glob asserts live paths).
