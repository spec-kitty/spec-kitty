# Contract: `policy_metadata.wp_window` on status transition events

**Status**: Proposed with the Mission ADR (`docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md`).
**Contract version**: `schema_version: 1`.
**Carrier**: `kitty-specs/<mission>/status.events.jsonl`, the `policy_metadata` object of a lifecycle transition row. `spec_kitty_events` types `policy_metadata` as an open `dict[str, Any]`, so the key needs no events-library release to be written or read.
**Writers**: the Python status shells (`status/emit.py`, `coordination/status_transition.py`) through `status/transition_pipeline.py`, in this Mission. The Java write service is asked by the FR-006 issue, spec-kitty/spec-kitty-events#229, to write, preserve and type the same key (the `lane_branch_missing` gap reason was added after filing; a follow-up comment on #229 carries it, with operator authorization).
**Readers**: `consolidation/wp_attribution.window_open_of` (the only reader).

## Purpose

This key records the **window-open SHA** of a work package: the lane head when its work started. If that head could not be read, it records a typed **window gap** instead. The consolidation gate can then judge each approved work package against `(window-open SHA, newest approval stamp]` without rebuilding the window from branch history.

## JSON Schema (the value of `policy_metadata.wp_window`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://spec-kitty.ai/schemas/status/policy-metadata/wp-window/1",
  "title": "wp_window (status transition policy_metadata key)",
  "type": "object",
  "required": ["schema_version"],
  "properties": {
    "schema_version": { "const": 1 },
    "open_sha": { "type": "string", "pattern": "^([0-9a-f]{40}|[0-9a-f]{64})$" },
    "gap": {
      "type": "object",
      "required": ["reason"],
      "properties": {
        "reason": { "enum": ["capture_failed", "lane_branch_missing"] },
        "cause": { "enum": ["git_error", "probe_error"] },
        "detail": { "type": "string", "maxLength": 500 }
      },
      "oneOf": [
        { "properties": { "reason": { "const": "capture_failed" } }, "required": ["cause"] },
        { "properties": { "reason": { "const": "lane_branch_missing" } }, "not": { "required": ["cause"] } }
      ],
      "additionalProperties": false
    }
  },
  "oneOf": [
    { "required": ["open_sha"], "not": { "required": ["gap"] } },
    { "required": ["gap"], "not": { "required": ["open_sha"] } }
  ],
  "additionalProperties": false
}
```

## Examples

A recorded opening, on the `planned → claimed` row:

```json
{"actor":"claude","at":"2026-11-09T10:00:00+00:00","event_id":"01M70...","evidence":null,"execution_mode":"worktree","feature_slug":"example-01M6ZZZZ","force":false,"from_lane":"planned","reason":null,"review_ref":null,"to_lane":"claimed","wp_id":"WP02",
 "policy_metadata":{"lane_head":"3f1c0d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e","wp_window":{"schema_version":1,"open_sha":"3f1c0d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e"}}}
```

The lane branch does not exist yet at the opening move (for example `move-task --to claimed` before `implement`). The move still succeeds, and `lane_head` is absent as it is today. Readers skip this opener when it leads the cycle (R-1):

```json
{"...":"...","from_lane":"planned","to_lane":"claimed","wp_id":"WP02",
 "policy_metadata":{"wp_window":{"schema_version":1,"gap":{"reason":"lane_branch_missing","detail":"refs/heads/kitty/mission-example-lane-b not found"}}}}
```

A failed capture: the lane branch exists but cannot be read:

```json
{"...":"...","from_lane":"planned","to_lane":"in_progress","wp_id":"WP02",
 "policy_metadata":{"wp_window":{"schema_version":1,"gap":{"reason":"capture_failed","cause":"git_error","detail":"fatal: bad object refs/heads/kitty/mission-example-lane-b"}}}}
