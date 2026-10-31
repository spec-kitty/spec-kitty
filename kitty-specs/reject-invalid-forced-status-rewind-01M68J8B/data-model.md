# Data Model: Reject invalid forced status rewinds before append (#6514)

No stored shape changes. `StatusEvent`, `status.events.jsonl` and `status.json` keep
their current schema and byte layout; this mission only narrows which events may be
written. The entities below are the ones the rule reads.

## `REVIEW_REF_REQUIRED_EDGES` (new, `status/wp_state.py`)

The single owning definition of "an event on this edge must carry a `review_ref`".

| Field | Type | Notes |
|---|---|---|
| members | `frozenset[tuple[Lane, Lane]]` | `{(Lane.FOR_REVIEW, Lane.IN_PROGRESS)}` |
| consumers | `WPState.check_transition`, `validate.validate_event_schema` | writer admission + auditor |
| growth rule | add an edge here only when the auditor refuses that edge's events without a pointer | prevents a second, drifting copy |

## `requires_review_ref(from_lane, to_lane) -> bool` (new, `status/wp_state.py`)

The predicate over the set above. Resolves nothing and raises nothing: it is a membership
test on two already-canonical lanes. Whitespace handling belongs to the *requirement
check*, not the predicate, so the auditor (which sees a decoded string or `None`) and the
writer (which sees the request field) apply the identical `strip()` rule.

## Requirement check (one expression, two call sites)

```
requires_review_ref(from, to) and not (review_ref or "").strip()  →  refuse
```

| Call site | Input | Effect |
|---|---|---|
| `WPState.check_transition` (write admission) | `GuardContext.review_ref` / `TransitionContext.review_ref` | returns `(False, message)` ⇒ `InvalidTransitionError` ⇒ `TransitionError` at the pipeline ⇒ nothing appended |
| `validate.validate_event_schema` (audit) | decoded event's `review_ref` | appends the existing `Event <id>: for_review->in_progress without review_ref` finding |

## `StatusEvent` (unchanged, relevant fields)

| Field | Type | Role in this mission |
|---|---|---|
| `from_lane` | canonical lane | half the key into the requirement set |
| `to_lane` | canonical lane | half the key into the requirement set |
| `force` | bool | no longer sufficient to admit `for_review → in_progress` |
| `review_ref` | `str \| None` | the pointer the rule requires on that edge |
| `reason` | `str \| None` | unchanged: still the force audit note |

## Refusal message (new constant)

One message, naming the missing field and the flag that supplies it, e.g.

```
Transition for_review -> in_progress requires review_ref: a forced rewind out of
review must cite the review feedback it is rewinding (pass `--review-ref <ref>`).
```

It must appear in the `--json` `error` value verbatim (NFR-003) so an operator or a
harness can match on it without parsing prose.

## State invariants

| ID | Invariant | Proof |
|---|---|---|
| I-1 | A refused rewind leaves `status.events.jsonl` and `status.json` byte-identical. | SHA-256 of both files before and after the refused CLI invocation. |
| I-2 | No event on an edge in `REVIEW_REF_REQUIRED_EDGES` can be appended with a blank `review_ref`. | The refusal is inside `check_transition`, which every emit door reaches before any append. |
| I-3 | The auditor and the writer read one definition. | Both import `requires_review_ref`; a second inline copy is the review finding this mission forbids. |
| I-4 | History is never mutated. | The diff touches no `status.events.jsonl` and adds no writer of historical events. |
