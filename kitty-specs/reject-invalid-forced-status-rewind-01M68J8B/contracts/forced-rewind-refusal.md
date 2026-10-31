# Contract: the forced-rewind refusal (#6514)

The observable contract of this mission. It is stated in terms of what an operator or a
harness sees, so a test can assert it without reaching into the FSM.

## C-1 — Invalid forced rewind is refused before append

**Request** (either door: `agent status emit`, `orchestrator-api wp transition`):

```
wp_id        = WP01
from_lane    = for_review        (derived, not supplied)
to_lane      = in_progress
force        = true
reason       = "<non-blank>"
review_ref   = null | "" | "   "
```

**Outcome**

| Aspect | Before this mission | After |
|---|---|---|
| exit code | `0` | non-zero (`1`) |
| appended rows | `+1` | `+0` |
| `status.events.jsonl` | grew | byte-identical (same SHA-256) |
| `status.json` | rematerialized | byte-identical (same SHA-256) |
| `agent status validate` | `exit 1`, `for_review->in_progress without review_ref` | `exit 0` |
| `--json` | `{"event_id": ..., "to_lane": "in_progress", ...}` | `{"error": "...requires review_ref... --review-ref ..."}`, no `event_id`, no `to_lane` |

The refusal is raised from the pure validation step, so it holds whether the mission
writes flat or through a coordination worktree.

## C-2 — The pointer-carrying rewind still lands (positive control)

Same fixture, same request, `review_ref = "review-cycle://WP01/1"`:

| Aspect | Expected |
|---|---|
| exit code | `0` |
| appended rows | `+1`, `to_lane = in_progress`, `review_ref` preserved verbatim |
| `agent status validate` | `exit 0` |

This is the same-fixture positive control for C-1: without it, "nothing was appended"
cannot be distinguished from "the probe cannot see an append".

## C-3 — Force is otherwise unchanged

| Edge | `review_ref` | Expected |
|---|---|---|
| `done → in_progress` (forced, reason) | `null` | allowed, unchanged |
| `canceled → planned` (forced, reason) | `null` | allowed, unchanged |
| `planned → in_progress` (forced, reason) | `null` | allowed, unchanged |
| `for_review → planned` (forced, reason) | `null` | allowed, unchanged — outside the set, and the auditor does not refuse it |
| `in_review → in_progress` (forced, reason) | `null` | allowed, unchanged — #5446 force-note rule still the only gate |
| `for_review → in_progress` via `move-task` (forced) | `"force-override"` (supplied by `move-task`) | allowed, unchanged |

## C-4 — Message contract

The refusal message contains all of:

1. the missing field name `review_ref`;
2. the edge, in the `for_review -> in_progress` form the auditor uses;
3. the supplying flag, `--review-ref`.

A harness may match on `review_ref` and `--review-ref`; it must not need to match the
whole sentence.

## C-5 — Non-force behaviour is untouched

A force-free `for_review → in_progress` keeps today's refusal, including its text
(`Illegal transition: for_review -> in_progress`), because that path returns from the
structural check before the new requirement is evaluated.
