# Contract (FROZEN) — `is_review_rejection_edge`

WP01 introduces this; WP02 and all FIVE rejection-family call sites consume it. Frozen so WP02 and
reviewers can rely on the signature and semantics before WP01 lands. (The predicate signature is frozen;
the five-site enumeration below is a factual call-site correction, not an interface change.)

## Signature

```python
# src/specify_cli/cli/commands/agent/tasks_transition_core.py
def is_review_rejection_edge(old_lane: str, target_lane: str) -> bool: ...
```

## Semantics

Returns `True` iff the edge must durably record reviewer feedback (persist a review-cycle record, populate
the feedback location, emit a resolvable pointer, and refuse a no-rationale rejection):

```
resolve_lane_alias(old_lane)  == IN_REVIEW and
resolve_lane_alias(target_lane) in (PLANNED, IN_PROGRESS)
    OR
resolve_lane_alias(target_lane) == PLANNED     # preserve any-source ->planned rollback (non-regression)
```

- Pure; no I/O; alias-normalizing (`doing → in_progress`).
- Returns `False` for arbiter-forward edges `in_review → {approved, done}` (NFR-003 — untouched).
- Returns `True` for every `* → planned` edge that returns `True` today (behavior preserved).

## Call sites replaced (WP01)

| Gate | Site | Was | Becomes |
|------|------|-----|---------|
| content read | `tasks_move_task.py:615` | `st.target_lane == Lane.PLANNED` | `is_review_rejection_edge(st.old_lane, st.target_lane)` |
| persist gate | `tasks_move_task.py:2334` (via `Emit`) | `decision.planned_rollback` | `decision.is_review_rejection` |
| emit ref | `tasks_transition_core.py:296` | `target_lane == Lane.PLANNED and review_feedback_pointer` | `is_review_rejection_edge(old_lane, target_lane) and review_feedback_pointer` |
| no-rationale refusal | `tasks_transition_core.py:596` | `req.target_lane != Lane.PLANNED` | `not is_review_rejection_edge(req.old_lane, req.target_lane)` |
| emitted `review_result` | `tasks_move_task.py:2539` (`_mt_hop_review_result`) | `target == Lane.PLANNED and rejected is not None` | `is_review_rejection_edge(st.old_lane, target) and rejected is not None` |

The 5th site (`_mt_hop_review_result`) selects the emitted event's `review_result`; if left keyed on
`== Lane.PLANNED` the re-implement edge falls to the approval-shaped branch (`verdict=APPROVED`,
`reference="auto-forward:<WP>"`) and the emitted event no longer matches the resolvable pointer emitted by
the `emit ref` site — so SC-001 field-for-field VALUE parity is unprovable with only the first four routed.

## `Emit` flag generalization

`Emit.planned_rollback` (`tasks_transition_core.py:829`) → renamed `is_review_rejection`, set from
`is_review_rejection_edge(req.old_lane, req.target_lane)`. Consumers: persist-call gate
(`tasks_move_task.py:2334`) and plan-rebuild trigger (`tasks_move_task.py:2371`, whose now-redundant explicit
`in_review → {planned,in_progress}` clause is removed).

## Emitted reference shape (consumed downstream)

On a rejection edge, `event.review_ref` MUST be a resolvable `review-cycle://…` pointer (from
`st.review_feedback_pointer`), never a synthetic `review:<WP>` marker.
`is_non_resolvable_review_ref(ref) == False` for the emitted pointer.
