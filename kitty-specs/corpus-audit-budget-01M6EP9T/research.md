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

At the discovery checkpoint no budget value had been selected. No baseline failure was represented as passing, and no product or test behavior was changed during discovery.

## Hosted measurement — 2026-11-02

- Run: https://github.com/spec-kitty/spec-kitty/actions/runs/41501746918 (attempt 1, successful; no retry).
- Measured head: `359c6b7657585d334ad9f99dc01bb1c9aa740765`; compared main: `9aed3a8012cb5eb22c0128b14d525039f95fea7a`. The job required an empty diff for `src/`, `tests/` and `pytest.ini` before measuring.
- Runner: Ubuntu 24.04.5 LTS, x86_64, four CPUs; Python 3.11.15, pytest 9.0.3, Git 2.56.0. Canonical warmup `pr` mode, cache hit; same dynamically derived full-package coverage breadth as the upgrade shard.
- Artifact: `corpus-budget-diagnostic-41501746918-attempt-1`, id `13170455644`, archive digest `sha256:d68d2809f4998965ccec5b3eff4a4ed988fdce453b9f44d40d4fb157c56c8756`. It contains logs, metadata, JSONL phase records, summary metrics, JUnit and all eleven CLI stdout/stderr/JSON reports; no report was skipped by the copy bounds. Retention ends 2026-12-02; the measurements below and immutable run reference are retained in this Mission.
- All original controls passed: eleven audits, four inventories, two gates, one corpus build and one recovery; zero incomplete phase records and no assertion or subprocess timeout.

| Audit ordinal | Role | Duration (seconds) |
|---|---|---:|
| 1 | Original corpus | 22.767940 |
| 2 | Recovered corpus | 20.021178 |
| 3 | Landed corpus | 19.891625 |
| 4 | Attack 1 | 19.797833 |
| 5 | Healthy control 1 | 19.871610 |
| 6 | Attack 2 | 19.778666 |
| 7 | Healthy control 2 | 19.797395 |
| 8 | Attack 3 | 19.901266 |
| 9 | Healthy control 3 | 19.989360 |
| 10 | Attack 4 | 19.852191 |
| 11 | Healthy control 4 | 19.806222 |

The audit total was 221.475286 seconds. Top-level observed phases totaled 237.231490 seconds: corpus build 4.915135, inventories 3.701273, recovery 0.172789, gates 6.967007, plus audits. Nested CLI time is not added again.

**Timer-bound distinctions:** phase records measure the test body at 237.366898 seconds; pytest reports call 237.37 seconds and setup 19.65 seconds. JUnit's test-case time is **257.019 seconds**, the measured setup+call+teardown window with `tmp_path_retention_policy=all`: pytest-timeout defaults `timeout_func_only=false` and its protocol timer covers fixtures, not only the test body. The shard's normal `failed` retention policy additionally deletes the temporary corpus and reports during teardown; that cleanup duration was not measured by this diagnostic and is covered explicitly by the 30-second reserve below. The JUnit/session total of **485.911 seconds** includes collection/session costs and must not be mistaken for the per-test budget requirement. This is uncensored hosted evidence that the complete correctness workload exceeds the shared 240-second hang backstop, despite each CLI audit being far below its unchanged 180-second limit (slowest 22.767940 seconds).

**Approved correction:** the independent `debugger-debbie` evidence review recomputed the artifact and approved `@pytest.mark.timeout(450)` on this single test. The reviewer confirmed actual CLI exits `[0,0,0,1,0,1,0,1,0,1,0]`, matching four corruption/healthy-control pairs, and byte-identical clean control reports. Derivation: `ceil(((257.019 + 30) * 1.5) / 30) * 30 = 450` seconds (observed whole test case + 30-second reserve, 50% load headroom, rounded up to a 30-second boundary). This follows the existing shard headroom rationale without changing the shard or shared timeout. It is not a claimed p95 from one sample and not sized from the unrelated local stall. The final test must still validate under its actual marker in the hosted upgrade shard, with all assertions and the inner subprocess bound unchanged.

## Implementation checkpoint

The final correction adds only a function-level `@pytest.mark.timeout(450)` plus its measurement rationale to the existing corpus test. All assertions and the inner 180-second subprocess bound remain byte-for-byte unchanged; other tests retain the shared 240-second limit. The diagnostic workflow is removed before opening the draft PR, without changing its allowlist. Its 900-second experimental bound is not the final limit. Hosted validation under the actual marker and normal retention remains pending.
