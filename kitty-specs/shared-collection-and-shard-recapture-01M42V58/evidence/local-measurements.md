# Evidence: local measurements

**Date**: 2026-10-04. **Mission**: `shared-collection-and-shard-recapture-01M42V58`. **Requirements covered**: FR-022, NFR-004, NFR-005 (local part), NFR-006, SC-004, SC-005.

Every number below was taken from a command's output or from the capture log. A value that has not been observed is written `pending`. Nothing here was measured on CI; see `ci-measurements.md`.

## 1. Reuse run (first end-to-end run of the store)

Run in the lane worktree of the pre-test-step work (WP02), on a clean checkout, on the maintainer's workstation (32 logical CPUs). This ran before the later exit-code change, which did not touch the collection path. No log of this run was kept; the figures are the implementer's report.

| Command | Result | Seconds |
|---|---|---|
| `key` | key printed | 0.26 |
| `collect` (first) | outcome `collected` | 62.5 |
| `collect` (second) | outcome `reused` | 0.33 |
| `check` | exit 0 | not recorded |
| `compare` | 54,812 stored, 54,812 fresh, 0 differing | 22.3 |

The planning-time two-pass check (`two-pass-collection.md`) found 0 differences between two collections in separate temporary homes (54,723 records at that time).

## 2. Key computation

| Measure | Value | Bound |
|---|---|---|
| `key` command | 0.26 s | 1 s (NFR-004) |

A test also pins the bound of under 1 s, so a slower key computation fails the test run and does not depend on this one measurement.

## 3. Kept capture

Environment: standalone clone of the lane branch, the repository `.venv`, Python 3.11.15, environment synced from `uv.lock` with all extras, `SPEC_KITTY_PACK_HOME` removed, serial run, run id `mission-01M42V58-recapture`, workstation with 32 logical CPUs, 2026-10-04. Total: 3,509 seconds. Old and new counts are from the commit message of `d8e08b604f`; wall seconds are from the capture log; the duration sum and shard count are computed from the committed data after the capture.

| Module | Old count | New count | Exit | Wall seconds | Duration sum (s) | Shards |
|---|---|---|---|---|---|---|
| consolidation | 1615 | 1822 | 0 | 580 | 575 | 2 |
| missions | 633 | 336 | 0 | 12 | 9 | 1 |
| post_merge | 100 | 123 | 0 | 2 | 1 | 1 |
| release | 86 | 253 | 0 | 8 | 7 | 1 |
| status | 1702 | 1849 | 0 | 46 | 41 | 1 |
| review | 535 | 588 | 0 | 42 | 39 | 1 |
| next | 1588 | 573 | 1 | 33 | 31 | 2 |
| lanes | 318 | 704 | 0 | 106 | 104 | 1 |
| upgrade | 733 | 922 | 0 | 772 | 767 | 4 |
| cli | 2704 | 935 | 0 | 208 | 204 | 2 |
| charter | 6977 | 6975 | 0 | 611 | 599 | 7 |
| agent | 1538 | 1537 | 0 | 75 | 71 | 3 |
| kernel | 270 | 591 | 0 | 4 | 3 | 1 |
| glossary | 149 | 179 | 0 | 2 | 1 | 1 |
| execution_context | 4106 | 4381 | 0 | 316 | 307 | 3 |
| core_misc | 4332 | 4718 | 0 | 539 | 530 | 5 |
| unit | 454 | 489 | 0 | 9 | 6 | 1 |
| specify_cli_runtime | 77 | 118 | 0 | 13 | 13 | 1 |
| ci | 286 | 1870 | 0 | 114 | 112 | 1 |
| auth | 573 | 638 | 0 | 17 | 16 | 1 |

- **Shard counts**: none changed. The existing balance check (`tests/architectural/test_module_shard_registry.py`, 24 passed) accepts the new durations.
- **Caveat**: the duration sums are workstation durations of the test call. They are not CI wall time, so they do not prove that a shard fits its CI time cap.
- **`next` exits 1**: two tests in `tests/next/test_discovery_step_contract.py` fail under the in-process producer and pass under plain pytest (`573 passed, 1 skipped`). This reproduces on unchanged base code and is filed separately; see #5658. The capture is valid under the recapture trust rule (exit 0 or 1 with recorded durations).

## 4. Discarded capture

A first capture was run inside a linked git worktree and was discarded. Its log shows a total of 3,638 seconds and four modules with exit 1 (three from the linked worktree, one from a separate fault):

| Module | Failed tests in the discarded run |
|---|---|
| next | 2 (also fails in the kept capture; different cause, see below) |
| agent | 14 |
| consolidation | 1 |
| charter | 6 |

