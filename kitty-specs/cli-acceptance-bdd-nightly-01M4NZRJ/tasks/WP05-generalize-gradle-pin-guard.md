---
work_package_id: WP05
title: Generalize the shared Gradle pin-drift guard
dependencies:
- WP03
requirement_refs:
- NFR-003
planning_base_branch: feat/cli-acceptance-bdd-nightly
merge_target_branch: feat/cli-acceptance-bdd-nightly
branch_strategy: Planning artifacts for this mission were generated on feat/cli-acceptance-bdd-nightly. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cli-acceptance-bdd-nightly unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-acceptance-bdd-nightly-01M4NZRJ
base_commit: d5dcd63a662f62d83c3fa7854004d83fbdcb7974
created_at: '2026-10-11T18:57:56.490149+00:00'
subtasks:
- T017
- T018
phase: Phase 4 - Supply-chain guard
history:
- at: '2026-10-11T17:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: contracts/tools/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- contracts/tools/gradle_pin_check.py
- tests/contract/test_gradle_pin_check.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Generalize the shared Gradle pin-drift guard

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before reading anything else.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Per decision **DM-01M4P2B3S88TYZAK2WH5HM12PZ**, generalize the single canonical guard
`contracts/tools/gradle_pin_check.py` so it also guards the `acceptance-jvm/` pins — one
`GRADLE_PIN_MISMATCH` authority for both subprojects.

Done when:
- The guard cross-checks `acceptance-jvm/build.gradle`, `acceptance-jvm/tools/pins.json`, `acceptance-jvm/gradle/verification-metadata.xml`, and the `acceptance-bdd` nightly job's `gradle-version` against the acceptance-jvm Gradle pin.
- `contracts/` scanning behaviour and exit codes are **byte-identical** to before.
- Red-first unit tests cover the new scan paths (matching pins pass; injected drift fails).

## Context & Constraints

- Read `contracts/tools/gradle_pin_check.py` and `tests/contract/test_gradle_pin_check.py` first. See research.md §2/§4 for how it works today (stdlib + PyYAML; checks the `build.gradle` plugin version, the metadata plugin components, an optional `gradle-wrapper.properties`, and the `gradle-version:` inputs of `contracts*.yml`). It already tolerates an absent wrapper file.
- **Depends on WP03** — the acceptance-jvm pins/metadata must exist to scan (the live scan). Tests use fixtures, so they do not need the live files.
- Keep it stdlib + PyYAML; `ruff`/`mypy` at zero; complexity ≤ 15 (extract helpers rather than growing one function).
- Spec ref: NFR-003.

## Branch Strategy

- **Strategy**: already-confirmed
- **Planning base branch**: feat/cli-acceptance-bdd-nightly
- **Merge target branch**: feat/cli-acceptance-bdd-nightly

## Subtasks & Detailed Guidance

### Subtask T017 – Generalize the guard

- **Purpose**: Guard acceptance-jvm pin drift with the same authority.
- **Steps**:
  1. Add an acceptance-jvm scan alongside the contracts scan: resolve the Gradle version + sha256 from `acceptance-jvm/tools/pins.json`; cross-check the Gradle version referenced by `acceptance-jvm/build.gradle` (if any) and the components in `acceptance-jvm/gradle/verification-metadata.xml`.
  2. Extend the workflow-version glob so it also reads the `gradle-version:` input (or the install-tools `--pins acceptance-jvm/...` invocation / `setup-java` where relevant) of the `acceptance-bdd` job in `ci-nightly.yml`. Tolerate the job's absence the same way the wrapper file is tolerated (early-return / skip), so ordering does not hard-fail.
  3. Keep the `contracts/` code path and the `GRADLE_PIN_MISMATCH` code unchanged; factor shared logic into a small helper parameterised by subproject root + pins path rather than duplicating.
- **Files**: `contracts/tools/gradle_pin_check.py`.
- **Notes**: single canonical guard — do not fork a second script.

### Subtask T018 – Red-first unit tests

- **Purpose**: Prove the new scanning is non-vacuous.
- **Steps**: In `tests/contract/test_gradle_pin_check.py`, add fixture-based tests: (a) matching acceptance-jvm pins → pass; (b) injected drift in each new scan path (pins.json vs build.gradle vs metadata vs workflow `gradle-version`) → `GRADLE_PIN_MISMATCH`. Author them red-first (assert the new code is exercised — a revert of T017 must turn them red). Keep the existing contracts tests passing unchanged.
- **Files**: `tests/contract/test_gradle_pin_check.py`.

## Test Strategy

- `uv run --frozen pytest tests/contract/test_gradle_pin_check.py -q` (the contract-tools lane). Confirm both the new and existing cases pass. Run `ruff check contracts/tools/gradle_pin_check.py` and `mypy` on it.

## Risks & Mitigations

- **Regressing contracts scanning** → keep its path/codes identical; add coverage for new paths only; a contracts-only diff must still pass the old tests verbatim.
- **Ordering hard-fail** → tolerate a missing `acceptance-bdd` job like the absent wrapper file.

## Review Guidance

- Confirm one canonical guard now covers both subprojects, contracts behaviour is unchanged, and the new tests fail if T017 is reverted.

## Progress & Status

- Record a note: `spec-kitty agent tasks add-history WP05 --note "…"`
- Change status: `spec-kitty agent tasks move-task WP05 --to <status>`

## Activity Log

- 2026-10-11T19:18:11Z – claude – shell_pid=3136237 – T017/T018: generalized contracts/tools/gradle_pin_check.py into one canonical GRADLE_PIN_MISMATCH authority via a Subproject-parameterised _scan (shared _load_pins/_check_build/_check_metadata/_check_wrapper/_check_workflow). contracts path/codes byte-identical (check() unchanged; 21 existing tests green). Added acceptance-jvm scan (candidates gradle+plugin, only gradle required) covering tools/pins.json, build.gradle, verification-metadata.xml, and the acceptance-bdd job's gradle-version in ci-nightly.yml; absent plugin/wrapper/acceptance-bdd job tolerated like the absent wrapper (WP06 ordering safe). main() scans whole repo via check_all. 9 new fixture-based tests (matching pins pass; injected drift per path -> GRADLE_PIN_MISMATCH; gradle-only live-like tolerance; check_all aggregation; live repo agreement). 30 passed; ruff + mypy + format clean.
