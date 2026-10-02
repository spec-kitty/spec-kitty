---
affected_files: []
cycle_number: 2
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T23:13:14Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review, cycle 2: changes requested

Reviewer: claude (reviewer-renata, opus). Lane-o tip `60506b314c`, base `e7b085d26c`. The range now also contains the lane-j merge `908029805b` (WP11/WP12, already reviewed separately). WP07's own diff is `e7b085d26c..b35b12f6f2` plus `908029805b..HEAD`.

Most cycle-1 items are fixed and verified. Two verifications failed, and both have a concrete reproduction:

- **N1:** the narrowing does not stop the masking.
- **N5:** a parse regression remains against base.

Both fixes are small. Everything else below is non-blocking.

## Blocking

### R1 (N1): `commit_idempotent` still masks a genuinely empty changeset

`transaction.py:944` raises only when `not self._staged_paths and not self._pre_emit_events_existed`. But `_pre_emit_events_existed` is just `events_path.exists()` at acquire (`transaction.py:645`), and that is True for every Mission that has a status history. It is not the signal "the seed carried this caller's content" that the docstring (`transaction.py:916-935`) and commit `d650cd36ac` claim ("True exactly when the seed legitimately committed content").

**Reviewer probe (not committed).** Setup, using the `test_transaction.py` fixture:

1. `_write_modern_meta(repo)`.
2. Transaction 1 runs `append_event` then `commit`, so the coordination log exists.
3. Transaction 2 stages nothing (the `implement.py:1014` all-sources-missing shape) and calls `commit_idempotent`.

Result:

| Revision | Outcome |
|---|---|
| HEAD | `pre_emit_events_existed = True` and returns a silent `CommitReceipt(..., is_noop=True)` |
| base `e7b085d26c` | raises `commit() called with no events or artifacts to commit` |

So the real-failure case cycle 1 flagged is still masked for every Mission except one with no log at all. The new test `test_commit_idempotent_still_raises_when_every_requested_path_is_missing` pins only that no-log shape, so its name overclaims.

**Required.** Pick one:

- **(a) A real discriminator.** No-op on zero staged paths only when the caller's requested paths are all present and identical at the destination HEAD (the cycle-1 alternative). The transaction cannot see paths the caller skipped, so the caller has to pass them, for example `commit_idempotent(message, requested_paths=...)` from `implement.py` and `workflow.py`.
- **(b) The honest widening.** Drop the `_pre_emit_events_existed` branch. Correct the docstring. Record the accepted risk through `spec-kitty agent tracer-append --category design-decisions`. Rename or repurpose the test, and add a test that pins the existing-log all-missing behaviour as the accepted outcome.

Either way, the docstring, the test names and the behaviour must agree.

Mutation evidence: removing the narrowing (`if False:`) kills only the no-log test, which confirms it guards one shape only.

### R2 (N5): paths containing ` (` are misread as clean, a regression against base

`_dirty_paths_in_checkout` (`commit_router.py:1971`) cuts at `" ("` before it un-quotes. For a C-quoted path that itself contains ` (`, the cut lands inside the quotes: `"Copy (1).md"` becomes `"Copy`. `_c_unquote_git_path` then sees no closing quote and returns the token as is, so nothing matches.

Real-git probe:

| Path | Status | HEAD | base |
|---|---|---|---|
| `tracked b c.txt` | tracked-modified | dirty | dirty |
| `tracked (2).md` | tracked-modified | **clean (wrong)** | dirty |
| `a file.txt` | untracked | dirty | dirty |
| `café.txt` | untracked | dirty | dirty |
| `Copy (1).md` | untracked | **clean (wrong)** | dirty |
| `old name.txt -> new name.txt` | staged rename | dirty | dirty |
| `new dir/x y.txt` | collapsed untracked dir | dirty | dirty |

Quoted spaces, non-ASCII names, renames and directory collapse are correct. The ` (` case is a new false negative in the #2739 B16 wrong-surface discriminator and in the `COORD_RECORD_IN_ROOT_CHECKOUT` refinement.

**Required:**

