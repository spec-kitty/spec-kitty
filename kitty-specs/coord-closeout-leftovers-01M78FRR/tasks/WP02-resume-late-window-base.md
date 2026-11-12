---
work_package_id: WP02
title: Resume after the kept-only-copy remedy completes (#7491)
dependencies:
- WP01
requirement_refs:
- C-002
- FR-001
- FR-002
- FR-003
- FR-004
- FR-013
- SC-001
planning_base_branch: fix/7598-coord-closeout-leftovers
merge_target_branch: fix/7598-coord-closeout-leftovers
branch_strategy: Planning artifacts for this mission were generated on fix/7598-coord-closeout-leftovers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7598-coord-closeout-leftovers unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
phase: Phase 2 - Closeout fixes
history:
- at: '2026-11-12T18:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/phase_teardown.py
create_intent:
- tests/consolidation/test_late_window_base_resume.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/phase_teardown.py
- tests/consolidation/test_late_teardown_projection.py
- tests/consolidation/test_late_window_base_resume.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Resume after the kept-only-copy remedy completes (#7491)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address all feedback; record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Fix #7491 (P1) per operator ruling Decision `01M78G590V8HGBR048SMBQK9WC`:

> Persist the post-projection coordination tip at reconciliation PASS; use it as the resume base
> only when `landing_verified_for_resume`; else `pre_mutation_coord_sha`. Cleared/restored with
> the PASS anchor.

Done when:
- **FR-001**: the #7491 reproduction (`research/repro_7491.py.txt`) driven through `spec-kitty consolidate` → commit the review cycle → `consolidate --resume` exits 0 with teardown complete.
- **FR-002**: on the same fixture, a late coordination commit that edits `kitty-specs/<slug>/spec.md` to bytes not on the target still refuses `COORD_LATE_PROJECTION_REFUSED`, naming `spec.md`.
- **FR-003**: unit cells prove both arms of the base selection.
- **FR-004**: the persisted tip is written with the anchor and cleared/restored with it.
- **FR-013** (fold #4380 item 2): the marker-kept refusal text at `phase_teardown.py:980-985` describes the real state.

## Context & Constraints

- Root cause (reproduced, `research/code-grounding.md` §1): `_late_window_base` (`phase_teardown.py:425-454`) returns `state.pre_mutation_coord_sha` on every resume, so `assert_late_window_landed` (`bookkeeping_projection.py:1338-1441`) re-walks the whole merge and refuses primary artifacts a lane brought in and the target later changed. A first run uses the in-memory `run.coord_tip_after_projection` (set `phase_bookkeeping.py:384`, advanced `phase_teardown.py:412-422`), never persisted.
- **Soundness (challenger, §7)**: a resume that re-runs phases checkpoints the LIVE coordination tip (`run_state.py:446`, `phase_claim.py:489`); a tip from a rolled-back attempt would skip `pre_mutation..live`. So the persisted tip may be used **only** when `landing_verified_for_resume(main_repo, state)` (`run_state.py:540-560`) is true — exactly the case where phases are skipped — **and** it is an ancestor of the live coordination tip.
- **Write it at PASS, not at bookkeeping capture**: `_record_reconciliation_pass` (`phase_gate.py:138-153`) saves the anchor; save the tip in the same `save_state`. Also keep it current where teardown advances `run.coord_tip_after_projection` after proving late commits (`_advance_approved_tip`, `phase_teardown.py:412-422`) — that advance happens only after the late window was proven landed, so a narrower persisted base is still sound.
- **Pairing**: WP01 added `ConsolidationState.clear_reconciliation_pass()` / `restore_reconciliation_pass(anchor)`. Extend them so they clear/restore the new field too. `restore_reconciliation_pass` must restore the pair: change it to accept the pair captured before the span (`anchor_before` in `executor.py:670` becomes a pair), or have the executor capture both. Keep the method names; adjust signatures as needed.
- `phase_teardown.py:305` advances the anchor to a cleanup commit sitting on the landing: the coordination tip stays as it is there.
- **C-002**: no exit code, gate severity or refusal code changes. **C-001**: no new restore path.
- Ownership-map leeway (record each in history): `consolidation/state.py` + `executor.py` (owned by WP01, done before this WP), `consolidation/phase_gate.py::_record_reconciliation_pass` (owned by WP03, which depends on this WP), and docstring-only edits in `consolidation/bookkeeping_projection.py` (owned by WP03) that still say "a resume spans since the merge began".
- Docs row for `COORD_LATE_PROJECTION_REFUSED` in `docs/api/cli-commands.md:127` is updated by WP07.

## Branch Strategy

- **Planning base branch**: `fix/7598-coord-closeout-leftovers`; **merge target**: `fix/7598-coord-closeout-leftovers`. Lane from `lanes.json`.

```bash
spec-kitty agent action implement WP02 --agent claude --mission coord-closeout-leftovers-01M78FRR
```

## Subtasks & Detailed Guidance

### Subtask T004 – Red: e2e #7491 reproduction + negative control

- **Purpose**: pin the bug through the real CLI entry point (`spec-kitty consolidate` / `--resume`) before any fix.
- **Steps**:
  1. In `tests/consolidation/test_late_teardown_projection.py`, add a builder that reuses `tests/terminus/conftest.py` helpers exactly like `research/repro_7491.py.txt`: `_init_fixture_repo(..., extra_base_files={SPEC: ...})`, lane WP01's planted commit also edits line 0 of `kitty-specs/<slug>/spec.md`, `_finish_coord_mission`, `_declare_subtask_rosters`, `_seed_matrix`, then the target commits line 0 + a different line 10 edit ("re-finalize on the target").
  2. Test `test_resume_completes_after_kept_only_copy_when_target_amended_planning` (#7491): `_refuse_teardown` → assert exit 76 → `commit_review_cycle()` → `resume()` → assert exit 0, coordination worktree and branch gone, and `spec.md` on the target byte-identical to before the resume.
  3. Negative control `test_resume_still_refuses_a_late_planning_edit_not_on_target`: same fixture, but the operator's late coordination commit ALSO edits `spec.md` line 5 → resume exits 1 and the output contains `COORD_LATE_PROJECTION_REFUSED` and `spec.md`.
  4. Run both on the base: the first must fail (exit 1, `NON_COORDINATION_RECORD_NOT_LANDED`/`COORD_LATE_PROJECTION_REFUSED` naming `spec.md`); the control passes on the base too (it is the ratchet). Commit `test(consolidation): reproduce #7491 resume refusal after the kept-only-copy remedy (red)`.
- **Cost**: ~35 s per case; mark like the neighbouring e2e tests in that module.

### Subtask T005 – Persist the tip with the PASS anchor

- **Steps**:
  1. `state.py`: add `coord_tip_after_projection: str | None = None` to `ConsolidationState` (docstring: #7491, written only with the PASS anchor; absent on legacy records). `from_dict` filters unknown keys (`state.py:335`), so old records load `None`.
  2. Extend WP01's `clear_reconciliation_pass` / `restore_reconciliation_pass` to cover the field (pair semantics).
  3. `phase_gate.py::_record_reconciliation_pass`: set `run.state.coord_tip_after_projection = run.coord_tip_after_projection` alongside the anchor, in the same `save_state`.
  4. `phase_teardown.py::_advance_approved_tip`: when it advances `run.coord_tip_after_projection` AND the state's anchor is set, persist the advanced tip (`save_state`).
  5. `executor.py`: capture the pair before the span and restore the pair in `_report_rollback`.

### Subtask T006 – Resume arm of `_late_window_base`

- **Steps**:
  1. Rewrite the resume arm:
     ```python
     if run.is_resume:
         verified = _verified_resume_base(run)
         return verified if verified is not None else run.state.pre_mutation_coord_sha
     ```
  2. `_verified_resume_base(run) -> str | None`: returns `state.coord_tip_after_projection` only when it is set, `landing_verified_for_resume(run.main_repo, run.state)` is true, and `git merge-base --is-ancestor <tip> <live coordination ref>` holds (use the existing ancestry helper in `consolidation/git_probes.py` or `run_state.py`; do not add a new raw `git` argv outside `kernel/git` if a gate forbids it — check `tests/architectural/test_git_path_listing_owner.py`). Otherwise `None`.
  3. Keep complexity ≤ 15. Update the `_late_window_base` docstring: the resume arm now narrows only after a verified landing.

### Subtask T007 – Unit cells for the base selection; docstrings

- **Steps**:
  1. `tests/consolidation/test_late_window_base_resume.py`: cells with a stub `_MergeRunState` (see `tests/consolidation/test_projection_teardown.py:793-806` for the existing shape) and a tiny real git repo for ancestry:
     - first run → `run.coord_tip_after_projection`;
     - resume, verified landing, tip ancestor of live coord → persisted tip;
     - resume, verified, tip NOT an ancestor (rewritten) → `pre_mutation_coord_sha`;
     - resume, not verified → `pre_mutation_coord_sha`;
     - resume, legacy record (`None`) → `pre_mutation_coord_sha`;
     - `clear_reconciliation_pass` clears both; restore restores both.
  2. Update the three docstrings that say a resume window spans since the merge began (`_late_window_base`, `_land_late_coordination_commits`, `bookkeeping_projection.assert_late_window_landed` ~1371-1373).

### Subtask T008 – #4380 item 2: truthful marker-kept teardown text

- **Steps**:
  1. `phase_teardown.py:980-985`: the `CoordinationTeardownError` says "the marker was left intact so the branch, its worktree and the marker stay consistent". When the worktree is already gone this misdescribes the state. Build the message from what is true: name the branch that still exists, say whether its worktree is still registered (read through the existing registered-worktree authority in `coordination/surface_resolver.py`, never name-guessing), keep the marker statement, and keep the remedy (`git worktree list` then `consolidate --resume`) only when a worktree still references the branch; otherwise say what holds the branch (e.g. a ref still checked out elsewhere is impossible once the worktree is gone, so the delete failed for another reason: name it as "the compare-and-swap delete refused" and suggest `consolidate --resume`).
  2. Add a red-first unit cell in `tests/consolidation/test_late_window_base_resume.py` (or the existing teardown test module if one covers `_teardown_coordination_triple`) for the worktree-gone wording.
  3. Keep the exception type and exit code unchanged (C-002).

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/consolidation/test_late_window_base_resume.py tests/consolidation/test_reconciliation_pass_pair.py
.venv/bin/python -m pytest -q tests/consolidation/test_late_teardown_projection.py tests/consolidation/test_projection_teardown.py tests/consolidation/test_teardown_refusal_resume.py
.venv/bin/python -m pytest -q --dist loadfile -n 8 tests/consolidation tests/coordination
.venv/bin/python -m pytest -q tests/consolidation/test_single_rollback_authority.py tests/architectural/test_merge_reconciliation_class_guard.py tests/architectural/test_git_path_listing_owner.py
ruff check / ruff format --check --force-exclude / mypy on changed files
```

## Risks & Mitigations

- Using the tip without a verified landing: guarded and unit-tested.
- A pre-existing stuck record (no persisted tip) stays stuck on `--resume`; documented in the spec assumptions (fresh run recovers).

## Review Guidance

- Red→green of T004 on the base vs final commit; the negative control green on both.
- Confirm the tip is written only in the PASS save, cleared/restored as a pair, and used only behind `landing_verified_for_resume` + ancestry.
- Leeway edits recorded in history.

## Progress & Status

Event log only: `add-history`, `move-task`, `status`.