```

## Writer rules

| # | Rule |
|---|---|
| W-1 | Write the key on every transition where **all** hold: the actor is not a migration actor (`migration:` prefix); `to_lane` ∈ {`claimed`, `in_progress`}; the work package is mapped to a non-planning execution lane (or the Mission is `single_branch` with a minted Mission branch). |
| W-2 | Take the value from the **same** lane-head reading as `lane_head`. Do not read git a second time. When both are written, `open_sha == lane_head` on that row. |
| W-3 | A reading with a SHA writes `open_sha`. A reading of a mapped work package whose lane branch does not exist writes `gap.reason = lane_branch_missing` (no `cause`). Any other failed reading writes `gap.reason = capture_failed` with a `cause` from the closed set. A not-applicable reading (planning lane, unassigned work package, no `lanes.json`) writes nothing. |
| W-4 | Never refuse, delay or retry a move because of this key. |
| W-5 | Never change, add or remove any other key. A transition that does not qualify stays byte-identical to today's row. |
| W-6 | Never rewrite or backfill past rows (the log is append-only; ADR `2026-10-14-1-event-native-core-one-canonical-event-writer`, "Existing logs"). Never synthesize the key in a migration. |
| W-7 | A second writer (the Java write service) must write the same shape, or preserve the key verbatim when it relays a row. Dropping or renaming it turns every later window into a "not recorded" gap: a weaker check, never a refusal. |

## Reader rules

| # | Rule |
|---|---|
| R-1 | Bind to the **window opener** (FR-021): (a) the cycle starts after the work package's last non-migration move to `planned` whose `from_lane` is not `for_review`, `in_review`, `approved` or `done` (review rejections do not reset), found in event-log order; (b) candidates are the cycle's non-migration events with `to_lane` ∈ {`claimed`, `in_progress`}; `blocked` opens nothing; (c) leading candidates with `gap.reason = lane_branch_missing` are skipped; (d) if the first remaining candidate has no usable value, that is the gap (an unrecorded opener is never replaced by a later recorded one); otherwise, among candidates carrying `open_sha`, the one whose SHA is an ancestor of every other's wins, and event-log order decides when the SHAs are unrelated; (e) only skipped candidates → gap `lane branch missing`. |
| R-2 | That event has no key → gap `not recorded`. Read per event, never per Mission, so a log that straddles the upgrade still reads. |
| R-3 | `gap.reason = capture_failed` on the bound opener → gap `capture failed`, carrying the recorded `cause` and `detail`. |
| R-4 | `open_sha` present but not an ancestor of the lane tip, **or not resolvable in this clone** (another clone, garbage-collected object) → gap `not on lane`, never a probe error. The lane tip is the one the approved bound resolved for that lane, on every path (claim, forecast, resume, gate rebuild, `approved_bound_refusal`). The approval-stamp bound's existing rewritten-lane refusal still applies. |
| R-5 | A value that violates this schema (unknown `schema_version`, both or neither branch, bad SHA) is treated as absent (`not recorded`). It is never trusted and never fatal. |
| R-6 | A gap never produces a refusal by itself and introduces no refusal code. The work package is judged by the approval-stamp bound (degraded window from the claim base) and listed in the gap report. When every approved work package of a lane has a gap, the lane is judged by today's approval-stamp check unchanged (FR-023). |
| R-7 | Durability horizon: one consolidation attempt (forecast, fresh run, resume, teardown). After a rebase landing the SHA may not resolve, and no reader after landing may require it (ADR `2026-11-07-1-dossier-commit-shas-are-branch-relative-provenance`). |

## Compatibility and versioning

- **Additive**: old readers ignore the key. New readers accept old rows (R-2).
- **SHA classification**: `("status.events.jsonl", "policy_metadata.wp_window.open_sha")` is `BRANCH_RELATIVE` in `tests/architectural/test_dossier_sha_provenance.py::DOSSIER_SHA_FIELDS`.
- **Evolution**: a new field or cause bumps `schema_version`. Readers treat an unknown version as absent (R-5) until they are taught it. Typing the key in the spec-kitty-events status payload (with its own payload version) is the FR-006 follow-up; until then this document is the contract.
- **Not affected**: `orchestrator-api` envelopes (no contract-version change); the `lane_head` key and its consumers; the rollback snapshot and `state.json`. Named residual: because the envelope carries no gap report, a W-7 downgrade is invisible to an orchestrator until a later contract version carries it.
