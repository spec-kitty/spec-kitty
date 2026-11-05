# Implementation Plan: Compare-and-swap branch delete for `doctor workspaces --prune`

**Branch**: `issue-7212-cas-landed-branch-delete` | **Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/cas-landed-branch-delete-01M6P3ER/spec.md`

## Summary

The landed-worktree prune proves a worktree's branch tip is absorbed into
`origin/<primary>`, removes the worktree, then deletes the branch. The delete is
`git branch -D` after a separate tip read, so a branch that moves in the window
between the read and the delete loses the new commit. The repository already
owns the compare-and-swap primitive for this (`ref_advance.delete_branch_ref`,
`git update-ref -d <ref> <expected>`, #5570) and uses it for the coordination
and orchestrator-api branch deletes; the landed prune is the third delete site
and reintroduced read-then-delete. The fix binds the landed delete to the
assessed tip: `guarded_branch_delete` gains an `expected_tip`, requires it under
`LANDED_INTENT`, records the discarded tip only when it is still the branch tip,
and deletes through `delete_branch_ref` instead of `git branch -D`. The prune
passes `verdict.tip` and maps the guard's moved-tip refusal onto its existing
`BRANCH_MOVED` vocabulary. The routing gate pins that the LANDED caller always
passes an expected tip.

**The prune's order is not the defect and does not change** (prove landed →
re-assess → remove worktree → delete branch): git refuses to delete a branch a
worktree has checked out, so the delete must come after the removal. The wrong
side is the delete primitive, which performed a second, unbound read of the ref.

## Technical Context

**Language/Version**: Python 3.11 (repo floor `>=3.11`)
**Primary Dependencies**: stdlib only for this change; `git` ≥ 2.38 (the prune's
`merge-tree` absorption proof already requires it)
**Storage**: git refs (`refs/heads/<branch>`, `refs/spec-kitty/discarded/<branch>`)
**Testing**: pytest with real throwaway git repositories (`pytest.mark.git_repo`,
`pytest.mark.non_sandbox`); architectural AST gates for routing/ownership
**Target Platform**: POSIX and Windows (git plumbing only; no `/proc` dependency
in this change)
**Project Type**: single project (`src/specify_cli`, `src/kernel`, `tests/`)
**Performance Goals**: no additional git subprocess per pruned branch
**Constraints**: no new destructive argv outside the guard-internal modules; no
behaviour change for the plain, `--force-recreate` and `--discard` deletes; the
operator-facing prune vocabulary is unchanged
**Scale/Scope**: one guard function, its one LANDED caller, one architectural
gate pin, three test files

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority / canonical-source-unification** — pass: the fix
  reuses `ref_advance.delete_branch_ref`; it adds no second `update-ref -d`
  implementation. The guard stays the one destructive chokepoint.
- **DIRECTIVE_044 (destructive-op routing census)** — pass: the new argv lives in
  the already-excluded guard-internal module; the gate gains an assertion, not an
  allowlist.
- **DIRECTIVE_024 (locality of change) / change-apply-smallest-viable-diff** —
  pass: the edit surface is the delete path plus tests and one doc paragraph.
- **DIRECTIVE_038 / ATDD-first** — pass: the red test drives the real prune entry
  point (`prune_landed` on a real repo) and the real guard API, not a helper.
- **acceptance-criteria-non-vacuity** — pass: the moved-ref assertion is paired
  with a same-fixture positive control (the unmoved branch is deleted); the guard
  test pairs the stale-tip refusal with a matching-tip success.
- **Ownership boundaries for mutating flows** — pass: the worktree removal and
  the branch delete stay in the guard; the prune still re-assesses before acting.
- No charter violation requires the Complexity Tracking table.

## Project Structure

### Documentation (this mission)

```
kitty-specs/cas-landed-branch-delete-01M6P3ER/
├── plan.md              # This file
├── research.md          # Phase 0: grounding, intended order, options rejected
├── data-model.md        # Phase 1: expected-tip value, refusal codes, delete states
├── quickstart.md        # Phase 1: how to reproduce and verify
├── contracts/
│   └── guard-branch-delete-cas.md   # Phase 1: the guard parameter contract
└── tasks.md             # Phase 2 (tasks step)
```

### Source Code (repository root)

```
src/specify_cli/git/destructive_guard.py       # expected_tip + CAS under LANDED_INTENT
src/specify_cli/git/ref_advance.py             # delete_branch_ref (reused; --no-deref hardening)
src/specify_cli/workspace/landed_worktrees.py  # pass verdict.tip; map the refusal
tests/specify_cli/git/test_destructive_guard*.py
tests/specify_cli/workspace/test_landed_worktrees.py
tests/architectural/test_destructive_op_routing.py
docs/development/how-to/pr-landing.md          # one paragraph: the delete is CAS
docs/changelog/unreleased/<pr>.fixed.md        # per-PR fragment
```

**Structure Decision**: single project. `destructive_guard` is the destructive
chokepoint (`specify_cli.git`), `landed_worktrees` is its caller
(`specify_cli.workspace`), and the architectural gate lives under
`tests/architectural/`. The touched module and the new guard branch exist only
on the open #7196 branch, so the Mission is stacked on
`issue-7173-landed-worktree-cleanup` (C-001).

## Complexity Tracking

No charter violations; the table is not needed.

## Implementation Concern Map

### IC-01 — Bind the landed delete to the assessed tip

- **Purpose**: Make the prune's branch delete a single compare-and-swap so a ref
  that moves in the window is kept instead of deleted.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001,
  NFR-002, NFR-003, C-002, C-003
- **Affected surfaces**: `src/specify_cli/git/destructive_guard.py`
  (`guarded_branch_delete`, `_discard_branch_keeping_tip`, new refusal codes),
  `src/specify_cli/workspace/landed_worktrees.py` (`_delete_landed_branch`, the
  module docstring paragraph that documents the non-atomic window)
- **Sequencing/depends-on**: none
- **Risks**: the tip-keep record must still be written *before* the delete
  (crash safety); a refused CAS may leave that create-only record behind, which
  is harmless and keeps the assessed tip reachable. The guard must not let
  `RefDeleteError` escape untyped.

### IC-02 — Pin the invariant in the routing gate and the runbook

- **Purpose**: Make a LANDED delete without an expected tip fail structurally,
  and stop the runbook from describing a non-atomic compare.
- **Relevant requirements**: FR-006, SC-003
- **Affected surfaces**: `tests/architectural/test_destructive_op_routing.py`
  (AST pin on the LANDED caller's keywords),
  `docs/development/how-to/pr-landing.md` (removal step wording)
- **Sequencing/depends-on**: IC-01
- **Risks**: the gate must stay content-keyed with no allowlist; the pin must be
  non-vacuous (a planted caller without `expected_tip` turns it red).

## Phases

### Phase 0: Outline & Research

See [research.md](research.md): the reproduction, the intended order traced
through the #7173 Mission record, the two prior CAS fixes for the same defect
class, the options considered (new raw argv vs. reusing `delete_branch_ref`),
and the disposition of each.

### Phase 1: Design & Contracts

See [data-model.md](data-model.md) for the expected-tip value, the refusal
codes and the delete state machine, [contracts/guard-branch-delete-cas.md](contracts/guard-branch-delete-cas.md)
for the guard's parameter contract, and [quickstart.md](quickstart.md) for the
reproduction and verification commands.
