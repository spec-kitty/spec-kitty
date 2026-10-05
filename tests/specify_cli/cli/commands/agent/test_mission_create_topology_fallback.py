"""Decision-level pin of the create-time topology fallback (follow-up #5707).

The existing ``_resolve_default_topology_phase`` and ``coord_topology_reachable``
are called on REAL repositories, never copies and never with patches.

The divergence #5707 tracks: with no ``origin/HEAD`` the topology default asks
``resolve_primary_branch(repo)`` (``bias=True``: the checked-out branch wins),
while protection/placement code asks ``resolve_primary_branch(repo, bias=False)``
(the TRUE primary: ``main``).  On a non-common branch the two disagree, so the
default resolves ``coord`` where the true primary would say ``lanes``.  When
#5707 changes this deliberately, this file is the pin that has to be updated.

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


def test_no_origin_head_topology_default_uses_the_checked_out_branch_as_primary(tmp_path: Path) -> None:
    repo = _repo_without_origin_head(tmp_path)

    primary_for_topology_default = resolve_primary_branch(repo)
    primary_for_protection = resolve_primary_branch(repo, bias=False)

    # The two Primary Branch inputs disagree on a non-common branch (#5707).
    assert primary_for_topology_default == _TOPIC
    assert primary_for_protection == "main"
    assert primary_for_topology_default != primary_for_protection

    resolved = _resolve_default_topology_phase(explicit_topology=None, repo_root=repo, current_branch=_TOPIC, pr_bound=False)

    # Observed today: COORD (the CLAUDE.md "Create-time topology" caveat), because
    # current == bias=True primary.  The true primary would make this a non-primary
    # branch, i.e. LANES.
    assert resolved is MissionTopology.COORD
    assert (primary_for_topology_default == _TOPIC) is True
    assert (primary_for_protection == _TOPIC) is False


def test_no_origin_head_pr_bound_arm_reaches_coord_via_current_is_primary(tmp_path: Path) -> None:
    repo = _repo_without_origin_head(tmp_path)
    primary_for_topology_default = resolve_primary_branch(repo)
    current_is_primary = primary_for_topology_default == _TOPIC

    resolved = _resolve_default_topology_phase(explicit_topology=None, repo_root=repo, current_branch=_TOPIC, pr_bound=True)

    # Feature-branch bias makes the current branch "primary" even though ``main`` is
    # the true primary; the same predicate on the same inputs agrees with the phase.
    assert current_is_primary is True
    assert coord_topology_reachable(True, False, current_is_primary) is True
    assert resolved is MissionTopology.COORD


def test_no_origin_head_explicit_topology_and_missing_context_short_circuit(tmp_path: Path) -> None:
    repo = _repo_without_origin_head(tmp_path)

    assert _resolve_default_topology_phase(explicit_topology=MissionTopology.LANES, repo_root=repo, current_branch=_TOPIC, pr_bound=False) is MissionTopology.LANES
    assert _resolve_default_topology_phase(explicit_topology=None, repo_root=None, current_branch=_TOPIC, pr_bound=False) is MissionTopology.COORD
    assert _resolve_default_topology_phase(explicit_topology=None, repo_root=repo, current_branch=None, pr_bound=False) is MissionTopology.COORD


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
