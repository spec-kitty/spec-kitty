---
work_package_id: WP03
title: 'Consolidate, abort and teardown: context wiring and refused-teardown handling'
dependencies: [WP02]
requirement_refs:
- FR-004
- FR-005a
- FR-005b
- C-004
- C-005
- NFR-001
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T18:22:03.118551+00:00'
subtasks:
- T013
- T014
- T015
- T016
- T017
- T018
- T019
phase: Phase 3 - Wiring
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_teardown_refusal_resume.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/consolidation/rollback.py
- src/specify_cli/coordination/workspace.py
- src/specify_cli/coordination/teardown.py
- src/specify_cli/consolidation/phase_teardown.py
- src/specify_cli/consolidation/state.py
- src/specify_cli/consolidation/run_state.py
- src/specify_cli/consolidation/_constants.py
- src/specify_cli/consolidation/entry_preflight.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/orchestrator_api/consolidation.py
- tests/coordination/test_coord_teardown_guard.py
- tests/specify_cli/coordination/test_workspace.py
- tests/consolidation/test_teardown_refusal_resume.py
- tests/specify_cli/coordination/test_teardown_single_seam_routing.py
- tests/specify_cli/coordination/test_workspace_mid8_guard.py
- tests/integration/test_mission_close.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – Consolidate, abort and teardown: context wiring and refused-teardown handling

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP03 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Make both reproductions from WP01 pass: pass this run's context at every consolidation destructive site, and turn a refused coordination teardown into a safe, resumable failure (operator decision A, research D3/D4).

## Subtasks

### T013 — Rollback resync and restore with context (#5966)
- `consolidation/rollback.py:688` `_restore_one` and `:762` `_resync_kept_coord_checkout`: replace `is_residue=is_toolchain_generated_churn` with the run's context. The run's Mission slug and stored topology are on `ConsolidationState` / the lanes manifest available to `rollback_to_snapshot`; thread them down (do not re-read `meta.json` per branch). Use the per-checkout role resolver from WP02.
- Update the `_resync_kept_coord_checkout` docstring: the predicate now keeps other Missions' files; drop "deliberately unchanged".
- Expected outcome: the #5966 reproduction passes (refusal naming Mission B's files, files intact).

### T014 — Coordination teardown with a coordination-role context (#5965)
- `coordination/workspace.py:355` `CoordinationWorkspace.teardown`: build the context inside with `ResidueContext.for_mission(repo_root, mission_slug, CheckoutRole.COORDINATION)` and pass `context=`. Keep the `(repo_root, mission_slug, mid8)` signature unchanged: about ten test files and five src callers (`consolidate.py`, `mission_type.py`, `missions/_create.py`, `mission_creation_rollback.py`, `phase_teardown.py`) reach it through `teardown_coordination_topology`, and none of them should change.
- `_remove_worktree_registration` (line 251, raw `worktree remove --force` on an already-gone path): switch to `guarded_worktree_prune` from WP02 or keep a single-registration removal through a guard helper; the raw argv must leave this module.

### T015 — Stop swallowing the refusal; skip the branch delete
- `coordination/teardown.py:246` `_destroy_coordination_worktree`: let `DestructiveOpRefused` propagate; keep the best-effort `except Exception` for every other failure (narrow the except to exclude the refusal).
- `teardown_coordination_topology` (line ~271): on the refusal, raise a new `CoordTeardownKeptOnlyCopy` exception (error code `COORD_TEARDOWN_KEPT_ONLY_COPY`, carrying the kept files and the worktree path) after persisting the retrospective (persist-before-destroy still holds).
- `consolidation/phase_teardown.py` `_teardown_coord_worktree` and the later branch-delete leg (line ~717 `branch -D` — the raw argv itself moves in WP04? No: phase_teardown.py is owned here, so route it through `guarded_branch_delete` in this WP too): when the refusal fires, skip the coordination branch delete, so the branch, worktree and marker stay together.

### T016 — Exit without rollback (brownfield scout: already structurally true)
- Add `COORD_TEARDOWN_KEPT_ONLY_COPY` and its dedicated exit code to `consolidation/_constants.py` (look at how `COORD_MOVED_AFTER_LANDING` / exit 75 is defined; pick an unused code and document it).
- Coordination teardown runs AFTER the rollback door (`executor.py` ~541-574 is the door; `settle_branch` ~578 then cleanup ~581 → `phase_teardown.py` `_teardown_coordination_triple` ~501). A teardown exception never reaches `rollback_to_snapshot`, and `rollback.py` `_refusal` (`reconciliation_passed_for_tip`) would refuse a verified target anyway. Pin both facts in a test (C-005); do not add a catch in the executor.
- Translate the exception to the exit code in `cli/commands/consolidate.py` next to the existing `CoordinationTeardownError` (~852) / `ProjectionTeardownAbort` (~868) handlers. `consolidate.py` is not in owned_files: record a one-line out-of-map rationale (it is the CLI translation point for this exact exception family). Prefer making `CoordTeardownKeptOnlyCopy` a subclass of `CoordinationTeardownError` with its own `exit_code`, so the existing handler covers it with no new branch.
- Do NOT add a `teardown_refused` field to the state: a refused teardown is derivable (PASS anchor equals the live target tip and the coordination branch still exists). If you find the derivation insufficient, add the field and justify it in `traces/design-trace.md`.
- The message (NFR-002): the kept files (max 20 + count), the worktree path, and the remedy "Commit the files on the coordination branch, or move them out of the worktree, then run `spec-kitty consolidate --resume`."

