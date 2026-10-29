---
affected_files: []
cycle_number: 1
mission_slug: synthesis-record-integrity-01M5ZBC9
reproduction_command:
reviewed_at: '2026-10-27T20:13:18Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (reviewer-renata), cycle 1

Verdict: changes requested. The lock module, the restamp wiring, the API export and the CLI wiring look correct. All gates are green. The blocker is that the CLI tests do not prove two acceptance points. I checked both with mutants, as described below.

## Issue 1 (blocking): the resynthesize CLI wiring is untested

FR-002 and FR-003 apply to `charter resynthesize`. The WP's acceptance-gap rule asks: "if I delete the implementation code, does this test still pass?"

Evidence: in a scratch copy of the lane, I deleted the `_hold_synthesis_lock(lock_stack, repo_root, read_only=list_topics)` line from `resynthesize.py`. Both resynthesize tests in `tests/charter/synthesizer/test_synthesis_lock_cli.py` still pass (2 passed). This matches your own note that `test_resynthesize_topic_refuses_when_lock_held_and_writes_nothing` was green before the wiring. It refuses only because the run later reaches `restamp_bundle_hash`, and the fixture's first write happens to be that restamp. So the test does not exercise the run-wide lock that T009 adds to resynthesize, and it was never red-first.

Fix: add a resynthesize refusal test that goes red when the CLI lock is removed. See Issue 2: a fixture with a legacy directive does this, because the convergence writes before any restamp. Confirm the test is red with the line removed and green with it restored.

## Issue 2 (blocking): no test proves the lock is taken before the legacy convergence

FR-002 and the WP Review Guidance require the lock to be taken before the legacy convergence. FR-003 requires the directive files to stay byte-identical.

Evidence: in a scratch copy, I moved `_hold_synthesis_lock(...)` to just after `_converge_legacy_project_intent_directive(...)` in both `synthesize.py` and `resynthesize.py`. All 7 tests in `test_synthesis_lock_cli.py` pass. `_seed_project` seeds no legacy `mission-type-scope-directive`, so the convergence has nothing to write and the ordering is never observed.

Fix: in `test_synthesis_lock_cli.py`, seed a legacy project-intent directive. Do it the way `tests/specify_cli/cli/commands/charter/test_synthesize_dry_run_evidence_6443.py` and `tests/charter/synthesizer/test_legacy_rename.py` do, so that `rename_legacy_project_intent_directive` reports `pending`. Then, for both `charter synthesize` and `charter resynthesize --topic ...`:

- hold the lock from another thread;
- assert exit 1 with `CHARTER_SYNTHESIS_LOCK_HELD`;
- assert that `_snapshot` is unchanged, including the legacy directive file and its provenance, which must still sit under the old name.

Pair each test with a lock-free positive control on the same fixture that shows the rename happens. Each new test must go red when the lock is moved after the convergence.

## Issue 3 (non-blocking, recommended): duplicated `_hold_synthesis_lock` helper

The same helper is defined in both `synthesize.py` and `resynthesize.py`. It is small and does not trip Sonar S1192, which covers duplicated string literals. It is still a second copy of a lock-acquisition policy, and the charter's single-canonical-authority principle asks for one owner.

Suggested fix:
- Add a factory to `charter.activation.synthesizer.synthesis_lock`, for example `synthesis_lock_unless(read_only: bool, repo_root: Path) -> AbstractContextManager[Path | None]`. It returns `contextlib.nullcontext()` when `read_only` is true, and `synthesis_lock(repo_root)` otherwise.
- Export it through `charter.activation.api`, add it to `__all__`, and add a `_SEAM_TABLE` row.
- In both commands, call `lock_stack.enter_context(synthesis_lock_unless(<read_only>, repo_root))` and delete both local helpers.
- Add a unit test for both branches.

## Verified OK (no action)

- **Lock module:**
  - The root is resolved before hashing, and the digest matches the `kernel/event_log_append.py` derivation.
  - The non-git fallback is `.kittify/runtime/locks/charter-synthesis.lock`.
  - `GitTopologyUnavailableError` becomes `CHARTER_SYNTHESIS_LOCK_UNAVAILABLE`.
  - The lock is `machine_file_lock(blocking=True, reentrant=True)`, and the timeout is read at call time.
  - Both errors are `KittyInternalConsistencyError`, their bodies name the lock file, and `__all__` is present.
- **Restamp:** the read-modify-write runs under the lock and is re-entrant. No restamp caller holds another lock or runs on a worker thread, so there is no lock-order inversion.
- **CLI:** the `ExitStack` and `finally: close()` cover `typer.Exit` and exceptions and add no branch to the `noqa: C901` bodies. No new suppression was added. `--dry-run`, `--dry-run-evidence` and `--list-topics` take no lock, and tests cover all three.
- **Unit tests:** the holder runs on another thread, and the crashed-holder subprocess test, the two-worktree test and the restamp held/free pair are all present.
- **Gates:** ruff, format and mypy are clean apart from the two `untyped-decorator` errors, which also appear on the base. All commits carry the correct trailer and touch only owned files.
