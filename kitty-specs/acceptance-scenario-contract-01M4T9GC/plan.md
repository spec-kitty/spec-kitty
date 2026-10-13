# Implementation Plan: Acceptance scenario contract, per-PR check and nightly evidence

**Branch**: `ccr-002603b2-bip646` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/acceptance-scenario-contract-01M4T9GC/spec.md`

## Summary

Four slices, all black-box and inside test infrastructure:

1. **Contract docs (#6134)**: the tag vocabulary and drafted-scenario flow in the scenario README and the contributor guide; ADR 2026-10-13-1 marked Accepted.
2. **Nightly evidence (#6136)**: one Gradle property `acceptance.pass` (`gating` | `wip`) selects the tag filter and the output folder `build/acceptance/<pass>/`; a static Cucumber `@BeforeAll` hook writes Allure `environment.properties` and `executor.json`; a stdlib script `scripts/ci/acceptance_evidence.py` writes `evidence.json` after both passes from the JUnit XML; the upload is tightened.
3. **Per-PR check (#6135)**: `tests/architectural/test_scenario_contract.py` backed by a stdlib module `scripts/ci/scenario_contract.py` (Gherkin subset reader, tag rules, Cucumber-expression matcher); added to the `architectural-fast` roster, which runs on every pull request.
4. **Mission builders (#6137)**: a `MissionFixture` that drives `spec-kitty` commands through the driver, new Arrange and Assert steps, and a `tests/scenarios/mission/` area.

## Technical Context

**Language/Version**: Python 3.11+ (check, evidence script, tests); Java 25 toolchain (acceptance-jvm, unchanged); Gradle 8.14.5 pinned.
**Primary Dependencies**: none new. Python stdlib only for the check and the script; Java uses the existing Cucumber 7.20.1, Allure 2.29.1, AssertJ (no new artifacts, so `verification-metadata.xml` is unchanged).
**Storage**: files: `build/acceptance/<pass>/…`, `build/acceptance/evidence.json`.
**Testing**: pytest unit tests for `scenario_contract.py` and `acceptance_evidence.py`; the architectural test over the real tree plus one broken fixture per rule; a pytest pin on the nightly upload step via `tests/architectural/_gate_coverage.load_spliced_workflow`; Java verified by compiling and running the scenarios locally.
**Target Platform**: GitHub Actions (ubuntu, macOS, Windows legs for the nightly; ubuntu for per-PR).
**Project Type**: single repository, test infrastructure only.
**Performance Goals**: per-PR check under 5 s (NFR-001); roster budget 10 s.
**Constraints**: C-001 to C-006 in the spec. JDK 25 cannot be downloaded in this environment (GitHub release assets blocked), so Java changes are verified in a scratch copy of `acceptance-jvm/` with the toolchain set to 21 (never committed); CI's `sonar.yml` JDK 25 `compileTestJava` and the nightly are the authoritative checks.
**Scale/Scope**: about 6 Python files, 5 Java files, 3 docs, 2 workflow/registry files.

## Charter Check

- **ATDD-first (C-011)**: each work package lands a failing test first: the evidence script's tests and a pass-isolation test before the Gradle change; the contract check's broken fixtures before the reader; a mission scenario before the builder. PASS (planned).
- **Single canonical authority**: the step vocabulary is read from the Java annotations, never copied into Python; the tag vocabulary is defined once in `scenario_contract.py` and documented in the guide. PASS.
- **Architectural gate discipline**: the roster entry follows `special_tiers.architectural.fast_gate` admission rules (static, deterministic, no CLI round trip). PASS.
- **Terminology**: "Mission" throughout; no "feature" aliasing beyond Gherkin's own `Feature:` keyword. PASS.
- **Black-box (ADR 2026-10-11-3)**: builders call the CLI only. PASS.
- **No promise index (ADR 2026-10-11-3 amendment, ADR 2026-10-13-1)**: identifier shape only. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/acceptance-scenario-contract-01M4T9GC/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/evidence.schema.json
└── tasks.md
```

