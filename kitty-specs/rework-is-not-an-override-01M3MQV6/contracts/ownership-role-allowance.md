# Contract: ownership role allowance

`_ownership_role_allowance(req) -> bool` is pure (no I/O) and is evaluated by `_guard_agent_ownership` only when the existing checks would refuse. The existing checks refuse when all of these hold: the slot occupant is not a generic actor, the tool keys differ, and `--force` is absent.

Returns True iff `req.latest_implementer` is known (not `None`/empty) and one of the following holds:

1. **Reviewer arm**: `old_lane == for_review`, `target_lane ∈ {in_review, approved, planned}`, and `_actor_key(req.agent) != _actor_key(req.latest_implementer)`.
2. **Implementer arm**: `old_lane ∈ {planned, claimed, in_progress}`, `target_lane ∈ {claimed, in_progress, for_review}`, and `_actor_key(req.agent) == _actor_key(req.latest_implementer)`.

Otherwise it returns False, and the refusal is byte-identical to today's: the `Agent mismatch: …` error; for rejection/approval saves under auto-commit, the `ownership_refusal` diagnostic; and the console warning, which may add one hint line.

Lanes are alias-normalized. `in_review → *` is never allowed by this function.

## `latest_implementer_actor(events, wp_id)` (pure, `status/review_roles.py`, re-exported from `specify_cli.status`)

It returns the actor of the latest transition with `to_lane ∈ {claimed, in_progress}`, skipping two kinds of event:

- a **reviewer rework verdict**: `from_lane ∈ {for_review, in_review, approved}` and a `review_ref` set. This covers `in_review → in_progress` rejections and the legacy review claim `for_review → in_progress` with `review_ref="action-review-claim"`.
- an event whose actor projects (`_actor_key`) to a generic actor (`GENERIC_IMPLEMENTATION_ACTORS`: `user`, `implement-command`, `unknown`, …).

It returns `None` when nothing qualifies, and the guard then allows nothing.

Notes (post-plan squad):

- `agent action implement` rework emits `for_review|in_review|approved → in_progress` with the implementer as actor and **no** `review_ref`. That event counts, so a takeover via `action implement` moves the implementer role.
- A forced `planned → claimed` on a legacy log may carry a copied rejection `review_ref`. Its `from_lane` is `planned`, so it still counts.
- `move-task` hop expansion stamps whoever moves a WP forward from `planned`/`claimed`. Anyone who walks a WP through `claimed`/`in_progress` becomes the latest implementer, by definition. The acceptance tests must not route a reviewer through `planned → in_review`.
- The residual is accepted and documented, not fixed: once a same-tool implementer resubmits, the slot holds that implementer. The existing same-key check then lets it approve its own work from `for_review` unforced. This is today's behaviour (pre-existing), and the guidance must not claim otherwise.
