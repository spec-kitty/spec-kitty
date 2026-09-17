# Implementation Plan: Source-aware unblock refusal message

**Branch**: `issue-3937-blocked-planned-refusal-message` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/blocked-planned-refusal-message-01M2Q4E0/spec.md`

## Summary

Make the `move-task --to planned` refusal emitted by `_guard_planned_rollback`
(`src/specify_cli/cli/commands/agent/tasks_transition_core.py`) **source-aware**,
so a `blocked`/`canceled`/`done` work package is told its real legal targets
(e.g. `blocked` → resume via `--to in_progress`) instead of the misleading
"requires review feedback". The guard's allow/deny logic is unchanged: every
`--to planned` move without a valid, non-empty review-feedback file is still
refused, for all source lanes, with and without `--force`. This is a
message-only change plus a non-vacuous regression battery; the state machine is
not touched.

**Technical approach (locked by grounding):** inside the existing missing-feedback
branch of `_guard_planned_rollback`, branch the *message string* on whether
`planned` is reachable from the source lane —
`Lane.PLANNED in wp_state_for(resolve_lane_alias(req.old_lane)).allowed_targets()`:

- **reachable** (`in_review`, `in_progress`, `approved`, `genesis`): keep the
  current review-feedback message verbatim (preserves the pinning test and
  legitimate review-rollback guidance).
- **not reachable** (`blocked`, `canceled`, `done`, `uninitialized`): emit a
  legal-targets message naming `allowed_targets()` for that lane, and for
  `blocked` specifically point to `--to in_progress` as the resume path. No
  mention of review feedback.

Both arms `return RefuseExit1(...)` — there is **no** new early-return and **no**
path that lets a source reach `build_transition_plan`/the state machine. The
source lane is read only to *shape the message*, never to decide *whether* to
refuse.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (existing; no new dependency added or changed)
**Storage**: N/A (no persistence change; append-only status event log untouched)
**Testing**: pytest (unit-level, against the pure decision core `decide_transition` / `_guard_planned_rollback`)
**Target Platform**: Linux/macOS CLI (`spec-kitty` command surface)
**Project Type**: single (CLI adapter layer, `src/specify_cli/`)
**Performance Goals**: N/A — a refusal message; no hot path, no measurable latency budget
**Constraints**: Message-enrichment only (spec C-001/C-002); `_guard_planned_rollback` stays unconditional and force-proof; `_GUARDS` order/identity unchanged; `wp_state.py` allow/deny and `fsm_parity_baseline.jsonl` byte-unchanged; canonical terminology (no forbidden legacy terms)
**Scale/Scope**: One source file changed (guard message), one test file extended (regression matrix). No new module, symbol, CLI flag, or public surface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter (v1.4.0) alignment for this change:

- **Single canonical authority** — legal targets are read from the state
  machine's own `allowed_targets()` accessor; the message duplicates no
  allow/deny rule. PASS.
- **Architectural alignment** — change stays in the CLI adapter layer
  (`src/specify_cli/`); the state-machine module (`status/wp_state.py`) is not
  touched, so no seam is crossed. PASS.
- **ATDD / red-first (DIRECTIVE_034/041, Standing Order #4)** — the regression
  matrix rows (esp. the flagless `done → planned` resurrection tripwire) are
  written RED against a deliberately-holed guard and proven to fail before the
  fix. The prior attempt was cut precisely because its test was vacuous
  (`--force` nowhere; `done`/`canceled`/`genesis` never a source). PASS by
  construction — see WP tasks.
- **Non-vacuous gate (DIRECTIVE_043, Standing Order #5)** — the force-proofness
  is asserted observably (resulting lane + emitted-event absence), not by
  message substring alone. PASS.
- **Smallest-viable-diff vs Boy-Scout (RECONCILE_CHANGE_SCOPE_TENSIONS)** — the
  reachability partition is the smallest change that fixes the reported defect
  *and* the two adjacent misleading cases (`canceled`/`done`), chosen over an
  FSM change by explicit operator decision `01M2Q4F897ANB84HA6EHA9DG98`. No
  guard refactor into source-scoped arms. PASS.
- **Terminology canon** — new prose uses canonical lane names and `--to`
  vocabulary; guarded by `test_no_legacy_terminology.py`. PASS.

No charter conflicts. No supply-chain section applies (no dependency add/upgrade/removal).

## Project Structure

### Documentation (this mission)

```
kitty-specs/blocked-planned-refusal-message-01M2Q4E0/
├── plan.md              # This file
├── research.md          # Phase 0 output — grounding synthesis + design decision
├── data-model.md        # Phase 1 output — lanes, reachability partition, request fields
├── quickstart.md        # Phase 1 output — how to reproduce & verify
├── contracts/
│   └── planned-rollback-message.md   # behavioral contract for the refusal message
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/
└── tasks_transition_core.py          # CHANGED: _guard_planned_rollback message (source-aware)

src/specify_cli/status/
└── wp_state.py                       # READ-ONLY: wp_state_for(...).allowed_targets() (unchanged)

tests/specify_cli/cli/commands/agent/
└── test_tasks_transition_core.py     # EXTENDED: reachability × force regression matrix
```

## Implementation Concern Map

| Concern | Detail | Owning WP |
|---------|--------|-----------|
| IC-1 Reachability helper | Compute "is `planned` reachable from source lane?" from `wp_state_for(resolve_lane_alias(old_lane)).allowed_targets()` — pure, read-only, no allow/deny duplication. | WP01 |
| IC-2 Source-aware message | Branch the missing-feedback message: reachable → existing review-feedback text (verbatim); unreachable → legal-targets text (blocked names `--to in_progress`). Both `return RefuseExit1`. | WP01 |
| IC-3 Force-proof invariant | No new early-return; no source reaches the state machine; the four feedback-field checks unchanged; `_GUARDS` order unchanged. | WP01 |
| IC-4 Regression battery | `{done, canceled, genesis, blocked, in_review}` × `{none, --force}` all refuse, lane unchanged; flagless `done → planned` emits no forced-rewind event; positive control `in_review + valid feedback → planned`; fabricated feedback on `blocked` still refused. Written RED-first. | WP01 |
| IC-5 Terminal/empty-target wording | `done`/`canceled` (empty `allowed_targets`) and `uninitialized` produce correct prose, not an empty list or a raise. | WP01 |

## Parallel Work Organization

Single work package. The change is one guard-message edit plus its co-located
regression tests in one test file; the concerns above are tightly coupled
(splitting the message from its force-proof tests would let a vacuous slice
merge). One lane, one worktree.

- **WP01** (owns `src/specify_cli/cli/commands/agent/tasks_transition_core.py`
  and `tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py`):
  IC-1 … IC-5.

## Complexity Tracking

No new complexity introduced. The added branch is a single reachability check
plus two message strings; `_guard_planned_rollback` stays well under the
complexity ceiling (15). No suppressions.
