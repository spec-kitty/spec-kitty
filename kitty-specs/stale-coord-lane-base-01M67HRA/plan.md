# Implementation Plan: Stale coord lane base (#6753)

**Branch**: `issue-6753-stale-coord-lane-base` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/stale-coord-lane-base-01M67HRA/spec.md`
**Input**: Mission specification from `kitty-specs/stale-coord-lane-base-01M67HRA/spec.md`

## Summary

A fresh code lane on a coordination-topology Mission is parented on the
coordination branch by design (`_resolve_lane_parent`, C-005/FR-006). When the
target branch advances after the coordination branch is minted, the lane is cut
behind the target and nothing says so. This mission does two things and nothing
else:

1. **Make the gap visible.** At a fresh coord-topology lane allocation, compare
   the ref the lane is cut from against the target tip (one `git merge-base
   --is-ancestor`). When the base does not contain the target tip, print one
   `WARNING:` naming the base ref, the target branch, the missing target commit
   and the runnable remedy. Stay silent when the base is current or the probe
   cannot answer.
2. **Make the remedy reachable.** `spec-kitty agent action implement` — the path
   `next` and the `/spec-kitty.implement` shim dispatch — accepts `--base` and
   threads it to the same allocator seam the internal `spec-kitty implement`
   command already uses.

The topology default, every `UnhonorableBaseError` refusal route and the
legacy-topology path are untouched.

## Technical Context

**Language/Version**: Python 3.13 (repo floor 3.11)
**Primary Dependencies**: Typer (CLI), pytest (`pytest.ini` sets `pythonpath = src`)
**Storage**: N/A (git refs only; no persisted state is added)
**Testing**: `pytest` with the `unit`/`fast`/`git_repo` markers; fixtures build
throwaway git repos under `tmp_path` exactly as
`tests/specify_cli/lanes/test_worktree_allocator_coord.py` does
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single project (`src/specify_cli`, `tests/`)
**Performance Goals**: the probe adds at most one `git merge-base --is-ancestor`
subprocess per fresh coord allocation and zero on every other route (NFR-001)
**Constraints**: no new refusal route, no automatic merge/rebase/fast-forward of
either branch, one new CLI option only (C-001..C-005)
**Scale/Scope**: two source modules (`lanes/worktree_allocator.py`,
`cli/commands/agent/workflow*.py`) plus tests and a changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
| --- | --- |
| Single canonical authority | **PASS** — the probe reuses `capture_branch_tip` (target tip) and the existing `WARNING:` stdout convention; no second branch-resolution authority is introduced. |
| Architectural alignment | **PASS** — the check lives in the allocator (the one place a lane parent is decided), not in a CLI command, so every caller (`implement`, `next`, orchestrator-api) gets it. |
| DDD + tiered rigour | **PASS** — the change is a read-only diagnostic plus one option threaded through an existing seam; no aggregate or boundary moves. |
| ATDD-first | **PASS** — see Risk/Red-first below: both halves ship a failing test through the pre-existing entry point first. |
| Terminology adherence | **PASS** — "coordination branch", "target branch", "lane base", "fresh lane allocation" are used as `docs/context` defines them. |
| C-001 default parent unchanged | **PASS** — `_resolve_lane_parent` is not edited. |
| C-002 warn, do not refuse | **PASS** — no `StructuredError` subclass is added; the probe cannot fail allocation. |
| Boy Scout / locality | **PASS** — edits stay in the two modules that own the decision and its dispatch; no drive-by refactor. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/stale-coord-lane-base-01M67HRA/
├── spec.md              # Mission specification
├── plan.md              # This file
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
├── tasks/               # Work-package prompts
├── issue-matrix.json    # Tracker verdicts (#6753)
└── traces/              # approach / design-decisions / tooling-friction
```

### Source Code (repository root)

```
src/specify_cli/
├── lanes/
│   └── worktree_allocator.py        # stale-base probe + warning (FRESH_COORD arm)
└── cli/commands/
    ├── implement.py                 # the existing top-level --base (unchanged reference)
    └── agent/
        ├── workflow.py              # agent action implement: new --base plumbing
        └── workflow_cores.py        # ImplementRequest gains `base`

tests/
├── specify_cli/lanes/
│   ├── test_worktree_allocator_coord.py            # existing coord fixtures (reused shapes)
│   └── test_issue_6753_stale_coord_lane_base.py    # NEW: probe + warning + parentage
└── specify_cli/cli/commands/agent/
    └── test_issue_6753_agent_action_implement_base.py  # NEW: --base accepted + threaded
```

**Structure Decision**: single project; the mission touches the allocator that
owns the lane-parent decision and the two CLI modules that dispatch to it. Tests
go beside their subjects (`tests/specify_cli/lanes/`,
`tests/specify_cli/cli/commands/agent/`) and follow the existing throwaway-git
fixture style rather than inventing a new harness.

## Red-first proof (per DIRECTIVE_034 / ATDD-First)

Both halves are defects with a pre-existing entry point, so both get a failing
test before the fix:

- **FR-001/FR-002/FR-003**: `allocate_lane_worktree` on a coord fixture whose
  target advanced past the coordination branch. Asserted through `capsys`: today
  the output is empty (red), after the fix it carries the warning, and the same
  fixture with a current coordination branch stays silent (positive control).
- **FR-004**: `CliRunner().invoke(workflow.app, ["implement", WP, "--mission",
  slug, "--agent", agent, "--base", "main"])`. Today Typer exits 2 with
  `No such option: --base` (red). After the fix the run reaches the dispatch
  point with `base="main"` captured, while the same invocation without `--base`
  captures `None` (positive control).

## Complexity Tracking

No charter violations; nothing to justify.

## Implementation Concern Map

### IC-01 — Stale-base probe and report at fresh coord allocation

- **Purpose**: turn the silent stale cut into a named, actionable warning at the
  one place the lane's parent ref is decided, so every caller inherits it.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-006, NFR-001, NFR-002,
  NFR-003, SC-001, SC-002.
- **Affected surfaces**: `src/specify_cli/lanes/worktree_allocator.py` (the
  `FRESH_COORD` arm of `allocate_lane_worktree`, a new private probe helper
  beside `_ensure_branch_exists`); `tests/specify_cli/lanes/test_issue_6753_stale_coord_lane_base.py`.
- **Sequencing/depends-on**: none (first).
- **Risks**: the message must name a commit id that a reader can verify; it must
  degrade to silence when `capture_branch_tip` returns `None` or git fails, and
  it must not fire on reuse/crash-recovery/legacy/planning routes (NFR-001).

### IC-02 — `--base` on `agent action implement`

- **Purpose**: give the documented, dispatched agent path the same explicit-base
  escape the internal top-level command already has, so the warning's remedy is
  runnable where agents actually are.
- **Relevant requirements**: FR-004, FR-005, SC-003, SC-004.
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/workflow.py`
  (`implement` option surface + the `_create_workspace` dispatch),
  `src/specify_cli/cli/commands/agent/workflow_cores.py` (`ImplementRequest`);
  `tests/specify_cli/cli/commands/agent/test_issue_6753_agent_action_implement_base.py`.
- **Sequencing/depends-on**: IC-01 (the warning is what points at the option),
  but the two are independently revertible — see SC-004's half-by-half proof.
- **Risks**: the option must reach the allocator only on the create path, must
  not swallow the reuse/crash-recovery/dependency refusals, and must keep the
  planning-lane "ignored" warning unchanged.
