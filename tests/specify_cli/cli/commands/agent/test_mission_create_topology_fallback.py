"""Decision-level pin of the create-time topology fallback (follow-up #5707).

The existing ``_resolve_default_topology_phase`` and ``coord_topology_reachable``
are called on REAL repositories, never copies and never with patches.

The divergence #5707 tracks: with no ``origin/HEAD`` ``resolve_primary_branch(repo)``
(``bias=True``: the checked-out branch wins) and ``resolve_primary_branch(repo,
bias=False)`` (the TRUE primary: ``main``) disagree on a non-common branch. Before
S7 (#7282) the create-time topology default read the biased one and resolved
``coord``; it now reads neither (no ``--topology`` is always a provisional
``single_branch``), so this file pins the resolver fact and the new default.

Change it only for an intended behaviour change.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent.mission_create import _resolve_default_topology_phase
from specify_cli.coordination.surface_authority import coord_topology_reachable
from specify_cli.core.git_ops import resolve_primary_branch
from specify_cli.meta_keys import TopologySource
from tests._factories import provision_test_charter
from tests._support.git_template import clone_template

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TOPIC = "feat-x"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _repo_without_origin_head(tmp_path: Path) -> Path:
    """Real repo standing on ``feat-x``, ``main`` present, no remote at all."""
    repo = clone_template(tmp_path / "repo")
    provision_test_charter(repo)
    _git(repo, "add", ".kittify")
    _git(repo, "commit", "-m", "chore(fixture): provision charter")
    _git(repo, "remote", "remove", "origin")
    _git(repo, "checkout", "-b", _TOPIC)
    return repo


def test_no_origin_head_primary_resolutions_still_diverge(tmp_path: Path) -> None:
    """The two Primary Branch inputs still disagree on a non-common branch (#5707).

    The create-time topology default no longer reads either (S7 #7282: no
    ``--topology`` always yields a provisional ``single_branch``), so the
    divergence no longer changes the default; this pins the resolver fact alone.
    """
    repo = _repo_without_origin_head(tmp_path)

    assert resolve_primary_branch(repo) == _TOPIC
    assert resolve_primary_branch(repo, bias=False) == "main"


def test_no_origin_head_default_is_provisional_single_branch(tmp_path: Path) -> None:
    _repo_without_origin_head(tmp_path)

    assert _resolve_default_topology_phase(explicit_topology=None) == (MissionTopology.SINGLE_BRANCH, TopologySource.DEFAULT)
    assert _resolve_default_topology_phase(explicit_topology=MissionTopology.LANES) == (MissionTopology.LANES, TopologySource.EXPLICIT)


@pytest.mark.parametrize(
    ("pr_bound", "primary_protected", "current_is_primary", "expected"),
    [
        (False, False, False, False),
        (False, False, True, False),
        (False, True, False, False),
        (False, True, True, False),
        (True, False, False, False),
        (True, False, True, True),
        (True, True, False, True),
        (True, True, True, True),
    ],
)
def test_coord_topology_reachable_truth_table(pr_bound: bool, primary_protected: bool, current_is_primary: bool, expected: bool) -> None:
    assert coord_topology_reachable(pr_bound, primary_protected, current_is_primary) is expected
