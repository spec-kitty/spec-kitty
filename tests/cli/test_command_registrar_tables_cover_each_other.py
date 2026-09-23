"""PR-CONTRACT-002: ``_COMMAND_REGISTRARS`` and ``_ALL_COMMAND_REGISTRARS``
must stay in sync.

``register_commands()`` maintains two hand-written parallel collections:
``_COMMAND_REGISTRARS`` (dict, the lazy single-leaf-command path) and
``_ALL_COMMAND_REGISTRARS`` (tuple, the eager fallback / ``--help`` / unknown-
command listing). Nothing previously enforced that every registrar reachable
through one table is also reachable through the other -- a future one-sided
edit could silently desync single-leaf-reachable commands from ``--help``/
did-you-mean listings, or vice versa.
"""

from __future__ import annotations

from specify_cli.cli.commands import _ALL_COMMAND_REGISTRARS, _COMMAND_REGISTRARS


def test_every_command_registrar_is_reachable_from_both_tables() -> None:
    lazy_registrars = set(_COMMAND_REGISTRARS.values())
    eager_registrars = set(_ALL_COMMAND_REGISTRARS)

    assert lazy_registrars == eager_registrars, (
        "_COMMAND_REGISTRARS (lazy single-leaf lookup) and "
        "_ALL_COMMAND_REGISTRARS (eager fallback) have desynced -- "
        f"only in _COMMAND_REGISTRARS: {sorted(r.__name__ for r in lazy_registrars - eager_registrars)}; "
        f"only in _ALL_COMMAND_REGISTRARS: {sorted(r.__name__ for r in eager_registrars - lazy_registrars)}"
    )


def test_all_command_registrars_has_no_duplicate_entries() -> None:
    """``_ALL_COMMAND_REGISTRARS`` is documented as listing each registrar
    "exactly once" for the eager fallback -- a duplicate would double-register
    the same module's commands."""
    assert len(_ALL_COMMAND_REGISTRARS) == len(set(_ALL_COMMAND_REGISTRARS))
