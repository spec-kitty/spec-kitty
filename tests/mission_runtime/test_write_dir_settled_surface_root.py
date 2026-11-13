"""``write_dir(kind).surface_root`` names the checkout that holds ``write_dir(kind).path`` (#7546, FR-001).

After ``finalize-tasks`` settles a default Mission to ``lanes_with_coord``, the repository root
checkout is back on ``create_return_branch`` and the coordination worktree holds the topic
branch, so every declared-PRIMARY kind reads (and writes) its directory inside that worktree.
The seam must then report that worktree as the write checkout, not the repository root checkout
(data-model invariant 1: ``path`` lies inside ``surface_root``). A Mission settled to
``single_branch`` is the positive control: its write checkout stays the repository root checkout.
Both rows drive the real ``agent mission create`` core and the real ``finalize-tasks`` command.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    _quiet_status_fanout,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

# Re-export so pytest discovers the imported autouse fixture (chdir + silenced status fan-out).
__all__ = ["_quiet_status_fanout"]

_PRIMARY_KINDS = (
    MissionArtifactKind.SPEC,
    MissionArtifactKind.TASKS_INDEX,
    MissionArtifactKind.WORK_PACKAGE_TASK,
    MissionArtifactKind.PRIMARY_METADATA,
)


def _assert_write_checkout(root: Path, slug: str, expected_checkout: Path) -> None:
    seam = placement_seam(root, slug)
    for kind in _PRIMARY_KINDS:
        location = seam.write_dir(kind)
        assert location.path.resolve().is_relative_to(location.surface_root.resolve()), (kind, location)
        assert location.surface_root.resolve() == expected_checkout.resolve(), (kind, location)


def test_settled_default_mission_writes_in_the_coordination_worktree(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict) and decision["settled_topology"] == "lanes_with_coord"

    _assert_write_checkout(mission.root, mission.slug, mission.coord_mission_dir.parents[1])


def test_single_branch_mission_writes_in_the_repository_root_checkout(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, ("src/one.py", "src/two.py"))
    code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict) and decision["settled_topology"] == "single_branch"

    _assert_write_checkout(mission.root, mission.slug, mission.root)


# ---------------------------------------------------------------------------
# ``_containing_checkout``: the spelling of ``surface_root`` (anchored under ``path``)
# ---------------------------------------------------------------------------


def _checkout(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    return root


@pytest.mark.unit
def test_containing_checkout_answers_the_nearest_checkout(tmp_path: Path) -> None:
    from mission_runtime.resolution import _containing_checkout

    root = _checkout(tmp_path / "repo")
    worktree = root / ".worktrees" / "probe-coord"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    assert _containing_checkout(root / "kitty-specs" / "probe", root) == root.resolve()
    assert _containing_checkout(worktree / "kitty-specs" / "probe", root) == worktree.resolve()


@pytest.mark.unit
def test_containing_checkout_keeps_a_symlinked_spelling_of_path(tmp_path: Path) -> None:
    from mission_runtime.resolution import _containing_checkout

    real = _checkout(tmp_path / "real" / "repo")
    alias = tmp_path / "alias"
    alias.symlink_to(real.parent, target_is_directory=True)
    path = alias / "repo" / "kitty-specs" / "probe"
    surface_root = _containing_checkout(path, real)
    assert surface_root == alias / "repo"
    assert path.is_relative_to(surface_root)


@pytest.mark.unit
def test_containing_checkout_answers_resolved_when_the_link_hides_the_checkout(tmp_path: Path) -> None:
    from mission_runtime.resolution import _containing_checkout

    real = _checkout(tmp_path / "real" / "repo")
    (real / "kitty-specs").mkdir()
    link = tmp_path / "specs-link"
    link.symlink_to(real / "kitty-specs", target_is_directory=True)
    assert _containing_checkout(link / "probe", real) == real.resolve()
    assert _containing_checkout(link, real) == real.resolve()


@pytest.mark.unit
def test_containing_checkout_falls_back_to_the_main_repo_root_outside_every_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mission_runtime import resolution

    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.resolve()))
    fallback = tmp_path / "main-root"
    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", lambda _root: fallback)
    assert resolution._containing_checkout(tmp_path / "elsewhere" / "kitty-specs", tmp_path) == fallback


@pytest.mark.unit
def test_containing_checkout_answers_the_walk_when_path_cannot_be_resolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A symbolic-link loop cannot be resolved: the walk's own answer stands."""
    from kernel import git_anchor
    from mission_runtime import resolution

    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    holder = tmp_path / "elsewhere"
    monkeypatch.setattr(git_anchor, "checkout_root_containing", lambda _path: holder)

    assert resolution._containing_checkout(loop / "kitty-specs", tmp_path) == holder


@pytest.mark.unit
def test_containing_checkout_answers_resolved_when_path_is_shallower_than_its_depth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A relative spelling with fewer parts than its depth under the checkout has no lexical ancestor to name."""
    from mission_runtime.resolution import _containing_checkout

    real = _checkout(tmp_path / "real" / "repo")
    (real / "kitty-specs" / "probe").mkdir(parents=True)
    (tmp_path / "probe-link").symlink_to(real / "kitty-specs" / "probe", target_is_directory=True)
    monkeypatch.chdir(tmp_path)

    assert _containing_checkout(Path("probe-link"), real) == real.resolve()


@pytest.mark.unit
def test_containing_checkout_keeps_a_link_that_names_the_checkout_itself(tmp_path: Path) -> None:
    """A link spelling the checkout itself (depth 0) is its own surface root."""
    from mission_runtime.resolution import _containing_checkout

    real = _checkout(tmp_path / "real" / "repo")
    alias = tmp_path / "repo-alias"
    alias.symlink_to(real, target_is_directory=True)

    assert _containing_checkout(alias, real) == alias
