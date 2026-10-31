---
work_package_id: WP01
title: Red-first regression and controls
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-004
- NFR-001
planning_base_branch: issue-6464-protected-target-override-refusal
merge_target_branch: issue-6464-protected-target-override-refusal
branch_strategy: Planning artifacts for this mission were generated on issue-6464-protected-target-override-refusal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6464-protected-target-override-refusal unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-protected-target-override-refusal-01M68JPV
base_commit: 5b145d9f9b80c8af49d892201acbe5bb14e30f9c
created_at: '2026-10-31T08:59:17.147542+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - The regression
history:
- at: '2026-10-31T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/test_protected_target_preflight.py
execution_mode: code_change
model: ''
owned_files:
- tests/terminus/test_protected_target_preflight.py
- tests/orchestrator_api/test_consolidate_mission_protected_target.py
role: implementer
tags: []
task_type: test
tracker_refs:
- '6464'
---

# Work Package Prompt: WP01 – Red-first regression and controls

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completing, and record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- The defect from issue #6464 is pinned end to end, through the **real** `spec-kitty consolidate`
  CLI over real git (nothing mocked), in `tests/terminus/test_protected_target_preflight.py`: a
  Mission recorded for `develop` run with `--target main` (a branch this project protects) must exit
  1 with `PROTECTED_BRANCH_REFUSED`, `main` at its pre-run SHA, no squash commit on `main`, and a
  remedy that names the recorded target.
- **These tests are red on current `main`** — that is the point of this WP. Do not touch production
  code; WP02 makes them green. Confirm red and say so in the completion note, with the failing
  assertion text.
- The same-fixture controls prove the assertions are not vacuous: `--target <recorded target>`
  consolidates, the operator hatch stands the guard down, and every pre-existing #5385 control in the
  file keeps passing untouched.
- `--dry-run --json --target main` reports the same refusal code, and
  `orchestrator-api consolidate-mission --target main` reports it in its failure envelope.

## Context & Constraints

- Read first: `kitty-specs/protected-target-override-refusal-01M68JPV/spec.md` (FR-001, FR-003,
  FR-004, NFR-001), `plan.md` (IC-02 and its risk note), and
  `research.md` (the reproduction transcript).
- The existing module `tests/terminus/test_protected_target_preflight.py` is the home for the CLI
  cases: it already owns the #5385 contract, its `_consolidate` helper, `_assert_refused_before_any_mutation`,
  and the `REFUSAL_CODE` / `_PREFLIGHT_LINE` constants. Reuse them; do not build a parallel harness and
  do not weaken any existing assertion.
- The existing module `tests/orchestrator_api/test_consolidate_mission_protected_target.py` is the home
  for the API case; reuse its `_envelope` / `_assert_refused_unmoved` helpers.
- Fixtures: `tests/terminus/lanes_fixture.py::build_lanes_mission(tmp_path, wps=(...),
  target_branch=..., mid8=...)` builds a real LANES Mission. To reproduce #6464 you need a Mission
  whose **recorded** target is `develop` and a protected `main` that exists: create `main`
  (`git branch main`), then check it out — the pre-existing `MERGE_UNSAFE_PRIMARY_OFF_TARGET` guard
  refuses a run whose checkout is not on the resolved target, so a fixture left on `develop` would make
  this test pass for the wrong reason.
- Real behaviour on current `main` (verified): the squash prints `✓ kitty/mission-… → main  Commit:
  <sha>`, then the run fails on `SafeCommitHeadMismatch` and the #5385 rollback door restores the refs.
  Therefore assert on the **output** (`→ main`) as well as the exit code, so the test fails on `main`
  for the right reason; keep the ref-SHA and `blob_present_at` assertions as the durable contract.
- Mark the module's new cases `pytest.mark.regression` (the module is integration + git_repo; the new
  functions add `regression`).
- Never run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Run the two touched files only.
- Quality gates for this diff: `ruff check`, `ruff format --check`, `mypy` clean on the touched files.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6464-protected-target-override-refusal`
- **Merge target branch**: `issue-6464-protected-target-override-refusal`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with
`spec-kitty agent action implement WP01 --agent claude --mission protected-target-override-refusal-01M68JPV`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first e2e: the protected override is refused

- **Purpose**: one test that fails on `main` and states the contract.
- **Steps**:
  1. Build a LANES Mission with `target_branch="develop"` and two code WPs; `git branch main`, then
     `git checkout main`.
  2. Capture `ref_shas(mission)`, `_reflogs(mission)` and `_merge_records(mission)`.
  3. Run `_consolidate(mission, "--target", "main")`.
  4. Assert: exit code 1; `PROTECTED_BRANCH_REFUSED` in the flattened output; `Consolidation refused
     before any branch moved.` present; no `Traceback` in stderr; `ref_shas` unchanged; reflogs
     unchanged; no merge record; `not blob_present_at(mission.repo, "main", "src/pkg/wp01.py")`; and
     the output must **not** contain `→ main` (the squash reached the protected branch).
  5. Docstring: name #6464 and say why the checkout sits on `main` (the `MERGE_UNSAFE_PRIMARY_OFF_TARGET`
     guard would otherwise refuse first and the case would prove nothing).
- **Files**: `tests/terminus/test_protected_target_preflight.py`

### Subtask T002 – Same-fixture controls

- **Purpose**: prove the new assertion is not vacuous on the fixture that produced it.
- **Steps**:
  1. `--target develop` (the recorded target restated) on the same fixture shape: exit 0 and
     `blob_present_at(mission.repo, "develop", "src/pkg/wp02.py")`.
  2. `--target main` with `env={"SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS": "1"}`: the guard stands
     down (no `_REFUSAL_CODE`, no `_PREFLIGHT_LINE`).
- **Files**: `tests/terminus/test_protected_target_preflight.py`

### Subtask T003 – `--dry-run` parity

- **Purpose**: the preview may not be more permissive than the real run.
- **Steps**:
  1. Same fixture; run `["consolidate", "--dry-run", "--mission", mission.slug, "--json", "--target", "main"]`.
  2. Assert exit 1, the last stdout line parses as JSON, `payload["error_code"] == "PROTECTED_BRANCH_REFUSED"`,
     the remedy text names the recorded target, and no ref moved.
- **Files**: `tests/terminus/test_protected_target_preflight.py`

### Subtask T004 – orchestrator-api parity

- **Purpose**: the machine contract reports the same refusal.
- **Steps**:
  1. In `tests/orchestrator_api/test_consolidate_mission_protected_target.py`, add the override case:
     Mission recorded for `develop`, `git branch main` + `git checkout main`, then
     `orchestrator-api consolidate-mission --mission <slug> --target main --strategy squash`.
  2. Assert the existing `_assert_refused_unmoved` contract plus `PROTECTED_BRANCH_REFUSED` in the
     envelope and no squash content on `main`.
- **Files**: `tests/orchestrator_api/test_consolidate_mission_protected_target.py`

## Definition of Done

- Both modules pass **except** the new red cases, which fail for the documented reason on `main`.
- `ruff check` and `ruff format --check` clean on both files; `mypy` clean on both files.
- The completion note records the exact failing assertion produced by each new case (the red proof).

## Reviewer Guidance

- Are the new assertions built on the **real** CLI (not a helper)? Is there a positive control on the
  same fixture shape for every refusal assertion?
- Could this test pass on `main`? It must not: check that the `→ main` / no-squash assertions would
  catch the current behaviour. Run the test on `main` (or reason from the reproduction transcript in
  `research.md`) and confirm.
- Nothing outside `owned_files` may be modified.
