---
work_package_id: WP08
title: Widen the destructive-op routing gate, empty its allowlist, retire is_residue
dependencies: [WP03, WP04, WP05, WP06, WP07, WP09]
requirement_refs:
- FR-006
- SC-003
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T19:33:42.127519+00:00'
subtasks:
- T043
- T044
- T045
- T046
- T047
phase: Phase 5 - Gate
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/consolidation/test_teardown_keeps_only_copy.py
- tests/consolidation/test_abort_keeps_other_mission_edits.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/architectural/test_destructive_op_routing.py
- tests/architectural/_destructive_op_census.py
- docs/changelog/CHANGELOG.md
- tests/consolidation/test_teardown_keeps_only_copy.py
- tests/consolidation/test_abort_keeps_other_mission_edits.py
- tests/coordination/test_coherence_integrity.py
- tests/git/test_ref_advance_git_paths.py
- tests/git/test_restore_branch_ref_resync.py
- tests/orchestrator_api/test_mission_branch_delete_cas.py
- tests/specify_cli/cli/commands/test_merge_residue_gate_single_authority_wp13.py
- tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py
- tests/specify_cli/cli/commands/test_issue_2795_claim_blocker.py
- tests/specify_cli/test_no_manual_ffmerge.py
- tests/mission_runtime/test_decision_ledger_reader_flips.py
- tests/context/test_is_mission_dir.py
- tests/consolidation/test_checkout_role_recovery.py
- tests/coordination/test_materialize_coord_surface.py
- tests/specify_cli/retrospective/test_tracer_writer_coord_e2e.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP08 – Widen the destructive-op routing gate, empty its allowlist, retire is_residue

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP08 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Close the defect class by construction (DIRECTIVE_043, ADR `2026-09-30-1`): the routing gate covers the full destructive set, its allowlist is empty, and the guard's `is_residue` parameter is gone.

Note on ownership: `owned_files` lists the gate files and the changelog. This WP also makes two justified out-of-map edits, sequenced after every routing WP so nothing runs in parallel with them: removing `is_residue` from `git/destructive_guard.py` and `git/ref_advance.py` (owned by WP02), and converting WP01's transitional reproductions (owned by WP01). Record a one-line rationale for each in the activity log.

## Subtasks

### T043 — Widen the patterns
`tests/architectural/test_destructive_op_routing.py` `_PATTERN_NEEDLES`: add `branch_delete_force: ("branch", "-D")`, `worktree_prune: ("worktree", "prune")`, `clean_force: ("clean", "-f")` (also match `-fd`, `-fdx` tokens: extend `_classify_argv` to match a token prefix for this one needle), `checkout_force: ("checkout", "--force")` and `("checkout", "-f")`, `stash_drop: ("stash", "drop")`. Widen the scanned roots to `src/specify_cli/`, `src/runtime/`, `src/charter/`, `src/kernel/`. Update the module docstring (the C-004 note that `branch -D` is out of scope is now false).

### T044 — rmtree AST check
New test in the same file: walk every `ast.Call`; refuse `shutil.rmtree(...)`, `rmtree(...)` imported from shutil, and `atexit.register(shutil.rmtree, ...)` outside `src/kernel/tree_removal.py`, `src/specify_cli/git/destructive_guard.py`, `src/specify_cli/asset_preservation/guard.py`, `src/charter/activation/synthesizer/path_guard.py`. These four are named module constants with a reason each, not `CensusKey` rows. Add the self-mutation non-vacuity test (a planted `shutil.rmtree` in a temp module is caught by the same scanner).
- Add a third check: `CheckoutRole.TOOL_OWNED` may be constructed only in the modules that create scratch or cache checkouts (`consolidation/workspace.py`, `consolidation/mission_number/bake.py`, `lanes/consolidation.py`, `review/baseline.py`, `charter_packs/sources/git_source.py`), named as a module constant with a reason each. Any other construction fails.

### T045 — Empty the allowlist
Delete every `_ALLOWLIST` entry. The guard's own internals (`git/destructive_guard.py`, `git/ref_advance.py`) are excluded by module, as today. The gate must pass. If a site is still caught, it was missed by WP03–WP07 or WP09: route it here with a test (record which WP missed it in the activity log) rather than re-adding a row. Keep the T020-style non-vacuity test working with an empty allowlist (it currently drops a real entry; switch it to planting a literal).

### T046 — Retire `is_residue`
Remove the `is_residue` parameter (and the exactly-one-of checks) from `assert_worktree_clean`, `guarded_worktree_remove`, `advance_branch_ref`, `restore_branch_ref`, `resync_checkouts_to_tip` and the private chain. `grep -rnw "is_residue" src/ tests/` must return nothing (no named survivors). Update the WP02 transition tests and every test file in `owned_files` that passes `is_residue=` (they switch to `context=`); check each hit is really the parameter, since some may only match a longer identifier.

