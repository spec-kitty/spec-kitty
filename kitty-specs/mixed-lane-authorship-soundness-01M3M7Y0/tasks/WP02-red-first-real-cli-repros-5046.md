---
work_package_id: WP02
title: 'Red-first real-CLI reproductions of #5046'
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
planning_base_branch: issue-5046-mixed-lane-authorship
merge_target_branch: issue-5046-mixed-lane-authorship
branch_strategy: Planning artifacts for this mission were generated on issue-5046-mixed-lane-authorship. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5046-mixed-lane-authorship unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mixed-lane-authorship-soundness-01M3M7Y0
base_commit: c04d2db37ab7446a9258599f0c340a5a90aeefcf
created_at: '2026-09-28T16:12:49.364603+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Red-first (#5046)
history:
- at: '2026-09-28T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/test_repro_5046.py
- tests/terminus/test_repro_5046_controls.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/terminus/test_repro_5046.py
- tests/terminus/test_repro_5046_controls.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Red-first real-CLI reproductions of #5046

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before reading further.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. All feedback items are your TODO list.

---

## Objectives & Success Criteria

Pin #5046 RED through the real `spec-kitty consolidate` entry point **before any product change** (C-006, charter ATDD-first, ADR 2026-07-17-1), plus same-builder positive controls (non-vacuity tactic: every refusal/absence assertion paired with a positive control on the same builder).

- `tests/terminus/test_repro_5046.py` — the defect cases (T006–T008). **RED on the mission base.** Use the same marker set as `tests/terminus/test_repro_5018.py` (`integration`, `git_repo`, `regression` — in `pytest.ini:56` `regression` means an issue-pinned end-to-end reproduction) — never `xfail`, never skipped. They go GREEN once WP05 (FAIL/REFUSE verdicts) and WP07 (REFUSE restores the target) are both in. CI note: `tests/terminus` runs in the consolidation module shard; these tests are red there until WP05+WP07 land — fine inside the mission, and the final PR contains all of them.
- `tests/terminus/test_repro_5046_controls.py` — positive controls (T009). **GREEN on the base and after WP05.**
- The activity log records the observed red/green matrix (T010).

## Context & Constraints

- Builder: `build_coord_mission_mixed_lane_canceled` from WP01 (`tests/terminus/conftest.py`). Helpers: `run_terminus`, `blob_present_at`, `git_rev`, `output_names_content_fail` (read its body — it may match the squash "un-attributable" wording; your new assertions must match the **canceled-content FAIL** wording defined below, not the generic one).
- Contract: `kitty-specs/mixed-lane-authorship-soundness-01M3M7Y0/contracts/attribution-and-verdicts.md` (verdict table C3, messages C4).
- **Verdict text to assert** (WP05 implements exactly this; keep the assertion to stable substrings):
  - FAIL: output contains `Reconciliation FAILED` **and** `canceled WP02` **and** each offending path (add/modify render as `carries canceled WP02's change`, deletions as `deleted by canceled WP02`).
  - REFUSE: output contains `Reconciliation refused (fail-closed)` **and** `WP02` **and** `no commit attribution`.
  - Both: exit code ≠ 0 **and** `git_rev(mission.repo, target)` equals the pre-consolidation target SHA captured before `run_terminus`, **and** the output names the lane (`lane-a`) and the recovery step (`re-run spec-kitty consolidate`) (NFR-003).
  - The CLI prints through rich, which word-wraps: collapse whitespace in stdout+stderr before substring matching (copy the normalisation `output_names_content_fail` uses, but do NOT use that helper for these assertions — it also matches the generic squash FAIL).
  - `blob_present_at(repo, ref, path)` is the helper signature.
- **Why the text matters:** FAIL and REFUSE both exit non-zero and restore the target; only the verdict text distinguishes them (post-spec BLOCKER 1).
- Runtime (NFR-004): one consolidation per test; group add+modify+delete into one build per strategy.
- Do NOT touch `src/`, `tests/integration/**`, or WP01's `conftest.py` (if the builder needs a change, raise it in the activity log / as review feedback to WP01 rather than editing it).

## Branch Strategy

