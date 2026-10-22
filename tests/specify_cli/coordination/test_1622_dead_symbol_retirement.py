"""Regression lock for GitHub issue #1622 — coordination.status_service dead-symbol debt.

Resolution history
------------------
Mission 01KTPKST WP09 (commit be932d19a, approved 2026-06-09) resolved the bulk
of #1622 by delivering 2/5 deletions:

* ``append_event_log_batch`` — truly dead, zero callers → **deleted**.
* ``read_wp_lane_actor`` — truly dead, zero callers → **deleted**.

The remaining 3 symbols (``StatusReadSource``, ``EventLogWriteTarget``,
``StatusContractError``) are **load-bearing live internals** of the kept facade:

* ``StatusReadSource`` is the ``.source`` field type of ``EventLogReadContract``.
* ``EventLogWriteTarget`` is the ``.target`` field type of ``EventLogWriteContract``.
* ``StatusContractError`` is raised by ``read_event_log`` and ``append_event_log``.

Re-deleting any of the three breaks the live facade and ``test_status_transition.py``.
The prescribed remedy was de-exporting from ``status_service.__all__`` (the
dead-symbol gate's canonical fix for orphan-``__all__`` entries with live callers),
not deletion.  They were de-exported in the same WP09 commit.

This module locks that resolved state so a future reader cannot accidentally
"re-retire" the remaining three symbols.  The tests below are non-fakeable:
they assert the exact module shape AND exercise the live runtime guard.

References: #1622, mission 01KTPKST WP09, mission codebase-sanitization-1060-1622-01KV5F0B WP04.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import specify_cli.coordination.status_service as status_service
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    EventLogWriteContract,
    EventLogWriteTarget,
    StatusContractError,
    StatusReadSource,
    read_event_log,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# A1 – truly-dead functions are absent
# ---------------------------------------------------------------------------


def test_append_event_log_batch_deleted() -> None:
    """append_event_log_batch must not exist — it was deleted in WP09 (be932d19a)."""
    assert not hasattr(status_service, "append_event_log_batch"), (
        "append_event_log_batch should have been deleted; re-introducing it would "
        "resurrect a dead symbol."
    )


def test_append_event_log_deleted() -> None:
    """append_event_log must not exist — the dead single-event door was deleted (#6614)."""
    assert not hasattr(status_service, "append_event_log"), (
        "append_event_log should have been deleted; callers use append_event_stream_log(contract, [event])."
    )


def test_read_wp_lane_actor_deleted() -> None:
    """read_wp_lane_actor must not exist — it was deleted in WP09 (be932d19a)."""
    assert not hasattr(status_service, "read_wp_lane_actor"), (
        "read_wp_lane_actor should have been deleted; re-introducing it would "
        "resurrect a dead symbol."
    )


# ---------------------------------------------------------------------------
# A2 – retained-but-live symbols are de-exported (not in __all__)
# ---------------------------------------------------------------------------


def test_status_read_source_not_in_all() -> None:
    """StatusReadSource is a live internal — not part of the public API surface."""
    assert "StatusReadSource" not in status_service.__all__, (
        "StatusReadSource is an internal implementation detail of EventLogReadContract; "
        "exporting it would widen the public surface incorrectly."
    )


def test_event_log_write_target_not_in_all() -> None:
    """EventLogWriteTarget is a live internal — not part of the public API surface."""
    assert "EventLogWriteTarget" not in status_service.__all__, (
        "EventLogWriteTarget is an internal implementation detail of EventLogWriteContract; "
        "exporting it would widen the public surface incorrectly."
    )


def test_status_contract_error_not_in_all() -> None:
    """StatusContractError is a live internal — not part of the public API surface."""
    assert "StatusContractError" not in status_service.__all__, (
        "StatusContractError is raised by the live facade; it is an internal guard, "
        "not a public contract type callers should import directly."
    )


# ---------------------------------------------------------------------------
# A3 – retained symbols ARE importable (they are live, not gone)
# ---------------------------------------------------------------------------


def test_live_internals_importable() -> None:
    """All three de-exported symbols must still be importable from the module.

    They are live internals — their definitions must stay in the module for the
    facade functions to work correctly.
    """
    # The import at the top of this module already exercises this; if any of the
    # three were deleted the import would raise ImportError and the whole file
    # would fail to collect.  This test makes the assertion explicit and adds a
    # human-readable failure message.
    assert StatusReadSource is not None, "StatusReadSource must exist in the module"
    assert EventLogWriteTarget is not None, "EventLogWriteTarget must exist in the module"
    assert StatusContractError is not None, "StatusContractError must exist in the module"


# ---------------------------------------------------------------------------
# A4 – field-type proof: contracts carry the live enum types
# ---------------------------------------------------------------------------


def test_event_log_read_contract_source_field_type() -> None:
    """EventLogReadContract.source field type must be StatusReadSource."""
    fields = EventLogReadContract.__dataclass_fields__
    source_type = fields["source"].type
    # The dataclass stores the annotation as a string due to __future__.annotations;
    # accept either the string form or the live type itself.
    assert source_type in ("StatusReadSource", StatusReadSource), (
        f"EventLogReadContract.source field type is {source_type!r}, "
        "expected StatusReadSource — the enum is a live internal dependency."
    )


def test_event_log_write_contract_target_field_type() -> None:
    """EventLogWriteContract.target field type must be EventLogWriteTarget."""
    fields = EventLogWriteContract.__dataclass_fields__
    target_type = fields["target"].type
    assert target_type in ("EventLogWriteTarget", EventLogWriteTarget), (
        f"EventLogWriteContract.target field type is {target_type!r}, "
        "expected EventLogWriteTarget — the enum is a live internal dependency."
    )


# ---------------------------------------------------------------------------
# A5 – runtime raise: passing a write contract to the read function (load-bearing)
# ---------------------------------------------------------------------------


def test_read_event_log_rejects_write_contract(tmp_path: Path) -> None:
    """read_event_log must raise StatusContractError when passed a write contract.

    This exercises the live runtime guard at status_service.py lines 146-147:

        if not isinstance(contract, EventLogReadContract):
            raise StatusContractError("read_event_log requires EventLogReadContract")

    A hasattr/__all__-only test cannot catch a future regression where the guard
    is accidentally removed.  This test is the non-fakeable anchor.
    """
    write_contract = EventLogWriteContract.primary_checkout_append(tmp_path)
    with pytest.raises(StatusContractError):
        read_event_log(write_contract)  # noqa: PGH003  # deliberate wrong-type to trigger runtime guard
