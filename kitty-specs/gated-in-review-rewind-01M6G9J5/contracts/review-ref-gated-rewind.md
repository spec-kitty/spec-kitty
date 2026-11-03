# Contract: the review-ref-gated rewind family

The shared `spec_kitty_events` contract (its module docstring, "Review-Ref-Gated Rewind
Family") gates three backward rewinds to `in_progress` on a non-empty `review_ref`, whether or
not the event is `force`d:

| from_lane | to_lane |
|---|---|
| `for_review` | `in_progress` |
| `in_review` | `in_progress` |
| `approved` | `in_progress` |

This mission (`#7080`) makes the local tree conform on `in_review -> in_progress`.

## C-1 — One owning edge set

`src/specify_cli/status/wp_state.py::REVIEW_REF_REQUIRED_EDGES` is the single definition of
"this edge requires a `review_ref`". The write path (`WPState.check_transition`), the auditor
(`status.validate.validate_event_schema`) and the emitter's sentinel fill
(`tasks_transition_core.build_transition_plan`) all read it. No second literal set.

On this branch the set is `{for_review -> in_progress, in_review -> in_progress}`. The third
contract edge, `approved -> in_progress`, is gated by #6955 (PR #7102) and is deliberately not
asserted here, so the two missions cannot falsify each other's pins in either merge order.

## C-2 — The pointer reaches the wire before the gate

An `in_review` exit carries its evidence as a structured `review_result`. `prepare_transition`
(`src/specify_cli/status/transition_pipeline.py`) — the tree's only validation and event-build
authority, reached by `agent status emit`, `orchestrator-api wp transition`,
`emit_status_transition`, the batch door and the coordination shell — derives the event's
`review_ref` from `review_result.reference` when the caller supplied none. The derived value is
used for BOTH the guard context and the recorded event, so the two cannot disagree.

Rules:

- an absent pointer is filled from a non-blank string `review_result.reference`;
- a caller-supplied `review_ref` is returned unchanged (never replaced);
- the existing `review_ref == review_result.reference` consistency refusal is unchanged;
- a blank or non-string structured reference is not a pointer, so the requirement stays
  unsatisfied.

## C-3 — The requirement is force-insurmountable

`--force --reason` overrides a missing edge or a guard, never this. A `migration:` actor keeps
its #5446 exemption (it reconstructs state; the auditor still reports such a row).

## C-4 — Refusal is a zero-byte decision

A refused rewind exits non-zero naming `review_ref` / `--review-ref` and leaves
`status.events.jsonl` and `status.json` byte-identical: the rule is evaluated in validation,
before the lock-protected append, the materialization and the frontmatter mirror.

## C-5 — History is append-only

No code or migration rewrites a stored row. A pointerless row written before this change stays
as written; `status validate` reports it, and the only supported correction is an operator
append that preserves the original record (see the status reference, "Rows written before this
refusal").

## C-6 — The wire contract is consumed, never changed

The mission does not edit, vendor, patch or re-pin `spec-kitty-events`; the emitted payload
conforms to the installed release.
