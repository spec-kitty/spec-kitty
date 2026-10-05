# Data model

No stored schema changes. The mission reads fields that already exist and adds one metadata value.

## Approval stamp (read)

- **Source**: `StatusEvent.policy_metadata["lane_head"]` on the latest non-migration event of a work package that has `to_lane == "approved"` or is an approved-reviewed attestation.
- **Absent when**: the approval was recorded before 4.0.0rc5, the probe could not read the lane branch, or the work package reached `done` with no `approved` event.

## Attestation record (written)

| Field | Value |
|---|---|
| `from_lane`, `to_lane` | the work package's current lane (`approved`, or `done` after an interrupted run) |
| `force` | `true` |
| `reason` | fixed prefix + the operator's reason |
| `reason_source` | operator |
| `policy_metadata.attestation` | `"approved_reviewed"` |
| `policy_metadata.lane_head` | stamped by the transition pipeline |
| `evidence` | as the transition contract requires for `approved` / `done` |

## Lane check result (in memory)

| Field | Meaning |
|---|---|
| `code` | `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_MISSING` or `APPROVAL_STAMP_NOT_ON_LANE` |
| `lane_id`, `branch` | the refused lane |
| `wp_ids` | the work packages the refusal names |
| `commits`, `path` | up to three commits and one path (post-approval commits only) |

## Gate re-check inputs (in memory, set at claim time)

| Field | Meaning |
|---|---|
| `validated_lane_tips` | lane branch to the tip the up-front check validated |
| `bound_anchor_shas` | the mission branch, the target and the coordination base, each resolved to a SHA at claim time |

## Invariants

- The `done` restamp is never an approval stamp.
- A migration event never supplies an approval stamp.
- An absent stamp is never replaced by the lane tip.
- Refusal order at claim time: existing claim refusals, then the mixed-lane resolution, then the lane check.
