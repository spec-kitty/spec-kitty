---
work_package_id: WP06
title: Nightly acceptance-bdd job (3 OSes)
dependencies:
- WP04
- WP05
requirement_refs:
- FR-010
- FR-011
- FR-014
- NFR-001
- NFR-004
- NFR-005
- SC-001
planning_base_branch: feat/cli-acceptance-bdd-nightly
merge_target_branch: feat/cli-acceptance-bdd-nightly
branch_strategy: Planning artifacts for this mission were generated on feat/cli-acceptance-bdd-nightly. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cli-acceptance-bdd-nightly unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-acceptance-bdd-nightly-01M4NZRJ
base_commit: b324bf3b25cdd6c5ee0d48f01ae3475f110d3e3b
created_at: '2026-10-11T19:26:23.531351+00:00'
subtasks:
- T019
- T020
- T021
phase: Phase 5 - CI
history:
- at: '2026-10-11T17:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Nightly acceptance-bdd job (3 OSes)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before reading anything else.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Add an `acceptance-bdd` job to `.github/workflows/ci-nightly.yml` that runs the `acceptance-jvm`
runner on **Linux, macOS and Windows**.

Done when:
- The job is a 3-OS matrix; each leg builds the wheel (`uv build`), installs the pinned Gradle + JDK 25, and runs the scenarios.
- A **gating** run filters `not @wip and not @manual` with **no retries**; a separate **non-gating** run executes `@wip`.
- Cucumber JSON, JUnit XML and Allure results are uploaded as named artifacts.
- The generalized `gradle_pin_check.py` runs as a pre-step.

## Context & Constraints

- **Hot file** (40 commits/90d) — keep the diff additive and self-contained; append the job, do not reshuffle existing ones. See research.md §1/§6.
- Every current nightly job is single-OS `ubuntu-24.04`; this is the **first** multi-OS nightly job — use a `strategy.matrix.os` of `[ubuntu-24.04, macos-latest, windows-latest]`.
- Install the pinned Gradle via the shared installer: `python contracts/tools/install_tools.py --pins acceptance-jvm/tools/pins.json --dest "$RUNNER_TEMP/tools" --only gradle`; set up JDK 25 with `actions/setup-java` (`temurin`, `java-version: '25'`).
- **NFR-004**: this job is nightly-only; it must NOT be wired as a per-PR trigger.
- **Depends on WP04** (the runner) and **WP05** (the generalized guard).
- Spec refs: FR-010, FR-011, FR-014, NFR-001, NFR-004, NFR-005, SC-001.

## Branch Strategy

- **Strategy**: already-confirmed
- **Planning base branch**: feat/cli-acceptance-bdd-nightly
- **Merge target branch**: feat/cli-acceptance-bdd-nightly

## Subtasks & Detailed Guidance

### Subtask T019 – The acceptance-bdd job (3-OS matrix)

- **Purpose**: Run the scenarios nightly cross-OS (FR-010, NFR-001, NFR-005).
- **Steps**: Add a job `acceptance-bdd` with `strategy.fail-fast: false` and `matrix.os: [ubuntu-24.04, macos-latest, windows-latest]`. Steps per leg: checkout; set up Python + `uv`; set up JDK 25 (`actions/setup-java` temurin 25); install pinned Gradle via `install_tools.py`; run the **gating** set `gradle test --no-daemon -Dcucumber.filter.tags="not @wip and not @manual"` with **no retry wrapper**; then run the **non-gating** `@wip` set as a separate step with `continue-on-error: true` (so `@wip` never fails the leg).
- **Files**: `.github/workflows/ci-nightly.yml`.
- **Notes**: no `nick-fields/retry` or re-run loop on the gating step — a flake must be reported (NFR-005).

### Subtask T020 – Upload results artifacts

- **Purpose**: Hand results to the spec-kitty-qa nightly (FR-011).
- **Steps**: After the runs (with `if: always()`), upload Cucumber JSON, JUnit XML and Allure results via `actions/upload-artifact` under named keys that include the OS (e.g. `acceptance-bdd-results-${{ matrix.os }}`), pointing at `acceptance-jvm/build/` outputs.
- **Files**: `.github/workflows/ci-nightly.yml`.

### Subtask T021 – Pin-check pre-step; summary wiring

- **Purpose**: Guard pins (NFR-003) and keep the hot-file diff minimal.
- **Steps**:
  1. Add a pre-step (once, e.g. on the Linux leg or as a tiny separate `needs`-free step) running `python contracts/tools/gradle_pin_check.py` so acceptance-jvm pin drift fails the nightly.
  2. Leave the `acceptance-bdd` job **out of** `nightly-summary.needs` (it is non-gating and uploads its own artifacts). **First verify** `tests/release/test_release_ci_ownership.py` and `.github/workflows/release-readiness.yml` do not require every nightly job in the summary — if one does, wire it into both the `needs:` list and the echo block instead.
- **Files**: `.github/workflows/ci-nightly.yml`.

## Test Strategy

- YAML is validated by the architectural workflow guards (exercised via WP07's changes) and by CI parsing. Locally, lint the YAML and dry-read the job with `python scripts/ci/gate_selection.py` helpers if applicable. Confirm `tests/release/test_release_ci_ownership.py` passes after the edit:
  `uv run --frozen pytest tests/release/test_release_ci_ownership.py tests/ci/test_contracts_workflows.py -q`.

## Risks & Mitigations

- **Freezing a nightly job set** → check the release/ownership tests before assuming the summary can omit the job.
- **Accidental per-PR trigger** → the job lives only in `ci-nightly.yml`; do not add it to any `pull_request` workflow.
- **Windows runner quirks** → rely on the `CliProcessDriver` normalisation (WP04); keep the YAML OS-agnostic.

## Review Guidance

- Confirm: 3-OS matrix; gating tag filter + no retries; separate non-gating `@wip` run; all three result formats uploaded; pin-check pre-step; and the release/ownership tests still pass.

## Progress & Status

- Record a note: `spec-kitty agent tasks add-history WP06 --note "…"`
- Change status: `spec-kitty agent tasks move-task WP06 --to <status>`

## Activity Log

- 2026-10-11T19:37:27Z – claude – shell_pid=3227738 – Added 3-OS acceptance-bdd job to ci-nightly.yml (T019-T021): fail-fast:false matrix [ubuntu-24.04,macos-latest,windows-latest]; JDK 25 temurin; pinned Gradle 8.14.5 via shared install_tools.py; gating run 'not @wip and not @manual' with no retry wrapper; non-gating @wip run continue-on-error; if:always() upload of Cucumber JSON/JUnit XML/Allure under acceptance-bdd-results-${{matrix.os}}; gradle_pin_check.py pre-step on the Linux leg. Verified release/ownership + contracts-workflow tests (161 passed) do NOT require every nightly job in nightly-summary (ci-nightly.yml is only an INTRODUCED workflow name, not a frozen job set), so left out of nightly-summary.needs per minimal-diff guidance. pin-check green (exit 0, compared=6); gradle_pin_check contract tests 30 passed.
