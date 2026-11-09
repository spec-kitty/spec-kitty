# Draft follow-up comment for spec-kitty/spec-kitty-events#229 (NOT posted; posting needs operator authorization)

Follow-up from the core Mission closeout (spec-kitty/spec-kitty#7403): the shape as shipped, which differs from the issue body in two places.

1. **Written vs reader-only gaps.** A writer only ever writes two gap reasons: `capture_failed` (with `cause`: `git_error` | `probe_error`) and `lane_branch_missing` (**no `cause`**; the lane branch did not exist at the move, for example a claim before `implement`). `not_recorded` and `not_on_lane` are derived by the reader and must never be written.
2. **Every opener carries the key.** The writer stamps every non-migration move into `claimed` or `in_progress` of a lane-mapped work package, not only the first; the reader picks the opener. `blocked` writes nothing.

Value of `policy_metadata.wp_window` (`schema_version: 1`, `additionalProperties: false` at both levels):
```
{"schema_version": 1, "open_sha": "<40 hex>"}                         # or
{"schema_version": 1, "gap": {"reason": "capture_failed", "cause": "git_error"|"probe_error", "detail": "<=500 chars"}}
{"schema_version": 1, "gap": {"reason": "lane_branch_missing", "detail": "<=500 chars"}}   # cause forbidden
```
Writer rules: same lane-head reading as `lane_head` (`open_sha == lane_head` on the row); never refuse, delay or retry a move for it; never touch another key; never backfill; a relaying writer preserves the key verbatim.

Reader rules, for reference: R-1 bind to the window opener (cycle after the last non-review move to `planned`; skip leading `lane_branch_missing`; topology order, log order when unrelated); R-2 no key → `not_recorded`; R-3 `capture_failed` keeps its `cause`/`detail`; R-4 SHA not an ancestor of the lane tip or unresolvable → `not_on_lane`; R-5 schema-invalid value → `not_recorded`, never fatal; R-6 a gap never refuses; R-7 the SHA is valid for one consolidation attempt (branch-relative).

**Request (unchanged):** when the Java write service writes or relays status transitions, write and preserve `policy_metadata.wp_window` with exactly this shape, and type it in the mission-status contract. The full contract is `kitty-specs/consolidation-window-provenance-01M6Y84D/contracts/status-event-wp-window.md` on spec-kitty/spec-kitty `feat/consolidation-window-provenance`.