### T046b — Tighten `guarded_merge_abort` (WP02 review, MEDIUM)
`guarded_merge_abort` exempts every path the merge touched, so an operator's half-done conflict resolution on a conflicted path is discarded without refusal. For each conflicted path (unmerged in the index), compare the working-tree file to git's conflict result (the file as `git merge` left it, with conflict markers); if it differs, refuse with `DESTRUCTIVE_OP_ONLY_COPY` naming it. Cleanly merged paths stay exempt. Add the refusal test and a positive control (untouched conflict → abort proceeds). Out-of-map edit on `git/destructive_guard.py`, sequenced after all routing WPs.

### T046c — Fix `_rmtree_writable` recursion on Python ≥ 3.12 (WP05 review, HIGH)
`git/destructive_guard.py` `_rmtree_writable`: the 3.12+ branch calls itself instead of `shutil.rmtree(path, onexc=<handler>)`, recursing to RecursionError; callers that suppress exceptions (Mission-creation rollback) then silently leave trees behind. Fix the branch (the `onexc` handler takes `(func, path, exc)`, not `exc_info`; adapt the existing `_make_writable_and_retry` or add a sibling). Add a test that exercises BOTH branches by monkeypatching `sys.version_info` (the local venv is 3.11) and a read-only file.

### T046d — Route the `--force-recreate` branch delete (WP05 review, MEDIUM)
`missions/_create.py::_delete_branch` (`--force-recreate`) is the last unrouted `branch -D`. Route it through `guarded_branch_delete` with an explicitly named keyword (for example `operator_intent="force_recreate"`) that skips the unique-commit check for that one intent only. Pin in the routing gate that `_create.py::_delete_branch` is the only caller passing it (AST check). Keep `tests/missions/test_create*` / `test_force_recreate_resets_diverged_branch_to_target` green. Out-of-map edits on `missions/_create.py` and `git/destructive_guard.py`.

### T046e — `guarded_tree_delete` must see ignored files (WP09 finding, HIGH)
`guarded_tree_delete` scans with `git status`, where ignored entries never count as dirty. Reproduced by WP09: with `.worktrees/` in `.gitignore`, a husk holding `work.py` is deleted by `fix_workspace_husks`. When `path` is not itself a checkout root (or the scan says the path is ignored by an enclosing checkout), treat every file under `path` as local state: refuse unless the classifier marks each one disposable. Add a red-first test (ignored husk with a file → refused) plus a positive control (empty husk → removed). Out-of-map edit on `git/destructive_guard.py`.

### T046f — Update `tests/architectural/test_mutation_ownership_routing.py`
`test_git_source_removal_literals_only_target_ephemeral_temps` pins the old `shutil.rmtree` literals in `charter_packs/sources/git_source.py`, which WP09 routed. Update it to the new helper calls (or retire the assertion if the destructive-op gate now covers it, with a note). Out-of-map edit.

### T046g — `--` separator in `guarded_branch_delete` (WP09 review, MEDIUM)
`guarded_branch_delete` runs `git branch -D <branch>` with no `--`, so a branch name starting with `-` is parsed as an option at every caller except the one WP09 protected with a leading-dash refusal. Add `--` before the name inside the guard (and in any other guard argv taking a ref or path), with a test using a name like `-x`.

### T047 — Transitional repros and changelog
- Per ADR 2026-07-17-1: after the fix, the WP01 reproductions stop being `regression`/`p0_repro` tests. Move each into a functional home (for example `tests/consolidation/test_teardown_keeps_only_copy.py` and `tests/consolidation/test_abort_keeps_other_mission_edits.py`), drop the transitional markers, keep the positive controls, and keep the data-loss assertions byte-identical to WP01's commit (the WP08 reviewer diffs them).
- `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink to it) `[Unreleased]`: bold impact-first lead with `(#5965, #5966)`, then before → after: consolidate and abort no longer delete uncommitted review feedback, traces or another Mission's edits; refused teardown exits with `COORD_TEARDOWN_KEPT_ONLY_COPY` and `--resume` finishes it; every destructive git operation and recursive checkout deletion goes through one guard; lane-retry reset and Mission-creation rollback now refuse over unique work. Run `uv run --frozen --no-sync python -m scripts.docs.check_spelling` (or the repo's codespell entry) if it exists.
- Also fold the WP01 review lows: move `_run_hard_killed` into `tests/terminus/rollback_harness.py` and reuse `rollback_harness.flat` in the moved #5965 test.
- Run: `.venv/bin/python -m pytest tests/architectural/test_destructive_op_routing.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py -q`, plus the moved functional tests; record counts.

## Definition of Done
Empty allowlist, widened gate green with non-vacuity proof, `is_residue` gone, transitional repros moved, changelog entry.

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
