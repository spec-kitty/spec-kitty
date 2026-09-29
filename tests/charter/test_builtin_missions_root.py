"""RED-first coverage for the promoted ``builtin_missions_root()`` accessor (#2668).

``MissionTypeProfileRepository._default_built_in_dir`` is a private classmethod
that two out-of-class call sites (``charter.activation.action_grain``,
``charter.activation.mission_type_profiles``) had to reach around ``# noqa: SLF001`` to
use. This test pins the public module-level replacement: it must resolve to
the same missions root the constructor already uses, so the promotion is a
byte-identical refactor (no behavior change).

Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` (FR-005)
relocated the missions data from ``src/charter/offering/missions`` to
``packs/built-in/missions`` and additionally converged
``builtin_missions_root()`` onto the FR-004 kernel sibling-path primitive (via
``MissionTemplateRepository.default_missions_root()``) rather than a path
computed relative to *this* module's own file -- so the two tests below no
longer assert a ``("doctrine", "missions")`` tail or a
``.parents[1] / "doctrine" / "missions"`` construction; they assert the actual
current contract instead.
"""

from __future__ import annotations

import pytest

from charter.activation.mission_type_profile_repository import builtin_missions_root
from charter.offering.missions.repository import MissionTemplateRepository

pytestmark = [pytest.mark.unit]


def test_builtin_missions_root_ends_with_built_in_missions() -> None:
    root = builtin_missions_root()

    assert root.parts[-2:] == ("built-in", "missions")


def test_builtin_missions_root_matches_module_relative_resolution() -> None:
    """The accessor is a thin delegate onto the one promoted authority.

    Not a second, independently-computed resolution -- see
    ``tests/charter/test_missions_root_authority.py`` for the full
    convergence regression this mirrors.
    """
    expected = MissionTemplateRepository.default_missions_root()

    assert builtin_missions_root() == expected
