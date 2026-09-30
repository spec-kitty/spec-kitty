# Review: #5353 slice-3 follow-up M (D2: real LANES done-bookkeeping guard)

Reviewer: reviewer-renata. Op: 01M3SSNQMKZMWJBACHJ80XQYDC. Branch: `issue-5353-m-followup` @ 00e35bc2.

## Verdict: APPROVE-WITH-NITS

The branch changes tests only (`git diff origin/main...HEAD -- src/` is empty). It matches the ledger's D2 target shape: it uses `build_lanes_mission` (target `develop`), runs a real `consolidate --mission <slug> --yes`, and checks `git show develop:` for the events and `status.json`. The 17-patch mock is retired.

## Key concern: is the `git show` layer ever load-bearing? YES.

- **Break D** (my own): both product guards weakened (`_assert_merged_wps_reached_done` and `_assert_merged_wps_done_on_target` each get an early `return`), and WP02's done emit is skipped in `_record_merged_wps_done_for_merge`. Consolidate exits 0. The new test goes RED at `test_merge_status_commit.py:257`: `assert {'WP01'} == {'WP01', 'WP02'}`.
- **Break C** (my own): `status.json` materialization only is corrupted (`reducer.materialize` writes WP02 as `approved` when the log says `done`). Consolidate exits 0. The new test goes RED at `:260`: `{'WP02': 'approved'} != {'WP02': 'done'}`.
  - No product guard catches this. The old 17-patch test PASSES against it, because it had no `status.json` assertion. The new test is strictly stronger here.
- **Break E** (my own, characterisation): only `_assert_merged_wps_reached_done` weakened, plus the WP02 skip. RED at `:252`, the exit-code assertion ("Post-merge target validation failed ... WP02=approved").
  - So `_assert_merged_wps_done_on_target` is the second product guard. The events assertion is load-bearing only when both guards are off.
- **Break A** (implementer's; retirement guard re-run): an early `return` in `_mark_wp_merged_done`. RED at `:252` ("Offending WPs: WP01=approved, WP02=approved").
  - The old test also went RED on break D, at its `:403` git-show assertion.
- After each break I ran `git checkout -- src/`, and `git status` was clean.

## Findings

1. (nit) `red-proofs-m.md` cites the failing line as `:293`. The committed file fails at `:252` (exit code), `:257` (events) and `:260` (snapshot). Refresh the evidence line numbers.
2. (nit) The branch is 35 commits behind `origin/main`, but it merges cleanly. I ran the branch's test file against `origin/main` `src`: 10 passed.
3. (info) Product gap, now pinned only by this test: no product guard checks that the target's `status.json` agrees with the event log (break C). Consider a follow-up issue.

## Checks

- `e.get("to_lane")` is correct. The log legitimately carries non-lane rows (retrospective lifecycle and annotation envelopes; `status/store.py:593-635`). The product's `_parse_target_lanes_by_wp` uses the same `.get`. A done row with no `wp_id` raises `KeyError`, which fails the test, so nothing is hidden. Set equality also rejects extra done WPs.
- The `slow` marker plus inline rationale matches `TestRealMergeCommitsBookkeeping`.
- The kept #5019 test is byte-identical to `origin/main` from its `def` onward; only the class was renamed.
- The ledger gets no `src/` change, and no planted break landed. Commit trailers are present. `ruff check`, `ruff format --check` and `mypy` pass on the file. No new noqa or type-ignore.

## Tests

`pytest tests/cli/commands/test_merge_status_commit.py tests/terminus/test_lanes_fixture_smoke.py tests/architectural/test_ruff_pytest_style_baseline.py tests/architectural/test_ruff_format_exclude_ratchet.py`: 26 passed (274 s).
