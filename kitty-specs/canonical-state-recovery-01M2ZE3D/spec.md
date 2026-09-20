# Mission Specification: Canonical-State Integrity & Recovery

**Mission Branch**: `fix/canonical-state-recovery`
**Created**: 2026-09-20
**Status**: Draft
**Input**: GitHub issues #4758 (P0) and #4786 (P0-as-ruled); milestone #11 (MVP launch). Slice: "unrecoverable canonical-state wedge."

## Intent Summary

**Primary actors:** the operator and the coding agent driving a Spec Kitty mission.
**Trigger:** a documented CLI command (`agent tasks finalize-tasks`, `move-task`, a review rejection) drives the mission's *canonical runtime state* — the reduced snapshot of the append-only status event log, plus `lanes.json` — into a shape that downstream gates refuse.
**Desired outcome:** the mission is always either *advanceable* or *repairable by a single documented command*; no legitimate command sequence can strand a mission, and every refusal names its own repair.
**Binding invariant:** *Every gate that refuses MUST name a repair path, and every repair path MUST re-establish the exact field the gate reads.*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover a wedged mission with one command (Priority: P1)

An operator whose mission was driven into a refused canonical-state shape (no `lanes.json` after execution began, or missing runtime attribution) runs one documented repair command and the mission becomes advanceable again — no hand-editing of state files.

**Why this priority**: This is the operator-facing payoff of the whole mission — the difference between "parked, unrecoverable" and "self-healing."

**Independent Test**: Reproduce the #4758 wedge (finalize-tasks then move-task, no `lanes.json`), run the repair command, then successfully advance the WP through approval — end to end, CLI only.

**Acceptance Scenarios**:

1. **Given** a mission whose event log shows execution began but `lanes.json` is absent, **When** the operator runs the canonical-state repair command, **Then** `lanes.json` is rebuilt deterministically from the event log and approval/implement no longer refuse.
2. **Given** a corrupt or partial event log, **When** the repair command runs, **Then** it fails closed with a clear diagnostic and writes no partial `lanes.json`.
3. **Given** a healthy mission, **When** the repair command runs, **Then** it is a no-op (idempotent) and reports "nothing to repair."

