# Implementation Plan: Merge/Git Destructive-Operation Safety

**Branch**: `fix/merge-destructive-op-safety` | **Date**: 2026-09-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/merge-destructive-op-safety-01M2XQF8/spec.md`

## Summary

Close a data-loss defect class: `spec-kitty merge` / `merge --abort` fire
destructive git commands (`reset --hard`, `worktree remove --force`,
`merge --abort`) against the operator's primary checkout and lane/coord worktrees
with no guard (#4752, #4753, #4754). Approach (Decision `guard_strategy`): introduce
**one** pre-mutation *refuse-before-destroy* guard in `src/specify_cli/git/`,
reusing the residue-aware dirty check (`ref_advance._dirty_entries`) and a new
typed refusal modeled on `RefAdvanceDirtyWorktreeError`; wire it into the
lane-based merge preflight (before the ref advance) and route all lane/coord
worktree force-removal through the `core/vcs/git.py remove_workspace` chokepoint.
Fold the two coupled same-seam surfaces (coord teardown, orchestrator-api cleanup
mirror); defer standalone `branch -D` unmerged-commit loss.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git (plumbing via `run_command`); typer/rich (CLI surface); internal seams `git/ref_advance`, `git/commit_helpers`, `merge/executor`, `merge/git_probes`, `merge/preflight`, `merge/state`, `core/vcs/git`, `coordination/workspace`, `coordination/coherence`, `orchestrator_api/commands`
**Storage**: N/A (git refs + worktrees; no datastore)
**Testing**: pytest — real-git integration harness (`tests/integration/test_merge_lane_planning_data_loss.py` Layer 2 pattern), plus focused unit tests and one architectural routing gate
**Target Platform**: Linux / macOS / Windows 10+ CLI
**Project Type**: single
**Performance Goals**: preserves the <2s CLI budget — the guard adds at most one `git status --porcelain` per worktree at preflight
**Constraints**: git-plumbing purity (no `specify_cli` import in `git/`; caller injects `is_toolchain_generated_churn`); pre-mutation atomicity (destructive call site unreachable on refusal); cyclomatic complexity ≤15; residue-aware (no false-positive block on the `meta.json` VCS-lock stamp); do not overload `SafeCommitHeadMismatch`
**Scale/Scope**: 1 shared guard primitive + 3 issue fixes + 2 folded sites; ~6–8 source files touched; 3 red-first `@regression` repros + unit tests + 1 arch gate

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ATDD-first (C-011)**: PASS — each issue lands a red-first `@pytest.mark.regression` repro (RED on base, GREEN after) as a separate first commit per WP, through the pre-existing merge/abort entry point (NFR-004).
- **Single canonical authority / unification (DIRECTIVE_044)**: PASS — the mission's premise is to unify one guard, not add a 10th parallel dirty predicate (FR-007, NFR-006 enforces it).
- **Architectural integrity + gate non-vacuity (DIRECTIVE_001/043)**: PASS — NFR-006 is a concrete, self-mutation-testable routing gate (destructive commands only behind the guard/chokepoint), not a vacuous allowlist.
- **Tiered rigour (tiered-standards)**: PASS — the guard primitive is core domain logic → highest rigour + direct unit tests; CLI wiring is glue → integration coverage.
- **Canonical sources (DIRECTIVE_044)**: PASS — reuse `_dirty_entries`, `_enforce_planning_artifact_target_branch`, `remove_workspace`; no improvised substitutes.
- **Git/workflow (DIRECTIVE_045)**: PASS — work on the mission lanes; PR to `main`; operator merges; no direct push.
- **Locality of change + smallest-viable-diff (DIRECTIVE_024/025)**: PASS — folds bounded to the same seam (coord teardown, orchestrator mirror); `branch -D` explicitly deferred (C-004).
- **Terminology canon**: N/A — internal git-safety change; no Mission/Feature user-facing surface introduced.
- **Supply chain (DIRECTIVE_051)**: N/A — no dependency added/upgraded/removed.

No violations → Complexity Tracking table empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/merge-destructive-op-safety-01M2XQF8/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding consolidation)
├── data-model.md        # Phase 1 output (guard primitive + typed refusal entities)
├── quickstart.md        # Phase 1 output (red-first repro recipe)
├── contracts/           # Phase 1 output (guard API + routing invariant contracts)
├── tracer-*.md          # Mission tracer files
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── git/
│   ├── ref_advance.py            # REUSE: _dirty_entries (residue-aware), RefAdvanceDirtyWorktreeError (pattern)
│   ├── destructive_guard.py      # NEW (proposed): unified refuse-before-destroy guard + typed refusal
│   └── commit_helpers.py         # SafeCommitHeadMismatch (do NOT overload — C-002)
├── merge/
│   ├── executor.py               # #4752 caller (_phase_capture_and_baseline); #4753 lane-cleanup loop; add preflight
│   ├── git_probes.py             # #4752 _refresh_primary_checkout_after_merge (reset --hard)
│   ├── preflight.py              # REUSE/EXTEND _enforce_planning_artifact_target_branch; add lane/coord dirty preflight
│   └── state.py                  # #4754 abort_git_merge scoping
├── core/vcs/git.py               # #4753 remove_workspace — the worktree-removal chokepoint (C-003)
├── coordination/
│   ├── workspace.py              # FOLD: teardown() force-remove; coord-triple coupling (FR-004)
│   └── coherence.py              # REUSE: is_toolchain_generated_churn (inject into guard — C-005)
├── orchestrator_api/commands.py  # FOLD: cleanup mirror of the executor loop (C-003)
└── cli/commands/merge.py         # #4754 _dispatch_abort

tests/
├── integration/                  # real-git red-first repros (#4752/#4753/#4754) + parity + --resume
├── git/ (or tests/specify_cli/git/) # guard primitive unit tests + residue false-positive test
└── architectural/                # NFR-006 routing/unification gate
```

