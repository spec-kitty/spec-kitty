---
type: reference
updated: 2026-11-12
---

# Data model

All types are frozen dataclasses (value objects). Nothing is persisted, except the status-event stamps of IC-02, whose schema is unchanged.

## WpReviewRange (`specify_cli/review/wp_range.py`)

| Field | Type | Notes |
|---|---|---|
| `wp_id` | `str` | |
| `base` | `str \| None` | Full SHA. `None` iff `status is UNAVAILABLE`. |
| `tip` | `str \| None` | Full SHA. `None` iff `status is UNAVAILABLE`. |
| `base_source` | `RangeSource` | `RECORDED_WINDOW` · `CLAIM_BASE_REF` · `EVENT_COMMIT` · `NONE` |
| `tip_source` | `RangeSource` | `RECORDED_SUBMISSION` · `EVENT_COMMIT` · `NONE` |
| `gap` | `str \| None` | The reason the recorded value was not used: `not_recorded`, `lane_branch_missing`, `capture_failed`, `not_on_lane`, `no_submission`, `unresolvable_sha`. |
| `status` | `RangeStatus` | `RECORDED` (both ends recorded) · `DERIVED` (either end derived) · `UNAVAILABLE` |
| `moved_past` | `int` | Commits on the branch after `tip`. 0 when the tip is the live head. |
| `commits` | `tuple[RangeCommit, ...]` | Implementation commits, oldest first, bookkeeping excluded. |
| `bookkeeping_commits` | `int` | Count of excluded commits. |
| `files` | `tuple[FileChange, ...]` | In-owned-files, path-sorted. |
| `out_of_map` | `tuple[str, ...]` | Changed paths outside the owned files. Empty when no owned files are declared. |
| `owned_pathspecs` | `tuple[str, ...]` | Pathspecs the commands use. Empty means unscoped. |

Invariants:
- `status is UNAVAILABLE` ⇔ `base is None or tip is None`.
- When available, `base` is an ancestor of `tip`. If it is not, the range is a `not_on_lane` gap, and the next fallback is tried.

## RangeCommit / FileChange

- `RangeCommit(sha: str, subject: str)`
- `FileChange(path: str, added: int | None, removed: int | None)`. `None` marks a binary file.

## CitedRequirement (`requirement_mapping/text.py`)

| Field | Type | Notes |
|---|---|---|
| `ref` | `str` | As cited (canonical form). |
| `resolution` | `Resolution` | `DECLARED` · `NOT_DECLARED` · `OTHER_MISSION` · `AMBIGUOUS` |
| `text` | `str \| None` | Declared text, at most 600 characters plus a marker. `None` unless `DECLARED`. |

## Status-event stamps (IC-02; schema unchanged)

`policy_metadata.lane_head` (every transition) and `policy_metadata.wp_window` (opening transitions) are now also written for commit-to-target `single_branch` WPs. The value is the head of the target branch (= write branch).