- Remove the explanatory suffix only when it matches what `_dirty_entries` actually appends: the `(untracked local file would be discarded …)` or `_RESET_OBSTRUCTION_MARKER` suffix, and only on `??`/`!!` lines. A safer alternative is to parse the quoted token first, or to have `ref_advance` expose the parsed path next to the display line.
- Add a test with `Copy (1).md` for both the untracked and the tracked-modified case.
- Also consider reusing `ref_advance._porcelain_path` for the rename split rather than re-implementing it. `_porcelain_entry_path` is now the third porcelain path parser, after `ref_advance._porcelain_path` and `acceptance._porcelain_dirty_path`. No existing C-unquote helper exists, so a new unquote function is fine.

### R3 (B1 residue, trivial)

`tests/specify_cli/coordination/test_transaction.py` is on `[tool.ruff.format].exclude` and gained 2 trailing blank lines at EOF (format-only noise; the file now ends `)\n\n\n`). Drop them, so the excluded files carry only semantic hunks.

## Verified (no action needed)

**B1.** The diff of `commit_router.py` against base is only the `_dirty_paths_in_checkout` change, the new helpers, and the `ref_advance` import. `test_ruff_format_exclude_ratchet` passes: 6 passed. I checked all 12 WP07-touched files on the format-exclude list:

- `agent_tasks_ports`, `commit_router`, `transaction`, `lanes/recovery`;
- `test_status_write_authority`, `test_implement_review_flow`, `test_placement_partition_golden_path`, `test_wp_integrity_crash_recovery`;
- `test_tasks_cli_contract_coord`, `test_outbound`, `test_transaction_legacy_topology_routing`, `test_transaction`.

They show only semantic hunks, apart from R3. In `test_transaction.py`, base has 34 tests and HEAD has 35 (the new N1 test). `_write_modern_meta(repo)` appears 17 times, the same as at `c2fe4d5afd`. The diff against `c2fe4d5afd` is purely additive, so no test content was lost.

**B2.** The T037 scenarios drive the real move-task CLI (`CliRunner`, no `--force`), and the post-fix EMPTY row is present: WARNING, restore, event on the coordination log, root unchanged. Probing the pre-fix EMPTY run:

- move-task appends 3 rows: the transition plus 2 annotation rows.
- No row carries a lamport field, so the append-order proxy is honest.
- The root porcelain baseline is `''`, so the root-unchanged equality is strong.

The relaxed counts are honest and not vacuous: the returned `event_id` is present, the carried set is contained, there are no duplicate ids, and every carried row comes before every new one. The `_seed_wp01_planned_on_coord` exception for MATERIALIZED-forked is accepted: a materialized Mission's read authority is the coordination log, which is where finalize-tasks lands WP01.

**B3.** diff-cover against `e7b085d26c` on the 6 WP07 source files: **93%** (119 lines, 8 missing). It passes the ≥90% gate. The claimed 98% does not reproduce, because the N5 parser arrived after that measurement. The missing lines:

| File | Lines | Branch |
|---|---|---|
| `commit_router.py` | 1889-1891, 1899-1900, 1903-1904 | `_c_unquote_git_path`: simple-escape, unknown-escape and UTF-8-decode-failure arms |
| `coord_seed.py` | 535 | staged-new residual |

Add `\"`/`\\` cases with the R2 test.

**B4.**

- No net new `# noqa` or `# type: ignore` in the WP07 files.
- RUF100 count is 49 at HEAD against 51 at base.
- Fresh-process imports of the 13 touched or affected modules succeed.
- `test_layer_rules`: 74 passed. `mypy --strict` error set is identical to base (25 = 25). ruff, `ruff format --check --force-exclude` and C901 are clean.

**N2.**

- `test_mission_resolver_walker_gate.py` is byte-identical to base, and the gate passes (4 passed).
- `os.rename` stays on one filesystem: the temp dir and `kitty-specs/` are siblings in the same worktree.
- No coordination-worktree code path runs a broad `git add`.

**N3.** `design-decisions-71f124fc4627` resolves, via `tracer_writer._entry_id`, to `traces/design-decisions.md` line 118, the lock-composition ruling.

