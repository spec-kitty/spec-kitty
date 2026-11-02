# Implementation Plan: Lane self-heal public seam (#6898)

**Branch**: `issue-6898-lane-self-heal-public-seam` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/lane-self-heal-public-seam-01M6EJR6/spec.md`
**Input**: Mission specification from `kitty-specs/lane-self-heal-public-seam-01M6EJR6/spec.md`
**Issue**: [#6898](https://github.com/spec-kitty/spec-kitty/issues/6898)

## Summary

`implement_support.reenter_lane_self_heal` reaches into `worktree_allocator.py`'s privates
(`_merge_recorded_planning_commit`, `_merge_dependency_lane_tips`, `_validate_worktree_clean`)
to redo the allocator's own reuse-path self-heal from the outside. Add ONE public allocator seam,
`adopt_lane_ancestry()`, which owns "make this lane worktree current": validate the worktree under
an explicit, documented clean-worktree policy, capture the planning target tip (unless the caller
supplies it), merge the recorded finalize-tasks planning commit, then merge the approved
dependency lane tips. Route the allocator's own REUSE / CRASH_RECOVERY / FRESH sites through it,
route `reenter_lane_self_heal` through it, and delete the private-name import. A red-first
structural gate (`tests/architectural/test_lane_adoption_single_seam.py`) then keeps the defect
class closed: no module outside the allocator may import the adoption trio, and the allocator's
own routes must call the seam.

## Technical Context

**Language/Version**: Python 3.11+ (repo baseline), `mypy --strict`
**Primary Dependencies**: stdlib only for the change (`pathlib`, `typing.Literal`); existing
`kernel.git`, `specify_cli.lanes.*`
**Storage**: N/A (git worktrees + `lanes.json`)
**Testing**: pytest — new `tests/architectural/test_lane_adoption_single_seam.py` (AST guard,
self-mutation fixtures) and a behavioural test file under `tests/lanes/`; existing
`tests/lanes/test_planning_claim_self_heal.py`, `tests/lanes/test_lane_tip_record_points.py`,
`tests/agent/test_agent_action_lane_context_refresh.py` must stay green unmodified
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: no additional `git` subprocess on the self-heal path (NFR-001)
**Constraints**: no behaviour change (C-001); one authority for ordering + policy (C-002);
no full heavy suite locally (C-003)
**Scale/Scope**: 2 production modules (`lanes/worktree_allocator.py`, `lanes/implement_support.py`),
1 new architectural gate file, 1 new lane test file, 1 changelog fragment

## Charter Check

- **Single canonical authority** — the seam is the one owner of "adopt the recorded planning
  commit and the approved dependency tips", replacing two parallel copies. ✅
- **Architectural alignment / module seams** — the seam stays inside the allocator that owns the
  worktrees; the caller keeps only the WP-level decisions (planning vs code lane, approved-tip
  filtering, protected-root guard). ✅
- **ATDD / red-first** — the structural gate is written first and is red on `main`; the
  behavioural tests assert the existing contract before the refactor lands. ✅
- **Architectural gate discipline (Standing Order #5)** — the gate has a concrete floor
  (three route call sites, zero external imports), a self-mutation fixture proving it fires, and
  no allowlist. ✅
- **No full heavy suites in mission** — only the named lane/agent/architectural files run locally. ✅
- **Mission hygiene** — issue claimed (`status:claimed`, `taken-by-human`, assigned to the
  operator) before any planning artifact. ✅
- **Terminology canon** — "Mission", "work package", "lane"; no `feature` vocabulary. ✅

## Project Structure

### Documentation (this mission)

```
kitty-specs/lane-self-heal-public-seam-01M6EJR6/
├── spec.md              # Mission specification
├── plan.md              # This file
├── tasks.md             # Work-package outline
├── tasks/WP01-*.md      # Work-package prompt
└── traces/              # tooling-friction.md, approach.md, design-decisions.md
```

### Source Code (repository root)

```
src/specify_cli/lanes/
├── worktree_allocator.py    # + public adopt_lane_ancestry(); 3 route sites call it
└── implement_support.py     # reenter_lane_self_heal() delegates; private import deleted

