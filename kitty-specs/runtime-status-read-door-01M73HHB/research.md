# Research: Runtime status readers through the read door

Phase 0 decisions. Evidence lives in `research/`:
- `intake-debrief.md`: the operator decisions;
- `code-grounding.md`: file:line inventory and reproductions;
- `architecture-options.md`: design options;
- `op-time-grounding.md`: the per-site verdicts from Op `01M726T6`;
- `repro/`: reproduction and parity scripts.

No dependency is added, upgraded or removed, so no supply-chain review or adversarial challenge is required for dependencies (DIRECTIVE_051 not triggered).

## R-1 Board read shape

- **Decision**: read the door once per decision and reduce once into a frozen board-status value, passed to the board and progress helpers. Their `status_dir=` keyword stays as an adapter (a board built from a Path) for the two outside callers and tests.
- **Rationale**:
  - one source and one reduction per decision (single canonical authority);
  - removes the "Path with no log" class behind #7507;
  - follows the #7335 precedent (`_st_reduce_surface`);
  - today one decision reads the same log up to about 8 times.
- **Alternatives considered**:
  - dual-typed `Path | surface` parameters: rejected, because each helper keeps its own read and the Path arms hide from the gate;
  - per-helper door reads: rejected, because they keep N reads and the reads can disagree.

## R-2 Reducer parity

- **Decision**: weighted progress is computed from the board's reduced work-package lanes, pinned by a parity test against `materialize_snapshot` on path sources.
- **Rationale**: on all 816 repo logs, per-WP lanes and weighted progress (1 dp) were identical across `get_all_wp_lanes`, `get_all_wp_snapshots`, `materialize_snapshot`, `materialize_status` and `reduce` (research/code-grounding.md §2). The only difference found was `implementer_of_record`, which runtime/next does not read. That is evidence, not proof, so the parity test stays.
- **Alternatives considered**: keep `materialize_snapshot(path)` for path sources (unnecessary, and it keeps a second read).
- **Kept behaviour**: a corrupt log line still raises in the lanes step and is logged and omitted in the weighted step (`decision.py:310`).

## R-3 Owned coordination entry and policy (DM-1)

- **Decision**: `resolve_status_read(owned=)` for a coordination topology locates the Mission and its `meta.json` through the owned checkout, and probes coordination state under the repository root. Query and progress read the committed branch for EMPTY/UNMATERIALIZED. An advancing dispatch refuses with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`. ADR `2026-11-06-2` §2 is amended to name this split.
- **Rationale**:
  - The ADR already says owned coordination checkouts read the ref instead of raising.
  - Today `resolve_status_read(owned=)` searches the repository root's `kitty-specs/`, which raises for an owned-only Mission.
  - `agent tasks status` already uses the door with `owned`, so `next` and the status board can disagree today.
- **Alternatives considered**:
  - always read the ref, including dispatch: rejected by the operator, because it would send agents into a missing workspace;
  - keep refusing everywhere: rejected, because it contradicts the ADR and keeps the silent empty board for unmaterialized worktrees.

## R-4 Advancing-path materialization (DM-2, corrected)

- **Decision** (Decision Moment `01M73J4X57HKNF5RK7WVN8QHC5`, 2026-11-11): no `--auto-remediate` flag. An advancing `next` keeps its existing automatic materialization of a missing or empty coordination worktree and reports it (one line, `remediation` in `--json`). The board selector's named block stays for direct callers, now decided from the door's surface source instead of a seam raise.
- **Rationale**: verified through the real CLI (`research/repro/advancing_cells.py`). The advancing bootstrap (`runtime_bridge.py:505` -> `runtime_bridge_decision_log._wrap_with_decision_git_log` -> `write_dir(DECISION_LOG)`) materializes, seeds or restores the coordination worktree before the board runs, so the block the original DM-2 kept never reaches a CLI user, and a flag to lift it would be a no-op. Query mode does not run that wrap, so #7507 shows in query mode for both empty and unmaterialized worktrees. The advancing run also reports 0.0% progress in those cells, because it computes progress before the wrap materializes.
- **Alternatives considered**:
  - make materialization opt-in behind `--auto-remediate`: rejected by the operator, because it would change what every agent harness sees today;
  - keep it silent: rejected, because an operator should know `next` changed their workspace.
- **Superseded**: the original R-4 (keep the block, add `--auto-remediate` via `materialize_coord_surface_for_write`).

## R-5 Identity sites (DM-3)

- **Decision**: pass the placement seam explicitly to `gather_artifact_presence` / `guard_failure_artifact_paths` (4 callers). `_dn_bootstrap` takes the Mission directory from PRIMARY metadata.
- **Rationale**: both sites use the status directory only as a key that is reverse-mapped back to a seam. Passing the seam removes the guess and both allowlist entries.
- **Alternatives considered**:
  - relabel the entries and defer: rejected by the operator;
  - swap in `PRIMARY_METADATA` naively: rejected, because coordination-kind artifacts would resolve in the primary directory.

## R-6 Lifecycle event write

- **Decision**: write `MissionNextInvoked` through the status write seam.
- **Rationale**: it is a write that went through a read projection. The gate exempts the write seam, and the readers in `runtime_bridge_composition.py:352-394` read that file, so a read-after-write test proves they still see the row.
- **Open check (implementation)**: whether `write_dir` raises on an unmaterialized worktree. Either way the best-effort event is dropped, as today.

## R-7 #7507 tracking (DM-4)

- **Decision**: #7507 is filed as a P2 bug under #7408 and fixed here red-first. The PR closes it.

## R-8 Test-pin hygiene

- **Decision**: behaviour pins stay. Mechanism pins that patch or spy on the old helpers are re-pinned to the new mechanism with their domain assertions kept, and each re-pin is named in the PR. Files:
  - `test_query_mode_unit.py`
  - `test_runtime_bridge_blocked_paths.py`
  - `test_runtime_bridge_read_path_branches.py`
  - `test_runtime_bridge_unit.py`
  - `test_next_invocation_lifecycle_seam.py`
  - `test_owned_next_runtime.py:376`
- **Rationale**: charter Standing Order 4 (judge the test: a stale pin is re-pinned, not deleted).
