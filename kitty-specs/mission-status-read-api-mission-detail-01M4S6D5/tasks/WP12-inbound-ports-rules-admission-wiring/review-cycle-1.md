---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-mission-detail-01M4S6D5
reproduction_command:
reviewed_at: '2026-10-14T07:54:52Z'
reviewer_agent: claude
wp_id: WP12
---

# WP12 review, cycle 1: REJECT (two small must-fix findings; everything else verified)

Tip reviewed: f11be6a61 (lane-k, includes the OO-6 merge 4cfdb41d2). Verified green on a scratch worktree of the tip: `clean check nativeCompile nativeTest` (test 3150, perfTest 18, kitTest 11, nativeTagJvmTest 3, test-native 3, 0 failures), `nativeSmoke` digest 15b1eb6ae389c4752ff3577e32e226730f31f610b61fdee4a9d169073bf2e979 (49 requests), bundle digest fadf8a86...0effd, JaCoCo domain=121 application=118 equal the plan section 2 command on this tree, pytest tests/ci/test_mission_status_*.py + conformance 380 passed, the plan's architectural gates 155 passed, ruff check and format clean.

## F1 (severity 2, must fix) RawQuery percent decoding is not strict: it accepts non-ASCII "hex digits"
- File: services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/RawQuery.java, `decode`, the two `Character.digit(..., 16)` calls.
- `Character.digit` accepts any Unicode decimal digit (fullwidth, Arabic-Indic, ...). Probed against the built classes: `RawQuery.path("path=%２e%２e/x")` returns `Values[../x]`; `path=a%١b` returns `Values[a<U+0001>b]`. T085 requires strict decoding (`%` followed by exactly two ASCII hex digits); Python's `unquote`, the oracle, leaves such sequences literal. Tomcat probably rejects non-ASCII bytes in the request target before this helper runs (not verified), so this is a latent defect in the one seam every artifact route reuses, not a reachable hole today. The `..` still dies later in `RelativePath`, so nothing escapes; the issue is the contract of the helper and the oracle divergence.
- Remedy: accept only `0-9A-Fa-f` (ASCII) as hex digits; anything else after `%` is `Undecodable` (or literal, whichever the AC-5.2 rows say; state it). Add RawQueryTest rows for `%２e`, `%١١` and a one-digit `%4`. Revert check: with `Character.digit` restored the new rows must go red.

## F2 (severity 1-2, must fix) the OO-6 merge duplicated three WP09 entries in tooling-friction.md
- File: kitty-specs/mission-status-read-api-mission-detail-01M4S6D5/traces/tooling-friction.md, lines 131-133 and 181-183 of the tip. Both parents (fa25c7cd3 and 835d89fbd) carry each of these entries once; the merge kept both positions:
  - "[2026-10-14][WP09] The WP's owned-file list has no test file for the port records ..."
  - "[2026-10-14][WP09] Two stale controls outside the owned map turned red by design ..."
  - "[2026-10-14][WP09] A parallel lane stopped the shared Gradle daemon mid-run ..."
- Remedy: delete the second copy (lines 181-183), keep one. approach.md and design-decisions.md have no lost or duplicated entries (checked as multisets against both parents).

## Notes recorded, not blocking
- N1 ProblemMapper.detail text differs from the contract examples and the Python goldens (trailing full stops, no `type: about:blank`, one generic `not_found` text for three routes). Recorded by the implementer as D-P8-4; WP13-16 goldens will force a named edit of `ProblemMapper#detail` (probably a route context for `not_found`). Mapping of kinds to statuses and codes is correct (404/400/413/415/422/500/500/500), no path, value or enum name in any body, no `type` member.
- N2 `FilesystemTextSource.forRoot(String)` edits a file that is not in WP12's owned_files (a D-162 frozen seam). It is additive (5 lines), the public `FilesystemTextSource(Path)` constructor and its seam test (`itIsConstructibleFromAPlainPathWithNoSpring`, which pins public-ness via `getConstructor(Path.class)`) are untouched, and rule 7 really does forbid `java.nio.file` in `config`. Acceptable; D-P8-1 records it.
- N3 The behavioural FIFO test in AdmissionGateTest passes with a non-fair semaphore; fairness is held by the reflection pin only. Acceptable.
- N4 R16IoException is co-red {2,16} and that is sound: with clause 16b disabled the control goes red (the 16 in the pinned set is then missing). Verified by mutation.

## Revert and mutation checks run (all went red as required)
AdmissionGate.run package-private -> `theGateAndItsRunAreTheFrozenSeamForGovernanceRoutes` red; non-fair semaphore -> `itHoldsExactlyFourPermitsAndTheSemaphoreIsFair` red; ARTIFACT_TOO_LARGE 413->400 -> two ProblemMapperDetailTest cases red; MissionId.parse accepting lowercase -> MissionIdParseTest red; rule 16b disabled -> control R16IoException and the production rule 16 run red; a fifth interface with a String parameter in `port.in` -> rule 16c red and the production-set pin red.
