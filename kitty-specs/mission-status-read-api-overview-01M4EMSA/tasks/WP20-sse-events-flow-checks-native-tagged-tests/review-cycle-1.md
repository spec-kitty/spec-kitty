---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T16:03:04Z'
reviewer_agent: reviewer-renata
wp_id: WP20
---

# WP20 review cycle 1: returned for fixes (reviewer-renata, plus an operator ruling)

The full evidence is in wp20-review-verdict.md (orchestrator scratchpad). Everything else passed:
- all 66 stream tests cover AC-3a..3o and S1..S6;
- every reviewer mutation went red;
- the stream package ran 3 times without a flake;
- the AC-11a, AC-16, AC-10c and AC-9h checks have positive controls;
- native is green;
- `check` passes with 1982 tests.

The rulings are at the end of reviews/analyze.ruling.md (2026-10-12) and in DD-110.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F2 | medium | application/MissionStatusService.java:375 (`projected`); flow/CanaryScanTest | AC-9g gap: `lastEventId` is served raw on `GET /missions` and `/project`. A path-shaped `event_id` canary came back verbatim, while the stream refuses the same value. | Operator ruling: project `lastEventId` strictly, through the same `Projector.strict` as the stream's `eventId`. Check the contract for whether `lastEventId` is nullable. Nullable means a leak-shaped value becomes null; non-nullable means it is refused with `projection_refused`. This is an out-of-map edit of WP06's file: make it its own commit with a one-line rationale. Keep per-class JaCoCo green. Add an `event_id` canary to the JSON-route part of the canary scan, plus a revert row (remove the projection, and the scan goes red). The JSON-route goldens must stay byte-equal, since real fixtures use ULID ids; confirm that. |
| F3 | low | config/nativetags/NativeJsonSseRoundTripTest.java:49 | The "members in sorted order" assertion is always true. | Compare `indexOf("acceptedAt") < indexOf("blockedCount")`, or check the full key order directly. Add a revert row. |
| F4 | low | flow/CanaryScanTest.java:38 | The synthetic canary uses a `/home/canary-user/...` literal. | Use a path-shaped value outside `/home` and `/Users`, for example `/srv/canary-user/CANARY-PATH-7`, and make sure it is still caught by a host-path pattern. If only `/home`-style paths are leak-classed, keep the shape but build the string at runtime, so no `/home` literal sits in the source. |
| F5 | low | flow/NoProcessStartTest.java:34, 83 | The JFR dump directories are created with `Files.createTempDirectory` and never deleted. | Use `@TempDir`. |

No action in this WP:
- F1: the skeleton native tests are deleted in WP12, and the floor stays at 3.
- F6: the skeleton ArchUnit probe is handled in WP12.

Run all mutations in a scratch worktree.
