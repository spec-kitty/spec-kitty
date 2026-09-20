# Implementation Plan: Canonical-State Integrity & Recovery

**Branch**: `fix/canonical-state-recovery` | **Date**: 2026-09-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification; research in [research.md](./research.md); post-plan squad corrections folded (see Design decisions & tracer).

## Summary

Two P0 defects share one shape: a documented CLI path drives the mission's canonical runtime state into a form every downstream gate refuses, with no operator command to repair it. This plan closes #4758's wedge **by construction** (legacy finalize never half-finalizes; `move-task` guards the `planned` boundary), makes the mission recoverable via **one** documented rebuild action homed in `doctor mission-state --fix`, and fixes #4786 at the **read-root** (derive durable implementer provenance from the immutable event log) rather than by re-writing a live-claim slot. Binding invariant: *every refusing gate names a repair path; every repair path re-establishes the field the gate reads.*

## Technical Context

**Language/Version**: Python 3.11+. **Primary Dependencies**: typer, `specify_cli` (status, lanes, acceptance, cli/commands/agent, migration). **Storage**: append-only `status.events.jsonl` + reduced snapshot; `lanes.json`. **Testing**: pytest (ATDD red-first, `@pytest.mark.regression`); ruff + mypy; complexity ≤15. **Project Type**: single. **Constraints**: no new suppressions; diff-cover ≥90% new code; terminology canon; layer discipline (`lanes/` is a pure domain layer — no CLI/console/policy imports).

## Constitution / Charter Check

- **Single canonical authority (DIRECTIVE_044):** narrow shared "wedge predicate" (execution-begun AND lanes-absent) used by BOTH the finalize refusal and the recovery detector; the broad triple-authority collapse is **rejected with rationale** (see Design decision 5). ✅
- **ATDD-first (C-003):** issue-pinned regression repro RED through the pre-existing entry point before each fix. ✅
- **Extend, don't invent (C-002):** recovery is a new action inside the existing `doctor mission-state` surface; no new command family. ✅
- **Layer discipline:** the extracted lane-compute core stays pure in `lanes/`; CLI wrapper stays in `mission_finalize.py`. ✅
- **Complexity ≤15, tests-with-branches, real fixes over suppression, terminology canon.** ✅
- No Complexity-Tracking violations.

## Architecture / Design

