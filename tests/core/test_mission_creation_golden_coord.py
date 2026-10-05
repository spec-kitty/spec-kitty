"""Golden cells, behaviour family 3: coordination-routed create on an unprotected target.

Golden behaviour matrix: regenerate only for an intended behaviour change
(``SPEC_KITTY_REGEN_GOLDEN=1``, serial); see ``tests/core/_mission_create_golden.py``.
Zero patches. Every cell runs ``create_mission_core`` on a real repository whose
write checkout sits on the unprotected branch ``topic``. The capture shows the
coordination branch, the coordination worktree, and the status log living in
the coordination worktree and not in the target checkout (the #5440
invariant).

Cell ids (11):

* ``<topology>/<variant>`` for topology in {``coord``, ``lanes_with_coord``}
  and variant in {``plain``, ``pr_bound``, ``retention``, ``documentation``,
  ``summary``} (10 cells).
* ``coord/force_recreate``: ``force_recreate_coordination_branch=True`` on a
  fresh mission.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import create_mission_core
from tests.core._mission_create_golden import (
    FLAG_VARIANTS,
    SUMMARY_VARIANT,
    assert_golden,
    build_repo,
    run_cell,
    variant_kwargs,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FAMILY = "coord"
_COORD = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)


@pytest.mark.parametrize("topology", _COORD, ids=lambda t: t.value)
@pytest.mark.parametrize("variant", [*FLAG_VARIANTS, SUMMARY_VARIANT])
def test_coord_create(tmp_path: Path, topology: MissionTopology, variant: str) -> None:
    slug = f"coord-{topology.value.replace('_', '-')}-{variant.replace('_', '-')}"
    kwargs = variant_kwargs(slug, variant)
    repo = build_repo(tmp_path)
    observed = run_cell(
        repo,
        tmp_path,
        lambda: create_mission_core(repo, slug, topology=topology, allow_worktree_context=True, **kwargs),
        slugs=[slug],
    )
    assert_golden(_FAMILY, f"{topology.value}/{variant}", observed)


def test_coord_force_recreate(tmp_path: Path) -> None:
    slug = "coord-force-recreate"
    repo = build_repo(tmp_path)
    observed = run_cell(
        repo,
        tmp_path,
        lambda: create_mission_core(
            repo,
            slug,
            topology=MissionTopology.COORD,
            force_recreate_coordination_branch=True,
            allow_worktree_context=True,
        ),
        slugs=[slug],
    )
    assert_golden(_FAMILY, "coord/force_recreate", observed)
