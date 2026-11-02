# Data model: Wire-valid approved reopen

Four shapes matter; none of them gains a field.

## `REVIEW_REF_REQUIRED_EDGES` (the one definition)

`src/specify_cli/status/wp_state.py`

| before | after |
|---|---|
| `{(FOR_REVIEW, IN_PROGRESS)}` | `{(FOR_REVIEW, IN_PROGRESS), (APPROVED, IN_PROGRESS)}` |

The contract's third gated edge, `IN_REVIEW -> IN_PROGRESS`, stays out of the set: the
status emit path carries its evidence as a structured review result and never turns the
reviewer's reference into a `review_ref`, so gating it first would refuse legitimate writes.
It is follow-up #7080 and is pinned here as still admitted (`test_force_elsewhere_is_unchanged`).

Read by `requires_review_ref(from, to)` and, through it, by:

| consumer | effect of the widening |
|---|---|
| `WPState.check_transition` (writer, every door) | a pointerless gated rewind is refused before the append, with `review_ref_required_message` |
| `status.validate.validate_event_schema` (auditor) | a stored pointerless gated row produces a `… without review_ref` finding |
| `build_transition_plan` (emitter) | an emitted forced gated rewind with no supplied pointer is filled with `force-override` |

Invariant: this set equals the pinned `spec_kitty_events` "Review-Ref-Gated Rewind Family",
proven per member by the family ratchet test (`SC-003`).

## `TransitionPlan` (emitter output, unchanged shape)

```
TransitionPlan(
    canonical_lane: str,
    transition_targets: list[str],
    emit_force: bool,
    emit_reason: str | None,
    emit_review_ref: str | None,
)
```

Behaviour on the family, after the change:

| edge | supplied pointer | `emit_force` | `emit_review_ref` |
|---|---|---|---|
| `approved -> in_progress` | none | `True` (FR-015, unchanged) | `"force-override"` (**was `None`**) |
| `approved -> in_progress` | feedback file | `False` (#6845, unchanged) | the file path (unchanged) |
| `approved -> in_progress` | explicit `--force` + file | `True` | the file path (unchanged; the real pointer wins) |
| `for_review -> in_progress` | none, forced | `True` | `"force-override"` (unchanged) |
| `in_review -> in_progress` | none | refused by the guard (never reaches the plan) | — |

## `StatusEvent` (append-only row, unchanged shape)

Fields the change reasons about: `from_lane`, `to_lane`, `force`, `reason`, `review_ref`.
After the fix, the reported repro records:

```json
{"from_lane": "approved", "to_lane": "in_progress", "force": true,
 "reason": "backward rewind: approved -> in_progress",
 "review_ref": "force-override"}
```

and the identical payload rebuilt as `spec_kitty_events.status.StatusTransitionPayload`
passes `validate_transition` (before: `review_ref: null`, `valid=False`).

## `force-override` (the sentinel)

- Member of `specify_cli.review.cycle.REVIEW_FEEDBACK_SENTINELS`; an operational marker,
  not a path.
- `resolve_review_cycle_pointer` returns `kind="sentinel"`, `path=None`: no reader tries to
  open it, and no reader mistakes it for a review artifact.
- Already recorded by `start_implementation_status` on this exact hop and by
  `move-task` on `for_review -> in_progress`.

## Refusal shape (unchanged message, wider reach)

```
Transition approved -> in_progress requires review_ref: a forced rewind out of review must
cite the review feedback it is rewinding (pass `--review-ref <ref>`).
```

Exit non-zero, no `event_id`/`to_lane` in `--json` output, `status.events.jsonl` and
`status.json` byte-identical (`NFR-001`).