**N4.** The dirty owned-root restore test is real: the `git checkout --` arm runs against `owned_root`.

## Non-blocking (record a decision or fix while in there)

- **`.spec-kitty-seed-tmp/` is not ignored.** After a crash it shows as `?? .spec-kitty-seed-tmp/` in the coordination worktree. That makes `ref_advance._dirty_entries(treat_untracked_as_dirty=True)`, the teardown and worktree-removal guard, refuse until the next seed for that Mission sweeps it. The old `kitty-specs/.<dir>.seed-*` location had the same residue. Consider `.git/info/exclude` for the coordination worktree, or a sweep of the temp root in teardown.
- **Weak behavioural pins (mutation).**
  - Reverting `_acquire_locked`'s coordination arm to the bare `CoordinationWorkspace.resolve` (M2) kills only the N1 no-op test, and only incidentally. Every T037 CLI scenario survives, because `feature_write_dir` already seeded. T039's "transaction on an EMPTY pre-fix Mission with a short lock timeout" test is still missing.
  - `_emit_on_coord_then_commit`'s `write_dir` swapped to `read_dir` (M6) survives every test and gate. It is effectively an equivalent mutant after acquire; document that, or pin it.
  - Reverting `reconcile_status` to `resolve_feature_dir_for_mission` (M4) survives every behavioural test (the transactional shell re-routes). It is killed only by the `test_no_read_side_bypass` gate, which is acceptable.
- **T037 parametrization.** Only the UNMATERIALIZED and pre-fix EMPTY tests are parametrized over `coord` and `lanes_with_coord`; the other five are COORD-only. The remote-only and DELETED tests assert the message, but not the recovery-hint command or a log-bytes snapshot. T042's C-008 control covers `lanes` only, not `single_branch`.

## Mutation evidence (scratch worktree at `60506b314c`)

Each mutant was run against the 6 WP07 test files, 176 tests in total.

| Mutant | Result |
|---|---|
| M1: ports `feature_write_dir` back to the read resolver | **7 killed** (T037 CLI ×6 plus the ports unit test) |
| M2: transaction coordination arm back to `CoordinationWorkspace.resolve` | 1 killed (the N1 test only) |
| M3: N1 narrowing removed | 1 killed |
| M4: recovery back to the read resolver | 0 killed by behavioural tests; killed by the `test_no_read_side_bypass` gate |
| M5: no un-quoting | 2 killed |
| M6: `_emit_on_coord_then_commit` `write_dir`→`read_dir` | 0 killed (tests and gates) |

## Tests run by the reviewer (`-n 6 --dist loadfile`, tip `60506b314c`)

| Suite | Result |
|---|---|
| `tests/coordination/`, `tests/specify_cli/coordination/`, `tests/status/`, `tests/lanes/`, `test_agent_tasks_ports_write_dir.py`, `test_coord_read_seam_callers.py` (with `--cov`) | 2897 passed, 18 skipped |
| 40 integration files matching the blast-radius grep, plus 3 B1 guards (`test_accept_matrix_coord_partition`, `test_issue_verdict_coord_legacy_md_preservation`, `test_issue_verdict_selfmat_hardening`) | 575 passed, 1 skipped |

Named gates, run individually:

| Gate | Result |
|---|---|
| layer_rules | 74 passed |
| no_write_side_rederivation | 27 passed |
| write_surface_placement_guard | 17 passed |
| status_events_writes_gate | 25 passed |
| ruff_format_exclude_ratchet | 6 passed |
| mission_resolver_walker_gate | 4 passed |
| destructive_op_routing | 37 passed |
| no_legacy_terminology | 96 passed |
| no_read_side_bypass | 38 passed |
| status_state_read_dir_single_authority | 13 passed |
| no_dead_symbols | 1 failed / 35 passed |
| dead_symbol_allowlist_contract | 1 failed / 3 passed |

Both dead-symbol reds are `coord_seed::COORD_SEED_TRAILER` only. They are allowed: WP06 cures them on lane-d.
