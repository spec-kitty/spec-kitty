"""Shared fixtures for ``tests/agent`` integration tests.

The narrower ``tests/agent/cli/commands/conftest.py`` still stubs
additional things (the M7 teamspace gate). Both layers apply via
pytest's nested-conftest autouse-fixture composition.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests._support.charter_warning import rearmed_charter_warning

from tests.conftest import reset_spec_kitty_queue_state


@pytest.fixture(autouse=True)
def _autoclean_spec_kitty_queue():
    """Wipe ``~/.spec-kitty/{queue.db,queues,daemon}`` before every test.

    The sync-boundary preflight added in upstream commit ``cc5e1ca9``
    gates ``agent mission finalize-tasks``, ``agent tasks status``, and
    ``sync now`` on the legacy-queue-rows-in-scope count read from
    ``~/.spec-kitty/queue.db`` (and the per-scope tree under
    ``~/.spec-kitty/queues/``). Earlier tests in the same shard that
    legitimately exercise sync emission populate those rows, then the
    preflight on later tests refuses (exit code 2) with
    ``Refusing `spec-kitty agent ...```. The failure is cross-test
    pollution, not a defect in the assertion under test.

    This autouse fixture wipes the user-scoped queue state *before*
    every test in ``tests/agent/`` so each test sees an empty queue at
    the preflight boundary. Tests that explicitly need to populate the
    queue (e.g. ``test_sync_doctor::test_doctor_healthy``) are not in
    this tree and are unaffected.

    The fixture also wipes *after* every test so tests in this tree do
    not leak pollution downstream. Combined, the pattern mirrors
    JUnit's ``@Before`` + ``@After`` reset.
    """
    reset_spec_kitty_queue_state()
    yield
    reset_spec_kitty_queue_state()


@pytest.fixture(autouse=True)
def _rearm_charter_ambient_warning() -> Iterator[None]:
    """Re-arm the once-per-process charter warning around each test (#5714; see tests/_support/charter_warning.py)."""
    with rearmed_charter_warning():
        yield
