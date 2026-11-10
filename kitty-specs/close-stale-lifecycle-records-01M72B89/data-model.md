# Data Model: Close stale WP lifecycle records

## Lifecycle record (`kitty-ops/lifecycle/<ulid>.json`)

| Field | Type | Notes |
|-------|------|-------|
| `canonical_action_id` | string | Copied verbatim from the `started` record (FR-011 of the lifecycle contract). |
| `phase` | `started` \| `completed` \| `failed` \| **`abandoned`** | `abandoned` is new: closed by `doctor ops --close-stale`. |
| `at` | ISO-8601 UTC | Write time of this record. |
| `agent` | string | Copied from the `started` record. |
| `mission_id` | string | Copied from the `started` record. |
| `wp_id` | string \| null | Copied from the `started` record. |
| `reason` | string \| null | For `abandoned`: names the doctor sweep and the threshold. |
| `metadata` | map, optional | For `abandoned`: `closed_by: doctor_sweep`. Readers that do not know it ignore it. |

**Invariants**

- A record file is created once and never rewritten or removed (ADR 2026-11-01-2).
- A completion is any of `completed`, `failed`, `abandoned`. A group `(mission_id, canonical_action_id)` is orphaned while `started` outnumbers completions.
- The sweep writes one `abandoned` record per stale unpaired `started` record, and only through the locked lifecycle append.

**State transitions (per started record)**

```
started --(next --result success)--> completed
started --(next --result other)----> failed
started --(doctor ops --close-stale, older than threshold)--> abandoned
```

## Sweep report entry (`lifecycle_records[]`)

| Field | Type | Notes |
|-------|------|-------|
| `canonical_action_id` | string | |
| `mission_id` | string | |
| `wp_id` | string \| null | |
| `agent` | string | |
| `started_at` | ISO-8601 | The `started` record's `at`. |
| `age_hours` | number \| null | `null` when `at` cannot be read. |
| `action_taken` | `none` \| `closed_abandoned` | `none` for a fresh orphan. |
| `path` | string \| null | Repository-relative path of the closure file, when written. |
| `commit` | string \| null | `committed`, `skipped:<reason>` or `not_committed:<refusal>`. |
| `error` | string \| null | A write failure for this entry; the sweep continues. |
