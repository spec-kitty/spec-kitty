"""Parse/format helper round-trips (WP04, FR-007, C-007).

Each helper wraps exactly one stdlib operation so consumers never need a raw
``datetime`` import merely to parse or format a value they already hold.
These tests prove round-trip fidelity against the producers that generate
the strings/floats these helpers consume -- not merely that the helpers
"exist" (C-009).
"""

from __future__ import annotations

import pytest

import kernel.clock as clock_module
from kernel.clock import (
    UTC,
    FrozenClock,
    datetime,
    from_epoch,
    now_epoch,
    now_utc_iso,
    now_utc_stamp,
    parse_iso,
    parse_stamp,
    timedelta,
)

pytestmark = pytest.mark.fast

_FIXED_INSTANT = datetime(2027, 1, 9, 23, 59, 1, 42000, tzinfo=UTC)


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch) -> datetime:
    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=_FIXED_INSTANT))
    return _FIXED_INSTANT


def test_parse_iso_round_trips_now_utc_iso(frozen: datetime) -> None:
    """``parse_iso(now_utc_iso())`` round-trips to the exact frozen instant.

    C-009 mutation verified: replacing :func:`parse_iso`'s body with
    ``return datetime.now(UTC)`` (ignoring its argument) turns this red --
    the round-tripped value would no longer equal the frozen instant.
    """
    parsed = parse_iso(now_utc_iso())

    assert parsed == frozen
    assert parsed.tzinfo is not None


def test_parse_stamp_round_trips_now_utc_stamp(frozen: datetime) -> None:
    """``parse_stamp`` inverts :func:`now_utc_stamp` given its exact format.

    Second-precision only (the stamp format has no sub-second component), so
    the round-tripped value is compared at second granularity, not exact
    equality with the microsecond-bearing frozen instant.
    """
    stamp_format = "%Y-%m-%dT%H:%M:%SZ"
    stamp = now_utc_stamp()

    parsed = parse_stamp(stamp, stamp_format)

    assert parsed.replace(tzinfo=UTC) == frozen.replace(microsecond=0)


def test_from_epoch_round_trips_now_epoch(frozen: datetime) -> None:
    """``from_epoch(now_epoch())`` round-trips to the frozen instant (the
    inverse pairing FR-007 calls out explicitly).

    C-009 mutation verified: replacing :func:`from_epoch`'s body with
    ``return datetime.now(UTC)`` (ignoring its argument) turns this red.
    """
    reconstructed = from_epoch(now_epoch())

    assert abs(reconstructed - frozen) < timedelta(microseconds=1)
    assert reconstructed.tzinfo is not None


def test_from_epoch_is_aware_utc_not_naive() -> None:
    """``from_epoch`` always returns an AWARE UTC datetime -- never naive
    (distinguishes it from an unqualified ``datetime.fromtimestamp`` call,
    which defaults to local/naive)."""
    result = from_epoch(0.0)

    assert result.tzinfo is UTC
    assert result == datetime(1970, 1, 1, tzinfo=UTC)