### Source Code (repository root)

```
scripts/ci/scenario_contract.py          # Gherkin subset reader, tag rules, step matcher (stdlib)
scripts/ci/acceptance_evidence.py        # writes build/acceptance/evidence.json from per-pass results
tests/architectural/test_scenario_contract.py
tests/architectural/fixtures/scenarios/  # one broken .feature (and steps) per rule
tests/ci/test_scenario_contract_reader.py
tests/ci/test_acceptance_evidence.py
tests/ci/test_acceptance_bdd_upload.py   # pins the nightly upload step and job condition
.github/ci-module-registry.yml           # architectural fast_gate roster row
.github/workflows/ci-nightly.yml         # acceptance-bdd: pass property, evidence step, upload
acceptance-jvm/build.gradle              # acceptance.pass → tags + output dirs + allure dir
acceptance-jvm/src/test/java/kitty/acceptance/environment/CliUnderTest.java   # version()
acceptance-jvm/src/test/java/kitty/acceptance/environment/RunMetadata.java    # writes env/executor files
acceptance-jvm/src/test/java/kitty/acceptance/environment/MissionFixture.java # CLI-only builders
acceptance-jvm/src/test/java/kitty/acceptance/steps/RunHooks.java             # static @BeforeAll
acceptance-jvm/src/test/java/kitty/acceptance/steps/{ArrangeSteps,AssertSteps}.java
tests/scenarios/mission/*.feature
tests/scenarios/README.md
docs/development/testing/acceptance-scenarios.md
docs/adr/4.x/2026-10-13-1-acceptance-scenarios-link-to-promises-by-identifier-only.md
```

**Structure Decision**: Python logic lives in `scripts/ci/` (importable, unit-testable, counted by coverage) and the architectural test is a thin wrapper, matching existing `scripts/ci/*` + `tests/ci/*` pairs.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Scenario contract documentation

- **Purpose**: write the tag vocabulary, gating rule and drafted-scenario flow where authors read them; record the ADR as Accepted.
- **Relevant requirements**: FR-001, FR-002
- **Affected surfaces**: `tests/scenarios/README.md`, `docs/development/testing/acceptance-scenarios.md`, ADR 2026-10-13-1, `docs/adr/4.x/index.md` (regenerated).
- **Sequencing/depends-on**: none
- **Risks**: docs SEO/freshness gates (description length, `updated:` date).

### IC-02 — Per-pass results and run metadata (Gradle + Java)

- **Purpose**: stop the `@wip` pass overwriting the gating evidence and stamp every Allure result with its build.
- **Relevant requirements**: FR-008, FR-009, NFR-004
- **Affected surfaces**: `acceptance-jvm/build.gradle`, `CliUnderTest.java` (keep the wheel path, expose `version()` parsed from `spec_kitty_cli-<version>-…whl`), new `RunMetadata.java`, new static `@BeforeAll` hook class.
- **Design**: `-Pacceptance.pass=gating|wip`; `gating` → `not @wip and not @manual`, `wip` → `@wip`; output root `build/acceptance/<pass>/` holding `allure-results/` (system property `allure.results.directory`), `cucumber.json` (plugin `json:`), `junit/` (`reports.junitXml.outputLocation`), separate binary results dir; the pass is declared as a task input so Gradle re-runs the task when it changes. Without the property, a developer's `-Dcucumber.filter.tags` keeps working into `build/acceptance/adhoc/`; giving both is refused. The zero-scenario guard exempts only `wip`. Metadata keys: `cli.version`, `commit.sha` (`GITHUB_SHA`, else `git rev-parse HEAD`), `os.name`, `java.version`, `acceptance.pass`; `executor.json` only when `GITHUB_RUN_ID` is set.
- **Sequencing/depends-on**: none
- **Risks**: local JDK is 21 (verified in a scratch copy); Allure property name verified against the 2.29.1 jar; Windows path separators (use Gradle `layout` APIs only).

