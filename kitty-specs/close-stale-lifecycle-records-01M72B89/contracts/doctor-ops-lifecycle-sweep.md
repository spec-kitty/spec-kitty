# Contract: `doctor ops --close-stale` lifecycle sweep (additive)

Extends the frozen sweep contract of `kitty-specs/do-dispatch-open-op-lifecycle-01KTSJ2H/contracts/doctor-ops-close-stale.md` with one additive key. That archived contract is not edited.

## Command

`spec-kitty doctor ops --close-stale [--threshold HOURS] [--json]` (unchanged flags).

## Behavior

1. Close stale Ops exactly as today.
2. In every checkout of the repository, read the lifecycle records and find each unpaired `started` record.
3. A `started` record older than `--threshold` hours (or any, at `0`) gets one new `abandoned` record paired with it, with reason `abandoned by doctor ops --close-stale (older than <N>h)` `metadata.closed_by = doctor_sweep` and `metadata.closes_started_at` (the `at` of the record it closes).
4. Commit each checkout's new closure files in one commit on its current branch, unless the #6410 rules skip it (path ignored, or the primary branch tracks no lifecycle records). A protected-branch refusal is reported, not bypassed.
5. Never read or write Mission status, `meta.json` or work package files.

## Exit code

`1` when any Op or lifecycle entry has an error, or any fresh Op or fresh lifecycle orphan is left open; otherwise `0`.

## JSON (additive)

```json
{
  "open_ops": [...],
  "swept": 0,
  "skipped_fresh": 0,
  "threshold_hours": 24.0,
  "closure_spine": "kitty-ops/op-closures.jsonl",
  "lifecycle_records": [
    {
      "canonical_action_id": "implement::implement",
      "mission_id": "01M6VYS1...",
      "wp_id": "WP04",
      "agent": "claude",
      "started_at": "2026-11-07T10:00:00+00:00",
      "age_hours": 50.2,
      "action_taken": "closed_abandoned",
      "path": "kitty-ops/lifecycle/01M72....json",
      "commit": "committed",
      "error": null
    }
  ]
}
```

`open_ops`, `swept`, `skipped_fresh`, `threshold_hours` and `closure_spine` keep their meaning and count Ops only.