- **Planning base / merge target**: `issue-5046-mixed-lane-authorship`. Workspace resolved from `lanes.json` via `spec-kitty agent action implement WP02 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T006 – FAIL repros, both strategies

- Build with `canceled_changes=[add src/pkg/wp02_new.py, modify src/pkg/shared.py (exists at base), delete src/pkg/legacy.py (exists at base)]`, `stamp_attribution=True`.
- `test_canceled_content_ships_under_default_squash_is_refused_as_fail`: capture target SHA, run default strategy, assert FAIL text naming all three paths, exit ≠ 0, target restored, and `blob_present_at(target, "src/pkg/wp02_new.py")` is False after the run.
- `test_canceled_content_ships_under_merge_is_refused_as_fail`: same with `--strategy merge`.
- Base-line RED expectation: exit 0, canceled content on target.

### Subtask T007 – Survivor-undone repros (SC-007, residual R1)

- Shape A: `survivor_before=[add src/pkg/survivor.py]`, `canceled_changes=[delete src/pkg/survivor.py]`.
- Shape B: `survivor_before=[modify src/pkg/shared.py → v1]`, `canceled_changes=[modify src/pkg/shared.py → base content v0]`.
- One build containing both shapes (different paths), default strategy; assert the FAIL verdict naming both paths (the gate decides this via `pre_state_by_survivor` — plan D-4), exit ≠ 0, target restored.
- **Why**: a naive "compare with the mission base" check would drop both (the canceled state equals the base) and ship the undo — the pre-state rule (plan D-3) must catch them.

### Subtask T008 – REFUSE repro (no attribution)

- `canceled_changes=[add src/pkg/wp02_new.py]`, `stamp_attribution=False`, default strategy.
- Assert REFUSE text, exit ≠ 0, target restored.
- Base-line RED expectation: exit 0.

### Subtask T009 – Positive controls [P] (GREEN before and after)

In `test_repro_5046_controls.py`, each asserting **exit 0** and the expected target content:
1. `superseded_by_survivor` (default + merge, two tests): canceled modifies `src/pkg/shared.py`, adds `src/pkg/tmp.py`; `survivor_after` rewrites `shared.py` fully and deletes `tmp.py`. Target carries WP01's `shared.py`; `tmp.py` absent.
2. `canceled_self_revert` (default): canceled modifies `shared.py` then sets it back to its pre-state within its own commits.
3. `lane_sync_merge_inside_canceled_session` (default): `lane_sync_merge_in_canceled_session=True` plus a superseded canceled change — the merge commit must not be flagged.
4. `never_implemented_cancel_squash_twin` (default): `canceled_entered_implementation=False` (the default-strategy twin of `test_repro_5018.py`'s merge-only pin).
5. `legacy_all_approved_lane_no_attribution` (default): same builder with `wp02_final="approved"`, WP02's changes planted, `stamp_attribution=False` → exit 0. (Pairs with T008 on the same builder: the canceled twin refuses.)

### Subtask T010 – Record the red/green matrix

- Run both files on the WP02 workspace (which does not yet contain WP05/WP07) and paste into the Activity Log, per T006–T008 test, the **failing assertion line**: it must be the verdict/exit assertion, with exit 0 observed and `blob_present_at(...)` True for a canceled path — a failure from a builder exception or a typo is not a valid red. Every T009 control must PASS. If a T006–T008 test is GREEN on the base, the repro is wrong — fix it before handing off.

## Test Strategy

```bash
PWHEADLESS=1 uv run --frozen pytest tests/terminus/test_repro_5046.py -q        # expect RED (all)
PWHEADLESS=1 uv run --frozen pytest tests/terminus/test_repro_5046_controls.py -q  # expect GREEN (all)
PWHEADLESS=1 uv run --frozen pytest tests/terminus/test_repro_5018.py -q          # unchanged GREEN
uv run --frozen ruff check tests/terminus/ && uv run --frozen ruff format --check tests/terminus/
```

## Risks & Mitigations

- Asserting only `exit != 0` would let a REFUSE satisfy a FAIL test — always assert the verdict substring.
- If the builder cannot express a shape, request a WP01 change rather than post-build mutation.

## Review Guidance

- Reviewer re-runs both files on the WP02 head and confirms: repro file RED for the stated reason, controls GREEN.
- Check every negative assertion has a positive control on the same builder.
- Check no `xfail`/`skip` on the repro tests.

## Activity Log

- 2026-09-28T15:40:00Z – system – Prompt created.
- 2026-09-28T17:40:00Z – orchestrator – T010 red/green matrix (implementer, confirmed by reviewer-renata spot check). RED on the WP02 lane (no WP05/WP07): `test_canceled_content_ships_under_default_squash_is_refused_as_fail`, `..._under_merge_...`, `test_survivor_undone_content_is_refused_as_fail`, `test_no_commit_attribution_is_refused_as_refuse` — each fails at `assert result.returncode != 0` with exit 0; debug runs showed `src/pkg/wp02_new.py` on the target, `shared.py` carrying WP02's content, `legacy.py` deleted, and (T007) WP01's `shared.py` v1 undone to the exact base bytes. GREEN: 6 controls + `test_repro_5018.py`. Approved in review cycle 2.
