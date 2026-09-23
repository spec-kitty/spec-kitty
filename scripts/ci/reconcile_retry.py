"""Shared bounded retry-with-backoff primitive for CI reconciliation scripts.

Extracted so `fleet_verdict.py`/`fleet_main.py` (retry-then-skip on a
repeating `workflow_run` event) and `wait_for_artifacts.py` (a bounded
in-process wait against a single, non-repeating event) can both retry an
unstable read without each hand-rolling their own loop -- the duplication
that produced the double-snapshot drift this mission fixes in the first
place.

Compatibility contract (binding on this module and on all future changes to
it): `reconcile_retry.py` MUST remain fully caller-agnostic. No
GitHub-specific parameters (e.g. a PR-number or run-ID argument), no
fleet-verdict-specific terminal-behavior knobs (e.g. a flag that changes
what `None` means), and no optional hooks added for one caller's
convenience. Any caller-specific need belongs in that caller's own
`attempt()` closure or a caller-side wrapper, never inside this module. This
protects callers from coupling to each other's needs through a shared
dependency.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

__all__ = ["retry_with_backoff"]

T = TypeVar("T")


def retry_with_backoff(
    attempt: Callable[[], T | None],
    *,
    max_attempts: int,
    backoff_seconds: Callable[[int], float],
    sleep: Callable[[float], None] = time.sleep,
) -> T | None:
    """Call attempt() up to max_attempts times. attempt() returns None to mean
    "not yet stable/visible, retry"; anything else is returned immediately.
    Sleeps backoff_seconds(i) between attempts (never after the last). Returns
    None if every attempt returned None -- the CALLER decides what None means
    (skip-and-defer vs. fail loudly); this primitive makes no such decision.

    `i` passed to `backoff_seconds` is the 1-indexed count of attempts
    completed so far: after attempt 1 returns None, `backoff_seconds(1)` is
    called; after attempt 2 returns None, `backoff_seconds(2)`; and so on.
    """
    for i in range(1, max_attempts + 1):
        result = attempt()
        if result is not None:
            return result
        if i < max_attempts:
            sleep(backoff_seconds(i))
    return None
