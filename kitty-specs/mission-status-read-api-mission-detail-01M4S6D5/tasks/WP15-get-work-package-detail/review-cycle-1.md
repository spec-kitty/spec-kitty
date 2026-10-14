---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-mission-detail-01M4S6D5
reproduction_command:
reviewed_at: '2026-10-14T10:48:58Z'
reviewer_agent: claude
wp_id: WP15
---

---
work_package_id: WP15
reviewer: claude (reviewer-renata)
reviewed_tip: deaf407d9
verdict: changes_requested
---

# WP15 review, cycle 1

Gates all green (see the report): `clean check` 3675 tests, 0 failed; native compile, nativeTest and nativeSmoke with digest 15b1eb6a...e979 (unchanged); pytest 380; 4 architectural files (48 + 96 tests); ruff check and format; JaCoCo recount domain=130, application=126. Goldens: 66 served and byte equal (the 67th, head-dates-nulled, is also compared byte for byte in the divergence test). The findings below are what is left.

## F1 (severity 3): a "survived, equivalent" mutation is not equivalent, and no test pins the rule it guards

**Where:** `WorkPackageDetailQueryService#humanOrNull` (`if (leaks.credential(value))` before `projector.human`). The implementer's mutation "serve a credential title" (`if (false)`) survived and was called equivalent.

**Scenario (reproduced in a scratch worktree, through the controller with `startWired`):** a `tasks.md` title `Edit /home/someone/<credential> today` (the credential assembled from `DetailRoute.secret()`).
- Production tip: 200, `"title": null`, one `projection_refused`. This equals the oracle, whose `human_text` runs `has_credential` on the raw text first.
- With the pre-check removed: 200, `"title": "Edit [path] today"`, no diagnostic. The path replacement swallows the credential before `humanLeak` looks, so the post-replacement check cannot stand in for the pre-check.

The plain-credential case the tests use (`Rotate <credential> now`) is caught by either check, so the standing revert row for AC-3.7 passes with the pre-check deleted. The production code is right; the guard is untested.

**Remedy:** add the credential-inside-a-host-path case for a subtask title (expect null plus one `projection_refused`) and for a dependency title (expect the id plus one `projection_refused`) in `WorkPackageDetailQueryServiceTest`. Re-run the mutation and show it killed.

## F2 (severity 2): D-P11-1, "last cycle" is last in history order, the oracle's is last in file order

**Where:** `ReviewCycleReader#verdict` iterates `WpResolved.history()`, which `ResolvedFold` sorts with `HistoryOrder` (instant, then event id). The oracle's `cycle_verdict` iterates `source.rows` in file order.

**Scenario:** two rows of one Work Package with the same trimmed `review_result.reference`, the later one in the file carrying the earlier instant, and different verdicts. The oracle answers the later-in-file verdict; Java answers the later-in-time one. No golden, no `knownDivergence` entry (V1 to V25) and no spec or plan sentence covers it; the only basis given is that the route may not read the ledger twice.

**Remedy (either):** (a) the orchestrator rules it a recorded divergence, adds a V-entry and a Java-outcome test that pins the differing outcome; or (b) `HistoryRow.reviewReference` order is made file order for this purpose (for example carry the file ordinal of the row) and the oracle behaviour is restored. This is a fork for the operator or orchestrator, not for the implementer to choose.

## F3 (severity 2): D-P11-6, a cycle file with more than nine digits is silently dropped

**Where:** `CycleNames#cycleNumber` returns empty for `digits.length() > 9`, so `review-cycle-1234567890.md` is not listed.

**Scenario:** the oracle's `_CYCLE_NAME` is `[1-9][0-9]*` and Python integers are unbounded; the contract says `cycleNumber` is an `integer, minimum 1`, with no upper bound, and the schema text says a file the product cannot parse is "still an entry: its number comes from its file name". Java omits the entry with no diagnostic and no refusal. That is a silent drop on a fail-loud route (FR-012). No fixture has one, so nothing notices.

**Remedy (either):** refuse the request (500 `source_unreadable`, one diagnostic) when a cycle file name is a cycle name by the oracle's pattern but too large for the contract's `int`; or get a ruling that a silent omission is accepted and record it as a V-entry with a Java-outcome test. A refusal is the smaller departure from "never answered as a partial detail".

## F4 (severity 1, process): ProblemBody edit is missing from the commit message

Obligation 7 requires a named edit to be stated in the commit message. `381dc9d38` states `ProblemMapper#workPackageDetail` only. `ProblemBody` gained the optional `type` member in the same commit (byte identical to lane-o's, checked). Not a code change; fix it in the closeout note or the hand-off, or ignore it if the orchestrator squashes.

## Checked and fine (no action)

- `HistoryRow.reviewReference` (item 1): strict (`instanceof String`, nothing stringified), equals the oracle's `isinstance(reference, str)` plus the Java-side `PyText.strip` match; no served byte of the overview or the stream changes (PR A goldens green, native smoke digest unchanged). The single changed expected value in `LedgerLineDecoderResolvedMembersTest` (`"x"`) is the new member and nothing else. The retained 9-argument constructor means obligation 19's three WP14 constructions compile without the 10th argument; they pass null, which is right for a presentation copy.
- Revert check: with the production classes replaced by the red-first shells, 337 of 361 targeted tests fail; the 24 that pass are harness and control tests that need no route.
- Read safety (item 3), planted through the controller: a symlinked cycle file gives an entry with null members and null `artifactPath` and its target is never read; a 262144-byte cycle file is parsed, a 262145-byte one gives null members; a symlinked `tasks.md` gives no titles (200); a symlinked or 1 MiB + 1 `lanes.json` and a 4 MiB + 1 `tasks.md` give 500 `source_unreadable`; a linked worktree directory gives `worktreePresent` false. Every read in the new main code goes through `TextSource` with `ReadScope.AUTHORED`; no direct file API. `WorkPackageDetailScopesTest` asserts `readScopes()` explicitly.
- Deviations: `ProblemMapper#workPackageDetail` as a new method (precedent WP16, keeps getMission bytes); all 500s are `source_unreadable` (the contract's 500 and `default` text); meta slug for lane branch and worktree (oracle `identity.mission_slug`); constant reference kinds (oracle `artifact_references`); link on the way to a worktree reads as absent (V7); cycle read fault gives null members (oracle `except (ValueError, OSError)`).
- Mutations 1 ("worktree directory link accepted") and 3 ("cycle file symlink followed") are equivalent: reproduced with the mutants applied, the served bodies are identical to the tip's, because `FilesystemTextSource` refuses a link in any non-final path component and a link as the final component of a cycle file reads as not regular.
- Note, not a finding: a symlinked `lanes.json` answers 500 where the oracle follows the link; neither the spec nor the manifest lists it, and it is the stricter side.
