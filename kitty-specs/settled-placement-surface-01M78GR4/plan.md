# Implementation Plan: One placement surface after topology settlement

**Branch**: `fix/7546-settled-placement-surface` | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/settled-placement-surface-01M78GR4/spec.md`

## Summary

After settlement a default Mission's branch is held by the coordination worktree, but several
write paths still assume the repository root checkout holds it. Make the placement seam's
`write_dir(kind).surface_root` the single answer to "which checkout holds this write" (operator
ruling, decision `01M78GRZDX410TZ1V8H1ZVC1EM`), then route the commit router, the protected-branch
preflights, the baseline commit, the target-branch helpers and the path-convention renderer through
it. No topology read changes (resolution already returns the settled value), no refusal or exit
code changes, no ProtectionPolicy change.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); no dependency added, removed or upgraded (no supply-chain surface)
**Storage**: git refs and the Mission files under `kitty-specs/<slug>/` in whichever checkout holds the Mission branch
**Testing**: pytest; red-first integration tests on the real `make_default_mission` + `run_finalize` fixture (`tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py`, 3 code lanes, root on protected `main` and on an unprotected branch) driving the pre-existing entry points (`spec-commit`, `safe-commit`, `agent action implement`, `agent tasks move-task`, `accept`), plus focused unit tests for each extracted helper
**Target Platform**: Linux, macOS, Windows 10+ (path handling stays `pathlib`, no shell)
**Project Type**: single (CLI + libraries under `src/`)
**Performance Goals**: no extra `git` subprocess for the seam's checkout lookup (pure filesystem walk); spec-commit of one file on the fixture ≤ 2 s (NFR-001)
**Constraints**: C-001..C-007 of the spec; the mission_runtime outbound ledger is shrink-only; `test_no_write_side_rederivation`, `test_topology_inference_retired`, `test_single_mission_surface_resolver`, `test_no_read_side_bypass`, `test_write_surface_placement_guard`, `test_commit_scope_owner`, `test_safe_commit_import_boundary` stay green
**Scale/Scope**: ~10 source files across `kernel`, `mission_runtime`, `specify_cli.coordination`, `specify_cli.cli.commands`, `specify_cli.core`, `specify_cli.git`, `specify_cli.validators`

## Charter Check

| Principle / Standing Order | Status | How |
|---|---|---|
| Single canonical authority | Pass | One checkout authority (`PlacementSeam.write_dir(kind).surface_root`); the router's private holder probe and the two root-path target helpers converge on it; nothing new is added beside it |
| Architectural alignment | Pass | The pure "checkout containing a path" walk moves down to `kernel` (allowed by every layer); no `mission_runtime → specify_cli` edge added |
| ATDD / red-first (SO 4, C-011) | Pass | Each WP lands its failing test through the pre-existing entry point first, as its own commit |
| Campsite / tidy-first (SO 2) | Pass | The kernel hoist and the seam `surface_root` fix are a behaviour-preserving enabler ahead of the behaviour changes |
| Architectural gate discipline (SO 5) | Pass | No new gate; allow-list entry #2453 is drained (shrinks); `test_no_read_side_bypass` sanction tokens for the two target helpers are removed when the helpers stop composing the root dir |
| Git discipline (SO 7) | Pass | Topic branch, draft PR, operator merges |
| Mission hygiene (SO 8) | Pass | Implementer ≠ reviewer; issue-matrix rows for #7551, #7601, #7602, #7595, #7607 |
| Terminology canon | Pass | "repository root checkout", "coordination worktree", "Mission"; no "feature" in new prose or flags |
| No full heavy suites | Pass | Targeted files + named gate files only |

## Project Structure

### Documentation (this mission)

```
kitty-specs/settled-placement-surface-01M78GR4/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── research/ (code-grounding.md, foldable-issues.md)
├── decisions/  (escalation rulings)
├── traces/     (approach, design-decisions, tooling-friction)
└── tasks/
```

### Source Code (repository root)

```
src/kernel/git_topology.py                        # + checkout_root_containing (pure walk)
src/mission_runtime/resolution.py                 # PlacementSeam._declared_primary_write_dir surface_root
src/specify_cli/coordination/planning_commit.py   # primary_partition_checkout → seam surface_root
src/specify_cli/coordination/commit_router.py     # _primary_commit_root → seam; re-anchor; status lock
src/specify_cli/git/commit_helpers.py             # SafeCommitHeadMismatch remedy names the holder
src/specify_cli/cli/commands/implement_claim.py   # protected preflight judges write_target(WPT).ref
src/specify_cli/cli/commands/agent/tasks_move_task.py / tasks_shared.py / tasks_transition_core.py  # --note guard
src/specify_cli/cli/commands/agent/workflow_executor.py  # baseline commit at the holder
src/specify_cli/core/git_ops.py, core/paths.py    # target helpers read through the seam (#7595)
src/specify_cli/validators/paths.py               # path-convention frame (#7602)
tests/…                                           # mirrors of each, + one settled-fixture integration module
```

**Structure Decision**: single project; changes stay in the modules that own each behaviour.

## Implementation Concern Map

### IC-01 — One checkout authority in the seam (enabler)

- **Purpose**: `write_dir(kind).surface_root` names the checkout that contains `write_dir(kind).path` for PRIMARY-partition kinds too, so every caller can ask the seam instead of probing.
- **Relevant requirements**: FR-001, C-001, C-004, C-005
- **Affected surfaces**: `kernel/git_topology.py` (hoist `planning_commit._checkout_root_of` as a public pure walk), `mission_runtime/resolution.py::_declared_primary_write_dir`, `coordination/planning_commit.py::primary_partition_checkout`
- **Sequencing/depends-on**: none
- **Risks**: every PRIMARY kind of an unlanded default Mission now reports the coordination worktree as `surface_root`; all current `surface_root` consumers ask COORD kinds (verified), but the change must keep `path` byte-identical to `read_dir(kind)` (C-008 of the seam contract) and keep the root checkout for every other topology and for owned checkouts.

### IC-02 — Commit router resolves the holder through the seam (#7551, #7607)

- **Purpose**: spec-commit lands Mission files on the topic branch from either checkout; a root-only copy refuses without copying; coordination status files are committed under the status lock.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-011, FR-012 (HEAD-mismatch remedy)
- **Affected surfaces**: `coordination/commit_router.py` (`_primary_commit_root`, the PRIMARY arm of `_commit_partition_group`, `_coord_status_locks` predicate; reuse `_translate_to_owning_surface` for the re-anchor), `git/commit_helpers.py` (`SafeCommitHeadMismatch` remedy), `cli/commands/spec_commit_cmd.py` (only if a message needs the holder)
- **Sequencing/depends-on**: IC-01
- **Risks**: keep the ref-inequality `use_coord` rule (design A rejected: PUBLISHED/landed regressions); never copy a root leftover over the holder copy; `WRONG_SURFACE` / `no_op_wrong_surface` codes unchanged, only the diagnostic names the holder.

### IC-03 — Protected-branch preflights judge the write surface (#7601)

- **Purpose**: `agent action implement` and `move-task --note` on a settled Mission judge the branch their commit lands on, not the root checkout's branch or the meta `target_branch`.
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-012 (`--no-auto-commit` advice)
- **Affected surfaces**: `cli/commands/implement_claim.py` (`_status_commit_destination_branch` → `placement_seam(...).write_target(WORK_PACKAGE_TASK).ref`, remedy text), `tests/architectural/test_no_write_side_rederivation.py` (drain #2453 entry), `cli/commands/agent/tasks_move_task.py` / `tasks_shared.py` (feed the WP file's commit ref to `_skip_target_branch_commit`), remedy text in `tasks_transition_core.py`
- **Sequencing/depends-on**: none (uses `write_target`, unchanged)
- **Risks**: accepted message change for a flat Mission whose root HEAD differs from a protected target (protected refusal instead of the #5738 mismatch refusal; decision `01M78GS4H8AAJW5Y4ATZ3TES6B`); explicit `lanes_with_coord` on protected `main` must still refuse (FR-008 positive control).

### IC-04 — Baseline commit and target banner read through the seam (#7551 baseline, #7595)

- **Purpose**: `baseline-tests.json` is committed in the checkout that holds it; the target-branch helpers read the Mission's `meta.json` where the seam finds it instead of falling back to the primary branch.
- **Relevant requirements**: FR-005, FR-009
- **Affected surfaces**: `cli/commands/agent/workflow_executor.py` (baseline needs-commit probe + commit worktree), `core/git_ops.py::resolve_target_branch`, `core/paths.py::get_feature_target_branch`, `tests/architectural/test_no_read_side_bypass.py` sanction tokens for those two sites
- **Sequencing/depends-on**: IC-01
- **Risks**: 24 callers of the target helpers; the change only matters when the root copy of `meta.json` is absent and the topic holder carries one; import-layering of `core/paths.py` (keep the deferred import).

### IC-05 — Path-convention message frame (#7602)

- **Purpose**: accept names a missing artifact-tagged deliverable relative to the checkout that holds it.
- **Relevant requirements**: FR-010
- **Affected surfaces**: `validators/paths.py` (`validate_mission_paths` rendering), `acceptance/summary_core.py` only if the holder must be threaded
- **Sequencing/depends-on**: none
- **Risks**: build paths (`src/`, `tests/`) keep rendering project-relative; low severity.