### Data model (canonical runtime state)
- **Claim triple** `agent`+`shell_pid`+`shell_pid_created_at` (`status/models.py:535-551`) — a **live current-actor** marker that legitimately changes hands (implementer→reviewer). Released on rollback→planned via `release_runtime_claim` (`:569`). **This is correct and stays untouched.**
- **Durable implementer provenance** — does NOT exist as a field today; lives only implicitly in the append-only event log (the implementer's claim event `policy_metadata`, `tasks_move_task.py:2567-2571`). #4786's fix surfaces it as a **read-side projection**.
- **`lanes.json`** — computed execution-lane manifest; presence gates approval/implement (`require_lanes_json`, `lanes/persistence.py:111`).
- **Wedge predicate** — the pair (`_execution_has_begun` True AND `lanes.json` absent); the #4758 anti-state, shared by the finalize refusal and the recovery detector.

### Design decisions (post-squad corrected)
1. **#4758 close-by-construction (FR-001/FR-002).** (a) Legacy `agent tasks finalize-tasks` co-locates the `lanes.json` write with the event-log bootstrap (or refuses to half-finalize and names the canonical command). (b) `move-task` refuses to move a WP out of `planned` when `lanes.json` is absent (via `require_lanes_json` at `tasks_move_task.py:638-642`), naming the repair. **1b lives in `tasks_move_task.py` = WP02.**
2. **Recovery homed in `doctor mission-state --fix` (FR-003, C-002).** A new action inside `run_mission_state`/`repair_repo` (`migration/mission_state.py:685`, already `--mission`-scoped and primary-anchored at `:501-532`, with no coordination-partition gate). Rebuilds `lanes.json` from the event log when the wedge predicate holds, reusing WP01's extracted pure core. **Not `agent mission repair`** — its `shas is None` early return (`mission_repair.py:286-292`) short-circuits exactly the non-coordinated topologies (SINGLE_BRANCH/LANES/flat) where the #4758 wedge is reachable. Home change recorded in tracer; operator's scope ruling (a recovery command exists) preserved.
3. **#4786 fixed at the read-root (FR-004/FR-005).** Add `_project_implementer_attribution` to `status/reducer.py`, a sibling of the existing `_project_cancellation_provenance` (`reducer.py:67-90`): scan the raw event stream for the prior implementer-role claim and expose a **derived** attribution slot the fold/release never touches. The accept gate (`summary_core.py:79/86-87`) reads that derived slot. **Do NOT edit `tasks_move_task.py:2891/:2970` for attribution** (that would be patch #5, fighting #4673) and **do NOT touch** the upstream `spec_kitty_events.diary` fold. Honest by construction: a never-owned WP has no claim event → projection yields nothing → the gate correctly refuses.
4. **Read-side family + honest messages + latent guard (FR-006/FR-007/FR-008).** `summary_core.py:86-98` reads agent/assignee/shell_pid through one shared accessor; the `doctor.py:215-240` blanked-slot detector is narrowed to genuine on-disk `agent: ""` blanks (its true #2960 remit) and its recommended-action reworded (a released-but-historically-owned WP is no longer a finding — the projection makes the gate pass). Every #4758 refusal (finalize refusal `mission_finalize.py:2210-2230`, `MissingLanesError` `persistence.py:115`, protected-branch `tasks_transition_core.py:407`, move-task guard) names its repair. `merge.py:259/456` `(mission or "").strip()` guarded against an unresolved `OptionInfo` default.
5. **Narrow wedge-predicate fold ONLY (C-001).** Introduce one named predicate for (execution-begun AND lanes-absent) shared by the finalize refusal and the recovery detector so detect≡cure. The **broad** "single execution-ready predicate across ~18 gates" is **rejected/deferred**: file-existence gates consume the `LanesManifest` object (not a bool), the file-vs-log disagreement is the #4758 signal itself, and ~6 soft `read_lanes_json→None` sites are legitimately None-tolerant (coord husks, topology probes — `workflow.py:214-232`, `lifecycle_sync.py:144`, `backfill_topology.py:56`).

### Structure Decision
Single project. Touched source: `cli/commands/agent/{tasks_finalize,mission_finalize,tasks_move_task,tasks_transition_core,tasks}.py`, new `lanes/compute_and_persist.py`, `lanes/persistence.py` (message), `migration/mission_state.py` + `cli/commands/_mission_state_doctor.py`, `status/reducer.py`, `status/doctor.py`, `acceptance/summary_core.py`, `cli/commands/merge.py`. `status/models.py` is **off-limits** (no WP needs it — verified). Tests mirror under `tests/cli/`, `tests/status/`, `tests/acceptance/`, `tests/unit/migration/`.

## Parallel Work Analysis

### Dependency Graph
```
WP01 (#4758 finalize minting + EXTRACT pure compute_and_write_lanes → lanes/ + wedge predicate)
   │  (WP03 imports the pure core + shared wedge predicate)
   ▼
WP03 (recovery: lanes.json rebuilder in doctor mission-state --fix)

WP02 (#4758 move-task planned-boundary guard)        ─┐ independent write-scopes,
WP04 (#4786 attribution projection + read-side + folds)─┘ parallel with WP01 and each other
```
- **Sequential:** WP01 → WP03.
- **Parallel:** WP02 ∥ WP04 ∥ WP01.

### Work Distribution (owned files — write-scope-disjoint)
- **WP01**: `cli/commands/agent/tasks_finalize.py`, `cli/commands/agent/mission_finalize.py` (CLI wrapper + finalize-refusal message + wedge predicate), new `lanes/compute_and_persist.py`, `lanes/persistence.py` (MissingLanesError message), `cli/commands/agent/tasks.py` (registration, only if signature changes).
- **WP02**: `cli/commands/agent/tasks_move_task.py` (planned-boundary guard only — NOT attribution), `cli/commands/agent/tasks_transition_core.py` (protected-branch refusal message).
- **WP03**: `migration/mission_state.py`, `cli/commands/_mission_state_doctor.py` (new lanes-rebuild action; imports WP01 pure core + shared wedge predicate read-only).
- **WP04**: `status/reducer.py` (`_project_implementer_attribution`), `acceptance/summary_core.py` (read derived slot + family accessor + name repair), `status/doctor.py` (narrow detector + reword), `cli/commands/merge.py` (OptionInfo guard).

### Coordination Points
- `status/models.py` — **untouched by all WPs** (highest latent collision if any WP touches the reducer release-order; watch it).
- WP01 lands the pure-core extraction before WP03 builds on it (enforced by the lane dependency).
- Integration checks: after WP01+WP03 the #4758 wedge is repairable end-to-end; after WP04 the rejection→re-review→approve repro reaches `accept` clean via derivation.

## Risks

- **R1 — legacy-finalize contract change:** prefer refuse-and-delegate if any consumer depends on events-only; verify with `tests/cli/` finalize coverage.
- **R2 — recovery must not rewrite existing lanes:** rebuild only when the wedge predicate holds (lanes absent); preserve #3311's guard. NFR-004 idempotence test.
- **R3 — projection honesty:** derive attribution only from a real implementer claim event; never fabricate. Covered by the honest-gate edge case + the never-owned test.
- **R4 — extraction layer inversion:** extract the pure core only (no console/JSON/policy into `lanes/`); keep the wrapper in `mission_finalize.py`; pass `planning_commit_sha`+`mission_id` as resolved inputs.
- **R5 — doctor mission-state action scope:** the new action must not disturb `repair_repo`'s existing JSON-shape canonicalization; add as a distinct, independently-tested branch.

## Test Strategy (ATDD red-first)
- Per defect: issue-pinned `@pytest.mark.regression` RED through the pre-existing CLI entry point (#4758 wedge repro; #4786 rejection-cycle repro) before the fix.
- NFR-001 matrix over the documented command surface: no state refuses both advance and repair.
- NFR-002 parity: every detected canonical-state condition has a clearing repair (or is no longer a finding under the projection).
- NFR-004: determinism (same log → byte-identical lanes) + idempotence (repair on healthy = no-op); projection idempotent/read-only.
