---
affected_files: []
cycle_number: 2
mission_slug: write-service-protocol-01M5Z6N5
reproduction_command:
reviewed_at: '2026-10-27T19:41:31Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback, cycle 2 (reviewer-renata)

**Verdict: changes requested (one item).** Every cycle-1 item is fixed and each fix is pinned by a
test that fails first. At c2ced792 (tests only), 19 tests fail and 46 pass; at HEAD, 227 targeted
tests pass. ruff, format and mypy are clean. The new decision record DM-01M5ZC1PYHBB6QB02YQ4H1V52P
closes the cycle-1 note about the dead-gate ruling. One regression came in with the
open-once rework.

## Must fix

1. **A FIFO at the endpoint path hangs the reader forever, before any refusal**
   (`src/specify_cli/status/write_service_protocol.py`, `_open_private` / `_load`).
   `os.open(path, O_RDONLY | O_NOFOLLOW)` blocks on a named pipe until a writer opens it. The
   regular-file check and the directory-mode check only run afterwards, on `fstat`. The cycle-1
   code refused a non-regular file at `lstat`, before it opened anything, so this is a regression.
   Reproduction: make the endpoint directory mode `0777`, which the reader must refuse as
   `EXPOSED`, then `os.mkfifo(endpoint_path)`. `read_endpoint_file` does not return; under
   `timeout 20` it exits with 124. A process that can write to a misconfigured directory, or a
   stray FIFO, therefore wedges every CLI write instead of failing closed.
   Fix: add `O_NONBLOCK` to the open flags. On a regular file it has no effect; on a FIFO the open
   returns at once and the `fstat` `S_ISREG` check refuses it as `EXPOSED`. Clear the flag before
   reading, or rely on `S_ISREG` having already passed. Also consider checking the directory's
   `lstat` mode before the open, so an exposed directory is refused without opening anything.
   Test, red first, POSIX only: a FIFO at the endpoint path gives `EndpointFileError(EXPOSED)`.
   Run the call in a thread with a join timeout, or under `pytest-timeout` if the suite has it, so
   the red run fails instead of hanging.

## Nit (non-blocking)

- `raise ... from None` sets `__suppress_context__`, but the `JSONDecodeError` (whose `.doc` holds
  the token) stays reachable as `error.__context__`. `traceback.format_exception` hides it, which
  I verified, so standard renderers are clean. A tool that walks `__context__` regardless still
  reaches it. To close that path completely, decode inside the `except`, set a flag, and raise
  after the `except` block ends.

## Anti-pattern checklist

1 PASS · 2 PASS · 3 PASS (silent defaults in `transition_unit_from` now refuse) · 4 PASS ·
5 PASS · 6 PASS · 7 PASS · 8 FAIL (item 1: a blocking open on the fail-closed read path)
