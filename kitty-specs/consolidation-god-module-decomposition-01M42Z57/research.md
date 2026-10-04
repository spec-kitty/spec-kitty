# Research: Consolidation god-module decomposition

The code-grounding run is the primary research artifact:
[research/code-grounding.md](research/code-grounding.md). This file records the
decisions it led to and the baseline taken before any change.

## Decisions

### R-1 Where the mission_number bake cluster goes (#2600)

- **Decision:** convert `consolidation/mission_number.py` into the package
  `consolidation/mission_number/`. `__init__.py` is the old file, unchanged
  (stdlib-only `is_assigned_mission_number`). The cluster moves verbatim to
  `consolidation/mission_number/bake.py`.
- **Rationale:** #2600's 2026-10-04 refresh asks for the cluster to live under
  `mission_number`. The module it names is a documented stdlib-only leaf
  (`mission_number.py:1-15`) that `drivers.py:87` imports inside git's
  merge-driver subprocess; putting ~775 LOC with `console`, git and worktree
  imports into it would break that contract. A package keeps both: the leaf
  file's own imports stay standard-library-only, and the cluster sits under the
  same name. (Correction after the pre-PR review: importing any
  `specify_cli.consolidation` submodule first runs the parent package
  `__init__`, which re-exports `assign_next_mission_number` and so loads
  `bake.py`, exactly as it loaded `ordering.py` before. The contract is
  file-level, and what the merge driver loads is unchanged.)
- **Alternatives rejected:** (a) move into `mission_number.py` itself: breaks
  the leaf contract; (b) new sibling `number_assignment.py`: the issue's
  original target, explicitly superseded by the refresh comment.
- Decision Moment `01M42ZJG3GFPYZQN15JX7E6MCB` (resolved under the brief's
  "confirm or adjust after grounding" delegation).

### R-2 How executor.py is cut (#2026 slice 1)

- **Decision:** ten modules by phase / cross-phase concern (plan.md, Project
  Structure). `executor.py` keeps `_run_lane_based_consolidation_locked` (with
  its inline door `try` and inline phase calls), `_report_rollback`,
  `_record_operator_attestations` and `_run_lane_based_consolidation`.
- **Rationale:** the door pins (`test_single_rollback_authority.py`) and the
  phase-order pins (`test_executor_phase_boundary.py`, `test_reconciliation.py`)
  read the driver's source in `executor.py`; keeping it there keeps every pin
  honest without re-pointing it. Cutting by phase follows where the 90-day fix
  history clusters (code-grounding §6) and puts the two #5613 hot spots
  (resume recovery, teardown codes) in small modules (§5).
- Decision Moment `01M42ZJJS4XWJ39317N932BP8N`.

### R-3 Monkeypatch targets

- **Decision:** re-point each test patch of `executor.<name>` to every new
  module whose code loads `<name>` as a module global, computed from the AST.
- **Rationale:** before the split, patching `executor.<name>` intercepted every
  lookup of `<name>` by any executor function. After it, the lookups are spread
  over modules; patching each module that looks the name up reproduces exactly
  the old interception set. Keeping aliases in `executor` would make many such
  patches silently stop intercepting. Decision Moment `01M42ZJNERKY2TB1RPKF2GJ0GT`.

### R-4 Parameter object (#3457)

- **Decision:** `ConsolidateOptions` frozen dataclass in
  `cli/commands/consolidate.py`; `run_consolidate(options)` holds the command
  body; the Typer `consolidate()` keeps its 19 `typer.Option` parameters
  (C-006, and `test_wrapper_delegation.py:202` binds against that signature)
  and only builds the object.
- **Rationale:** direct callers construct one object whose fields have real
  defaults; a new option gets a default there instead of a Typer sentinel.
- **Out of scope (follow-ups named in #3457):** a new doctrine refactoring tactic
  and a `**kwargs` lint rule. Both are separate design passes; this mission
  records them as follow-ups only.

## Baseline (origin/main @ 43b66f60, before any change)

`pytest tests/consolidation tests/specify_cli/consolidation tests/orchestrator_api tests/lanes -n 4 --dist loadfile`
→ 2412 passed, 2 skipped, 5 xfailed, 1 failed (`tests/consolidation/test_profile_charter_e2e.py::test_local_support_declarations_end_to_end`).
The failure is an artifact of running the baseline from a linked git worktree
("Refusing charter write from linked git worktree"); it is environmental, not a
product red. It is re-checked from the repository-root checkout during implement.
