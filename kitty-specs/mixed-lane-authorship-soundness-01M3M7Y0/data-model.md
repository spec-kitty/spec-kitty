# Data Model — Mixed-lane authorship soundness

## Attribution stamp (persisted)
`StatusEvent.policy_metadata["lane_head"]: str` — 40-hex SHA of `refs/heads/<lane branch>` at the moment the transition was persisted. Present only when the WP maps to a non-planning lane whose branch exists. Merged with any caller-supplied `policy_metadata` (caller keys win on conflict — none today).

## WorkWindow (derived, pure)
| Field | Meaning |
|---|---|
| `wp_id` | WP the window belongs to |
| `kind` | `implementation` (`claimed`/`in_progress`/`blocked`) or `review` (`for_review`/`in_review`) |
| `open_head` | stamp on the transition that entered the interval |
| `close_head` | stamp on the transition that left it; `None` = still open |

Invariants: windows per WP are ordered by event append order; an entered-implementation WP with zero stamped windows ⇒ unattributable.

## AttributionOutcome (derived, per canceled WP in a mixed lane)
`attributed(commits: frozenset[sha])` (non-merge commits only) | `unattributable(reason)` — reasons: `no_stamp`, `open_window`, `stamp_not_ancestor_of_lane_tip`, `contested_commit`, `events_unreadable`, `spine_unreadable`.

## CanceledContent (claim field)
`ApprovedWpCommitSet.canceled_content: frozenset[CanceledPathState]` with `CanceledPathState(wp_id, lane_id, path, canceled_state, pre_state, pre_state_by_survivor)` (`pre_state_by_survivor` = a non-canceled, non-merge lane commit on the spine touched the path before the canceled WP's oldest touch); a state is a blob sha or `None` (absent). Present iff the newest non-merge, non-bookkeeping first-parent commit touching the path is the canceled WP's and `canceled_state != pre_state` (pre-state = content at the parent of the canceled WP's oldest commit touching the path). Empty for hand-built claims (pre-change behaviour byte-for-byte).

## Divergence.canceled_content (verdict)
`tuple[tuple[wp_id, lane_id, path, blob_or_None], ...]` — entries whose state the target carries. Any entry ⇒ FAIL.

## State transitions affected
None added or changed; stamping is metadata on existing transitions.
