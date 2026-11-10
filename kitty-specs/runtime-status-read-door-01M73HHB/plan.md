# Implementation Plan: Runtime status readers through the read door

**Branch**: `kitty/mission-runtime-status-read-door-01M73HHB` (lands on `refactor/7310-status-read-door-s5`) | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/runtime-status-read-door-01M73HHB/spec.md`

## Planning answers (captured)

- **Engineering alignment** (Decision Moment `01M73HSF99TDJK8ESTDF1H7NAG`, approved as proposed, 2026-11-10):
  - read the door once per decision into a `BoardStatus` value;
  - fix the door's owned entry;
  - decide the board block from the surface source;
  - `--auto-remediate` goes through the canonical materializer;
  - five concerns, sequenced tidy-first.
  - Rejected: dual-typed `Path | surface` parameters.
- **Specify decisions**: DM-1 to DM-4 and the `--auto-remediate` scope (see `decisions/`).

## Summary

`spec-kitty next` (advancing and query) reads Mission status through the placement seam's Path-typed `STATUS_STATE` projection. When the door's declared source is a committed branch, that path reads an empty history, which causes #7507. This plan:

- resolves the status read door once per decision;
- reduces that read once into an immutable **board status** value, which the board and progress helpers consume;
- fixes the door's owned-checkout entry, so an owned coordination Mission is found through its owned checkout;
- routes the four non-read sites to their proper homes: the write seam, and an explicitly passed placement seam;
- adds `next --auto-remediate`, which calls the canonical coordination materializer and then continues.

Each step lowers the single-door gate's allowlist, finishing at 33.

## Technical Context

**Language/Version**: Python 3.11+ (the repository's floor; mypy strict on changed code)
**Primary Dependencies**: typer (CLI flag), the in-tree `specify_cli.status.read_surface` door, `mission_runtime` placement seam, `spec_kitty_events` reducer (unchanged; no dependency added, upgraded or removed, so DIRECTIVE_051 supply-chain controls are not triggered)
**Storage**: files and git refs: `status.events.jsonl` in a checkout or on a committed branch (read via `git cat-file --batch`), `mission-events.jsonl` (write)
**Testing**: pytest; red-first test per behaviour change (C-002). Targeted suites: `tests/runtime/`, `tests/next/`, `tests/runtime/next/`, `tests/integration/test_owned_next_runtime.py`, `tests/integration/test_next_preview_primary_routing.py`, `tests/specify_cli/next/`, `tests/status/` (door), the gates `tests/architectural/test_status_read_single_door.py` and `test_ratchet_baselines.py`, plus `make test-fast`. No `make test-full` (C-006).
**Target Platform**: the cross-platform CLI (Linux, macOS, Windows)
**Project Type**: single project (`src/` layered `kernel <- charter <- {runtime, mission_runtime} <- specify_cli`)
**Performance Goals**: at most 1 status-log read and 1 reduction per `next` decision (today up to ~8); existing `next` suites' wall time within +10% (NFR-002)
**Constraints**:
- refusal texts, codes and exit codes stay byte-identical outside the FR-001/005/007 cells (NFR-003);
- complexity ≤ 15 (NFR-004);
- the layer rule `runtime -> specify_cli` stays within the shrink-only outbound ledger. The door lives in `specify_cli`, which `runtime/next` already imports.
**Scale/Scope**: 8 allowlist entries across 6 runtime modules; about 48 Path-typed call sites; 25 test files touch the board helpers (research/code-grounding.md §1, §6)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | How |
|---|---|---|
| Single canonical authority | PASS | All status reads go through the one door. `BoardStatus` is derived from one door read, not a second source finder (C-001). |
| Architectural alignment | PASS | Layer direction unchanged: `runtime.next` already imports `specify_cli.status`. ADR `2026-11-06-2` is amended for DM-1, not bypassed (FR-012). |
| DDD + tiered rigour | PASS | Board status is a value object with a single builder. More rigour (parity test, red-first) on decision logic; light touch on adapters. |
| ATDD-first | PASS | Each behaviour change has a failing acceptance test committed first (C-002). |
| Standing Order 2 (tidy first) | PASS | The first concern (board status + parity) changes no call site. |
| Standing Order 5 (gate discipline) | PASS | No new gate. The existing allowlist (priced debt, #7310) shrinks in the same commit as each move; floor and baseline lowered with it. |
| Standing Order 4 (red-first, judge the test) | PASS | Mechanism pins that the move makes stale are re-pinned and named in the PR; behaviour pins stay (research/code-grounding.md §6). |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted suites + named gates + `make test-fast` only. |
| Terminology Canon | PASS | Mission/coordination worktree vocabulary; `test_no_legacy_terminology.py` before push. |

Post-design re-check: PASS (no new authority, no new gate, no new dependency).

## Project Structure

### Documentation (this mission)

```
kitty-specs/runtime-status-read-door-01M73HHB/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: decisions and rationale
├── research/            # squad notes (intake debrief, code grounding, architecture options, repro scripts)
├── data-model.md        # Phase 1: BoardStatus, surface source -> board behaviour
├── quickstart.md        # Phase 1: how to see the fix and the flag
├── contracts/
│   └── next-auto-remediate.md   # CLI contract for the new flag
└── tasks.md             # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/runtime/next/
├── discovery.py                         # BoardStatus value + builder; preview_claimable_wp(board=)
├── decision.py                          # _compute_wp_progress / _find_first_wp_by_lane (board=); _with_guard_failure_paths (seam)
├── runtime_bridge.py                    # _dn_bootstrap: door read + PRIMARY identity
├── runtime_bridge_decision_mapping.py   # board action: door read, block from surface source, helpers take board=
├── runtime_bridge_query.py              # query_current_state / finalized override: door read
├── runtime_bridge_io.py                 # gather_artifact_presence / guard_failure_artifact_paths take the seam
└── next_invocation_lifecycle.py         # MissionNextInvoked via the write seam
src/specify_cli/status/read_surface.py   # owned coordination entry (FR-007)
src/specify_cli/cli/commands/next_cmd.py # --auto-remediate flag
src/specify_cli/coordination/surface_resolver.py  # materialize_coord_surface_for_write (reused, unchanged)
docs/adr/4.x/2026-11-06-2-one-status-read-contract.md  # amendment (FR-012)
tests/architectural/test_status_read_single_door.py, _baselines.yaml   # allowlist 41 -> 33
```

**Structure Decision**: single project. Changes stay inside `src/runtime/next/`, the door module and the `next` command, plus one ADR amendment.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

> Concerns are not work packages; `/spec-kitty.tasks` maps them to WPs.

### IC-01 — Board status value (tidy-first enabler)

- **Purpose**: one immutable reading of a Mission's status per decision (lanes, per-WP states, log present, weighted progress), built once from a door surface, so every board/progress check reads the same thing.
- **Relevant requirements**: FR-008, NFR-001, NFR-002, C-003
- **Affected surfaces**: `src/runtime/next/discovery.py`, `decision.py`, `runtime_bridge_decision_mapping.py` (helpers gain `board=`; the `status_dir=` keyword becomes an adapter that builds a board from a Path)
- **Sequencing/depends-on**: none
- **Risks**:
  - Reducer parity. Per-WP lanes and weighted progress must equal today's output on all repo logs; pin that with a parity test (research/code-grounding.md §2).
  - Corrupt-line behaviour must stay split: the lanes step raises, while the weighted step logs and omits.

### IC-02 — Door owned-checkout entry and owned policy

- **Purpose**: the door finds an owned coordination Mission through its owned checkout. Query and progress read the committed branch; an advancing dispatch keeps `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`. ADR amended.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-012
- **Affected surfaces**: `src/specify_cli/status/read_surface.py` (`resolve_status_read(owned=)`), owned arms in `runtime_bridge.py` / `runtime_bridge_query.py`, ADR `2026-11-06-2`
- **Sequencing/depends-on**: none (parallel with IC-01)
- **Risks**:
  - `_is_owned_coordination_unavailable` does not map the door's `WorktreeRegistryUnavailable` / `StatusSurfaceRefUnreadable`. Read after the decision-log wrap, or map them (research/code-grounding.md §4).
  - The pins `test_owned_next_runtime.py:301-374` and `test_owned_lifecycle_acceptance_next.py:276` must keep the dispatch refusal.

### IC-03 — Board and query read the door (#7507)

- **Purpose**: `_resolve_wp_board_action`, `query_current_state` and the finalized-override query read the door once and pass the board status. The unmaterialized block is decided from the surface source. #7507 is fixed.
- **Relevant requirements**: FR-001, FR-002, FR-008, FR-011 (4 entries)
- **Affected surfaces**: `runtime_bridge_decision_mapping.py`, `runtime_bridge_query.py`, outside callers `workflow.py:1261` and `runtime_bridge_guards.py:102` (adapter)
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**:
  - Mechanism pins go stale: `test_query_mode_unit.py` (9 patches), `test_runtime_bridge_blocked_paths.py`, `test_runtime_bridge_read_path_branches.py`. Re-pin them and name each in the PR.
  - The unmaterialized block's text must stay byte-identical (pins `test_next_board_authority.py:601`, `test_coordination_remedy_5113.py`).

### IC-04 — Explicit placement seam for artifact presence; bootstrap identity

- **Purpose**: `gather_artifact_presence` / `guard_failure_artifact_paths` receive the placement seam instead of reverse-mapping a status directory. `_dn_bootstrap` takes its Mission directory from PRIMARY metadata and its board from the door.
- **Relevant requirements**: FR-010, FR-011 (3 entries: `_with_guard_failure_paths`, `_artifact_presence_seam`, `_dn_bootstrap`)
- **Affected surfaces**: `runtime_bridge_io.py`, `decision.py`, `runtime_bridge.py`, `runtime_bridge_composition.py:495`, `acceptance/non_wp_runtime.py:89`
- **Sequencing/depends-on**: IC-02, IC-03 (shared files: run in sequence)
- **Risks**:
  - Swapping in `PRIMARY_METADATA` naively would send coordination-kind artifacts to the primary directory. Pin the reported guard-failure paths before the move.

### IC-05 — MissionNextInvoked via the write seam; `next --auto-remediate`

- **Purpose**: the lifecycle row is written through the status write seam (read-after-write proven). `next --auto-remediate` materializes a missing or empty coordination worktree through `materialize_coord_surface_for_write`, reports it, and continues. It never acts on a deleted branch or in query mode.
- **Relevant requirements**: FR-003, FR-004, FR-009, FR-011 (1 entry)
- **Affected surfaces**: `next_invocation_lifecycle.py`, `next_cmd.py`, the advancing decision entry (`decide_next_via_runtime` path)
- **Sequencing/depends-on**: IC-03 (the block it remediates)
- **Risks**:
  - Assumption to verify: `write_dir` may raise on an unmaterialized worktree where `read_dir` tolerated it. Either way the best-effort event is dropped, as today.
  - The flag must be ignored in query mode (FR-004).

### Allowlist ledger (41 -> 33)

| After | Entries removed |
|---|---|
| IC-01 | — (41) |
| IC-02 | — (41) |
| IC-03 | `_resolve_wp_board_action` ×2, `query_current_state`, `_build_finalized_override_query_decision` (37) |
| IC-04 | `_with_guard_failure_paths`, `_artifact_presence_seam`, `_dn_bootstrap` (34) |
| IC-05 | `emit_mission_next_invoked` (33) |

The live-hit floor and the `_baselines.yaml` count are lowered in the same commit as each removal.