### IC-03 — Evidence bundle and nightly job

- **Purpose**: one versioned file per leg, a strict upload, and no dead condition.
- **Relevant requirements**: FR-010, FR-011
- **Affected surfaces**: `scripts/ci/acceptance_evidence.py`, `contracts`-style schema in the Mission's `contracts/evidence.schema.json`, `.github/workflows/ci-nightly.yml` (`acceptance-bdd`), `tests/ci/test_acceptance_evidence.py`, `tests/ci/test_acceptance_bdd_upload.py`.
- **Design**: the script reads each pass folder's JUnit XML (tests, failures, errors, skipped) and `environment.properties`, sets per-pass `outcome` to `passed` / `failed` / `missing`, and writes `evidence.json` (`schema_version: 1`, `commit_sha`, `cli_version`, `os`, `run_url`, `passes{gating,wip}`). Gating step gets an `id`; the evidence step runs `if: always()` and records the step outcomes it is given; upload path `acceptance-jvm/build/acceptance/`, `if-no-files-found: error`, `retention-days: 30`; job `if:` drops `pull_request`.
- **Sequencing/depends-on**: IC-02
- **Risks**: the gating step failing must not skip the evidence step (`if: always()`).

### IC-04 — Per-PR scenario contract check

- **Purpose**: catch malformed feature files, bad tags and unbound gating steps on the pull request without a JDK.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002
- **Affected surfaces**: `scripts/ci/scenario_contract.py`, `tests/architectural/test_scenario_contract.py`, `tests/architectural/fixtures/scenarios/`, `tests/ci/test_scenario_contract_reader.py`, `.github/ci-module-registry.yml` (one `fast_gate.roster` row, 10 s budget).
- **Design**: line-based reader for `Feature`/`Rule`/`Background`/`Scenario`/`Scenario Outline`/`Examples`, tags, steps (`Given/When/Then/And/But/*`), doc strings and data tables; tags inherit Feature → Rule → Scenario; outline steps expanded per `Examples` row; step definitions extracted by regex from `@Given|@When|@Then("…")` in `acceptance-jvm/src/test/java/**/steps/*.java`, Java string escapes decoded; `{string}` → `"[^"]*"|'[^']*'`, `{int}` → `-?\d+`, `{word}` → `[^\s]+`, any other `{…}` is an error; a step matches when exactly one full-match regex matches. Routing: the `architectural-fast` job runs on every pull request, so scenario-only and acceptance-jvm-only pull requests are covered with no `ci-router.yml` change and the "ungated by design" filter groups stay as pinned in `tests/architectural/test_workflow_coherence.py`.
- **Sequencing/depends-on**: IC-01 (vocabulary text)
- **Risks**: Cucumber expression optional text `(s)` and alternation `a/b` are not used today; treat them as errors with a clear message rather than guessing.

### IC-05 — Mission state builders and scenarios

- **Purpose**: let scenarios start from a project with a Mission in a known state.
- **Relevant requirements**: FR-012, FR-013
- **Affected surfaces**: `MissionFixture.java`, `ArrangeSteps.java`, `AssertSteps.java`, `tests/scenarios/mission/*.feature`, `tests/scenarios/README.md` step table.
- **Design**: builder runs `spec-kitty init`, `git` commit, `spec-kitty agent mission create <slug> --json` and, for a work package in a lane, the minimal planning commands plus `spec-kitty agent tasks move-task`; asserts parse `spec-kitty agent tasks status --json`. Exact command sequence confirmed during implementation against the current CLI.
- **Sequencing/depends-on**: IC-04
- **Risks**: Mission creation needs the full planning chain to reach a WP lane; if that is too heavy for a nightly scenario, the lane step is scoped to what `create` plus a committed spec allows, and the remainder is recorded.
