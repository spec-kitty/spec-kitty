"""Regression guard for #3926: the coord triple comes down in an order that works.

At merge time a coord-topology mission's coordination branch is *checked out*
in ``.worktrees/<slug>-coord``. ``git branch -D`` refuses to delete a branch in
that state (``cannot delete branch '...' used by worktree at '...'``), and the
executor ran ``check_return=False``, so the refusal was invisible: the marker
flatten ran anyway and the phase printed "Cleaned up mission/coordination
branch + worktree" over the git error. The reporter was left with a live coord
branch, a live coord worktree, a flattened ``meta.json`` that no longer
declares either — so ``doctor coordination`` could not see them — and a success
message.

That is #3131 INV-2's all-or-nothing invariant broken in the inverted #3086
direction, so these tests pin both halves of the fix:

1. the worktree is torn down FIRST, releasing the checkout, so the branch
   delete succeeds and the flatten follows a branch that is genuinely gone;
2. a leg that does not come down raises :class:`CoordinationTeardownError`
   instead of flattening the marker and reporting success.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.lanes.branch_naming import coord_dir_name
from specify_cli.merge import executor as ex
from specify_cli.merge.state import MergeState
from specify_cli.mission_metadata import load_meta

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01M1VRA2ZAP70V8DVJZ8XN0M3T"
_MID8 = _MISSION_ID[:8].lower()
_SLUG = f"coord-teardown-order-{_MID8}"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _branch_exists(repo: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
            cwd=repo,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def _meta_payload() -> str:
    return (
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mid8": _MID8,
                "mission_slug": _SLUG,
                "coordination_branch": _MISSION_BRANCH,
                "topology": "coord",
                "flattened": False,
            },
            indent=2,
        )
        + "\n"
    )


@pytest.fixture
def coord_repo_with_live_worktree(tmp_path: Path) -> Path:
    """A coord mission exactly as merge finds it: branch checked out in the coord worktree.

    This is the state the old ordering could not handle — and the fixture is
    the whole point of the regression, so the worktree is created for real
    rather than mocked.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Spec Kitty Test")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "seed")
    _git(repo, "branch", _MISSION_BRANCH)

    coord_path = repo / ".worktrees" / coord_dir_name(_SLUG, mid8=_MID8)
    _git(repo, "worktree", "add", str(coord_path), _MISSION_BRANCH)

    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(_meta_payload())
    return repo


def _run_state(repo: Path) -> ex._MergeRunState:
    feature_dir = repo / "kitty-specs" / _SLUG
    lanes_manifest = SimpleNamespace(
        target_branch="main",
        mission_branch=_MISSION_BRANCH,
        lanes=[],
    )
    return ex._MergeRunState(
        main_repo=repo,
        mission_slug=_SLUG,
        canonical_id=_MISSION_ID,
        canonical_mission_id=_MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=True,
        remove_worktree=True,
        teardown_coordination=True,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=MergeState(
            mission_id=_MISSION_ID,
            mission_slug=_SLUG,
            target_branch="main",
            wp_order=["WP01"],
        ),
        is_resume=False,
        baseline_mission_id=_MISSION_ID,
    )


def test_coord_branch_checked_out_in_its_worktree_is_still_fully_torn_down(
    coord_repo_with_live_worktree: Path,
) -> None:
    repo = coord_repo_with_live_worktree
    coord_path = repo / ".worktrees" / coord_dir_name(_SLUG, mid8=_MID8)

    # Fixture sanity: without a live checkout of the branch there is no bug to
    # reproduce, so a false-green here would be silent.
    assert coord_path.is_dir(), "fixture invalid: coord worktree must exist"
    assert _branch_exists(repo, _MISSION_BRANCH), "fixture invalid: coord branch must exist"

    ex._teardown_coordination_triple(_run_state(repo))

    assert not _branch_exists(repo, _MISSION_BRANCH), (
        "#3926: the coordination branch survived teardown — `git branch -D` was refused because the branch was still checked out in the coord worktree"
    )
    assert not coord_path.exists(), "#3926: the coordination worktree was stranded on disk"
    meta = load_meta(repo / "kitty-specs" / _SLUG)
    assert meta is not None
    assert "coordination_branch" not in meta, "the marker must be flattened once the branch is gone"


def test_a_leg_that_does_not_come_down_raises_instead_of_flattening(coord_repo_with_live_worktree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """INV-2 is all-or-nothing: no success line, and no half-flattened marker.

    The worktree teardown is stubbed out to model the real failure mode — its
    destroy leg is best-effort and swallows its own errors, so the branch can
    still be pinned when the delete runs.
    """
    repo = coord_repo_with_live_worktree
    monkeypatch.setattr(ex, "_teardown_coord_worktree", lambda run: None)

    with pytest.raises(ex.CoordinationTeardownError) as caught:
        ex._teardown_coordination_triple(_run_state(repo))

    assert _MISSION_BRANCH in str(caught.value)
    meta = load_meta(repo / "kitty-specs" / _SLUG)
    assert meta is not None
    assert meta.get("coordination_branch") == _MISSION_BRANCH, (
        "#3926: the marker was flattened while the branch and worktree both survived — the inverted #3086 shape INV-2 forbids"
    )
    assert _branch_exists(repo, _MISSION_BRANCH)
