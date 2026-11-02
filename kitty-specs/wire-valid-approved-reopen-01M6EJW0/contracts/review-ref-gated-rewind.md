# Contract: the review-ref-gated rewind family

**Owner**: this mission pins the *local* shape only. The wire contract itself is
`spec-kitty-events` 11.3.0's "Review-Ref-Gated Rewind Family" and is consumed, never edited
(`C-001`).

## C-RRR-1 — Member edges

The local "this edge requires a `review_ref`" set is exactly:

```
(for_review, in_progress)
(approved,    in_progress)
```

No other edge is a member. The pinned contract's third gated edge,
`in_review -> in_progress`, is deliberately absent: its evidence is a structured
`review_result` that the status emit path never turns into a `review_ref`, so gating
it here would refuse legitimate writes. Closing that edge is follow-up #7080, and
`test_force_elsewhere_is_unchanged` pins that it is still admitted locally until
then, so the deferral cannot silently flip in either direction. `for_review -> planned`, `approved -> planned`,
`in_progress -> planned`, `done|blocked|canceled -> *`, `planned -> in_progress` and every
forward edge are unaffected.

## C-RRR-2 — The requirement is force-insurmountable

A pointerless (missing or whitespace-only) payload on a member edge is refused by the
writer whether or not `force` is set, before any append. The refusal names `review_ref` and
`--review-ref`, exits non-zero, and leaves `status.events.jsonl` and `status.json`
byte-identical.

## C-RRR-3 — A `migration:` actor is exempt at the writer

`is_migration_actor(actor)` bypasses the refusal (reconstruction restates state; #5446
precedent). The auditor still reports such a row.

## C-RRR-4 — An emitted forced rewind cites an existing reference

When the emitter plans a forced transition on a member edge and no pointer was supplied, it
fills `review_ref` with `force-override` — a sanctioned, non-resolvable sentinel
(`review.cycle.REVIEW_FEEDBACK_SENTINELS`). A supplied real pointer always wins over the
sentinel.

## C-RRR-5 — Evidence policy is not this contract's subject

The FR-015/#6845 rule for the approved reopen (usable feedback ⇒ force-free + file pointer;
empty or missing file ⇒ refusal; no file ⇒ forced) is unchanged. This contract only says
the forced row must carry a reference, which is what the wire contract already required.

## Verification map

| Contract clause | Test |
|---|---|
| C-RRR-1 | `test_requires_review_ref_covers_the_gated_family` (enumerates the set) + `test_local_edge_set_equals_the_contract_members_it_claims` against the pinned package |
| C-RRR-2 | `test_pointerless_gated_rewind_is_refused_before_append` for `approved` + SHA-256 identity (the `for_review` edge keeps its #6514 pins) |
| C-RRR-3 | `test_migration_actor_is_exempt_from_the_requirement` |
| C-RRR-4 | owned-checkout `move-task` repro (sentinel + wire validity) and the `for_review` control |
| C-RRR-5 | `test_owned_approved_reopen_feedback_contract` for the `provided`, `empty` and `missing` kinds (existing pins) |
