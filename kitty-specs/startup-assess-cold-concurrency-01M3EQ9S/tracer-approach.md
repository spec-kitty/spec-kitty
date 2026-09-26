# Tracer: Approach

Mission: `startup-assess-cold-concurrency-01M3EQ9S`, which fixes P1 #3998 (and closes the stale #4017).

## Plan of attack

1. **Red-first (ADR 2026-07-17-1).** Add the issue-pinned `@pytest.mark.regression` test, driven through each owner's `ensure_*`. The torn read is injected at leaf `node_state`, and the peer "finishes" inside the real `machine_file_lock`. It is red on main with the production message.
2. **Tidy-first.** Extract `_serialize_owner` from `recheck_assets`. This is behaviour-preserving, and the existing recheck tests guard it.
3. **Fix.** Add `TornReadError`, `build_serialized` (replacing `retry_torn_read`), the `incomplete()` codes, the owner swaps, and `StartupAssetError` through the existing error hook. Add the INFO signal.
4. **Prove.** Primitive unit tests, the lock-set identity test, the warm spy, the Windows lock-read test and the ancestor-directory test, plus fresh-home reproducer evidence.

## Log

- 2026-09-26: the grounding squad reproduced the bug (5/32 at N=32) and the post-spec squad folded its findings. The plan is committed.
- 2026-09-26: WP01 executed the plan exactly as drafted here — red-first regression test (`a20797b6da`, RED on the planning base `81b835441b` for all 3 owners with `RuntimeError: Asset changed during preparation: …`), tidy-first `_serialize_owner` extraction, then the fix (`TornReadError`, `build_serialized`, `incomplete()` codes, owner swaps, `StartupAssetError`, INFO signal), then proof (primitive tests, lock-set identity, warm spy, Windows lock-read, ancestor-directory tests, flip regression → functional, no-traceback CLI tests). Two review cycles: cycle 1 rejected on test-fold strength and suppressions (6 blocking + 3 non-blocking items, all remediated); cycle 2 approved. Full commit list and test counts are in WP01's Activity Log (`tasks/WP01-torn-read-escalation.md`).
- 2026-09-26: WP02 (this WP) ran the fresh-home reproducer against the approved lane tip (`6b005a1c71`) via a `PYTHONPATH`-wrapped interpreter, plus a baseline contrast against the planning base (`81b835441b`). See `evidence-fresh-home-repro.md` for the full table. Verdict and CHANGELOG entry recorded there and in `docs/changelog/CHANGELOG.md`.

## Tracker closeout text

Drafted for the orchestrator to post (not posted by this WP — `authoritative_surface` here is `docs/changelog/`, not the tracker).

**#4885 comment:**

> This mission (#3998) fixed a distinct failure mode: an *unlocked* torn read at the leaf `node_state`/`AssetPreparation.observe()` level, where a losing reader raced a concurrent installer's in-progress write with no lock at all. The fix (`build_serialized`) makes that read wait for the installing peer's own lock and re-check once, instead of retrying blind. It does not touch, remove, or narrow the "Global asset input changed" reassess gate this issue owns — that gate fires when a *recorded* observation no longer matches at recheck time, which is a different check running at a different point (`recheck_assets`, still lock-serialized exactly as before). The two are related only in that both raise through the startup asset-preparation path; #3998's fix leaves #4885's gate exactly as it found it.

**#4017 closing evidence:**

> Closed by this mission's PR. Nightly run 36215053547 passed all 20 parameters of `test_installed_cli_keeps_two_owned_worktrees_isolated`; the underlying fix was PR #4174, which this ticket was never linked back to. No further action needed.

**#3998 resolution summary:**

> Fixed. The torn-read escalation now waits for the installing peer's own serialization lock and re-checks once, instead of retrying unlocked up to three times and aborting. A destination-role torn read escalates; a source-role torn read (asset drift) is still refused immediately, unwaited. When startup preparation genuinely cannot complete, the command now prints one `Error:` line (or one JSON error object under `--json`) with no traceback, via the existing `GuardedReadError` presentation hook. Warm-start behaviour is unchanged (lock-free, one check). See `docs/changelog/CHANGELOG.md` (`[Unreleased]` → `Fixed`) for the user-facing note and `evidence-fresh-home-repro.md` for the fresh-home concurrency evidence (NFR-001/SC-001). Also closes the stale #4017 (see above).
