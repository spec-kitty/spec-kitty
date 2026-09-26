# Phase 1 Data Model: Advancing next — task-board authority unification

No persisted schema changes. The "entities" here are the in-memory decision structures and the board-state read that flows through them. Documented so the contract and tests have named referents.

## Board step (value)

The step name the board authority derives from the finalized task board + coord-aware status surface.

| Value | Meaning | Advancing decision |
|-------|---------|--------------------|
| `implement` | ≥1 WP in a pre-review lane (`planned`/`claimed`/`in_progress`) | `kind=step action=implement wp_id=<claimable>` |
| `review` | ≥1 WP in `for_review` | `kind=step action=review wp_id=<for_review>` |
| `accept` | all WPs at an acceptable ending, not all `done` | advance-past-step (handled by the leave-step path) |
| `done` | all WPs `done` | terminal |
| `blocked:review_in_progress` | only `in_review` WPs (claimed by another reviewer) | `kind=blocked` + recovery |
| `blocked:no_actionable_wp` | nothing claimable/actionable (e.g. dependency wall) | `kind=blocked` + recovery |

Derived by `_finalized_task_board_override_step(task_board_dir, progress, status_dir=<coord-aware>)`. **Invariant**: advancing mode and query mode derive this value from the identical inputs (same `task_board_dir`, same coord-aware `status_dir`), so they never disagree.

## Advancing decision envelope (existing `DecisionEnvelope`)

Fields relevant to this fix:

| Field | Pre-fix bug value (#4980) | Pre-fix bug value (#4975) | Post-fix required |
|-------|---------------------------|---------------------------|-------------------|
| `kind` | `step` | `blocked` | `step` (re-dispatch) or `blocked` (floor) |
| `action` | `review` | `None` | `implement` (re-dispatch) / board step |
| `wp_id` | `null` | `null` | `WP01` (the actionable WP) |
| `mission_state` | `review` | `implement` | board step |
| `prompt_file` | composed placeholder | — | real action prompt, or blocked reason |
| exit code | 0 | 1 | 0 (step) / 1 (blocked) |

**Invariant (FR-005)**: no live advancing result has `kind=step` with `wp_id=null` for a WP-iteration step. A WP-less WP-iteration state is either a real re-dispatch (`wp_id` set) or `kind=blocked`.

## Issued step marker (persisted, unchanged)

The run's `issued_step_id` (e.g. `review`). **Invariant (NFR-001)**: unchanged by the re-dispatch; the advancing action is recomputed from the board each call. The whole persisted run/engine snapshot is byte-identical before and after the re-dispatch call.

## Coord status surface (read, fail-closed)

The coord-aware `status_dir` resolved via the placement seam (`mission_context_for(repo_root, mission_slug).artifact(STATUS_STATE).read_dir`). **Invariant (NFR-003)**: on an unmaterialized/deleted coordination surface the read raises the typed fail-closed error (ADR 2026-09-24-2); it is never substituted with an empty primary read that fabricates "no WP".

## State transitions (advancing loop, post-fix)

```
issued=review, WP01 for_review        --review success-->  reviewer verdict
  ├─ approve → WP01 approved  → board=accept  → advance → accept → terminal
  └─ reject  → WP01 planned   → board=implement → RE-DISPATCH implement WP01   (was: spin on placeholder ∞)
issued=implement (coord), WP01 planned → board=implement (coord-aware) → DISPATCH implement WP01  (was: blocked "No action mapped")
board=blocked:*                        → kind=blocked + named recovery command  (never composed placeholder)
coord surface unmaterialized           → typed fail-closed error (named), NOT generic no-actionable-WP
```
