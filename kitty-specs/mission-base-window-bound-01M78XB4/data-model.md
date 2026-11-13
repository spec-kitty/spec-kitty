# Data model — mission-base-window-bound-01M78XB4

## MissionBase (value object, `consolidation/mission_base.py`)

| Field | Type | Rule |
|---|---|---|
| `sha` | `str \| None` | `None` iff provenance is `unavailable` |
| `provenance` | `recorded \| derived \| unavailable` | recorded wins; derived only when nothing is recorded |
| `reason` | `str \| None` | why it is derived/unavailable (shown in the note line) |

Invariant: a non-`None` `sha` resolves to a commit that is an ancestor of (or equal to) the Mission branch tip.

## PreMissionHistory (claim inputs → claim)

| Field | Source |
|---|---|
| `shas` | `rev-list <window_base>..<mission_base>`; empty when the target reaches the base |
| `blobs`, `deletions` | `_final_authored_walk(shas)` — the walk #6771 uses |

## meta.json

New optional key `mission_base_sha` (40-hex), written once where the Mission branch is created (topic/protected mint, coordination-branch create). Absent on older Missions.

## ApprovedWpCommitSet (claim)

New fields `pre_mission_shas`, `pre_mission_blobs`, `pre_mission_deletions` (default empty), read by the verifier wherever it reads `external_dependency_*`.
