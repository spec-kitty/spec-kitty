# Data Model: CLI Acceptance Scenarios & Cucumber-JVM Nightly

This mission has no persistent data store. The "entities" below are the conceptual objects the
runner and the scenario corpus are built from — their fields, invariants, and (where relevant)
lifecycle — so the implementation and review share one vocabulary.

## Entity: Scenario

A Gherkin description of a promised CLI behaviour.

- **Location**: `tests/scenarios/<area>/<name>.feature` (seed area: `init`).
- **Fields**: `area` (directory, e.g. `init`); `name`; Gherkin `Feature`/`Scenario`/steps; optional `tags`.
- **Invariants**:
  - A scenario drives the CLI **only** through step bindings that call the `SpecKittyDriver` port — never Python imports, never internal Java (C-001).
  - A bound, untagged scenario runs in the gating nightly; the two seed scenarios are of this kind.
- **Relationships**: executed by the **Runner**; may carry one or more **Tag**s.

## Entity: Tag

An annotation on a Scenario.

- **Allowed**: `@promise:<id>`, `@wip` (+ `@wip-owner:<handle>`, `@wip-since:<YYYY-MM-DD>`), `@defect:<issue>`, `@qa:SC-A-NNN`, `@manual`.
- **Meaning in core**: only `@wip` and `@manual` have effect — each **excludes** the scenario from the gating nightly run. `@promise`/`@defect`/`@qa` are inert in core (C-003, FR-014); spec-kitty-qa attaches meaning to them.
- **Invariant**: no core check (per-PR or nightly) reads a promise index or validates `@promise` ids — that machinery is out of core scope.

## Entity: SpecKittyDriver (port)

The only seam a step is allowed to use.

- **Operations**: run a CLI command and return `{ exit_code, stdout, stderr, parsed_json (for --json), working_tree }`.
- **Invariant**: steps depend on this interface, not on any concrete process mechanics.

## Entity: CliProcessDriver (implementation of SpecKittyDriver)

- **Fields/behaviour**: `ProcessBuilder` invocation; drained stdout/stderr; a timeout; descendant processes killed on exit/timeout; line endings normalised (CRLF↔LF); paths compared via real/canonical path.
- **Invariant**: the CLI it invokes is the **wheel under test** installed in the temp venv — never PyPI, never an editable install (C-002).

## Entity: Isolated Scenario Environment

Created fresh per scenario; destroyed after.

- **Fields**: a temporary directory containing a freshly `git init`-ed repo (the *harness's* repo, so a scenario can observe git state); env vars `SPEC_KITTY_HOME`, `HOME`, `USERPROFILE`, the XDG dirs and `LOCALAPPDATA` all redirected **inside** the temp dir; `LANG`/`LC_ALL` = UTF-8; `NO_COLOR=1`; `COLUMNS` fixed.
- **Invariant (NFR-002)**: a scenario performs 0 reads/writes to the real `HOME`/`SPEC_KITTY_HOME`/global state. Positive control: the run observably writes inside the temp dir.
- **Note**: the harness `git init` is the test fixture; the *behaviour under test* (FR-004) is that `spec-kitty init` itself never creates a repo or a commit — asserted against the unchanged harness-repo HEAD/commit-count.

## Entity: CLI-under-test (wheel)

- **Provenance**: built by `uv build` from the commit, installed into a throwaway venv (C-002).
- **Lifecycle**: built once per nightly job leg, reused across scenarios on that leg.

## Entity: Runner (acceptance-jvm Gradle subproject)

- **Fields**: pinned Gradle (`tools/pins.json`, version + sha256); Gradle-generated `gradle/verification-metadata.xml`; `build.gradle` (Cucumber-JVM 7, JUnit Platform, allure-cucumber7-jvm); JDK 25; reads `../tests/scenarios` in place; no committed wrapper jar.
- **Invariant (NFR-003)**: 100% of JVM deps pinned/verified; distribution checksum-pinned; 0 wrapper jars committed; drift guarded by the generalized `gradle_pin_check.py`.

## Entity: Nightly acceptance-bdd job

- **Fields**: 3-OS matrix (Linux/macOS/Windows); a **gating** run (`not @wip and not @manual`, 0 retries) and a separate **non-gating** `@wip` run; uploads Cucumber JSON, JUnit XML, Allure results as named artifacts.
- **Invariant**: gates no per-PR job (NFR-004); a red on any OS leg fails that leg (NFR-001).

## Entity: Router group (ci-router)

- **`scenarios`** → globs `tests/scenarios/**`; **`acceptance_jvm`** → globs `acceptance-jvm/**`.
- **Invariant (C-005/FR-012)**: neither is referenced by any job `if:` → both gate **no** per-PR job; both are registered in `_DELIBERATELY_UNGATED_FILTER_GROUPS`; both globs match ≥1 git-tracked path.