(Attribution recovery is covered by User Story 3 — it is derived at the read-root, so a WP's implementer attribution is never "missing" and needs no repair-command step.)

---

### User Story 2 - No legitimate command mints an unrecoverable state (Priority: P1)

An operator following the documented `agent tasks` / `move-task` commands can never produce a mission that every gate refuses.

**Why this priority**: Closing the wedge *by construction* is more durable than only adding a cure. This is #4758's root.

**Independent Test**: Run `agent tasks finalize-tasks` then `move-task --to doing` on a fresh mission and confirm either `lanes.json` exists or the command refused early with a named recovery — never the silent events-seeded-no-lanes state.

**Acceptance Scenarios**:

1. **Given** a fresh mission, **When** the legacy `agent tasks finalize-tasks` runs, **Then** it writes `lanes.json` alongside the event-log bootstrap (or refuses to half-finalize and names the canonical finalize command) — it never seeds events without lanes.
2. **Given** a mission with no `lanes.json`, **When** `move-task` is asked to move a WP out of `planned`, **Then** it refuses and names the finalize/repair command instead of silently succeeding.

---

### User Story 3 - Attribution survives an ordinary rejection cycle (Priority: P2)

A reviewer rejects a work package the normal way; the implementer's attribution is preserved so acceptance is not later blocked.

**Why this priority**: #4786's residual defect. Currently clearable via `move-task --agent`, but the ordinary path silently drops attribution — recurring scar tissue (#2512/#2960/#4673).

**Independent Test**: Drive a WP claim→for_review→reject→re-review→approve with no explicit `--agent` on the return legs, then run `accept`; it must not report "missing agent."

**Acceptance Scenarios**:

1. **Given** a WP with a prior real owner, **When** it is rejected (`move-task --to planned`) and later re-reviewed and approved without re-passing `--agent`, **Then** the implementer's attribution is preserved in canonical state.
2. **Given** that same approved WP, **When** the operator runs `accept`, **Then** no attribution-related outstanding item is reported.

---

### User Story 4 - Every refusal names its repair (Priority: P2)

An operator who hits any canonical-state refusal is told the exact command that clears it.

**Why this priority**: Recoverability is only real if it is discoverable at the point of refusal.

**Independent Test**: Trigger each canonical-state refusal (accept "missing agent", finalize "execution has begun … no lanes.json", `MissingLanesError`, protected-branch metadata refusal) and assert each message names a concrete repair command.

**Acceptance Scenarios**:

1. **Given** any canonical-state refusal, **When** it is emitted, **Then** the message names the specific recovery command and the field it will re-establish.

### Edge Cases

- A mission whose event log is itself corrupt/partial: repair fails closed with a clear diagnostic, never a partial rebuild that masks corruption.
- A WP legitimately never owned (no prior real owner) that reaches a lane requiring attribution: repair does not fabricate a false owner; the gate stays honest.
- `move-task --to planned` on a coord mission with a protected target branch (the rollback path): must remain recoverable rather than refusing with `WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH` and no exit.
- Re-running finalize after execution began with `lanes.json` present must still NOT rewrite existing lanes (preserve #3311's guard — repair reconstructs only when lanes are absent).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Legacy finalize never half-finalizes | As an operator, I want `agent tasks finalize-tasks` to write `lanes.json` with the event-log bootstrap (or refuse and name the canonical path) so I never get events-without-lanes. | High | Open |
| FR-002 | move-task guards the planned boundary | As an operator, I want `move-task` to refuse to move a WP out of `planned` when `lanes.json` is absent, naming the repair, so the wedge cannot be minted. | High | Open |
| FR-003 | Recovery rebuilds lanes.json from the log | As an operator, I want one documented command that rebuilds `lanes.json` from the canonical event log when execution began but lanes are absent. | High | Open |
| FR-004 | Attribution is durable, never "missing" at accept | As an operator, I want implementer attribution derived from the immutable event log so the accept gate never reports it "missing" after an ordinary rejection cycle — no manual restore step. (Satisfied by the WP04 read-root projection, not by the recovery command.) | High | Open |
| FR-005 | Rejection preserves attribution | As a reviewer, I want an ordinary reject→re-review→approve cycle to preserve the implementer's attribution so acceptance is not blocked. | High | Open |
| FR-006 | Refusals name their repair | As an operator, I want every canonical-state refusal message to name the exact repair command and the field it re-establishes. | High | Open |
| FR-007 | One accessor for the metadata family | As a maintainer, I want the accept-gate agent/assignee/shell_pid checks to read canonical state through one shared accessor, and the existing blanked-slot detector to point at the recovery command. | Medium | Open |
| FR-008 | merge slug-resolution never crashes on a default | As an operator, I want `merge --dry-run` and the merge slug path to return a clean message instead of an unhandled error when the mission arg is an unresolved default. | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero unrecoverable states | Over the documented `agent tasks` / `agent mission` / `move-task` command surface, no reachable canonical state refuses BOTH advance and documented repair (verified by a matrix/property test enumerating the surface). | Reliability | High | Open |
| NFR-002 | Detect==repair parity | Every canonical-state condition a gate or `doctor` DETECTS as bad has a repair path that clears it; proven by a parity-table test with 0 detect-without-cure rows. | Reliability | High | Open |
| NFR-003 | No behavioral regression, clean gates | A genuinely wrong/corrupt state still fails (repair fires only on the reconstructable-from-log case); `ruff check`, `ruff format --check`, and `mypy` are clean with zero new suppressions; per-function cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-004 | Deterministic, idempotent recovery | Rebuilding `lanes.json` from a given event log is deterministic (same log → byte-identical lanes) and idempotent (repair on a healthy mission is a no-op). | Correctness | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical authority | One "execution-ready / has-lanes" predicate; recovery reuses the existing lane-compute and the existing blanked-slot detector — no fourth authority (DIRECTIVE_044). | Technical | High | Open |
| C-002 | Extend, don't invent | Recovery extends the existing `agent mission repair` surface (or `doctor mission-state`); no new top-level command family without justification. | Technical | High | Open |
| C-003 | ATDD red-first | Each defect lands an issue-pinned `@pytest.mark.regression` repro that is RED through the pre-existing entry point before the fix (ADR 2026-07-17-1); transitional repros become focused unit tests after. | Process | High | Open |
| C-004 | Terminology canon | Mission (not feature); no retired terms; `test_no_legacy_terminology` clean. | Regulatory | Medium | Open |
| C-005 | Primary-partition planning | Planning/spec artifacts stay on the primary partition; never transit the coordination worktree. | Technical | Medium | Open |

### Key Entities

- **Canonical runtime state**: the reduced snapshot of the append-only status event log, including the claim triple (`agent`, `shell_pid`, `shell_pid_created_at`) and `assignee`/`role`. The single source of truth for WP lane state and attribution.
- **Execution-lane manifest (`lanes.json`)**: the computed execution lanes; its presence gates approval/implement.
- **Execution-ready predicate**: the (currently triple-authored) decision "has lanes / has execution begun" that, when authorities disagree, mints the wedge.
- **Repair action**: the documented operation that rebuilds `lanes.json` from the event log and restores blanked attribution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Documented command sequences that produce an unrecoverable mission drop from ≥1 (today: #4758) to **0**, proven by the NFR-001 matrix test.
- **SC-002**: An operator recovers a wedged mission with **exactly one** documented command and **zero** hand-edits of state files.
- **SC-003**: **100%** of canonical-state refusal messages name their specific repair command.
- **SC-004**: An ordinary reject→re-review→approve cycle reaches `accept` with **0** attribution-related outstanding items.

## Assumptions

- **#4758 fix strategy (delegate decision):** co-locate the `lanes.json` write in the legacy `agent tasks finalize-tasks` **and** guard `move-task` from leaving `planned` when lanes are absent — defense in depth, closing the class by construction, per grounding (both lenses).
- **Recovery home (delegate decision):** extend `agent mission repair` with a canonical-state action that reuses the extracted lane-compute and the existing `doctor` blanked-slot detector, rather than a fourth authority.
- **#4786 honest severity:** on HEAD `b17f199576` the attribution-drop is **clearable today** via `move-task --to <lane> --agent <x>` (#3029 remedy-1, shipped in `e455ce26c1`); it is an *ergonomic* defect, not an unrecoverable wedge. It is taken as a **full structural fix per operator ruling** because the spot is recurring scar tissue (#2512/#2960/#4673). FR-003/FR-004 (recovery) and FR-008 (merge guard) are therefore **defense-in-depth / latent-bug hardening**, not remediation of a live P0 crash.
- **#4758 distinctness:** confirmed not a duplicate of #4075 (failure-path txn ordering), #2802 (flattened-topology commit dest), or #3311 (rerun rewrites lanes — opposite mode).
- The `merge --dry-run` `OptionInfo` crash does **not** reproduce via the CLI on HEAD (#4723 wrapped it); FR-008 is a defensive guard for the programmatic-call path, low priority.

## Domain Language

- **Wedge**: a canonical state every gate refuses with no documented repair — the anti-state this mission eliminates.
- **Canonical runtime state / claim triple / execution lane / execution-ready predicate / repair**: as defined under Key Entities. Prefer these terms over ad-hoc synonyms ("status blob", "lanes file", "unstick").
