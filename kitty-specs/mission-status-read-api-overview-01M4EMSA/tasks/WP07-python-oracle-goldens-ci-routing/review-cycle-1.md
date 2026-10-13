---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T11:04:22Z'
reviewer_agent: reviewer-renata
wp_id: WP07
---

# WP07 review: rejected (cycle 1), reviewer-renata

The only blocking finding is F1. Everything else passes: T036 to T041 are met, all four revert tests go red, the validation and architecture runs are green, and hygiene is clean. The judgement calls (the coord-worktree/husk-worktree convention, the uppercase mid8, patternDivergences, the email-shaped refused field) are all sound.

## F1 (severity 4): the blank-line overview golden records a refusal, but the spec says the overview is served

- **File:** `services/mission-status-api/src/test/resources/conformance/malformed-rows/blank-line/golden/missions.json`. It contains only `{"refusal":{"exception":"JSONDecodeError","line":null}}`.
- **Cause:** `tests/contract/_mission_status_payloads.py:722-743` `load_source` calls `poll_once` before `materialize_snapshot`, and `poll_once` raises on a terminated blank line. The generator's `missions_document()` goes through `load_source`, so the golden pins a test-helper artefact, not production Python.
- **Spec:** spec.md:288 says the blank-line variant "records both answers (`read_events_raw` skips it and the overview is served; `poll_once` raises, which the stream scenario asserts as row L10)". spec.md:121, row L10 (spec.md:216) and S4 (spec.md:228) all make the blank line stream-only, with no request-route observable.
- **Inconsistency:** the same fixture's `project.json` golden is healthy.
- **Test:** `tests/contract/test_mission_status_conformance.py:72` maps `"blank-line": {"JSONDecodeError"}` in `REFUSAL_CLASS_OF_MALFORMED`, and `malformed_problems` (around lines 505-525) demands a refusal. So the test codifies the defect.

**Remedy:**
1. Build the blank-line overview without `poll_once` on the source path: reduce through `materialize_snapshot` / `read_events_raw`, which skip the blank line.
2. Compute `streamCursor` as the orchestrator ruled below.
3. Regenerate `missions.json` for blank-line as a served overview (an `items` page, eventCount 3).
4. Keep the `stream.json` refusal for blank-line.
5. Change `REFUSAL_CLASS_OF_MALFORMED["blank-line"]` and `malformed_problems` so that blank-line requires a served `missions.json` plus the stream refusal, and add a content-level assertion (eventCount 3, served) so this cannot regress.
6. Verify that the other malformed variants still refuse. For those, production `materialize` itself raises, so the refusal is correct.
7. Do not change `_mission_status_payloads.py` behaviour for the other fixtures. If you change `load_source`, the reality and corpus tests that use it must still pass: run `tests/contract/test_mission_status_*.py`, and classify the 8 baseline worktree failures as before.

**Orchestrator ruling on the cursor question (the spec reading at spec.md:131 and :219 says streamCursor describes the same bytes the counts were reduced from):**
- For a ledger whose blank line falls mid-file, `streamCursor` is the cursor after the full file. Its offset is the file size.
- Its content invariant is the one `poll_once` would hold when resuming past the blank line, that is, the digest of the last consumed non-blank terminated line. Compute it with `tail_reader`'s own digest helper, not a re-implementation.
- Record this in the manifest or the fixture notes, so WP09 and WP19 reproduce it.
- A blank line as the final line is NOT a fixture in this WP. Do not add one.

## Note F2 (severity 2): the provider-prefixed probe string

`manifest.json` carries the probe `ghp_` plus 36 `a` characters. The orchestrator brief asked for fake secrets with no real provider prefix. If the leak pattern under test genuinely needs that prefix to match, keep it, but check that the repo's own secret-scanning gates (grep the repo for gitleaks / detect-secrets / secret-scan config and tests) accept it. Name the gate you checked in your report. If no pattern needs the prefix, replace it with a synthetic non-provider value.
