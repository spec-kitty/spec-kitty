"""The single door to wall-clock time.

Every wall-clock read in this codebase routes through this module. It is
the **sanctioned** home for stdlib ``datetime``/``time.time()`` access; a
repo-wide gate (``tests/architectural/test_clock_import_ban.py`` +
``test_clock_call_ban.py``, landed WP01b) bans the raw stdlib forms
everywhere else, including through this module's own re-exported types
(re-exporting a type never creates a sanctioned ``.now()`` path).

**Distinct from a Lamport logical clock** -- such a counter tracks causal
ordering for event synchronization, not the current civil time. The two
concepts must never be conflated: this module owns *wall-clock* time (what
a developer means by "the current timestamp"); a logical clock owns a
monotonically-increasing counter unrelated to the wall clock. (The sync
package that hosted one was removed in issue #5.)

**Distinct from duration clocks** (``time.monotonic()`` / ``time.perf_counter()``)
used for elapsed-time measurement -- those are out of scope for this door
and remain unbanned (only the wall-clock ``time.time()`` call is banned by
the gate).

This module hosts (mission ``kernel-clock-single-door``):

- The injectable :class:`Clock` protocol, :class:`SystemClock` (the one real
  wall-clock boundary), :class:`FrozenClock` (a deterministic test double),
  and the :data:`DEFAULT_CLOCK` singleton every producer below reads through
  (WP02, FR-008/009).
- The producer family: :func:`now_utc_iso`, :func:`now_utc_stamp`,
  :func:`now_utc_compact_stamp`, :func:`now_utc_seconds`, :func:`now_utc`,
  :func:`now_epoch` -- one function per distinct on-disk/on-wire
  serialization contract (C-003); folding two contracts together is
  forbidden even when they look similar (WP03, FR-004/005/006).
- Parse helpers -- :func:`parse_iso`, :func:`parse_stamp`, :func:`from_epoch`
  -- so consumers never need a raw stdlib ``datetime`` import merely to parse
  a value they already have (WP04, FR-007/C-007). The former
  ``format_stamp`` lost its last caller (#7569) and was removed; a held
  ``datetime`` formats itself with ``.strftime``.
- Minimal type re-exports (:data:`__all__`) so consumers can import
  ``datetime``/``date``/``timedelta``/``UTC`` from the door for annotations,
  arithmetic, and parsing rather than importing stdlib ``datetime``
  directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol, runtime_checkable

__all__ = [
    "UTC",
    "UTC_SECOND_TIMESTAMP_FORMAT",
    "Clock",
    "DEFAULT_CLOCK",
    "FrozenClock",
    "SystemClock",
    "date",
    "datetime",
    "from_epoch",
    "now_epoch",
    "now_utc",
    "now_utc_compact_stamp",
    "now_utc_iso",
    "now_utc_seconds",
    "now_utc_stamp",
    "parse_iso",
    "parse_stamp",
    "timedelta",
]


# ---------------------------------------------------------------------------
# WP02 -- the injectable clock (FR-008/009)
# ---------------------------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    """The injection seam every door producer reads through.

    Modelled 1:1 on ``GitPort``
    (``src/specify_cli/cli/commands/implement_cores.py``): a minimal read
    surface with exactly one real implementation (:class:`SystemClock`, the
    sole sanctioned wall-clock boundary) and one deterministic test double
    (:class:`FrozenClock`). Every producer below delegates to
    :data:`DEFAULT_CLOCK` rather than calling ``datetime.now``/``time.time``
    directly, so freezing one clock instance freezes every producer
    uniformly (SC-002) -- no per-module monkeypatching required.
    """

    def now(self) -> datetime:
        """The current aware-UTC instant."""
        ...

    def now_iso(self) -> str:
        """The current instant's ``isoformat()``.

        Kept as its own :class:`Clock` method (rather than derived by
        callers from :meth:`now`) so both :class:`SystemClock` and
        :class:`FrozenClock` can produce it directly -- :func:`now_utc_iso`
        just forwards here.
        """
        ...

    def now_epoch(self) -> float:
        """The current time as a Unix epoch float."""
        ...


class SystemClock:
    """The ONE real wall-clock boundary.

    The sole sanctioned holder of ``datetime.now()``/``time.time()`` calls
    in this module's :class:`Clock` implementations (:func:`now_utc_iso` and
    peers hold their own direct calls too, for producers that predate the
    ``Clock`` seam or need a distinct contract shape). :data:`DEFAULT_CLOCK`
    is an instance of this class.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)

    def now_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    def now_epoch(self) -> float:
        return time.time()


