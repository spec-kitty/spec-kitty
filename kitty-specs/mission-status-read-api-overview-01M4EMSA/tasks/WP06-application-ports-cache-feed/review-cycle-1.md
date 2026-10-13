---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T16:18:43Z'
reviewer_agent: reviewer-renata
wp_id: WP06
---

# WP06 review cycle 1: REJECT (reviewer-renata) with operator and orchestrator rulings

The full evidence is in wp06-review-verdict.md (orchestrator scratchpad). The rulings are at the end of reviews/analyze.ruling.md ("rulings from the WP06 review"), in spec FR-004 (amended) and in DD-91 to DD-93. WP06's owned_files now also cover `domain/model/**` (main and test), `domain/oracle/**` (test) and `adapter/out/filesystem/codec/**` (main and test), so this one round can make the cross-WP changes.

Everything else passed: scope, a green `check` with 930 tests, per-class coverage of at least 0.974 on every application class, framework-free code, every L-row and S-row pinned, every ruled item, and four revert rows re-run red.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| R1 | high | application/Resume.java:199, ChangeFeed.java:352; codec RowClassifier INVALID_ROW; domain MalformedReason; ChangeFeedTest:62-69 and 259-267 | A well-formed object that is not a usable row (unknown `kind`, unknown lane, missing key) arrives as `Malformed(NOT_OBJECT)` and closes the stream. AC-3b(iii) and FR-003 say it is dropped and the connection stays open. Python's `poll_once` raises only on invalid JSON or a non-object. | Add `MalformedReason.UNUSABLE_ROW`. The codec emits it for every object that is not a usable row (WP17's `INVALID_ROW` class). On a stream it is skipped and the offset advances past it, with no event and no close. The request routes are unchanged: every reason still gives `ledger_unparseable` (L3a), and the enum name is never served. Update `ValueObjectsTest`'s enum pin and WP17's parity tests and DIVERGENCES where they assert `NOT_OBJECT` for such objects. Fix `ac3b` so it asserts the stream stays open, and fix `s4EachKind...` so `{"actor":"c"}` is skipped, not closed on. Keep non-JSON, non-object and blank lines closing (L10/S4, AC-3k). Add a revert row. |
| R2 | medium | ChangeFeed.connectUnscoped (159-183); single `floor` in StreamSubscriber | Two unscoped subscribers lose a row. A is open, then Mission gamma is created with a row. B connects before the 1 s relist has found gamma. The shared watch is baselined at its end, so A never gets the row (the reviewer's scratch test printed `A=[] B=[]`). | Make the floor per subscriber and per Mission. Create watches for refs not yet `known` from offset 0. Record the connect offset as the new subscriber's floor for each Mission, so existing subscribers still receive rows the new watch reads. Add the reviewer's interleaving as a test. Add a revert row. |
| R3 | low | MissionStatusService:311-319 | A torn tail is reported as `ledger_torn_tail` even when an earlier terminated line is malformed. Python reports the first failing line. | Scan the terminated lines for `Malformed` before the tail check, and adjust the pinned test. |
| R4 | low | ProjectionCache.cursorOf (keep); domain/oracle/FixtureMissions comment | The code's cursor invariant is RIGHT: the last terminated line, blank included, as verified on `tail_reader`. The orchestrator's earlier ruling was wrong and is corrected (DD-92). No test covers a ledger ending in a blank line. | Keep the code. Add a test for a ledger ending in a blank line, asserting the `tail_reader` result. Run the oracle on that ledger and record its output in the test comment. Reword the `FixtureMissions` comment, and make `FixtureMissions` follow the same rule if it computes cursors. |
| R5 | medium | domain StatusEvent; codec RowClassifier; contract StatusTransitionEvent and Actor | The contract requires `actor {tool, role, profile}` on `status-transition`, and the domain carries none. WP20 is blocked on this. | Add an `Actor` value (domain/model) with the contract's `decode_actor` semantics: read `contracts/mission-status/schemas/Actor.yaml` and `ActorHandle.yaml` and the Python `decode_actor` they name. `StatusEvent` carries it and `RowClassifier` fills it. Add parity cases against the Python `decode_actor` for a string actor, a structured actor and the invalid shapes. Per-class JaCoCo floors apply, so update `domain=<n>` from the report. |
| R8 | low | MissionStatusService:71-90 | `ProjectionCache` is public with no public user. The plan is now amended so that the service builds it. | Make `ProjectionCache` and `Entry` package-private, unless a test outside the package needs them. |
| R11 | nit | InMemoryMissionEventSourceTest:113 | The test name promises more than it asserts ("not null"). | Rename it, and assert that the stamp differs with and without the tail. |

Recorded, no code change: R6 (operator, keep fail-loud, now in FR-004), R7 (L7 and L3a choices, now in FR-004), R9 (WP20 must catch `IllegalStateException` from `next()` after a concurrent `close()`; add one javadoc line), and R10 (the `.gitignore` `out` re-include, done at the slice-1 wrap-up, not here).
