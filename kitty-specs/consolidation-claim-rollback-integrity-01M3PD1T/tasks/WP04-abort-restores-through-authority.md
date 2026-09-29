---
work_package_id: WP04
title: --abort restores through the authority (#5318)
dependencies:
- WP03
requirement_refs:
- FR-005
- FR-007
- FR-011
planning_base_branch: issue-5338-consolidation-claim-rollback-integrity
merge_target_branch: issue-5338-consolidation-claim-rollback-integrity
branch_strategy: Planning artifacts for this mission were generated on issue-5338-consolidation-claim-rollback-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5338-consolidation-claim-rollback-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
phase: Phase 3 - Recovery
history:
- at: '2026-09-29T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/consolidation/test_single_rollback_authority.py
- tests/terminus/test_repro_5318_abort.py
- tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/consolidation/test_single_rollback_authority.py
- src/specify_cli/cli/commands/consolidate.py
- tests/terminus/test_repro_5318_abort.py
- tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – `--abort` restores through the authority (#5318)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⛔ HARD RULE: no heavy full suites during the mission

During implement and **every WP review**, you AND every implementer/reviewer subagent you dispatch must NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave broad sweeps to the END of the mission or to CI (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission consolidation-claim-rollback-integrity-01M3PD1T` and the Activity Log for a `review_ref`; if present, every feedback item is your TODO list.

---

## Objectives & Success Criteria

Today `_dispatch_abort` (`src/specify_cli/cli/commands/consolidate.py:~407`) clears `state.json` and tears down the coordination worktree **without restoring any ref** — discarding the only snapshot, so the next fresh run captures the advanced base (#5318). Make `--abort` restore through WP02's single authority first.

Done means (FR-005, FR-007, FR-011, SC-005, SC-006):
- A failed consolidation followed by `--abort` leaves target, mission/coordination branch and lane branches at their pre-run SHAs, clears the record, and a fresh run after removing the cause exits 0 with work attributed.
- SC-005: after a failed run, moving the mission (or coordination) branch with plain git, then `--abort` → that branch keeps the moved SHA, is named "NOT restored" with observed/expected, the record is KEPT, exit code 1.
- FR-011: `--abort` on a record whose `reconciliation_passed_target_sha` equals the current target tip (crash mid-teardown) keeps the verified landing, keeps the record, exits 1 with the report.
- A pre-fix record without `pre_mutation_refs` keeps today's abort behaviour, printing a notice that no snapshot was recorded.
- The abort runs the rollback while holding the global consolidation lock; it refuses (exit 1, nothing touched) while another mission's merge holds a live lock.

## Context & Constraints

- Read: `spec.md` (FR-005/007/011, SC-005/006), `plan.md` IC-03 (abort bullet), `contracts/rollback-authority.md`, WP02's `consolidation/rollback.py`, WP03's wiring (snapshot + post tips are persisted by real runs).
- `_dispatch_abort` is NOT #5359-touched; `consolidate()` and `_run_real_merge` ARE — do not edit them.
- **Complexity**: `_dispatch_abort` is already 13 (measure with `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=1' src/specify_cli/cli/commands/consolidate.py`). `ruff.toml` has a per-file C901 ignore for consolidate.py, so local ruff will NOT warn, but Sonar S3776 will. Extract the new logic into `_abort_restore_or_keep_record(repo_root, state_entry) -> bool` (True = proceed with today's cleanup, False = keep record and exit 1) so `_dispatch_abort` stays ≤ 15.
- Lock API (reuse, no second lock path): `acquire_merge_lock` / `release_merge_lock_if_owned` / `is_merge_locked` / `read_merge_lock_owner` in `src/specify_cli/consolidation/state.py:~444-600`; the abort already releases via `release_merge_lock_if_owned("__global_merge__", …, owner_token=<mission_id>)` (:~471).
- Ordering inside `_dispatch_abort` when a state entry exists (post-tasks finding 7): (1) acquire/verify lock ownership, (2) the existing `abort_git_merge` scoped to the merge workspace + `_cleanup_merge_workspaces_for_state` (spec-kitty-owned scratch, always cleaned — otherwise a snapshotted branch checked out mid-merge in the conflict-resolution workspace makes the dirty check NOT_RESTORED and the abort sticky; verify what that workspace checks out), (3) `_abort_restore_or_keep_record`, and only if it returns True: (4) `clear_state` and `_teardown_coordination_for_abort`. Restore BEFORE clear/teardown.
- The AST pin `tests/consolidation/test_single_rollback_authority.py` (WP03-owned) has a caller floor constant of 1 with a note to bump: bump `_CALLER_FLOOR` to 2 and add the abort helper to the allowlist (file co-owned via sequential dependency).

## Branch Strategy

- **Strategy**: lanes (computed by finalize-tasks; see `lanes.json`)
- **Planning base branch**: `issue-5338-consolidation-claim-rollback-integrity`
- **Merge target branch**: `issue-5338-consolidation-claim-rollback-integrity`

Start with `spec-kitty agent action implement WP04 --agent claude --mission consolidation-claim-rollback-integrity-01M3PD1T` (after WP03 is approved).

## Subtasks & Detailed Guidance

### Subtask T018 – Red-first real-CLI repros (commit FIRST)

Post-tasks finding 3: WP03 already restores in-process on gate/projection refusals, so the red for `--abort` must come from a REAL exit OUTSIDE the gate phase, not from hand-written state. Use the #5385 shape (live-verified): the LANES fixture (`tests/terminus/lanes_fixture.py`) with a **protected `main` target** raises an uncaught `BookkeepingPolicyRefused` in `_phase_record_done_and_project` (:~1628) AFTER the squash, with post tips recorded after `_phase_mission_to_target` (confirm which phase raises and that its preceding record call ran; if the phase is different on this base, pick any real in-phase exit after `_phase_mission_to_target` and document it).

`tests/terminus/test_repro_5318_abort.py`:
1. **Restore on abort**: record pre-run SHAs (target `main`, mission branch, lanes) → `consolidate --yes` (crashes non-zero; target advanced, canceled content on `main` in the #5385 repro) → `consolidate --abort` → exit 0; target and mission branch at pre-run SHAs; `state.json` gone. RED today: abort leaves the target advanced.
2. **SC-005 CAS control**: same crash, then add one plain-git commit on the mission branch (another actor) → `--abort` → exit 1; the mission branch == the moved SHA; output names it "NOT restored … moved by another actor" with `expected == state.post_mutation_refs[<mission branch>]` (read state before abort); `state.json` still present. (Assert the reason text — it must fail for the CAS reason, not "no post tip".)
3. **Operator fix kept (post-tasks BLOCKER 2)**: coord fixture, gate FAIL (WP03 restores in-process), then rewrite the carrier lane with plain git to remove the canceled commit, then `--abort` → exit 0, the lane keeps the operator's commit, state cleared; a fresh `consolidate --yes` exits 0 with the approved WPs' files on the target (SC-002's `--abort` half).
4. **FR-011 verified landing**: a record whose `reconciliation_passed_target_sha` equals the target tip from a real run interrupted mid-teardown the way `tests/terminus/test_repro_5021.py` does → `--abort` → exit 1, target unchanged, record kept, "Kept the landing verified by an earlier reconciliation".
5. **Pre-fix record**: a real older-shape record (run a failing consolidate, then drop the new keys `pre_mutation_refs`/`restore_targets`/`post_mutation_refs` from `state.json` to model a record written by the previous release — document this) → today's abort behaviour (exit 0, state cleared) plus the notice "no pre-mutation snapshot was recorded".
6. **Live lock**: another mission holds `__global_merge__` with a live owner → `--abort` exits 1, nothing restored/cleared.
Markers: `integration`, `git_repo`, `regression`. Commit: `test(consolidate): red-first repros for --abort restoring the pre-mutation snapshot (#5318)`.

### Subtask T019 – `_abort_restore_or_keep_record`

```python
def _abort_restore_or_keep_record(repo_root: Path, state: ConsolidationState) -> bool:
    if not state.pre_mutation_refs:
        console.print("[yellow]Notice:[/yellow] no pre-mutation snapshot was recorded for this consolidation (older record); aborting without restoring branches.")
        return True
    report = rollback_to_snapshot(repo_root, state, target_branch=state.target_branch)
    console.print(report.render())
    return report.fully_restored
```
Call it in `_dispatch_abort` right after the state entry is resolved and lock ownership is established, before `abort_git_merge`/`_clear_merge_state_for_mission`/`clear_state`/`_cleanup_merge_workspaces_for_state`/`_teardown_coordination_for_abort`. On False: print "Kept the consolidation record so nothing is lost; resolve the branches named above, then re-run `spec-kitty consolidate --abort`." and `raise typer.Exit(1)`.

### Subtask T020 – Lock + messages + complexity

- Lock: if `is_merge_locked("__global_merge__", repo_root)` and `read_merge_lock_owner(...)` is a different, live owner → print a refusal and exit 1 before touching anything. `_lock_owner_is_dead` is private to `state.py` — do not import it; add (in state.py? no — state.py is WP02-owned and approved by now) or reuse a public predicate: prefer the existing public `release_merge_lock_if_owned` outcome semantics or add a tiny public wrapper `merge_lock_held_by_live_other(...)` in `consolidate.py` built from public functions only. Otherwise acquire (or confirm own) the lock for the duration of the restore; the existing release at the end stays.
- Final success line stays truthful: "Aborted consolidation for <slug>. Branches restored to their pre-consolidation commits; state and workspace cleaned up." only when the report was fully restored; the pre-fix path keeps today's line.
- Measure `_dispatch_abort` complexity (isolated ruff, see Context) ≤ 15; report the number in the Activity Log.

### Subtask T021 – Unit tests + targeted runs

- `tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py`: helper branches (no snapshot → True + notice; fully restored → True; UNCHANGED_BY_RUN only → True; not restored → False; verified landing → False) using small real repos or WP02's authority with real git (no mocking of git; mocking the console is fine).
- Run (record counts): the two new files; `tests/specify_cli/cli/commands/` tests for consolidate/merge abort (`grep -rl "dispatch_abort\|--abort" tests/specify_cli/cli/commands tests/terminus tests/merge | head` → run those files); `tests/consolidation/test_single_rollback_authority.py`; fast tier `tests/cli -m "fast or unit"` if abort tests live there; NAMED gates: `tests/architectural/test_merge_pipeline_ratchets.py`, `tests/architectural/test_no_legacy_terminology.py`, `tests/architectural/test_layer_rules.py`; ruff check/format + mypy on `consolidate.py`.

## Risks & Mitigations

- **Abort becomes "sticky"** when a branch cannot be restored → intentional (no information lost); the message tells the operator exactly what to fix.
- **Abort racing a live merge** → lock check first.
- **Coordination worktree dirty** → NOT_RESTORED, reported.

## Review Guidance

- Reviewer ≠ implementer; red→green verified per repro.
- Confirm restore happens BEFORE `clear_state` and coordination teardown (read the diff order).
- Confirm SC-005's moved branch is untouched (compare SHAs) — the CAS premise.
- Confirm `_dispatch_abort` ≤ 15 (isolated measurement) and no edit to `consolidate()` / `_run_real_merge`.
- HARD RULE respected.

## Activity Log

- 2026-09-29T13:00:00Z – system – Prompt created.
