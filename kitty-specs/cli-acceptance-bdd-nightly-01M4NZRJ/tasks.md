# Work Packages: CLI Acceptance Scenarios & Cucumber-JVM Nightly

**Inputs**: Design documents from `kitty-specs/cli-acceptance-bdd-nightly-01M4NZRJ/`
**Prerequisites**: plan.md (required), spec.md, research.md (grounding), data-model.md, quickstart.md

**Tests**: This mission's product *is* a test surface. Scenario authoring (WP02) and the Java
harness tests (WP04) are the deliverable; WP05/WP08 add red-first Python tests for the guard and
the packaging exclusion. Normal ATDD discipline applies.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`), derived from
the plan's Implementation Concern Map (IC-01…IC-07).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- CLI source under test: `src/specify_cli/` (black-box only — never imported by the runner).
- New scenario corpus: `tests/scenarios/`. New JVM runner: `acceptance-jvm/`.
- CI: `.github/workflows/`. Packaging: `pyproject.toml` + `tests/cross_cutting/packaging/`.

---

## Work Package WP01: ADR amendment — record the owner ruling (Priority: P0)

**Goal**: Amend ADR `2026-10-11-3` to record the 2026-10-11 owner ruling narrowing promise machinery out of core. This is the mission's **first deliverable**.
**Independent Test**: The ADR carries an Amendment section stating the four narrowed items and the `scenarios`-gates-no-job flip; the original Decision text is preserved.
**Prompt**: `/tasks/WP01-adr-amendment.md`
**Requirement Refs**: FR-001, FR-014, C-003

### Included Subtasks

T001 Add an "Amendment (2026-10-11 owner ruling)" section recording that the promise index (`tests/scenarios/promise-index.json`), the per-PR promise-tag check (`tests/architectural/test_scenario_promise_tags.py`) and `PROMISE_INDEX_SYNC_TOKEN` are out of core scope (spec-kitty-qa owns them) and were never built
T002 Record the consequences: the `scenarios` ci-router group gates **no** job (was "gates the architectural job"); `acceptance_jvm` gates no job; `@promise`/`@defect`/`@qa` are inert in core; only `@wip`/`@manual` affect the nightly filter; `@manual` is an allowed tag
T003 Preserve the original Decision text and update the Status/front-matter note to point at the amendment, keeping the ADR internally coherent

### Dependencies
- None (can land first).

### Risks & Mitigations
- Rewriting rather than amending history → keep the original Decision intact; add an Amendment section only.

---

## Work Package WP02: Seed `init` scenarios + corpus layout (Priority: P1) 🎯 MVP

**Goal**: Establish `tests/scenarios/<area>/` and author the two bound, untagged `init` scenarios drawn verbatim from `init_help.py`.
**Independent Test**: Both scenarios parse as valid Gherkin and encode the idempotent-restore and no-git promises with same-fixture positive controls.
**Prompt**: `/tasks/WP02-seed-init-scenarios.md`
**Requirement Refs**: FR-002, FR-003, FR-004, SC-002

### Included Subtasks

T004 Create the `tests/scenarios/init/` area layout
T005 Author scenario "re-running init keeps project state, only restores missing skill roots" with a same-fixture positive control (a deleted skill root is restored; an untouched root + other project state stay unchanged) — bound, untagged
T006 Author scenario "init never runs git init or commits" with a same-fixture positive control (project files ARE created; repository HEAD + commit count unchanged; no new `.git`) — bound, untagged
T007 [P] Fix the Gherkin step vocabulary so WP04's step definitions can bind it (shared step language)

### Dependencies
- None. **Must be git-tracked before/with WP07** (glob-is-live gate).

### Risks & Mitigations
- Vacuous ratchet → each scenario pairs its unchanged/absent assertion with a positive control on the same fixture.

---

## Work Package WP03: acceptance-jvm Gradle scaffolding + supply-chain pinning (Priority: P1)

**Goal**: Stand up the `acceptance-jvm/` Gradle subproject mirroring the `contracts/` pinning precedent, wired for Cucumber-JVM 7 on the JUnit Platform (Java 25), reading `../tests/scenarios` in place.
**Independent Test**: `gradle help` runs under the pinned, checksum-verified Gradle with no committed wrapper jar; `verification-metadata.xml` is present and Gradle-generated.
**Prompt**: `/tasks/WP03-acceptance-jvm-scaffolding.md`
**Requirement Refs**: FR-005, FR-006, C-006, NFR-003

### Included Subtasks

T008 Create `acceptance-jvm/settings.gradle` (names the subproject; documents "no committed wrapper jar") and `acceptance-jvm/build.gradle` (Cucumber-JVM 7, JUnit Platform, `allure-cucumber7-jvm`; Java 25 toolchain; cucumber tag-filter system property; test resources point at `../tests/scenarios`)
T009 Create `acceptance-jvm/tools/pins.json` (Gradle 8.14.5 + its pinned sha256, mirroring `contracts/tools/pins.json`) and a README noting reuse of `contracts/tools/install_tools.py` and the metadata-generation command
T010 Generate and commit `acceptance-jvm/gradle/verification-metadata.xml` via `gradle --write-verification-metadata sha256 … --no-daemon`

### Dependencies
- None. **Must be git-tracked before/with WP07** (glob-is-live gate).

### Risks & Mitigations
- Hand-editing `verification-metadata.xml` → always regenerate; it carries `origin="Generated by Gradle"`.

---

## Work Package WP04: SpecKittyDriver port, process driver, isolation & runner (Priority: P1) 🎯 MVP

**Goal**: The black-box harness: a `SpecKittyDriver` port, a `CliProcessDriver`, per-scenario isolated env + temp git repo, the wheel-under-test provisioning, step definitions for the two init scenarios, and the JUnit-Platform Cucumber runner.
**Independent Test**: Running `gradle test` locally executes both init scenarios against a `uv build` wheel in a temp venv and reports Cucumber/JUnit results, touching no real home state.
**Prompt**: `/tasks/WP04-driver-and-runner.md`
**Requirement Refs**: FR-007, FR-008, FR-009, C-001, C-002, NFR-002, SC-004

### Included Subtasks

T011 Define the `SpecKittyDriver` port (run a command → exit code, stdout, stderr, parsed `--json`, working tree)
T012 Implement `CliProcessDriver` with `ProcessBuilder`: drained streams, timeout, descendant-process kill, line-ending normalisation, real-path comparison
T013 Provision the CLI under test: `uv build` wheel installed into a temporary venv (never PyPI, never editable); invoked only through the driver
T014 Per-scenario isolated environment + temp git repo (`SPEC_KITTY_HOME`/`HOME`/`USERPROFILE`/XDG/`LOCALAPPDATA` inside the temp dir; UTF-8, `NO_COLOR`, fixed `COLUMNS`) with the NFR-002 positive control
T015 Step definitions binding the two init scenarios' Gherkin to the driver (no Python import; no internal Java)
T016 JUnit-Platform Cucumber runner + Allure reporter honouring the `not @wip and not @manual` / `@wip` tag filters

### Dependencies
- Depends on WP02 (scenarios to bind/execute) and WP03 (build.gradle to compile).

### Risks & Mitigations
- Cross-OS process/path/line-ending differences, descendant-kill on Windows → centralise in `CliProcessDriver`; assert on normalised output.

---

## Work Package WP05: Generalize the shared Gradle pin-drift guard (Priority: P2)

**Goal**: Extend `contracts/tools/gradle_pin_check.py` to also scan `acceptance-jvm/` and the `acceptance-bdd` nightly job's `gradle-version`, keeping one canonical `GRADLE_PIN_MISMATCH` authority (decision DM-01M4P2B3).
**Independent Test**: The guard fails `GRADLE_PIN_MISMATCH` on injected acceptance-jvm pin drift and passes when pins match; `contracts/` behaviour is unchanged.
**Prompt**: `/tasks/WP05-generalize-gradle-pin-guard.md`
**Requirement Refs**: NFR-003

### Included Subtasks

T017 Generalize `gradle_pin_check.py` to scan `acceptance-jvm/` (build.gradle gradle refs, `tools/pins.json`, `gradle/verification-metadata.xml`) and the `acceptance-bdd` workflow step's `gradle-version`, with `contracts/` behaviour byte-identical
T018 Add red-first unit tests in `tests/contract/test_gradle_pin_check.py` for the new scan paths (matching pins pass; injected drift fails) using fixtures

### Dependencies
- Depends on WP03 (acceptance-jvm pins exist to scan).

### Risks & Mitigations
- Shared-gate regression → keep `contracts/` scan paths and codes untouched; add coverage for new paths only.

---

## Work Package WP06: Nightly acceptance-bdd job (3 OSes) (Priority: P2)

**Goal**: Add an `acceptance-bdd` job to `ci-nightly.yml` on a Linux/macOS/Windows matrix: a gating run (`not @wip and not @manual`, no retries) and a separate non-gating `@wip` run; upload Cucumber JSON, JUnit XML and Allure results; run the generalized pin-guard as a pre-step.
**Independent Test**: The job definition parses; the matrix is 3 OSes; the gating step uses the correct tag filter and no retries; artifacts are uploaded under named keys.
**Prompt**: `/tasks/WP06-nightly-acceptance-bdd-job.md`
**Requirement Refs**: FR-010, FR-011, FR-014, NFR-001, NFR-004, NFR-005, SC-001

### Included Subtasks

T019 Add the `acceptance-bdd` job (3-OS matrix): build the wheel (`uv build`), install the pinned Gradle via `contracts/tools/install_tools.py --pins acceptance-jvm/tools/pins.json`, set up JDK 25, run the gating (`not @wip and not @manual`, 0 retries) and the non-gating `@wip` runs
T020 Upload Cucumber JSON, JUnit XML and Allure results as named artifacts for the spec-kitty-qa nightly
T021 Run the generalized `gradle_pin_check.py` as a pre-step; leave the job out of `nightly-summary.needs` (verify `release-readiness.yml` / `tests/release/test_release_ci_ownership.py` do not require it)

### Dependencies
- Depends on WP04 (runner to invoke) and WP05 (generalized guard).

### Risks & Mitigations
- Hot file, first multi-OS nightly job → keep the job additive and self-contained; confirm release/ownership tests don't freeze the nightly job set.

---

## Work Package WP07: Non-gating ci-router groups (Priority: P2)

**Goal**: Add `scenarios` (`tests/scenarios/**`) and `acceptance_jvm` (`acceptance-jvm/**`) to the ci-router, gating **no** per-PR job, and register them in the coherence gate's deliberately-ungated set.
**Independent Test**: `gate_selection` parses both groups; no job `if:` references them; `test_workflow_coherence` and the transcription guards stay green.
**Prompt**: `/tasks/WP07-ci-router-nongating-groups.md`
**Requirement Refs**: FR-012, C-005, NFR-004, SC-003

### Included Subtasks

T022 Add `scenarios` + `acceptance_jvm` to the dorny filter block and the `changes.outputs` block of `ci-router.yml`; gate no job; keep both out of the `unmatched` union (non-src)
T023 Add `"scenarios"` and `"acceptance_jvm"` to `_DELIBERATELY_UNGATED_FILTER_GROUPS` in `tests/architectural/test_workflow_coherence.py`; confirm the transcription guards (`test_changes_outputs_cover_every_routing_group`, `test_unmatched_union_covers_every_src_backed_group`) pass

### Dependencies
- Depends on WP02 and WP03 (both globs must match git-tracked paths — FR-003c glob-is-live).

### Risks & Mitigations
- Hot file (54 commits/90d) → keep the diff minimal/additive; the frozenset exemption is honest (both genuinely gate no job).

---

## Work Package WP08: sdist exclusion + packaging assertion (Priority: P2)

**Goal**: Exclude `acceptance-jvm/**` and `tests/scenarios/**` from the sdist and assert it (with a same-fixture positive control) in `test_packaging_safety.py`.
**Independent Test**: A built sdist contains neither tree; a `src/` package IS present (positive control); the wheel is unchanged.
**Prompt**: `/tasks/WP08-sdist-exclude-and-assert.md`
**Requirement Refs**: FR-013, C-004

### Included Subtasks

T024 Add `"acceptance-jvm/**"` and `"tests/scenarios/**"` to `[tool.hatch.build.targets.sdist].exclude` in `pyproject.toml`
T025 Add a `@pytest.mark.slow` assertion in `tests/cross_cutting/packaging/test_packaging_safety.py` (reusing the `build_artifacts` fixture) that both trees are absent from the sdist, paired with a positive control that a `src/` package IS present

### Dependencies
- Depends on WP02 and WP03 (both trees must exist so the exclusion is exercised non-vacuously).

### Risks & Mitigations
- Second sdist build cost → reuse the existing `build_artifacts` session fixture; keep the test in the slow tier.

---

## Dependency & Execution Summary

- **Sequence**: WP01 ∥ WP02 ∥ WP03 (no deps) → WP04 (needs WP02+WP03), WP05 (needs WP03) → WP06 (needs WP04+WP05), WP07 (needs WP02+WP03), WP08 (needs WP02+WP03).
- **Parallelization**: WP01, WP02, WP03 can run concurrently. After WP02+WP03 land, WP07 and WP08 can run alongside WP04/WP05.
- **MVP Scope**: WP02 + WP03 + WP04 + WP06 deliver US-1 (write a scenario, see it run nightly cross-OS). WP01 is the mandated first deliverable; WP05/WP07/WP08 are the governance/CI/packaging guards.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP02 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| FR-005 | WP03 |
| FR-006 | WP03 |
| FR-007 | WP04 |
| FR-008 | WP04 |
| FR-009 | WP04 |
| FR-010 | WP06 |
| FR-011 | WP06 |
| FR-012 | WP07 |
| FR-013 | WP08 |
| FR-014 | WP01, WP06 |
| NFR-001 | WP06 |
| NFR-002 | WP04 |
| NFR-003 | WP03, WP05 |
| NFR-004 | WP06, WP07 |
| NFR-005 | WP06 |
| C-001 | WP04 |
| C-002 | WP04 |
| C-003 | WP01 |
| C-004 | WP08 |
| C-005 | WP07 |
| C-006 | WP03 |
| SC-001 | WP06 |
| SC-002 | WP02 |
| SC-003 | WP07 |
| SC-004 | WP04 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | ADR amendment: narrowed items | WP01 | P0 | No |
| T002 | ADR amendment: consequences/tags | WP01 | P0 | No |
| T003 | Preserve original Decision; coherence | WP01 | P0 | No |
| T004 | tests/scenarios/init/ layout | WP02 | P1 | No |
| T005 | Scenario: idempotent restore | WP02 | P1 | No |
| T006 | Scenario: never git-init/commit | WP02 | P1 | No |
| T007 | Align step vocabulary | WP02 | P1 | Yes |
| T008 | settings.gradle + build.gradle | WP03 | P1 | No |
| T009 | pins.json + README | WP03 | P1 | No |
| T010 | Generate verification-metadata.xml | WP03 | P1 | No |
| T011 | SpecKittyDriver port | WP04 | P1 | No |
| T012 | CliProcessDriver | WP04 | P1 | No |
| T013 | Wheel-under-test provisioning | WP04 | P1 | No |
| T014 | Isolated env + temp git repo | WP04 | P1 | No |
| T015 | Step definitions | WP04 | P1 | No |
| T016 | JUnit/Cucumber runner + Allure | WP04 | P1 | No |
| T017 | Generalize gradle_pin_check.py | WP05 | P2 | No |
| T018 | Pin-check unit tests | WP05 | P2 | No |
| T019 | acceptance-bdd job (3 OS) | WP06 | P2 | No |
| T020 | Upload results artifacts | WP06 | P2 | No |
| T021 | Pin-check pre-step; summary wiring | WP06 | P2 | No |
| T022 | ci-router filter + outputs groups | WP07 | P2 | No |
| T023 | Coherence frozenset + guards | WP07 | P2 | No |
| T024 | pyproject sdist exclude | WP08 | P2 | No |
| T025 | Packaging assertion + positive control | WP08 | P2 | No |