**Structure Decision**: single project; the change is localized to the git/merge/coordination/vcs seams above. Exact new-module name (`git/destructive_guard.py`) and test homedirs are confirmed during the brownfield scout point-cut before WP01.

## Implementation Concern Map

| Concern | Scope | Requirements | Depends on | Notes |
|---------|-------|--------------|------------|-------|
| **IC-1 Guard primitive (enabler)** | New `git/` unified refuse-before-destroy guard: HEAD-on-target assertion + residue-aware worktree-clean check (reusing `_dirty_entries`) + new typed refusal exception; churn classifier injected by caller | FR-007, C-001, C-002, C-005, NFR-005 | — | Tidy-first foundation; direct unit tests incl. the `meta.json` VCS-lock residue fixture (NFR-003) |
| **IC-2 Primary-checkout preflight (#4752)** | Assert primary checkout on-target AND clean in lane-based merge preflight, BEFORE `_phase_mission_to_target` advances the ref; make `_refresh_primary_checkout_after_merge` a no-op/guarded when off-target | FR-001, FR-002, NFR-001, NFR-002, NFR-004 | IC-1 | Red-first via `_real_merge_external_mocks`; also covers `--resume` (AC US1.4) |
| **IC-3 Worktree-removal chokepoint + folds (#4753)** | Route lane cleanup through `remove_workspace`; preflight-detect dirty lane/coord worktrees → fail-closed unless retained; couple coord-triple retention; apply to `coordination/workspace.teardown` + `orchestrator_api/commands` mirror | FR-003, FR-004, FR-006, C-003, NFR-001 | IC-1 | Red-first; coord-triple atomic (CLAUDE.md #3131); scratch workspace excluded (C-006) |
| **IC-4 Abort scoping (#4754)** | Gate `abort_git_merge` on active spec-kitty merge state and scope to the merge workspace, not `repo_root`; fix the contradictory success line | FR-005, FR-006, NFR-002, NFR-004 | IC-1 (typed refusal optional here) | Red-first via a `_dispatch_abort` harness |
| **IC-5 Unification gate (NFR-006)** | Architectural/routed-call test: the three destructive commands execute only behind the guard/chokepoint; no new parallel dirty predicate | FR-007, NFR-006, SC-004 | IC-2, IC-3, IC-4 | Non-vacuous, self-mutation tested (DIRECTIVE_043) |

## Parallel Work Analysis

### Dependency Graph

```
IC-1 (guard primitive, enabler)
   ├── IC-2 (#4752 primary-checkout preflight)
   ├── IC-3 (#4753 chokepoint + folds)
   └── IC-4 (#4754 abort scoping)
                    ↓ (all three routed)
             IC-5 (unification arch gate)
```

- **Sequential**: IC-1 first (all fixes consume the guard). IC-5 last (asserts the routing is complete).
- **Parallel**: IC-2, IC-3, IC-4 are independent once IC-1 lands (disjoint call sites: git_probes/executor-preflight vs vcs/coordination/orchestrator vs merge/state+cli).
- **Coordination point**: IC-1's typed-refusal signature and guard entry API is the shared contract; freeze it in IC-1 (see contracts/) before IC-2–IC-4 branch.

### Ownership (no-overlap guard)

- IC-1 (WP01): `git/destructive_guard.py` — the guard primitive AND the shared
  `guarded_worktree_remove` seam (+ its test module).
- IC-2+IC-3 (WP03): `merge/executor.py` (preflight in the outer driver + cleanup
  routing), `merge/git_probes.py`, `merge/preflight.py`. WP03 solely owns the
  `merge/` surface — resolving the earlier executor.py ownership overlap.
- IC-3 folds (WP02): `coordination/workspace.py`, `orchestrator_api/commands.py`.
  NOTE (brownfield scout): `core/vcs/git.py remove_workspace` is a dead adapter
  (zero callers) and is NOT owned/touched — the chokepoint is WP01's
  `guarded_worktree_remove`, which the live inline destroys route through.
- IC-4 (WP04): `merge/state.py`, `cli/commands/merge.py`.
- IC-5 (WP05): `tests/architectural/`.

No cross-owner edits: WP03 CALLS WP01's `guarded_worktree_remove` (does not edit
WP02's files); WP02 routes the coord/orchestrator destroys by editing its own
files. Ownership is disjoint (confirmed by finalize-tasks + the anti-laziness lens).
