# Data Model: Lane evidence and review independence

No persisted schema changes. Two value concepts and one recorded event shape.

## EvidenceWindow (value object)

| Field | Meaning |
|-------|---------|
| `base` | `lanes.json planning_commit_sha` |
| `tip` | code lane: the lane branch; planning lane: the target branch; single_branch: the Mission branch |

Invariant: `base` must be recorded; otherwise the verdict is `EVIDENCE_WINDOW_UNCOMPUTABLE`.

## EvidenceVerdict (per approved work package)

Ordered, first match wins:

1. `EVIDENCE_WINDOW_UNCOMPUTABLE`: no recorded base.
2. `IMPLEMENTATION_UNREADABLE`: the window's tree diff cannot be read.
3. `IMPLEMENTATION_MISSING`: no non-bookkeeping changed path matches the WP's owned files, and
   the WP carries no no-implementation attestation.
4. `REVIEW_NOT_INDEPENDENT`: `_independent_reviewer_confirmed` is False.
5. pass.

Codes 1–3 are lifted by nothing except (3) by the attestation; code 4 is lifted by nothing.

## No-implementation attestation (recorded transition)

| Field | Value |
|-------|-------|
| `from_lane` / `to_lane` | the WP's current lane (`approved` or `done`), to itself |
| `force` | `true` |
| `reason_source` | `operator` |
| `reason` | `operator attests no implementation is owed: <reason>` |
| `policy_metadata.attestation` | `no_implementation` |
| `evidence.review.reference` | `operator-attestation:<WP>` |

Read rules: lifts verdict 3 for its WP (the newest such record counts, any time); never read as
an approval, an approval stamp, the approving actor, or a review.
