"""Pytest fixtures over the shared coordination-Mission factory (WP02, FR-016).

Thin wrappers around ``tests._factories.coord_mission`` -- the importable
module other test directories use directly. These fixtures exist for
ergonomics inside ``tests/coordination/`` test modules that prefer
``pytest.fixture`` injection to calling the factory functions by hand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from tests._factories.coord_mission import (
    COORD_TOPOLOGIES,
    CoordMission,
    ForkFixture,
    make_coord_mission,
    make_fork_fixture,
    make_prefix_coord_mission,
)

__all__ = ["coord_mission", "fork_fixture", "prefix_coord_mission"]


@pytest.fixture(params=COORD_TOPOLOGIES, ids=lambda topology: topology.value)
def coord_mission(tmp_path: Path, request: pytest.FixtureRequest) -> CoordMission:
    """A production-created coordination-routed Mission, over both topologies."""
    topology: MissionTopology = request.param
    return make_coord_mission(tmp_path, topology)


@pytest.fixture
def prefix_coord_mission(tmp_path: Path, request: pytest.FixtureRequest) -> CoordMission:
    """The pre-fix shape, defaulting to an EMPTY coordination worktree.

    Indirect-parametrize with a kwargs dict to override any
    ``make_prefix_coord_mission`` argument (including ``topology``)::

        @pytest.mark.parametrize(
            "prefix_coord_mission", [{"worktree": "absent"}], indirect=True
        )
    """
    overrides: dict[str, Any] = dict(getattr(request, "param", {}))
    topology = overrides.pop("topology", MissionTopology.COORD)
    return make_prefix_coord_mission(tmp_path, topology, **overrides)


@pytest.fixture
def fork_fixture(tmp_path: Path, request: pytest.FixtureRequest) -> ForkFixture:
    """A NFR-002 fork fixture.

    Indirect-parametrize with the desired shape string::

        @pytest.mark.parametrize("fork_fixture", ["both_committed"], indirect=True)

    Or with a kwargs dict (``shape`` required) to also select the diverging
    stream (H2) and/or topology::

        @pytest.mark.parametrize(
            "fork_fixture",
            [{"shape": "both_committed", "stream": "decision_log"}],
            indirect=True,
        )
    """
    param = request.param
    overrides: dict[str, Any] = {"shape": param} if isinstance(param, str) else dict(param)
    overrides.setdefault("stream", "status_log")
    overrides.setdefault("topology", MissionTopology.COORD)
    return make_fork_fixture(tmp_path, **overrides)
