"""The shared fan-out sink must fail loudly when a patch target is missing.

A silent skip would let ``mock_fanout_sink.call_count == 0`` assertions pass
vacuously after a rename (the hazard the old ``hasattr`` guard allowed).
"""

from __future__ import annotations

import pytest

import specify_cli.status as status_pkg
from specify_cli.status import adapters, emit
from tests.conftest_fanout_sink import FANOUT_SINK_TARGETS, _RecordingSink, install_fanout_sink

pytestmark = [pytest.mark.unit]


def test_missing_patch_target_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    planted = (*FANOUT_SINK_TARGETS, "specify_cli.status.emit.fire_a_name_that_does_not_exist")
    with pytest.raises(AttributeError):
        install_fanout_sink(monkeypatch, _RecordingSink(), planted)


def test_every_real_target_exists_and_is_patched(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = _RecordingSink()
    install_fanout_sink(monkeypatch, sink, FANOUT_SINK_TARGETS)

    assert adapters.fire_status_fanout is sink
    assert status_pkg.fire_status_fanout is sink
    assert emit.fire_status_fanout is sink
