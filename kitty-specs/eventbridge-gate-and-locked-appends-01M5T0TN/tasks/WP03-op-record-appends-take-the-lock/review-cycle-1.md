---
affected_files: []
cycle_number: 1
mission_slug: eventbridge-gate-and-locked-appends-01M5T0TN
reproduction_command:
reviewed_at: '2026-10-25T19:58:51Z'
reviewer_agent: claude-reviewer
wp_id: WP03
---

# WP03 review feedback (cycle 1, reviewer-renata)

The routing itself is right: the identity check runs as the `precondition` under the lock anchored on `kitty-ops/`; the index and closure spine go through the door with `no_follow=True` and mode 0o600; `AlreadyClosedError` is still raised; not-found and unreadable map to `InvocationError` as before; the gate census follow-up counts `append_event_log_lines`. Tests: `tests/specify_cli/invocation` 622 passed, 5 skipped. `tests/architectural/test_status_events_writes_gate.py` plus the writer tests: 71 passed. ruff, format and mypy are clean. Two things block approval.

**Issue 1: the symlink error mapping changed on POSIX (`src/specify_cli/invocation/writer.py:182-183`).**
Base `_validated_append_handle` opened with `O_NOFOLLOW`. On POSIX a symlinked trail made `os.open` raise ELOOP, which mapped to `InvocationWriteError("Failed to open invocation record safely: ...")`. Only platforms without `O_NOFOLLOW` raised `InvocationError("Refusing symbolic-link invocation record")`. The lane maps `EventLogSymlinkError` to the base `InvocationError` everywhere. I reproduced it by calling the validated append on a symlinked `kitty-ops/<id>.jsonl`, the case where the file is swapped after `invocation_path`'s pre-check:
- base: `InvocationWriteError: Failed to open invocation record safely: [Errno 40] Too many levels of symbolic links`
- lane: `InvocationError: Refusing symbolic-link invocation record`

The WP and the review brief require that other OSErrors map to `InvocationWriteError` with today's messages. Fix: map `EventLogSymlinkError` to `InvocationWriteError(f"Failed to open invocation record safely: {exc}")`. If you think unifying on the non-O_NOFOLLOW behaviour is better, record that as a decision in the WP instead of changing it silently.

**Issue 2: the moved and new branches of `_append_validated` have no tests.**
Coverage of `writer.py` under `tests/specify_cli/invocation` misses lines 167-168 (a whole line that is not JSON: unreadable), 170 (no `started` event) and 183 (the symlink mapping). Each one is a refusal that now runs inside the lock precondition, so a test must show the refusal and that the file stays byte-identical. `test_symlinked_trail_is_still_refused` accepts `ValueError`, so it stops at `invocation_path` and never reaches the new branch. Add to `tests/specify_cli/invocation/test_writer_locked_appends.py`:
- a trail holding `b"not json\n"`: `append_correlation_link` raises `InvocationError` matching "unreadable", file unchanged;
- a trail whose first row is not `started`: raises "no started event", file unchanged;
- a symlink reached past the pre-check (call `writer._append_validated(link, id, "{}")` directly, or swap the file in after `invocation_path`): asserts the Issue 1 mapping, target unchanged.

**Nit (non-blocking), T010.** The WP says to drop `+ "\n"` at the two `_append_line_no_follow` call sites (lines 55 and 219). They still add it, and the helper strips it with `removesuffix`. The result is the same, so this is optional.

Not caused by this WP: `tests/architectural/test_archive_root_byte_identical.py::test_no_preexisting_archived_file_was_modified` fails on base as well.
