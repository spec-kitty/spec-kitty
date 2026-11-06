"""#5676: switching the write checkout onto a minted branch must respect occupancy and dirt.

Before the fix, ``agent mission create`` on a protected target switched the repository
root checkout onto the new Mission's branch while another ``single_branch`` Mission had a
work package ``in_progress`` there; the implementer's next commit then landed on the new
Mission's branch. The create's only pre-switch check was "dirty outside this scaffold",
and it carried no error code.

The extracted switch core
(:func:`specify_cli.core.write_checkout_switch.switch_write_checkout`) refuses
``WRITE_CHECKOUT_OCCUPIED`` and ``WRITE_CHECKOUT_DIRTY`` before any git write, and the
create path reaches the same refusals. Each refusal is paired with an accepting control.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import MissionCreationError
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from tests.git.protected_target_fixtures import build_protected_target_repo
from tests.utils import write_wp

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_OCCUPANT = "occupant-01OCCUPA"
_OCCUPANT_ID = "01OCCUPANT0000000000000000"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _seed_occupant(repo: Path, lane: str) -> None:
    """A committed ``single_branch`` Mission targeting ``main`` with WP01 in *lane* in the repo-root lane."""
    feature_dir = repo / "kitty-specs" / _OCCUPANT
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _OCCUPANT_ID,
                "mission_slug": _OCCUPANT,
                "slug": _OCCUPANT,
                "mid8": _OCCUPANT_ID[:8],
                "mission_type": "software-dev",
                "friendly_name": "occupant",
                "target_branch": "main",
                "topology": "single_branch",
                "created_at": "2026-11-06T00:00:00+00:00",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_OCCUPANT,
            mission_id=None,
            mission_branch="main",
            target_branch="main",
            lanes=[ExecutionLane(lane_id=PLANNING_LANE_ID, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
            computed_at="2026-11-06T00:00:00+00:00",
            computed_from="test",
        ),
    )
    write_wp(repo, _OCCUPANT, lane, "WP01")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "occupant mission")


def _repo(tmp_path: Path, *, occupant_lane: str | None = None) -> Path:
    repo = build_protected_target_repo(tmp_path).repo_root
    if occupant_lane is not None:
        _seed_occupant(repo, occupant_lane)
    return repo


def _switch(repo: Path, branch: str) -> None:
    from specify_cli.core.write_checkout_switch import switch_write_checkout

    switch_write_checkout(repo, branch, start_point="main", repository_root=repo, owned_paths=(".kittify",))


def test_occupied_write_checkout_refuses_switch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, occupant_lane="in_progress")

    with pytest.raises(MissionCreationError, match="WRITE_CHECKOUT_OCCUPIED") as excinfo:
        _switch(repo, "kitty/mission-new-01NEWNEW")

    assert excinfo.value.error_code == "WRITE_CHECKOUT_OCCUPIED"
    assert f"{_OCCUPANT}/WP01" in str(excinfo.value)
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert "kitty/mission-new-01NEWNEW" not in _git(repo, "branch", "--list")


def test_unoccupied_write_checkout_switches(tmp_path: Path) -> None:
    """Control: the same Mission with WP01 only ``planned`` does not occupy the checkout."""
    repo = _repo(tmp_path, occupant_lane="planned")

    _switch(repo, "kitty/mission-new-01NEWNEW")

    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "kitty/mission-new-01NEWNEW"


def test_dirty_write_checkout_refuses_switch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "README.md").write_text("operator edit\n", encoding="utf-8")

    with pytest.raises(MissionCreationError, match="WRITE_CHECKOUT_DIRTY") as excinfo:
        _switch(repo, "kitty/mission-new-01NEWNEW")

    assert excinfo.value.error_code == "WRITE_CHECKOUT_DIRTY"
    assert "README.md" in str(excinfo.value)
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_switch_onto_an_existing_branch(tmp_path: Path) -> None:
    """With no start point the core checks out an existing branch (the settlement return path)."""
    from specify_cli.core.write_checkout_switch import switch_write_checkout

    repo = _repo(tmp_path)
    _git(repo, "branch", "back")

    switch_write_checkout(repo, "back", start_point=None, repository_root=repo, owned_paths=())

    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "back"


def test_protected_create_refuses_switch_while_occupied(tmp_path: Path) -> None:
    """The create path reaches the occupancy refusal (#5676 reproduction), and leaves HEAD alone."""
    from specify_cli.core.mission_creation import create_mission_core

    repo = _repo(tmp_path, occupant_lane="in_progress")

    with pytest.raises(MissionCreationError) as excinfo:
        create_mission_core(repo, "beta", topology=MissionTopology.SINGLE_BRANCH, allow_worktree_context=True)

    assert excinfo.value.error_code == "WRITE_CHECKOUT_OCCUPIED"
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_protected_create_refuses_switch_when_dirty_with_code(tmp_path: Path) -> None:
    from specify_cli.core.mission_creation import create_mission_core

    repo = _repo(tmp_path)
    (repo / "README.md").write_text("operator edit\n", encoding="utf-8")

    with pytest.raises(MissionCreationError) as excinfo:
        create_mission_core(repo, "beta", topology=MissionTopology.SINGLE_BRANCH, allow_worktree_context=True)

    assert excinfo.value.error_code == "WRITE_CHECKOUT_DIRTY"


def test_create_switches_through_the_one_switch_core(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B2: create's topic-branch mint goes through ``switch_write_checkout``, the one switch core."""
    from specify_cli.core import mission_creation_protected_mint as mint
    from specify_cli.core.mission_creation import create_mission_core

    calls: list[tuple[str, str | None, tuple[str, ...]]] = []
    real = mint.switch_write_checkout

    def spy(
        write_root: Path,
        branch_name: str,
        *,
        start_point: str | None,
        repository_root: Path,
        owned_paths: tuple[str, ...],
        decide: Callable[[tuple[str, ...]], None] | None = None,
    ) -> None:
        calls.append((branch_name, start_point, owned_paths))
        real(write_root, branch_name, start_point=start_point, repository_root=repository_root, owned_paths=owned_paths, decide=decide)

    monkeypatch.setattr(mint, "switch_write_checkout", spy)
    repo = _repo(tmp_path)

    result = create_mission_core(repo, "beta", topology=MissionTopology.SINGLE_BRANCH, allow_worktree_context=True)

    minted = result.meta["mission_branch"]
    assert calls == [(minted, "main", (".kittify", f"kitty-specs/{result.mission_slug}"))]
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == minted
