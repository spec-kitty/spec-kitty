---
affected_files: []
cycle_number: 1
mission_slug: mission-status-contract-1-1-01M42XJC
reproduction_command:
reviewed_at: '2026-10-04T21:01:48Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review (Reviewer Renata): VERDICT: changes requested

Commits 6d08826ec, 79b63757c, dd3d853bb verified with cat-file (all commits), base 5b03a2297. No src/ or contracts/ diff. Tree clean after experiments.

## Findings
- F1 (sev 3, blocks) credential-before-redaction order is NOT pinned. Revert experiment E2: reader redacts first, then checks credentials on the redacted text; 19 targeted tests pass, nothing red. A file such as `<host path>/<token>` redacts to `[path]` and loses the credential (probe: has_credential True before, False after), so such a reader would serve a masked credential as 200 (AD-17 "never masked"). The oracle decides on decoded text correctly, but the fixture repository holds no file where redaction hides a credential. Remedy: plant one such file (path-glued and e-mail-glued token) in `_exam_files`, expected 422, plus a MUTANT "redacted before the credential check".
- F2 (sev 3, blocks) the three re-pinned floors are a loosening, not R-5 re-measurement need. Measured on this lane tree (probe): checkbox_rows 8,734, verdict_cycles 303, missions_without_lanes 79. The plan-time floors 8300, 290, 72 are all MET (8,734>=8300, 303>=290, 79>=72). Arithmetic of the re-pin is rule-conformant (95% of 8,734 = 8,297 -> 8200; 95% of 303 = 287.9 -> 280; 90% of 79 = 71 -> 71), but the rule fixes floors at plan time and WP08 needs no change: re-pinning lowers three guards for no reason. Ruling: reject hunk 2 of the patch (contracts note D keeps 8300/290/72) and restore the code floors to 8300, 290, 72. The patch's WP08 prompt line 117 hunk (named refused list) is correct and matches spec FR-021 and AC-DETAIL; keep it.
- F3 (sev 2) oracle independence is by construction only. E1: oracle_outcome replaced by `artifacts._decide_bytes(...).status`; all 10 oracle/mutant tests pass. Nothing guards against coupling (a structural assertion that the oracle does not call the reader would). Mutants patch `read_file`, not `_decide_bytes`. Current code IS independent (own cap, NUL, strict utf-8, SECRET_PATTERNS from the leak tool, own code table).
- F4 (sev 2) floors can be loosened silently: E3 sets checkbox_rows=1 and verdict_cycles=1; the 3 floor tests pass (only detail_work_packages and artifact_entries have a `>=` pin). Related to F2; a pin test over all new floors would stop F2 recurring.
- F5 (sev 1) the verdict-comparison skip when read_dir differs: zero Missions are non-comparable in the corpus (probe: 0), so there is no hole today. Wholesale skipping gives verdict_cycles 0 and fails the zero-count and floor guards (E6 red on the fixture test, 1 failed). A per-Mission skip would hide only that Mission. Ruling on finding 3 (implementer): acceptable, not a silent skip; recommend an assertion that non-comparable count is 0 on the corpus.
- F6 (sev 1) fixture subset check "unnamed new anomaly printed, never failed" is spec-conformant (FR-021 and the contracts note D say exactly this; the test `..._only_reports_a_new_one` proves a dropped named entry is reported not failed and a changed or vanished one fails). Not a skip: every refused file is still checked by the oracle for status and code.
- F7 (sev 1) Mission 058 mapping-roster ids: oracle states v1's rule (str(item)) so detail == v1; documented in the code; fine. Runtime: 776 passed in 86.5 s here (R-5 baseline 91 s for 577 tests); with the CI factor about 2 gives about 3 min, far under the 6 min re-plan threshold (the implementer's 285 s extrapolation is pessimistic and also under 360 s).

## Check 1 refused-list mechanics: conform
examined + refused == discovered (3193 + 9 == 3202); independent scan of lanes.json (feature_slug, no mission_slug) reads JSON directly; outside-list 500 fails (test plus code `not on the independently derived refused list`); stale entry fails (E4: dropping the stale line turns `test_a_listed_mission_that_answers_200...` red; wrong pinned count and a listed Mission answering 200 also tested); floors apply to the 200 count; no skip. Control: a broken lanes.json planted is red.
## Check 2 oracle order: 413, then NUL 415, then utf-8 415, then 422, then 200; matches spec order (spec line 336, AD-17). Planted order cases: cap boundary, over+NUL, over+secret, NUL+secret, latin1+secret, all pinned; six consistently-wrong reader mutants killed; readable by size alone killed. Credential before redaction is the gap (F1).
## Experiments (mine, distinct from the implementer's 14)
E1 oracle coupled to reader: survives (F3). E2 redact-before-credential: survives (F1). E3 floors loosened to 1: survives (F4). E4 stale-entry line dropped: killed. E5 schema validation skipped for refusal payloads: killed (1 failed). E6 verdict comparison never comparable: killed (1 failed). Every file restored with git checkout -- <literal file>; git status clean.
## Gates (TMPDIR under scratchpad)
reality+payloads corpus: 776 passed 86.5 s. Tool-job selection: 1645 passed, 37 skipped (plan baseline 1016/37, rises with the Mission's modules). artifacts+detail: 371 passed. Router/registry nine files: 368 passed, 1 skipped. Census/state eight files: 171 passed. layer+pyproject: 83 passed. ruff check clean; ruff format --check 3107 files formatted; TID251 clean; cutover-guard 0 un-cut-over. The ten contract checks are covered by the tool-job selection (tests of the tools); not separately run as CLI.