tests/architectural/
└── test_lane_adoption_single_seam.py   # NEW: AST guard + self-mutation fixtures

tests/lanes/
└── test_lane_adoption_seam.py          # NEW: policy + ordering + behaviour tests

docs/changelog/unreleased/
└── <pr>.internal.md                    # NEW: tech-debt fragment
```

## Implementation Concern Map

- **IC-01 — The adoption seam (allocator).** `adopt_lane_ancestry()` in
  `src/specify_cli/lanes/worktree_allocator.py`: keyword-only `clean_worktree_policy`
  (`refuse-dirty` | `allow-dirty`, no default), optional `target_tip` with the seam capturing it
  from `lanes_manifest.target_branch`, and the fixed merge order (recorded planning commit →
  approved dependency lane tips).
- **IC-02 — Caller migration and behaviour freeze.** The three allocator routes and
  `implement_support.reenter_lane_self_heal` call the seam; `implement_support` loses its
  private-name import, its hand-threaded `capture_branch_tip` and its local
  `_validate_worktree_clean`; the code lane keeps `allow-dirty`, the planning lane keeps
  `refuse-dirty` plus its protected-root guard and approved-tip filtering.
- **IC-03 — Defect-class gate.** `tests/architectural/test_lane_adoption_single_seam.py`:
  symbol/policy floor, route-coverage floor, zero external imports of the adoption trio, and
  self-mutation fixtures proving the checker fires; written first and red on `main`.

## Design

### The seam

```python
def adopt_lane_ancestry(
    repo_root: Path,
    worktree_path: Path,
    mission_slug: str,
    lane: ExecutionLane,
    lanes_manifest: LanesManifest,
    *,
    clean_worktree_policy: Literal["refuse-dirty", "allow-dirty"],
    target_tip: str | None = None,
) -> None:
```

- **Required, keyword-only policy.** No default. `refuse-dirty` runs `_validate_worktree_clean`
  (the allocator's existing `DirtyWorktreeError`) BEFORE any merge; `allow-dirty` skips it and
  documents why (an in-flight WP's legitimate WIP; git's own merge machinery is the gate that
  matters, and it refuses a merge that would clobber dirty paths).
- **Ordering owned here, once.** `_merge_recorded_planning_commit` then
  `_merge_dependency_lane_tips` — the order the allocator's routes already use.
- **Target tip.** `target_tip=None` → the seam calls `capture_branch_tip(repo_root,
  lanes_manifest.target_branch)` itself (never a lane HEAD). Callers that already captured it per
  allocation pass it in, so the allocator keeps one capture per `allocate_lane_worktree` call.

### Call sites

| Site | Policy | Why |
| --- | --- | --- |
| `allocate_lane_worktree` REUSE | `refuse-dirty` | allocator-owned disposable lane checkout, new WP must not inherit a prior WP's dirt; the route's own `_validate_worktree_clean` call moves into the seam, in the same position |
| `allocate_lane_worktree` CRASH_RECOVERY | `refuse-dirty` | same, after re-attach |
| `allocate_lane_worktree` FRESH | `allow-dirty` | the worktree did not exist before this call, so it holds no user state to protect; a clean check would only add a new refusal for repositories that are dirty by construction (smudge filters, line-ending normalisation), and git's own merge machinery is the meaningful gate |
| `reenter_lane_self_heal` code lane | `allow-dirty` | re-entry for the SAME in-flight WP; WIP is legitimate |
| `reenter_lane_self_heal` planning lane | `refuse-dirty` | shared repository-root checkout: it must be clean and unprotected before reconciliation |

The allocator's REUSE and CRASH_RECOVERY routes drop their own `_validate_worktree_clean` call: the
seam's `refuse-dirty` *is* that check, applied once, in the same position relative to the merges. A
future route cannot forget the policy, and no route pays for the probe twice.

### `reenter_lane_self_heal` after the change

- Keeps: manifest read, `lane_for_wp`, planning-vs-code routing, `create_planning_workspace`,
  `assert_not_protected_branch`, approved-tip filtering (`replace(lane, depends_on_lanes=...)`),
  the `workspace_path.exists()` guard, `record_tip` for code lanes.
- Loses: the private-name import, the hand-threaded `capture_branch_tip`, the local
  `_validate_worktree_clean` call (now the seam's `refuse-dirty`).
- The `_planning_dir` docstring still references `_read_coordination_branch` as a *narrative*;
  that private import (`_read_coordination_branch`) is out of scope (C-005) but must not be
  introduced anywhere new.

### The structural gate

`tests/architectural/test_lane_adoption_single_seam.py`:

1. **Symbol floor** — `adopt_lane_ancestry` is defined in the allocator with `clean_worktree_policy`
   keyword-only and no default.
2. **Route coverage** — at least three allocator call sites of the seam (REUSE, CRASH_RECOVERY,
   FRESH all reach it), counted by AST, plus `implement_support` calls it.
3. **No second entry** — no module under `src/` other than `worktree_allocator.py` imports
   `_merge_recorded_planning_commit`, `_merge_dependency_lane_tips` or `_validate_worktree_clean`
   from it (any of: `from ... import (name)`, aliased import, `getattr` on the module is not
   counted — AST import forms only, which is what the defect used).
4. **Self-mutation** — a synthetic source string that imports `_merge_dependency_lane_tips` from
   another module is flagged by the same checker; a synthetic clean module is not.

Measured red-first: on `origin/main` (1) and (2) fail (no seam), and (3) lists the
`implement_support` import. After the change all four pass.

## Risks

- **Silent policy change.** The one real hazard: a code-lane caller accidentally getting
  `refuse-dirty`. Mitigated by: no default on the parameter (`mypy`/runtime TypeError), the
  explicit call-site table, and the behavioural dirty-code-lane test.
- **Double clean check.** Avoided: the REUSE and CRASH_RECOVERY routes drop their own
  `_validate_worktree_clean` call, so the probe happens once, inside the seam. FRESH adds none
  (`allow-dirty`), so the allocation path costs exactly what it did before.
- **A new refusal on the fresh path.** Avoided by `allow-dirty` there: a just-created worktree
  holds no user state, and a clean check could only regress repositories whose checkout is dirty
  by construction. The review round flipped this row from `refuse-dirty` for that reason.
- **Ordering.** Recorded planning commit first, dependency tips second, unchanged.

## Testing plan

| Surface | Command |
| --- | --- |
| New gate (red first on `main`, then green) | `uv run pytest tests/architectural/test_lane_adoption_single_seam.py -q` |
| New behaviour tests | `uv run pytest tests/lanes/test_lane_adoption_seam.py -q` |
| Existing self-heal contract | `uv run pytest tests/lanes/test_planning_claim_self_heal.py tests/lanes/test_lane_tip_record_points.py tests/agent/test_agent_action_lane_context_refresh.py -q` |
| Neighbouring lane suites | `uv run pytest tests/lanes -q` (bounded lane suite, not the full battery) |
| Architectural neighbours | `uv run pytest tests/architectural/test_lane_allocation_single_seam.py tests/architectural/test_no_dead_symbols.py -q` |
| Static | `uv run ruff check src/specify_cli/lanes tests/architectural/test_lane_adoption_single_seam.py tests/lanes/test_lane_adoption_seam.py`, `uv run mypy src/specify_cli/lanes/worktree_allocator.py src/specify_cli/lanes/implement_support.py` |
| Changelog fragment | `uv run --frozen python -m scripts.docs.check_changelog_style` |
