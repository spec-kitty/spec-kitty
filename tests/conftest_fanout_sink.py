"""Reusable fan-out sink mock fixtures for WP09 (T041).

The canonical status fan-out boundary is
:func:`specify_cli.status.adapters.fire_status_fanout`.  The
``mock_fanout_sink`` fixture patches that boundary in *both* its
import-time location (``specify_cli.status.adapters.fire_status_fanout``)
and in the public package location where ``coordination.outbound`` performs
its architecture-compliant lazy import
(``from specify_cli.status import fire_status_fanout``).

A separate file (not directly auto-loaded by pytest) keeps this fixture
opt-in: tests that want to assert on outbound traffic do

    from tests.conftest_fanout_sink import mock_fanout_sink  # noqa: F401

inside their own conftest or import directly via ``pytest_plugins``.

Spec source: FR-022, NFR-009, SC-09.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest


class _RecordingSink:
    """Records every status fan-out call so tests can assert on it.

    The instance exposes a ``calls`` list of ``(args, kwargs)`` tuples
    and convenience helpers (``call_count``, ``last_kwargs``) that keep
    test code compact.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append((args, kwargs))

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_event(self) -> Any:
        if not self.calls:
            return None
        _, kwargs = self.calls[-1]
        return kwargs.get("event")

    @property
    def last_kwargs(self) -> dict[str, Any]:
        if not self.calls:
            return {}
        return self.calls[-1][1]


# Every boundary the sink replaces. ``emit`` captured the symbol at import
# time, so the source module alone does not reach its bound reference.
FANOUT_SINK_TARGETS: tuple[str, ...] = (
    "specify_cli.status.adapters.fire_status_fanout",
    "specify_cli.status.fire_status_fanout",
    "specify_cli.status.emit.fire_status_fanout",
)


def install_fanout_sink(
    monkeypatch: pytest.MonkeyPatch,
    sink: _RecordingSink,
    targets: tuple[str, ...],
) -> None:
    """Patch ``sink`` over every target, failing loudly on a missing one.

    ``monkeypatch.setattr`` with a dotted string raises ``AttributeError`` when
    the attribute does not exist, so a renamed or removed boundary breaks the
    test instead of leaving it unpatched (a vacuous ``call_count == 0``).
    """
    for target in targets:
        monkeypatch.setattr(target, sink)


@pytest.fixture
def mock_fanout_sink(monkeypatch: pytest.MonkeyPatch) -> Iterator[_RecordingSink]:
    """Patch ``fire_status_fanout`` at every observable boundary.

    Yields a :class:`_RecordingSink` that captures every call.

    Boundaries patched:
      * ``specify_cli.status.adapters.fire_status_fanout`` — the canonical
        import path. Existing callers that import the symbol at module
        load time see the patched version.
      * ``specify_cli.status.fire_status_fanout`` — the package-root
        re-export. ``coordination.outbound`` imports this symbol lazily,
        so tests must patch it too or they can fall through to any
        handler a transport owner registered.
      * ``specify_cli.status.emit.fire_status_fanout`` — emit.py imports
        the symbol at its module top, so monkeypatching the source alone
        does not catch its already-bound reference.

    The fixture is **safe to combine** with ``coordination.outbound.``
    ``queue_fanout_emission`` because that helper performs a lazy
    ``from specify_cli.status import fire_status_fanout`` inside
    ``_send_to_fanout`` — so the patched package attribute is read
    fresh on every call.
    """
    sink = _RecordingSink()
    install_fanout_sink(monkeypatch, sink, FANOUT_SINK_TARGETS)
    yield sink
