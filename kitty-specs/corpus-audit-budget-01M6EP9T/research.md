# Discovery: corpus recovery execution budget

## Decisions

1. Work separately from PR #7071. Its three-line fixture change has no call path into this historical-corpus test, and two independent reviews approved it. The failing corpus guard is valuable behavior, not an assertion to delete.
2. Measure on the existing hosted runner class before choosing a final budget. Preserve all eleven audits, four integrity inventories, recovery gates, corruptions and healthy controls. Do not change the shared pytest floor or move the test out of the required upgrade shard.
3. A diagnostic outer cap up to 900 seconds is an experiment, not the proposed final limit. Preserve the existing 180-second subprocess boundary, capture every attempt, and do not retry until a green result appears.
4. Use instrumentation outside production paths to record phase durations, SHA and runner. Temporary diagnostic wiring may be removed from the final diff once the run has a durable artifact/URL. Missing evidence or a real assertion failure stops calibration.

## Evidence and citations

- Issue: https://github.com/spec-kitty/spec-kitty/issues/5716 (open; assigned to Ivan-Melck with status:claimed and taken-by-human).
- PR #7071 upgrade shard: https://github.com/spec-kitty/spec-kitty/actions/runs/41487640410/job/125423047123 — `test_original_full_corpus_residue_then_recovered_and_landed_corpus_passes`, timeout >240 seconds at a healthy control; 1 failed, 397 passed.
- Main after #6846: https://github.com/spec-kitty/spec-kitty/actions/runs/41454363942 — the same test and timeout on `9d387d4359`.
- Earlier pristine-main reproduction on `512567eee7` is recorded in #5716 comments. The current source `9aed3a8012` retains the same uncalibrated shared 240-second floor and the same test. Last edit to the test predates both PRs (`e3b8f22845`, #6058).
- Source: `tests/upgrade/test_mission_corpus_recovery.py`. The test reconstructs a pinned 423-directory historical corpus, calls the real CLI eleven times, hashes full inventories and runs recovery gates. `pytest.ini` explicitly permits test-local timeout markers for legitimate longer workloads.
- Policy: `docs/development/testing/testing-flakiness.md` requires evidence-based budget tuning, never retry-to-green.
- A single local diagnostic with outer timeout 600 seconds instead hit the inner subprocess timeout 180 seconds at audit 2; total 289.97 seconds. CI reached a later healthy control, so that local stall is a distinct, undetermined condition and cannot size the CI budget.
- Independent adjudication (recorded on #5716 and #7071) recommends separate measurement-first work. It found no supported small remediation without hosted-runner measurements.

## Open questions

- What total and per-audit duration does the unchanged test actually require on the hosted runner when allowed a bounded completion window?
- Are individual audits comfortably below 180 seconds, and is a test-local total limit sufficient, or does measurement reveal a real bottleneck requiring separate scope approval?
- What explicit, bounded headroom is justified by the observed phases without hiding a consistently slower regression?

No budget value has been selected. No baseline failure is represented as passing, and no product or test behavior has been changed during discovery.
