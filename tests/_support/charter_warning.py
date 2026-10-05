"""Re-arm the once-per-process charter ambient warning around a test (#5714).

``emit_advisory_warnings`` surfaces each distinct charter warning at most once per
process: the latch is exactly the "once per command run" budget. A test process is one
long run, so without a reset the first test that drives a command in-process consumes the
warning every later test in the same worker would see, and the outcome depends on how
``--dist loadfile`` schedules files.

The suites that drive commands in-process (``tests/specify_cli``, ``tests/agent``,
``tests/integration``) each wire :func:`rearmed_charter_warning` into an autouse fixture
in their own ``conftest.py``. The root ``tests/conftest.py`` is deliberately not used:
its definition set is pinned (``tests/architectural/test_home_owner_behaviour.py``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def rearmed_charter_warning() -> Iterator[None]:
    """Reset the latch before and after the wrapped block. Imported lazily to keep collection flat."""
    from specify_cli.charter_runtime.preflight.ambient_warning import _reset_surfaced_for_testing

    _reset_surfaced_for_testing()
    try:
        yield
    finally:
        _reset_surfaced_for_testing()
