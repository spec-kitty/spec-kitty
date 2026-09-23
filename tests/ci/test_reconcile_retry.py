"""Pin the shared bounded retry primitive's contract (reconcile-flake-family WP01).

RED on ``fix/reconcile-flake-family-4882`` (``scripts/ci/reconcile_retry.py`` does not
exist yet, so every test in this file fails on import). GREEN once
:func:`retry_with_backoff` exists with the exact signature plan.md pins: bounded
attempts, ``None`` means "retry", any other value returns immediately, and
``sleep``/``backoff_seconds`` are both injected so this suite never actually
waits (NFR-002/NFR-003).

Indexing convention (documented here because the primitive's own docstring does not
pin it): ``backoff_seconds(i)`` is called with ``i`` equal to the number of attempts
completed so far (1-indexed) -- i.e. after attempt 1 returns ``None`` the loop calls
``backoff_seconds(1)``, after attempt 2 returns ``None`` it calls ``backoff_seconds(2)``,
and so on. There is never a sleep after the final attempt.
"""

from __future__ import annotations

from unittest.mock import Mock, call

import pytest

from scripts.ci.reconcile_retry import retry_with_backoff

pytestmark = pytest.mark.fast


def test_retry_with_backoff_returns_first_non_none_result_and_stops_retrying() -> None:
    """Recovery within budget: stop as soon as attempt() returns non-None."""
    sentinel = {"stabilized": True}
    results = [None, None, sentinel]
    attempt = Mock(side_effect=results)
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    outcome = retry_with_backoff(
        attempt,
        max_attempts=4,
        backoff_seconds=lambda i: 0.0,
        sleep=fake_sleep,
    )

    assert outcome is sentinel
    assert attempt.call_count == 3
    assert len(sleep_calls) == 2


def test_retry_with_backoff_returns_none_after_exhausting_bounded_budget() -> None:
    """Exhausted-budget termination: exact max_attempts call count, no over/under-call."""
    attempt = Mock(return_value=None)
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    outcome = retry_with_backoff(
        attempt,
        max_attempts=5,
        backoff_seconds=lambda i: 0.0,
        sleep=fake_sleep,
    )

    assert outcome is None
    assert attempt.call_count == 5
    assert len(sleep_calls) == 4


def test_retry_with_backoff_invokes_backoff_seconds_with_one_indexed_attempt_count() -> None:
    """backoff_seconds(i) is called once per sleep, i = attempts completed so far."""
    attempt = Mock(return_value=None)
    backoff_seconds = Mock(return_value=0.0)
    fake_sleep = Mock()

    retry_with_backoff(
        attempt,
        max_attempts=5,
        backoff_seconds=backoff_seconds,
        sleep=fake_sleep,
    )

    assert backoff_seconds.call_args_list == [call(1), call(2), call(3), call(4)]
    assert fake_sleep.call_args_list == [call(0.0), call(0.0), call(0.0), call(0.0)]


def test_retry_with_backoff_never_sleeps_after_the_final_attempt() -> None:
    """The last attempt (success or exhaustion) is never followed by a sleep."""
    sentinel = "ready"
    attempt = Mock(side_effect=[None, sentinel])
    fake_sleep = Mock()

    outcome = retry_with_backoff(
        attempt,
        max_attempts=2,
        backoff_seconds=lambda i: 0.0,
        sleep=fake_sleep,
    )

    assert outcome == sentinel
    assert attempt.call_count == 2
    fake_sleep.assert_called_once_with(0.0)
