# Implementation Plan: Implement lane-allocation integrity

**Branch**: `fix/implement-lane-recut-and-planning-commit-integrity` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/implement-lane-recut-and-planning-commit-integrity-01M3CM55/spec.md`

## Summary

Two fail-closed / correctness fixes in the `implement` lane-allocation seam, folded into one mission because they share a module and call chain (`allocate_lane_worktree` → `_merge_recorded_planning_commit`):

1. **#4889 (P0)** — `allocate_lane_worktree` routes on two structural predicates (`worktree_path.exists()` REUSE, `_branch_exists()` CRASH_RECOVERY) and falls through to a FRESH route that consults **no** WP lane state. A lane destroyed (worktree + branch both gone) while its WP is non-terminal is indistinguishable from a never-allocated lane → silent empty re-cut, exit 0, committed work stranded. Fix: a fail-closed pre-flight **inside `allocate_lane_worktree`** (covering both callers — the CLI `create_lane_workspace` and the orchestrator-api `_resolve_start_workspace`) keyed on persisted `WorkspaceContext` + non-terminal canonical status + both refs gone + persisted tip **not** reachable on target.

2. **#4905 (P1)** — on coord/`lanes_with_coord`, the agent-verb lifecycle commit stages the PRIMARY-partition `tasks/WP*.md` onto the coordination branch at three sites, all through the shared sink `_commit_via_coordination_transaction`. The next lane's FR-009 planning merge then hits an add/add conflict. Fix: partition staged paths by artifact kind at the shared sink so a `WORK_PACKAGE_TASK` file routes to the PRIMARY target and never lands on coord.

Both are dogfooded on this very mission (coord topology). Fail-closed posture, smallest-viable-diff, red-first per ADR 2026-07-17-1.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: no new dependencies (stdlib + existing `specify_cli`, `mission_runtime`, `kernel`, `spec_kitty_events` surfaces); `pytest` for tests. This mission adds/upgrades/removes **zero** dependencies, so the supply-chain-install-safety gate is N/A (recorded in research.md).
**Storage**: git (branches, worktrees, refs); `.kittify/workspaces/<slug>-lane-<id>.json` (persisted `WorkspaceContext`); `status.events.jsonl` (append-only canonical status log)
**Testing**: `pytest` — unit + regression (`@pytest.mark.regression`) in `tests/lanes/`, `tests/specify_cli/`, `tests/orchestrator_api/`; targeted file-scoped runs, not whole-suite
**Target Platform**: Linux/macOS/Windows dev environments (the CLI)
**Project Type**: single (Python CLI + library)
**Performance Goals**: N/A — correctness/reliability fix; no hot path changed. Added git ancestry probe (FR-009) runs only on the already-slow fresh-allocation path.
**Constraints**: every added/modified function complexity ≤ 15 (Ruff C901 / Sonar S3776); no new `# noqa`/`# type: ignore`; new branches/helpers covered by focused tests in the same change; read status from the resolved coordination surface, never the sparse-excluded lane tree
**Scale/Scope**: two write sites + a shared regression WP; ~3 source files touched (`lanes/worktree_allocator.py`, `cli/commands/agent/workflow.py` + `workflow_executor.py`), plus tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter (`.kittify/charter/charter.md`) governing points applied:

- **Single canonical authority** — #4889 reuses the existing `WorkspaceContext` + status reducer (no second lane-state authority); #4905 reuses the existing `commit_to_primary_target` / `is_primary_artifact_kind` partition mechanism rather than a new merge driver. ✅
- **ATDD / red-first (Standing Order #4, ADR 2026-07-17-1)** — each defect lands an issue-pinned `@pytest.mark.regression` repro RED through the real entry point before the fix. ✅
- **Architectural gate discipline (Standing Order #5)** — the fix is placed by construction at the shared seam both callers / all three staging sites pass through, so the defect class is closed rather than patched per-caller. ✅
- **Smallest-viable-diff + locality (RECONCILE_CHANGE_SCOPE_TENSIONS)** — two write sites; already-polluted coord corpora and an auto-recovery subcommand are explicitly out of scope. ✅
- **Terminology canon** — "Mission"/"work package"/"lane"; no `feature*` aliases introduced. ✅
- **Model discipline** — implement=sonnet, review=opus, profile-loaded delegations. ✅

No violations to justify (Complexity Tracking empty).

## Project Structure

### Documentation (this mission)

```
kitty-specs/implement-lane-recut-and-planning-commit-integrity-01M3CM55/
├── plan.md              # This file
├── spec.md              # Committed
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (behavioural contracts)
├── checklists/          # requirements.md (spec quality)
├── traces/              # approach / design-decisions / tooling-friction
└── tasks/               # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── lanes/
│   ├── worktree_allocator.py     # WP01: fail-closed destroyed-lane pre-flight before FRESH routes (covers both callers)
│   ├── implement_support.py      # WP01: create_lane_workspace — call site of the allocator (CLI caller)
│   └── recovery.py               # (read-only reference: WorkspaceContext helpers; not an allocator caller)
├── cli/commands/agent/
│   ├── workflow.py               # WP02: _commit_via_coordination_transaction — the shared sink; partition paths by kind
│   └── workflow_executor.py      # WP02: three staging sites funnel here (claim 876 / resume 1061 / review-claim 1736)
├── orchestrator_api/
│   └── commands.py               # WP01: _resolve_start_workspace (second allocator caller) — covered for free by allocator-level guard
├── workspace/context.py          # persisted WorkspaceContext (load/save/find_context_for_wp) — read by WP01
└── mission_runtime/…             # is_primary_artifact_kind — reused by WP02

tests/
├── lanes/                        # WP01 + WP03 regression (allocator routes)
├── specify_cli/ (cli/commands)   # WP02 coord-staging regression
└── orchestrator_api/             # WP01 caller-independence regression
```

**Structure Decision**: single Python project; changes are localized to `src/specify_cli/lanes/` (WP01) and `src/specify_cli/cli/commands/agent/` (WP02), with the WP01 guard placed inside the shared allocator so the orchestrator-api caller is covered without editing `orchestrator_api/commands.py`.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*

## Parallel Work Analysis

### Dependency Graph

```
WP01 (#4889 fail-closed detector, lanes/worktree_allocator.py)  ─┐
                                                                  ├─→ WP03 (shared regression + FR-009 resilience)
WP02 (#4905 coord-staging partition, agent/workflow*.py)        ─┘
        WP01 ∥ WP02  (write-scope-disjoint, no inter-gating)     then  WP03 depends on {WP01, WP02}
```

### Work Distribution

- **Sequential work**: none up front — WP01 and WP02 have disjoint write scopes (verified by the post-spec architecture lens: the orchestrator status commit in `coordination/status_transition.py` is already partitioned and stages only status artifacts to coord, so #4905 is confined to the CLI `workflow*.py` path and does not touch WP01's `worktree_allocator.py`).
- **Parallel streams**:
  - WP01 — `lanes/worktree_allocator.py` (pre-flight guard), reading `workspace/context.py` + the status reducer.
  - WP02 — `cli/commands/agent/workflow.py` + `workflow_executor.py` (partition staged paths by kind at the shared sink).
- **Convergence**: WP03 lands the cross-cutting regression proof (RED-first repros for #4889 across REUSE/CRASH_RECOVERY/FRESH + both callers; #4905 across claim + review-claim) plus any FR-009 `_merge_recorded_planning_commit` resilience assertion. It depends on both fixes being present so its green state is meaningful.

### Coordination Points

- **Sync schedule**: `spec-kitty merge` consolidates the lanes into the feature branch after all WPs are approved.
- **Integration tests**: WP03 exercises both defects end-to-end through the real `implement` / `agent action implement` entry points on a coord mission; the review-claim assertion (SC-003) guards the multi-site #4905 fix.

## Phase 0 / Phase 1 outputs

- `research.md` — decision log (detector placement, status-key breadth, false-positive bound, #4905 shared-sink partitioning) + supply-chain N/A record + adversarial-evidence dispositions from the post-spec lens.
- `data-model.md` — the lane-allocation route state, `WorkspaceContext` fields, the destroyed-lane decision table, and the coord-commit path-partition rule.
- `contracts/` — behavioural contracts for the fail-closed detector and the coord-staging partition.
- `quickstart.md` — how to reproduce both defects and verify the fixes.
