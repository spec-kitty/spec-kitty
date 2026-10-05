"""Stale-lane rules for primary-owned and content-identical overlaps (#5457, WP03).

``check_lane_staleness`` is what ``consolidate`` calls before folding a lane
into the mission branch. A pre-fix ``spec-kitty upgrade`` commits a different
``.kittify/metadata.yaml`` and the identical ``.gitattributes`` line on every
branch, so both paths overlap although neither is semantic lane work.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane
from specify_cli.lanes.stale_check import StaleCheckResult, _stale_remediation, check_lane_staleness
from tests.integration.primary_owned_fixtures import (
    LanesProject,
    build_older_version_lanes_project,
    commit_broken_upgrade_state,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _lane(lane_id: str, wp_id: str) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=(wp_id,),
        write_scope=("src/**",),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


@pytest.fixture
def broken_project(tmp_path: Path) -> LanesProject:
    """Two lanes; lane-b and the mission branch carry the pre-fix upgrade commit."""
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=2)
    commit_broken_upgrade_state(project, branches=[project.lane_branches["lane-b"], project.mission_branch])
    return project


def test_upgrade_overlap_is_not_stale(broken_project: LanesProject) -> None:
    """Path A (grounding Appendix A): metadata differs, .gitattributes is identical."""
    project = broken_project
    result = check_lane_staleness(
        _lane("lane-b", project.lane_wps["lane-b"]),
        project.lane_branches["lane-b"],
        project.mission_branch,
        project.repo,
    )
    assert result.is_stale is False
    assert result.stale_files == []
    assert result.remediation is None


# ---------------------------------------------------------------------------
# Unit level: direct-git fixtures for the two rules.
# ---------------------------------------------------------------------------

_MISSION = "kitty/mission-feat"
_LANE_BRANCH = "kitty/mission-feat-lane-a"
_GITATTRIBUTES_LINE = "kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


def _commit(repo: Path, branch: str, path: str, content: str | None, *, executable: bool = False) -> None:
    """Commit ``content`` at ``path`` on ``branch`` (``None`` deletes the file)."""
    _git(repo, "checkout", "-q", branch)
    target = repo / path
    if content is None:
        _git(repo, "rm", "-q", path)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        _git(repo, "add", path)
        if executable:
            _git(repo, "update-index", "--chmod=+x", path)
    _git(repo, "commit", "-q", "-m", f"{branch}: {path}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@test.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("init\n")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "init")
    (root / "src").mkdir()
    (root / "src" / "shared.py").write_text("base\n")
    _git(root, "add", "src/shared.py")
    _git(root, "commit", "-q", "-m", "shared")
    _git(root, "branch", _MISSION)
    _git(root, "branch", _LANE_BRANCH)
    return root


def _staleness(repo: Path) -> StaleCheckResult:
    return check_lane_staleness(_lane("lane-a", "WP01"), _LANE_BRANCH, _MISSION, repo)


def test_only_primary_owned_overlap_is_not_stale(repo: Path) -> None:
    _commit(repo, _MISSION, ".kittify/metadata.yaml", "mission\n")
    _commit(repo, _LANE_BRANCH, ".kittify/metadata.yaml", "lane\n")

    result = _staleness(repo)

    assert (result.is_stale, result.stale_files, result.remediation) == (False, [], None)


def test_primary_owned_overlap_is_dropped_but_real_overlap_is_kept(repo: Path) -> None:
    _commit(repo, _MISSION, ".kittify/metadata.yaml", "mission\n")
    _commit(repo, _MISSION, "src/shared.py", "mission\n")
    _commit(repo, _LANE_BRANCH, ".kittify/metadata.yaml", "lane\n")
    _commit(repo, _LANE_BRANCH, "src/shared.py", "lane\n")

    result = _staleness(repo)

    assert result.is_stale is True
    assert result.stale_files == ["src/shared.py"]
    assert result.remediation == _stale_remediation(_lane("lane-a", "WP01"), _LANE_BRANCH, _MISSION)


def test_identical_addition_is_not_stale(repo: Path) -> None:
    _commit(repo, _MISSION, "docs/notes.md", "same\n")
    _commit(repo, _LANE_BRANCH, "docs/notes.md", "same\n")

    assert _staleness(repo).is_stale is False


def test_different_content_is_stale(repo: Path) -> None:
    _commit(repo, _MISSION, "docs/notes.md", "mission\n")
    _commit(repo, _LANE_BRANCH, "docs/notes.md", "lane\n")

    result = _staleness(repo)

    assert result.is_stale is True
    assert result.stale_files == ["docs/notes.md"]


def test_same_content_with_mode_change_is_stale(repo: Path) -> None:
    _commit(repo, _MISSION, "bin/run.sh", "echo hi\n")
    _commit(repo, _LANE_BRANCH, "bin/run.sh", "echo hi\n", executable=True)

    result = _staleness(repo)

    assert result.is_stale is True
    assert result.stale_files == ["bin/run.sh"]


def test_deletion_against_modification_is_stale(repo: Path) -> None:
    _commit(repo, _MISSION, "src/shared.py", None)
    _commit(repo, _LANE_BRANCH, "src/shared.py", "changed\n")

    result = _staleness(repo)

    assert result.is_stale is True
    assert result.stale_files == ["src/shared.py"]


def test_identical_deletion_is_not_stale(repo: Path) -> None:
    _commit(repo, _MISSION, "src/shared.py", None)
    _commit(repo, _LANE_BRANCH, "src/shared.py", None)

    assert _staleness(repo).is_stale is False


def test_identical_and_different_overlaps_are_split_in_sorted_order(repo: Path) -> None:
    _commit(repo, _MISSION, ".gitattributes", _GITATTRIBUTES_LINE)
    _commit(repo, _MISSION, "src/shared.py", "mission\n")
    _commit(repo, _LANE_BRANCH, ".gitattributes", _GITATTRIBUTES_LINE)
    _commit(repo, _LANE_BRANCH, "src/shared.py", "lane\n")

    assert _staleness(repo).stale_files == ["src/shared.py"]


def test_probe_failure_keeps_the_path_stale(repo: Path) -> None:
    from specify_cli.lanes.stale_check import _filter_benign_overlaps

    kept = _filter_benign_overlaps(["docs/notes.md"], "no-such-lane-ref", _MISSION, repo)

    assert kept == ["docs/notes.md"]
