---
work_package_id: WP04
title: Release re-verification
dependencies:
- WP02
requirement_refs:
- FR-009
- SC-003
- NFR-003
planning_base_branch: feat/builtin-revendor-pin-gate
merge_target_branch: feat/builtin-revendor-pin-gate
branch_strategy: Planning artifacts for this mission were generated on feat/builtin-revendor-pin-gate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/builtin-revendor-pin-gate unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
phase: Phase 1 - Implementation
history:
- at: '2026-10-17T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/cross_cutting/packaging/
create_intent:
- tests/cross_cutting/packaging/test_built_in_release_parity.py
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/release.yml
- RELEASE_CHECKLIST.md
- tests/cross_cutting/packaging/test_built_in_release_parity.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3504'
---

# Work Package Prompt: WP04 – Release re-verification

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Close the loop at the release:

- `release.yml` and `RELEASE_CHECKLIST.md` run the pin verify step **before** `python -m build`
  (per the amendment: release uses `python -m build`, not `hatch build`).
- A post-build assertion confirms the **built wheel's** `packs/built-in/` clean-tree digest equals the
  committed pin — reusing the `tests/charter_offering/test_packaging_parity.py` pattern + the existing
  build fixtures.
- **The wheel force-include and the `packs/internal/` exclusion are unchanged**:
  `tests/cross_cutting/packaging/test_packaging_safety.py` is NOT edited (C-002), and `pyproject.toml`
  is NOT touched. Consumer install stays byte-identical; `resolve_pack_root("built-in")` resolves the
  same tree (NFR-003).

Success = FR-009, SC-003, NFR-003 in [spec.md](../spec.md) hold.

## Context & Constraints

- **Plan**: [plan.md](../plan.md) IC-04. **Research**: [research.md](../research.md) D5. **Charter**: `.kittify/charter/charter.md`.
- **Reuse the parity pattern**: `tests/charter_offering/test_packaging_parity.py` already builds a real
  wheel + sdist (`@pytest.mark.distribution`, `@pytest.mark.integration`, `@pytest.mark.corpus`),
  derives the expected `packs/built-in/` file set from `git ls-files`, and compares the built
  artifact's contents. Follow that shape, but the NEW assertion is a **digest equality**: extract the
  wheel's `packs/built-in/` into a temp dir and assert `clean_tree_digest(<extracted>, level=BUILT_IN)`
  equals the committed pin's `tree_digest.value` (load it via WP01's `load_built_in_pin`). This is the
  SC-003 contract: "the released wheel's `packs/built-in/` tree digest equals the committed pin."
- **Positive control (SC-004-style non-vacuity)**: add a control that points the digest probe at a
  deliberately mutated extracted tree and asserts it reds — so a drifted/no-op wheel would fail the
  test, proving the assertion is live.
- **Test home**: `tests/cross_cutting/packaging/test_built_in_release_parity.py` (beside
  `test_packaging_safety.py`, the owning packaging subsystem). Mark it `distribution` + `integration`
  so it does not run in the fast gate (it builds a wheel). Record the explicit invocation in the PR:
  `pytest tests/cross_cutting/packaging/test_built_in_release_parity.py -m distribution -v`.
- **`release.yml` edit**: add a verify step in `build-release` BEFORE the `Build distributions`
  (`python -m build`) step — `uv run --frozen spec-kitty charter pack vendor --check` (offline; it
  verifies the committed tree against the pin). Keep it minimal and in the existing job; do not add a
  new job or reorder unrelated steps.
- **`RELEASE_CHECKLIST.md` edit**: add the same `spec-kitty charter pack vendor --check` step to the
  manual pre-tag build sequence, before `python -m build`.
- **Do NOT change**: the hatchling `force-include` in `pyproject.toml`, `test_packaging_safety.py`, or
  the `packs/internal/` exclusion (C-002). If a change seems to require touching those, STOP and flag
  it — it is out of scope.

## Branch Strategy

- **Strategy**: single_branch (direct in the write checkout; no lane worktree)
- **Planning base branch**: feat/builtin-revendor-pin-gate
- **Merge target branch**: feat/builtin-revendor-pin-gate (PR → main)

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first wheel-parity digest test

- **Purpose**: ADR `2026-07-17-1`; SC-003, NFR-003.
- **Steps**:
  1. Create `tests/cross_cutting/packaging/test_built_in_release_parity.py` modelled on
     `test_packaging_parity.py`'s build-once fixtures (build the wheel once, share across tests;
     `@pytest.mark.distribution`, `@pytest.mark.integration`).
  2. Extract the wheel's `packs/built-in/` into a temp dir and assert
     `clean_tree_digest(temp, level=BUILT_IN) == load_built_in_pin(<repo>/packs/built-in.source.yaml).tree_digest.value`.
  3. Add the positive control: a mutated extracted tree reds the probe.
  4. Confirm the test is meaningful RED first (e.g. before the pin lockfile exists on the base, or by
     asserting the control reds); record the evidence.
- **Files**: `tests/cross_cutting/packaging/test_built_in_release_parity.py`
- **Parallel?**: No.
- **Notes**: Reuse the existing build helper rather than hand-rolling a second `python -m build`
  invocation where the parity test already provides one. Keep the clean-venv/import checks out of
  scope — NFR-003's "resolve_pack_root resolves the same tree" is already covered by the existing
  parity test; your new assertion is the DIGEST-equals-pin contract.

### Subtask T012 – Wire the release verify step

- **Purpose**: FR-009 — the release re-verifies before building.
- **Steps**:
  1. In `.github/workflows/release.yml` `build-release`, add `uv run --frozen spec-kitty charter pack vendor --check`
     as a step immediately before `Build distributions` (`python -m build`). A drift fails the release
     build (fail-closed).
  2. In `RELEASE_CHECKLIST.md`, add the same verify step to the manual pre-tag build sequence, before
     `python -m build`.
  3. Confirm `pyproject.toml` force-include and `test_packaging_safety.py` are untouched.
- **Files**: `.github/workflows/release.yml`, `RELEASE_CHECKLIST.md`
- **Parallel?**: No.

## Test Strategy

- Red-first wheel-parity digest test (built artifact's digest == pin) + mutated-tree positive control.
- Targeted surface: `tests/cross_cutting/packaging/test_built_in_release_parity.py -m distribution`,
  plus a smoke of `tests/cross_cutting/packaging/test_packaging_safety.py` to confirm it still passes
  unchanged. Record commands + counts in the PR.

## Risks & Mitigations

- **Touching the force-include / safety test (C-002)**: do not; flag if it seems necessary.
- **Double wheel build cost**: reuse the parity-test build fixtures.
- **Vacuous assertion**: the mutated-tree positive control proves the digest check is live.
- **Release step ordering**: verify must precede `python -m build`.

## Review Guidance

- Confirm the wheel-parity test asserts digest-equals-pin on the BUILT artifact.
- Confirm the positive control reds on a mutated tree.
- Confirm `release.yml` + `RELEASE_CHECKLIST.md` verify before `python -m build`.
- Confirm `pyproject.toml` and `test_packaging_safety.py` are unchanged (C-002, NFR-003).

## Progress & Status

Progress/history/status live in the status event log — do not hand-edit here.
- Record a note: `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- Change status: `spec-kitty agent tasks move-task WP04 --to <status>`
- View: `spec-kitty agent tasks status`