@dataclass(frozen=True)
class FrozenClock:
    """A deterministic test double: every method derives from one fixed
    ``instant``, regardless of when -- or how many times -- it's called.

    Usage (the SC-002 idiom -- ONE injection point, no per-module
    monkeypatching)::

        monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=FIXED))
    """

    instant: datetime

    def now(self) -> datetime:
        return self.instant

    def now_iso(self) -> str:
        return self.instant.isoformat()

    def now_epoch(self) -> float:
        return self.instant.timestamp()


DEFAULT_CLOCK: Clock = SystemClock()


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    The canonical producer of the aware-UTC ``isoformat()`` form: a local
    ``datetime.now(UTC).isoformat()`` copy anywhere in the codebase is a
    violation of the single-door contract. Do not use this for the
    second-precision ``%Y-%m-%dT%H:%M:%SZ`` stamp format (:func:`now_utc_stamp`)
    or for callers that need a ``datetime`` object back (:func:`now_utc`) --
    those are distinct producers (C-003).

    Reads through :data:`DEFAULT_CLOCK` (WP02): freezing
    :data:`DEFAULT_CLOCK` freezes this producer too, with no separate
    monkeypatch of this function.
    """
    return DEFAULT_CLOCK.now_iso()


# ---------------------------------------------------------------------------
# WP03 -- the producer family (FR-004/005/006, C-003)
# ---------------------------------------------------------------------------

#: The canonical second-precision stamp format (FR-004). This collapses the
#: four previously-duplicated ``TIMESTAMP_FORMAT`` /
#: ``UTC_SECOND_TIMESTAMP_FORMAT`` module constants
#: (``task_utils/support.py``, ``review/cycle.py``,
#: ``cli/commands/agent/tasks.py``, ``cli/commands/agent/tasks_materialization.py``)
#: into one definition; those four modules now import this constant under
#: their pre-existing local name rather than redefining it.
UTC_SECOND_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

#: The compact-stamp format (no separators) -- a DISTINCT serialization
#: contract from :data:`UTC_SECOND_TIMESTAMP_FORMAT` (C-003): do not fold
#: the two together even though they share a precision.
_COMPACT_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def now_utc_stamp() -> str:
    """The second-precision stamp: ``%Y-%m-%dT%H:%M:%SZ``.

    Distinct contract from :func:`now_utc_iso` (no ``+00:00`` suffix, no
    sub-second precision) -- do not use one for the other's on-disk format.
    """
    return DEFAULT_CLOCK.now().strftime(UTC_SECOND_TIMESTAMP_FORMAT)


def now_utc_compact_stamp() -> str:
    """The compact stamp: ``%Y%m%dT%H%M%SZ`` (no separators)."""
    return DEFAULT_CLOCK.now().strftime(_COMPACT_STAMP_FORMAT)


def now_utc_seconds() -> str:
    """The aware-UTC ISO form truncated to second precision
    (``isoformat(timespec="seconds")``) -- distinct from both
    :func:`now_utc_iso` (native/microsecond precision) and
    :func:`now_utc_stamp` (the ``Z``-suffixed, non-ISO stamp)."""
    return DEFAULT_CLOCK.now().isoformat(timespec="seconds")


def now_utc() -> datetime:
    """The current aware-UTC ``datetime`` -- for callers that need a
    ``datetime`` object back rather than a serialized string (FR-006:
    ``decisions/*`` and peers route here)."""
    return DEFAULT_CLOCK.now()


def now_epoch() -> float:
    """The current time as a Unix epoch float -- replaces raw
    ``time.time()`` wall-clock reads (FR-005)."""
    return DEFAULT_CLOCK.now_epoch()


# ---------------------------------------------------------------------------
# WP04 -- parse/format helpers (FR-007, C-007)
# ---------------------------------------------------------------------------


def parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 string into a ``datetime`` (wraps
    ``datetime.fromisoformat``) -- the inverse of :func:`now_utc_iso` /
    :func:`now_utc_seconds`."""
    return datetime.fromisoformat(value)


def parse_stamp(value: str, fmt: str) -> datetime:
    """Parse a stamp string into a ``datetime`` given its format (wraps
    ``datetime.strptime``) -- the inverse of
    :func:`now_utc_stamp` / :func:`now_utc_compact_stamp`."""
    return datetime.strptime(value, fmt)


def from_epoch(value: float) -> datetime:
    """Convert a Unix epoch float into an aware-UTC ``datetime`` (wraps
    ``datetime.fromtimestamp(value, tz=UTC)``) -- the inverse of
    :func:`now_epoch`."""
    return datetime.fromtimestamp(value, tz=UTC)
