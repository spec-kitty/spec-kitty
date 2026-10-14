---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-mission-detail-01M4S6D5
reproduction_command:
reviewed_at: '2026-10-14T10:39:09Z'
reviewer_agent: claude
wp_id: WP14
---

# WP14 review, cycle 1: changes requested

Tip reviewed: 23fa74f39. Gates all green (listed in the reviewer report). One finding, severity 3, plus two notes.

## F1 (severity 3): the V18 fixture `history-event-id-leak` is not valid JSON, and D-P10-1 plus the M3 row pin a false reason

**Where.**
- `services/mission-status-api/src/test/resources/conformance/projection-refusals/history-event-id-leak/PROVISION_PLAN` (WP07's file, line 1).
- `WorkPackageControllerRowsTest.java:241-242` (the `M3 ... history-event-id-leak` row and its comment).
- `design-decisions.md`, D-P10-1 "Consequence for T12".
- Comment of `ResolvedStateGoldenTest#v25` is fine (it does not repeat the claim).

**Failure scenario.**
- The plan substitutes `@@PATH@@` with `C:` + `\Users\` + `someone` + `\ev` as raw text. Inside the JSONL line this is `"event_id": "C:\Users\someone\ev"`, which has an invalid JSON escape (`\U`).
- The line is malformed, so the whole ledger is `ledger_unparseable` before any projection runs. That is why the row answers `ledger_unparseable`, not DD-110.
- The stated reason is false. Plan T2/T11 and the code (`MissionHeadProjection:81`, `strict(..., true)`) project the head `lastEventId` as nullable: a leaking last id gives null, not a refusal.
- Reproduced in the built JVM jar and in the native binary with the same fixture, only the backslashes escaped (`C:\\Users\\someone\\ev`):
  - `getMission` answers 200 with `"lastEventId":null`.
  - `getWorkPackage` answers 500 `projection_refused`.
  - Unescaped (as committed): both routes answer 500 `ledger_unparseable`.
- Consequences:
  - The Java-only fixture of plan T102 / V18 (`projection_refused`) never reaches T12.
  - The M3 row pins an outcome that only a broken fixture produces.
  - D-P10-1 tells the next reader that T12 is reachable only on a non-last row, which is wrong (it is reachable on the last row too).
  - Adopting "a spec fold" for it would write a falsehood into the spec.

**Remedy.**
1. Make the fixture valid JSON. Either escape the backslashes in the PROVISION_PLAN fragments (fragments joined raw: `C:` `\\` `Users` `\\` `someone` `\\` `ev`), or use a slash-shaped path with no backslash. This is a named edit of WP07's fixture.
2. Change the M3 row to `refused(PROJECTION_REFUSED, PROJECTION_REFUSED)` with a comment that says the head nulls `lastEventId` (T2/T11) and the history refuses (T12). Keep the non-last-row `WorkPackageMapperTest#t12` case.
3. Rewrite D-P10-1 "Consequence for T12" accordingly. No spec or plan fold is needed: plan T12 and V18 hold as written.
4. The whole-ledger refusal for a non-text `event_id` (V25) stands. I verified the stated reason: narrowing would make the overview and the stream serve ledgers they refuse today.

## Notes (not blocking)

- N-a: D-P10-5 says "9 `DIVERGENT` fixtures ... wpm-28 and the 8 resolved-state". The code holds 8: wpm-28 plus 7 resolved-state (V21: 1, V22: 3, V23: 1, V24: 1, V25: 1). Correct the count in the same edit as F1. The 17 empty goldens are exactly the 17 `wp-malformed-frontmatter` `{}` pairs, and `theNamedTestsCoverEveryDivergentFixture` covers the 8.
- N-b: `WorkPackageControllerRowsTest#symlink` uses `Assumptions.abort` on a host without symlinks. A skip does not write `build/reports/not-run.txt` (WP06 hook). WP17's CI check should know it, or the helper should append the line.
