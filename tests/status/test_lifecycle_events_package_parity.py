"""Pin the CLI's lifecycle vocabulary to the values ``spec_kitty_events`` publishes.

#6876 was filed because two frozen in-core contract tools
(``contracts/tools/event_mapping_check.py`` and ``contracts/tools/citation_check.py``)
resolved ``LIFECYCLE_EVENT_TYPES`` by *parsing the module's syntax tree*: a member was
accepted only when it was a module-level string literal assigned in the same file, so
#6447's "import the twelve constants instead of re-declaring them" change failed with
``LIFECYCLE_SOURCE_UNREADABLE`` / ``UNRESOLVED_INPUT``. Both tools — and the D-9 freeze
gate that pinned them — were removed from core by ``a212ccdf55`` (*"refactor!: remove
core's copies of the events service and contracts"*, 2026-11-01, ``Refs #6915``,
``Refs #6117``), which is ADR 2026-10-29-1 D-9's own exit clause.

Removing the tools also removed the only in-core assertion that the CLI's copy of the
vocabulary matches the package that owns it. This module restores that assertion without
restoring the mistake: it compares *values*, never declarations, so it stays green
whether the twelve names are local literals (today) or imports from ``spec_kitty_events``
(#6447), and it can never re-create the deadlock #6876 records.

The CLI's membership is deliberately narrower than the package's vocabulary:
``LIFECYCLE_EVENT_TYPES`` feeds ``AUTHORITATIVE_NON_LANE_EVENT_TYPES`` (which
``status.store`` and the mission-state repair use to decide what a repair pass preserves)
and the append guard, so deriving it from the package's wider sets would change which
rows survive a repair and which appends are accepted (#6447 triage, 2026-10-19).
"""

from __future__ import annotations

import pytest
import spec_kitty_events

from specify_cli.status import lifecycle_events as lifecycle

pytestmark = [pytest.mark.fast]

#: The twelve CLI lifecycle constant names, not the package's separate
#: ``CANONICAL_LIFECYCLE_EVENT_TYPES``. Each is exported at the ``spec_kitty_events``
#: top level from the pinned floor (``>=11.3.0,<12``).
LIFECYCLE_CONSTANT_NAMES = (
    "PROJECT_INITIALIZED",
    "MISSION_CREATED",
    "SPECIFY_STARTED",
    "SPECIFY_COMPLETED",
    "PLAN_STARTED",
    "PLAN_COMPLETED",
    "TASKS_STARTED",
    "TASKS_COMPLETED",
    "WP_CREATED",
    "REVIEWER_SELF_APPROVAL",
    "MISSION_REOPENED",
    "FOLLOW_UP_RECORDED",
)


def _package_attribute(name: str) -> object:
    """Return the ``spec_kitty_events`` attribute called *name*, failing loudly when absent.

    A future package release that renames or drops one of the pinned symbols must read as a
    named failure against the published exports, not as an ``AttributeError`` raised from
    inside an assertion, so the diagnosis is immediate (#6876 FR-004).
    """
    if not hasattr(spec_kitty_events, name):
        pytest.fail(
            f"spec_kitty_events does not export {name!r}. A pinned symbol was renamed or removed upstream: update the CLI vocabulary and this pin together."
        )
    return getattr(spec_kitty_events, name)


def _package_value(name: str) -> str:
    """Return the string value the package publishes for the constant *name*."""
    value = _package_attribute(name)
    assert isinstance(value, str), f"spec_kitty_events.{name} is not a str: {value!r}"
    return value


def _package_set(name: str) -> set[str]:
    """Return the package's frozenset of event-type names published as *name*."""
    value = _package_attribute(name)
    assert isinstance(value, frozenset), f"spec_kitty_events.{name} is not a frozenset: {value!r}"
    return set(value)


def _wide_vocabulary() -> set[str]:
    """The package's wider lifecycle vocabulary the CLI deliberately does not adopt.

    Neither package set is the CLI's vocabulary on its own — ``CANONICAL_LIFECYCLE_EVENT_TYPES``
    lacks ``MissionCreated``/``MissionReopened``/``FollowUpRecorded``, and
    ``MISSION_EVENT_TYPES`` lacks the project/spec/plan/tasks/WP types — so the comparison
    uses their union (22 values on 11.3.0, ten wider than the CLI's twelve).
    """
    return _package_set("CANONICAL_LIFECYCLE_EVENT_TYPES") | _package_set("MISSION_EVENT_TYPES")


@pytest.mark.parametrize("name", LIFECYCLE_CONSTANT_NAMES)
def test_cli_lifecycle_constant_matches_the_package(name: str) -> None:
    """Each CLI constant still carries the value the package publishes for that name."""
    cli_value = getattr(lifecycle, name)
    package_value = _package_value(name)
    assert cli_value == package_value, (
        f"{name}: the CLI emits {cli_value!r} but spec_kitty_events publishes {package_value!r}. The local copy drifted from the package."
    )


def test_lifecycle_event_types_is_exactly_the_twelve() -> None:
    """``LIFECYCLE_EVENT_TYPES`` is exactly the CLI's twelve values, no more, no less."""
    expected = {_package_value(name) for name in LIFECYCLE_CONSTANT_NAMES}
    actual = set(lifecycle.LIFECYCLE_EVENT_TYPES)
    # Keep twelve distinct values even if imported package names alias one another.
    assert len(actual) == len(LIFECYCLE_CONSTANT_NAMES), (
        f"LIFECYCLE_EVENT_TYPES has {len(actual)} members, expected {len(LIFECYCLE_CONSTANT_NAMES)}: {sorted(actual)}"
    )
    assert actual == expected, f"LIFECYCLE_EVENT_TYPES drifted from the CLI's twelve; missing {sorted(expected - actual)}, unexpected {sorted(actual - expected)}"


def test_cli_vocabulary_is_deliberately_narrower_than_the_package() -> None:
    """The CLI's set is a strict subset of the package's wide vocabulary, by design.

    A package release that adds a lifecycle type the CLI does not emit must stay green:
    the assertion is subset + strictness, never an exact difference set. A package
    release that *narrows* below the CLI's twelve is a red here, which is the signal to
    take a decision rather than to widen the CLI silently. Equality with the CLI's set
    also fails: revisit the deliberately-narrower premise, not the CLI's behavior.
    """
    cli_vocabulary = set(lifecycle.LIFECYCLE_EVENT_TYPES)
    wide_vocabulary = _wide_vocabulary()
    assert cli_vocabulary < wide_vocabulary, (
        f"the CLI lifecycle vocabulary is not a strict subset of the package's (outside it: {sorted(cli_vocabulary - wide_vocabulary)})"
    )


def test_a_symbol_the_package_no_longer_exports_fails_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """A renamed or dropped package symbol is a named failure, not an ``AttributeError``.

    FR-004: when a future ``spec-kitty-events`` release stops exporting one of the pinned
    names, the parity case must say which symbol is missing. Exercised through the public
    parametrized entry point so the assertion the suite would report is the one checked.
    """
    monkeypatch.delattr(spec_kitty_events, "TASKS_STARTED", raising=True)
    with pytest.raises(pytest.fail.Exception, match="TASKS_STARTED"):
        test_cli_lifecycle_constant_matches_the_package("TASKS_STARTED")