**Cause**: running in a linked worktree caused 21 failures in three modules: `agent` 14, `consolidation` 1 and `charter` 6 (charter generate, synthesize and context paths). The nine files that failed, including the `next` file, were re-run under plain pytest in a standalone clone and passed (78 passed), and CI on the primary branch (`main`) is green, so these 21 failures come from the checkout type and not from the code. The 2 `next` failures appear in both the discarded run and the kept standalone-clone run, so they are not a worktree effect; they are the separate producer fault described in section 3 (see #5658). Failed tests also return early, so the recorded durations were not usable. The capture was restarted in a standalone clone (section 3).

## 5. Strict agreement and provenance

| Check | Command | Result |
|---|---|---|
| Strict agreement at the capture commit (NFR-006, SC-004) | `SPEC_KITTY_STRICT_SHARD_TIMINGS=1 pytest tests/architectural/test_module_length_agreement.py` | 18 passed, about 40 s (standalone clone, orchestrator); re-run by the reviewer of the recapture work package: 38.8 s |
| Provenance record per module (SC-005) | `tests/architectural/test_shard_capture_provenance.py` | 9 passed |
| Same provenance check before the capture | same file | failed, naming 11 of 20 modules: missions, post_merge, release, review, next, lanes, upgrade, cli, kernel, glossary, execution_context |

## Conclusion

The store reuses a collection in 0.33 s against 62.5 s for the first collection on this workstation, with 0 differences between the stored and a fresh collection and a 0.26 s key. All 20 registry modules carry a capture record, the strict agreement test passes at the capture commit, and the provenance check went from failing on 11 modules to passing. None of this shows CI behaviour.

## Tracer assessment

The three tracer files are `traces/approach.md`, `traces/design-decisions.md` and `traces/tooling-friction.md`.

- The first approach (a cache shared between xdist workers) was dropped after grounding showed each per-PR job already collects once. The adopted approach moves that collection out of test setup into a pre-test step; it does not reduce first-run collections from three.
- A single upstream producer feeding all three consumers was not possible: the consumers span two independently triggered workflows on two interpreter versions.
- The key uses the committed tree id and not a list of input files, because collection reads files across the whole repository.
- A pre-test step that cannot store fails `collect` and `check`; only an unsupported platform may fall back. Without this rule, a key that never matches stays invisible because the fallback keeps every gate green.
- Two reviews returned work: WP04 (the rewrite dropped the tests that pinned token isolation and the bot commit identity; six mutations survived) and WP02 (the prompt let a never-storing pre-test step stay green).
- The measured capture moved from a lane worktree to a standalone clone after environment-caused failures (section 4), and the close-out order changed so the rename and documentation package runs before the capture.
- An accepted residual from the WP04 review: the count-only pass is capped per module (300 s) but not by the overall budget.
- An open risk carried to CI: a test that leaves an untracked file in the checkout while a collecting test runs makes that request `bypassed` and fails the reuse check.

### Tooling-friction items that could become tracker issues

For the operator to decide; nothing has been filed.

| Item | Observed |
|---|---|
| `safe_commit` hides the git error | `agent mission create` once failed with `safe_commit: failed to stage requested files`; `_stage_requested_files` discards git's stderr, and the cause was not found. A retry succeeded. |
| `record-analysis` leaves the report uncommitted | `analysis-report.md` stays staged and had to be committed with `spec-commit`. |
| `move-task` verdicts are not committed | A reviewer's `move-task` writes the verdict without committing it, and sometimes fails once with "Global asset input changed ... re-run the command". |
| Prompt regeneration drops `requirement_refs` | Regenerating work-package prompts after `map-requirements` dropped the mapped refs; `--replace` re-mapped them. |
| Lane worktrees lack a virtualenv | `uv run` also rewrites `uv.lock` on this machine; implementers used the repository root `.venv` with `PYTHONPATH=<lane>/src`. |
| Linked worktrees fail 21 tests | See section 4: 21 tests in `agent`, `consolidation` and `charter` fail in a linked worktree and pass in a plain clone. |
| `next` discovery tests fail under the producer | Already filed as #5658. |

## 7. Recaptures after merging the primary branch

The primary branch (`main`) was merged three times before the pull request was opened. Each merge changed some modules' test counts; the strict agreement check named them and only those were recaptured, in a standalone clone of the merged tree with the same environment as section 3. Wall seconds are from the capture logs.

| Merge | Primary-branch tip | Modules recaptured (wall seconds, exit) |
|---|---|---|
| 1 | `7c2dbd4eb0` | status (45, 0), unit (10, 0), cli (212, 0), core_misc (547, 0), consolidation (812, 0), ci (124, 0) |
| 2 | `3944272453` | execution_context (286, 0), consolidation (795, 0), ci (126, 0) |
| 3 | `ef5ce4f017` | lanes (75, 0), cli (209, 0), execution_context (281, 0), core_misc (541, 0), charter (611, 0) |

- Merge 3 brought a newer `consolidation` capture from the primary branch itself (run id `landing-5656-regression-slice`, exit 1, 1,960 tests). That capture is kept; this mission's `consolidation` capture from merge 2 is superseded.
- In merge 3 the first `charter` capture exited 1 with one failing test, `tests/charter/test_interview_mapping_mission_alias.py::test_synthetic_mission_type_is_picked_up_by_both_rosters`. That test, added on the primary branch the same day, shells out to `uv run`, and the clone had no environment. With the repository environment linked into the clone the test passes; `charter` was captured again and that capture (611 s, exit 0) is the one committed.
- After merge 3, at the committed data: strict agreement 18 passed (40 s); provenance check 9 passed; balance check 24 passed. No shard count was changed.
- Modules with a capture record that exits 1 at the pull request's tip: `next` (see section 3 and #5658) and `consolidation` (the primary branch's own capture).

The primary branch may move again before the pull request merges. Counts that drift after that are not recaptured here; per pull request the drift is a non-blocking warning, and the scheduled recapture is the remedy once its token is fixed (see #5624).

A fourth merge of the primary branch (tip `7d6982f664`) was done only to resolve a conflict in the timings file after the pull request was opened: the primary branch had recaptured `agent` (run id `landing-5659-agent-recapture`, exit 1, 1,537 tests), and that capture is kept. No module was recaptured for this merge and strict agreement was not re-run on it, by operator instruction.
