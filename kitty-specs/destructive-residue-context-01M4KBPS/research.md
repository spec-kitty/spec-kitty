# Research: Destructive ops never delete the only copy

## Squad provenance

Pre-spec research squad (2026-10-10, main `f810b924a9`): researcher-robbie (are the bugs still live?), architect-alphonso (root causes and shared code), paula-patterns (recurring-pattern check). Post-spec review: reviewer-renata (CHANGES REQUESTED, folded into spec commit `1ed4f7a2bd`).

## Decisions

### D1 — The guard owns the residue decision; callers pass context, not a predicate
- **Decision**: `guarded_worktree_remove`, `assert_worktree_clean`, `resync_checkouts_to_tip`, `restore_branch_ref` and `advance_branch_ref` take a required keyword `context: ResidueContext` and stop accepting `is_residue`. The guard calls `is_disposable_residue(path, context)`.
- **Rationale**: every recurrence in this family came from a caller passing the wrong or a context-free predicate (#4933, #5965, #5966). Removing the parameter makes the wrong call impossible to write.
- **Alternatives**: make `is_toolchain_generated_churn` arguments required (rejected: about 44 callers, most non-destructive gates that only block; a fail-safe there is already the safe answer); keep `is_residue` and add a lint (rejected: still a per-caller decision).

### D2 — `is_disposable_residue` composes the existing classifier with checkout-role rules
- **Decision**: in `coordination/coherence.py`, next to `is_toolchain_generated_churn`:
  1. a path under `kitty-specs/<other-slug>/` is never disposable;
  2. in the coordination worktree, a coordination-partition kind (`kind_is_coordination_residue` kinds: review cycle, traces/tracer, acceptance matrix, issue matrix, decisions) is never disposable; only self-bookkeeping (`is_self_bookkeeping_churn`) is;
  3. in the repository root, mission or lane checkout, delegate to `is_toolchain_generated_churn(path, mission_slug=..., topology=...)` with the stored topology;
  4. a context built from an unreadable topology cannot exist (construction refuses).
- **Rationale**: one classifier (C-001); the role rule is the missing invariant every squad lens converged on.

### D3 — A refused teardown fails the run; the landing stays
- **Decision**: `_destroy_coordination_worktree` lets `DestructiveOpRefused` propagate (other exceptions stay best-effort). `teardown_coordination_topology` and the consolidate teardown phase translate it into a new refusal `COORD_TEARDOWN_KEPT_ONLY_COPY` with its own exit code, skip the coordination branch delete, record `teardown_refused` in the consolidation state, and exit without entering the rollback door (the landing is already settled by its reconciliation PASS anchor). `orchestrator-api consolidate-mission` reports it as `PREFLIGHT_FAILED` with `data.teardown_error_code`, matching how it reports `COORD_MOVED_AFTER_LANDING`.
- **Rationale**: operator decision A (2026-10-10); C-005.

### D4 — `--resume` after a refused teardown
- **Decision**: `--resume` with `teardown_refused` set skips straight to the teardown phase. If the coordination tip moved since the refusal, the run re-projects the new coordination commits onto the target (the existing projection path) before re-running the teardown gate, so a commit the operator made to save the feedback reaches the target instead of being torn down. If the files were moved out instead, the tip is unchanged and teardown proceeds.
- **Rationale**: renata finding (d): without re-projection, the compare-and-swap gate refuses `PROJECTION_TEARDOWN_ABORTED`, a recovery dead end, and a commit left only on the coordination branch would be deleted with it.
- **Brownfield resolution (paula-patterns, post-tasks)**: re-projection already exists (`phase_teardown._land_late_coordination_commits`, #5570) and is reused. The one defect: on a gate-only resume the teardown gate expects `checkpoint.sha` because `coord_tip_after_projection` is not persisted; WP03 re-anchors it to the projected tip. Late projection carries only mission-dir paths, so the remedy says commit inside `kitty-specs/<slug>/` or move the files out, and a late commit outside the mission dir refuses. Teardown already runs after the rollback door, so D3 needs no executor catch. The orchestrator-api path never tears down the coordination triple, so its D3 clause is N/A. No `teardown_refused` state field: the condition is derivable.

### D5 — Every destructive operation has a guard entry point
- **Decision**: add `guarded_reset_hard`, `guarded_branch_delete` (allowed when the branch has no commit beyond its creation base or every commit is reachable from another ref; FR-009), `guarded_worktree_prune`, `guarded_merge_abort`, `guarded_tree_delete` (checkout directories) and `remove_tool_owned_tree` (asserts the path is under `.kittify/runtime/`, a `tempfile` root the caller created, or a managed-asset root proven by `asset_preservation`).
- **Rationale**: operator decision B (no ledger); ADR `2026-09-30-1`.
- **Layering amendment (tasks, 2026-10-10)**: `remove_tool_owned_tree(path, *, owned_root, reason)` lives in `src/kernel/tree_removal.py`, because `src/runtime/` and `src/charter/` sit below `specify_cli` in the enforced chain and cannot import the guard. It refuses (`TOOL_OWNED_PATH_UNPROVEN`) when `path` does not resolve inside `owned_root`, and refuses when `path` or any directory between it and `owned_root` contains a `.git` entry: a git checkout is deleted only through `guarded_tree_delete` in the guard. That is the run-time invariant that makes the static gate meaningful.

### D6 — Call-site inventory to route (main `f810b924a9`)
| Site | Op | Route |
|---|---|---|
| `charter_packs/sources/git_source.py:165` | reset --hard | `guarded_reset_hard` (pack cache checkout, tool-owned → context role `tool_owned`) |
| `lanes/worktree_allocator.py:1659` | reset --hard | `guarded_reset_hard`, lane role |
| `lanes/worktree_allocator.py:1914` | worktree remove --force | `guarded_worktree_remove`, lane role |
| `lanes/worktree_allocator.py:1147` | worktree prune | `guarded_worktree_prune` |
| `consolidation/resume_recovery.py:382`, `consolidation/git_probes.py:239` | reset --hard HEAD | `guarded_reset_hard` with the role of the checkout recovered |
| `consolidation/phase_teardown.py:717`, `orchestrator_api/consolidation.py:443` | branch -D | `guarded_branch_delete` |
| `core/mission_creation_rollback.py:163,240,246,262,352` | rmtree, prune, branch -D | `guarded_tree_delete`, `guarded_worktree_prune`, `guarded_branch_delete` |
| `missions/_create.py:456`, `cli/commands/agent/mission_create.py:200` | branch -D | `guarded_branch_delete` |
| `cli/commands/mission_type.py:1187,1234` | branch -D, worktree remove --force | guard |
| `core/vcs/git.py:252` | worktree remove --force | guard, or delete if still dead code |
| `coordination/workspace.py:268` | worktree remove --force (stale registration) | `guarded_worktree_prune` for the registration |
| `coordination/coord_seed.py:486`, `status/doctor_husks.py:180`, `core/worktree.py:559` | rmtree | `guarded_tree_delete` or `remove_tool_owned_tree` after reading each |
| `consolidation/workspace.py:79,128,142`, `consolidation/mission_number/bake.py:248,699`, `lanes/consolidation.py:1271,1348`, `review/baseline.py:294` | scratch worktree remove / rmtree | `remove_tool_owned_tree` / scratch helper |
| `state.py`, `lanes/consolidation.py`, `worktree_allocator.py` merge --abort sites | merge --abort | `guarded_merge_abort` |
| about 50 `shutil.rmtree` of temp, staging or managed-asset trees (charter_packs, skills, template, migrations, runtime bridge) | rmtree | `remove_tool_owned_tree`, or the existing `asset_preservation` guard where already used |

### D7 — Gate shape
- **Decision**: widen `_PATTERN_NEEDLES` with `branch -D`, `worktree prune`, `clean -f`, `checkout --force`, `stash drop`; add a second AST check that refuses any `shutil.rmtree` call outside `src/kernel/tree_removal.py`, `git/destructive_guard.py`, `asset_preservation/guard.py` and `charter/activation/synthesizer/path_guard.py`; empty `_ALLOWLIST`. The scan covers `src/specify_cli/`, `src/runtime/` and `src/charter/`.
- **Rationale**: telling a checkout path from a temp tree statically is not decidable; forbidding the bare call and routing through helpers that prove ownership at run time is.
- **Alternative rejected**: an allowlist of the 50 temp sites (a ledger; operator decision B).

## Findings disposition (post-spec review, reviewer-renata)

| Finding | Disposition | Evidence |
|---|---|---|
| FR-005 after-landing behaviour unspecified | accepted | spec FR-005a/FR-005b, C-005; D3, D4 |
| Root cause under-stated (topology missing at teardown) | accepted | spec Intent Summary "Root cause, precisely"; FR-002 |
| Missed ops: worktree prune, rmtree, workspace.py:268, baseline.py, core/vcs | accepted | spec Domain Language, FR-007; D6 |
| #5965 repro must use real move-task | accepted | spec US1 Independent Test, FR-008 |
| --abort / orchestrator-api / lane teardown scenarios | accepted | spec US1 AC4, edge cases |
| US2 "skip or refuse" disjunction | accepted (refuse) | spec US2 AC1 |
| branch -D assumption should be an FR | accepted | spec FR-009 |
| Gate must land after migration | accepted | spec FR-006; plan IC-05 sequencing |
| acceptance-matrix name check | accepted | `MissionArtifactKind.ACCEPTANCE_MATRIX` (`mission_runtime/artifacts.py:71`) confirmed |

## Findings disposition (post-tasks squad: reviewer-renata, paula-patterns)

| Finding | Disposition | Evidence |
|---|---|---|
| ~13 unowned tests reference `is_residue` | accepted | WP08 owned_files; strict `grep -rnw is_residue src/ tests/` done condition |
| `teardown` signature change reaches unowned tests | changed | WP03 keeps the signature; builds the context inside |
| WP02 sibling ref_advance tests | accepted | WP02 is additive, proven by running the siblings |
| TOOL_OWNED escape hatch at non-scratch sites | accepted | WP05 requires `guarded_tree_delete` for Mission-creation rollback; WP09 likewise for husks; WP08 gate confines TOOL_OWNED to named modules |
| Repro conversion could hide a weakened fix | accepted | WP03 records an empty diff of WP01 bodies; WP08 keeps assertions byte-identical |
| WP05 too large | accepted | split into WP05 and WP09 |
| Gate re-anchor on gate-only resume (HIGH) | accepted | WP03 T017 |
| Lane worktrees destroyed before coord refusal (HIGH) | accepted | WP03 T018 lane-role context |
| Late projection mission-dir only | accepted | WP03 T017 remedy + refusal |
| orchestrator-api D3 clause N/A | accepted | WP03 T018 |
| `teardown_refused` field redundant | accepted | WP03 T016 derives it |
