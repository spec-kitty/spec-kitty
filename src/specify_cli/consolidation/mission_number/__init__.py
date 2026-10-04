"""Canonical definition of "assigned" for a mission's ``mission_number`` (#4900).

Leaf module (standard library only): no ``specify_cli`` or third-party
imports, so it can be imported both by :mod:`specify_cli.consolidation.drivers`
(which must not pull in :mod:`specify_cli.consolidation.ordering`, per that
module's own import-boundary contract) and by ``ordering.py`` /
``cli/commands/agent/mission_check_prerequisites.py`` without risking a cycle.

Before this module existed, two definitions of "assigned" disagreed:
``ordering._is_assigned_mission_number`` treated 0 and negative integers as
assigned, while ``mission_check_prerequisites._is_assigned_mission_number``
(correctly) required a positive integer, matching
``kitty-specs/exit-zero-data-intact-01M3KDAS/data-model.md`` ("Mission
number" -- "assigned" means an integer >= 1). Both now delegate here; this is
the single source of truth (#4900).
"""

from __future__ import annotations

__all__ = ["is_assigned_mission_number"]


def is_assigned_mission_number(value: object) -> bool:
    """Return True only for a real, positive (``>= 1``) integer ``mission_number``.

    ``bool`` is excluded even though it is an ``int`` subclass in Python.
    ``None``, a missing field, a non-integer value, ``0`` and negative
    integers are all "unassigned".
    """
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1