### T017 — `--resume` completes a refused teardown (FR-005b, D4)
- Resume phase selection is binary (`executor.py` `_resume_reconciliation_already_passed`, `run_state.py` ~511): after a PASS, a resume runs the gate-only path and then cleanup, so it reaches teardown again with no new short-circuit needed. Verify this with the test below before adding any code.
- Moved-out files: teardown proceeds.
- Committed files: `_land_late_coordination_commits` (`phase_teardown.py` ~334-382, #5570) already re-projects `pre_mutation_coord_sha..live coord tip` onto the target on resume. Reuse it; build no new path.
- **The real bug to fix (brownfield HIGH):** on a gate-only resume the teardown gate's expected coordination SHA falls back to `checkpoint.sha` (`phase_teardown.py` ~473), because `run.coord_tip_after_projection` is run-local and not persisted (`run_state.py` ~308). After `_land_late_coordination_commits` projects up to the live tip, re-anchor the gate's `expected_coord_sha` to the tip it projected up to. Write the red test first: refuse → operator commits the files inside `kitty-specs/<slug>/` → `--resume` → teardown succeeds and the files reach the target.
- Late projection only carries mission-dir paths (`_post_checkpoint_mission_paths`). The remedy text says: commit the files inside `kitty-specs/<slug>/` on the coordination branch, or move them out of the worktree. A late coordination commit that touches paths outside the mission dir refuses (it would otherwise be destroyed with the branch); test it.

### T018 — orchestrator-api, --abort, lane leg
- `orchestrator_api/consolidation.py` (`is_residue=functools.partial(...)` at ~427 and the `branch -D` at ~443): pass context; route `branch -D` through `guarded_branch_delete`. This path does not tear down the coordination triple (documented at ~313-318), so there is no teardown refusal to report there; spec C-004/FR-005a's orchestrator-api clause is N/A — note it in the activity log.
- `phase_teardown.py` `_remove_lane_worktrees` (~664) runs BEFORE coordination teardown: pass a LANE-role context, so a lane worktree holding uncommitted rework refuses the same way (spec edge case).
- `consolidate --abort`'s coordination teardown goes through the same `teardown_coordination_topology`, so it gets the refusal for free; add a test.
- `consolidation/entry_preflight.py` (`is_residue=` at 177-252): these are clean-checks (not destructive), but they call the guard's `assert_worktree_clean`; pass the context with the right role per checkout so WP08 can remove `is_residue`.

### T019 — Tests
- `tests/consolidation/test_teardown_refusal_resume.py`: refusal keeps target landed (target tip unchanged after the refusal), coordination branch + worktree present, exit code is the new one; resume after moving the files completes teardown; resume after committing inside the mission dir lands them on the target and completes teardown; a late commit outside the mission dir refuses; `--abort` with only-copy files refuses the same way; a lane worktree with uncommitted rework refuses.
- Update `tests/coordination/test_coord_teardown_guard.py`, `tests/specify_cli/coordination/test_workspace.py`, `tests/specify_cli/coordination/test_teardown_single_seam_routing.py`, `tests/specify_cli/coordination/test_workspace_mid8_guard.py` and `tests/integration/test_mission_close.py` for the new signature.
- Run WP01's reproductions with `SPEC_KITTY_RUN_P0_REPRO=1`: both must now pass, with their test bodies byte-identical to WP01's commit. Record `git diff <WP01 commit> -- tests/consolidation/test_coord_teardown_only_copy_5965.py tests/consolidation/test_abort_resync_other_mission_5966.py` (empty) in the activity log. Do NOT edit WP01's files (WP08 converts them).
- Blast radius: `.venv/bin/python -m pytest tests/consolidation tests/coordination tests/specify_cli/coordination tests/orchestrator_api -q -n 4 --dist loadfile` and record counts.

## Definition of Done
- Both reproductions green; refusal never rolls back a verified landing; resume path proven; all owned tests green.

## Reviewer guidance
- Reject any path where the coordination branch is deleted while the worktree is kept.
- Reject a rollback of the target after the refusal.

## Branch Strategy

- Planning branch: `fix/5965-5966-destructive-residue-context`; final merge target: `fix/5965-5966-destructive-residue-context` (it reaches `main` by PR).
- Execution worktrees are allocated per computed lane from `lanes.json` by `spec-kitty agent action implement <WP> --agent claude --mission destructive-residue-context-01M4KBPS`. Never create or guess a worktree path yourself.
- In a lane worktree, set `PYTHONPATH=$PWD/src:$PWD` (absolute) for any subprocess-driven CLI test, and run pytest with `.venv/bin/python -m pytest` from the repository root's venv; never a bare `uv run` (it re-syncs and rewrites `uv.lock` to a private mirror). If `uv.lock` shows as modified, `git checkout -- uv.lock` before committing.
- Run narrow, file-scoped pytest only; never `make test-full` or a whole `tests/` directory sweep from inside the WP.

## Standing rules for this WP

- Complexity ≤ 15 per function; ruff, `ruff format --check --force-exclude <files>` and mypy clean on every touched file. No new `# noqa` / `# type: ignore` without an inline reason.
- Every new branch or helper gets a focused test in the same commit (diff coverage ≥ 90%).
- Commit frequently with conventional messages that cite the issue (`fix(consolidate): ... (#5965)`), ending with the Co-Authored-By / Claude-Session trailers.
- Terminology: Mission, consolidate, coordination worktree, repository root checkout. Never "feature"; never bare "primary" or "merge" (name the sense).
- Append witnessed tooling friction, approach notes and design notes to `kitty-specs/destructive-residue-context-01M4KBPS/traces/*.md` (commit them immediately; mission commands can rewrite the mission directory).
