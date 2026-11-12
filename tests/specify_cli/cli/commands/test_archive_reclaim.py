"""``spec-kitty archive reclaim`` releases an archived Mission's coordination triple (#4041).

Operator ruling (Decision ``01M78G5TMBJWFRE1ZPVSS2ATKN``): a new ``archive reclaim <mission>``
removes the coordination worktree, deletes the coordination branch once its content is proved
on the target, and flattens the ``coordination_branch`` marker with a commit. It refuses
(exit 1, a named code, nothing changed) a Mission that is not archived, one that never had a
coordination topology, a dirty coordination worktree, and a coordination branch whose content
is not on the target. A second run says nothing is left and exits 0.

Every cell drives the REAL CLI (``python -m specify_cli``) against a real git repository built by
the terminus harness: a coordination Mission consolidated with its triple retained
(``--keep-branch --keep-worktree``), whose coordination branch the target then merged with a real
merge, so the branch's content is on the target.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.terminus.conftest import CoordMission, _init_fixture_repo, build_coord_mission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_DONE_CHAIN: tuple[tuple[Lane, Lane], ...] = (
    (Lane.PLANNED, Lane.CLAIMED),
    (Lane.CLAIMED, Lane.IN_PROGRESS),
    (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
    (Lane.FOR_REVIEW, Lane.IN_REVIEW),
    (Lane.IN_REVIEW, Lane.APPROVED),
    (Lane.APPROVED, Lane.DONE),
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _coord_worktree(mission: CoordMission) -> Path:
    return mission.repo / ".worktrees" / f"{mission.slug}-coord"


def _branch_exists(mission: CoordMission, branch: str) -> bool:
    probe = subprocess.run(
        ["git", "-C", str(mission.repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


def _worktree_registered(mission: CoordMission) -> bool:
    listing = _git(mission.repo, "worktree", "list", "--porcelain")
    return f"worktree {_coord_worktree(mission).resolve()}" in listing


def _meta_bytes(mission: CoordMission) -> bytes:
    return (mission.feature_dir / "meta.json").read_bytes()


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _reclaim(mission: CoordMission, *extra: str) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["archive", "reclaim", mission.slug, *extra])


def _archive(mission: CoordMission, slug: str | None = None) -> subprocess.CompletedProcess[str]:
    archived = run_terminus(mission, ["archive", "create", slug or mission.slug, "--by", "t", "--reason", "done"])
    assert archived.returncode == 0, f"fixture invalid: archive create failed.\n{_output(archived)}"
    return archived


def _landed_coord_mission(tmp_path: Path, mid8: str) -> CoordMission:
    """A coordination Mission whose consolidation landed and retained the coordination triple.

    The target then merges the coordination branch with a real merge (``-s ours``: the content is
    already on the target), so the coordination tip is an ancestor of the target.
    """
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8=mid8)
    landed = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", "--keep-branch", "--keep-worktree"])
    assert landed.returncode == 0, f"fixture invalid: consolidate failed.\n{_output(landed)}"
    assert _branch_exists(mission, mission.coord_branch), "fixture invalid: the retained coordination branch must exist"
    assert _worktree_registered(mission), "fixture invalid: the retained coordination worktree must be registered"
    _git(mission.repo, "merge", "-q", "-s", "ours", "--no-edit", mission.coord_branch)
    return mission


@pytest.fixture
def archived_mission(tmp_path: Path) -> CoordMission:
    mission = _landed_coord_mission(tmp_path, "01M4041A")
    _archive(mission)
    return mission


def _assert_triple_kept(mission: CoordMission, meta_before: bytes) -> None:
    assert _branch_exists(mission, mission.coord_branch), "a refusal must keep the coordination branch"
    assert _worktree_registered(mission), "a refusal must keep the coordination worktree"
    assert _meta_bytes(mission) == meta_before, "a refusal must not touch meta.json"


def test_reclaim_removes_the_coordination_triple_of_an_archived_landed_mission(archived_mission: CoordMission) -> None:
    mission = archived_mission
    target_before = mission.rev(mission.target_branch)

    result = _reclaim(mission)

    assert result.returncode == 0, _output(result)
    assert not _worktree_registered(mission), _output(result)
    assert not _branch_exists(mission, mission.coord_branch), _output(result)
    meta = json.loads(_meta_bytes(mission))
    assert "coordination_branch" not in meta
    assert meta.get("flattened") is True
    assert mission.rev(mission.target_branch) != target_before, "the flattened marker must be committed"
    committed = json.loads(_git(mission.repo, "show", f"{mission.target_branch}:kitty-specs/{mission.slug}/meta.json"))
    assert "coordination_branch" not in committed
    for step in ("worktree", "branch", "marker"):
        assert step in result.stdout.lower(), _output(result)


def test_reclaim_twice_reports_nothing_left(archived_mission: CoordMission) -> None:
    first = _reclaim(archived_mission)
    assert first.returncode == 0, _output(first)

    second = _reclaim(archived_mission)

    assert second.returncode == 0, _output(second)
    assert "nothing" in second.stdout.lower(), _output(second)


def test_reclaim_finishes_when_the_worktree_is_already_gone(archived_mission: CoordMission) -> None:
    mission = archived_mission
    _git(mission.repo, "worktree", "remove", str(_coord_worktree(mission)))

    result = _reclaim(mission)

    assert result.returncode == 0, _output(result)
    assert not _branch_exists(mission, mission.coord_branch), _output(result)
    assert "coordination_branch" not in json.loads(_meta_bytes(mission))


def test_reclaim_refuses_a_mission_that_is_not_archived(tmp_path: Path) -> None:
    mission = _landed_coord_mission(tmp_path, "01M4041B")
    meta_before = _meta_bytes(mission)

    result = _reclaim(mission)

    assert result.returncode == 1, _output(result)
    assert "RECLAIM_NOT_ARCHIVED" in result.stdout + result.stderr, _output(result)
    _assert_triple_kept(mission, meta_before)


def test_reclaim_refuses_a_dirty_coordination_worktree(archived_mission: CoordMission) -> None:
    mission = archived_mission
    (_coord_worktree(mission) / "kitty-specs" / mission.slug / "scratch.md").write_text("unsaved\n", encoding="utf-8")
    meta_before = _meta_bytes(mission)

    result = _reclaim(mission)

    assert result.returncode == 1, _output(result)
    _assert_triple_kept(mission, meta_before)


def test_reclaim_refuses_coordination_content_that_is_not_on_the_target(archived_mission: CoordMission) -> None:
    mission = archived_mission
    worktree = _coord_worktree(mission)
    late = worktree / "kitty-specs" / mission.slug / "late-note.md"
    late.write_text("recorded after the landing\n", encoding="utf-8")
    _git(worktree, "add", str(late.relative_to(worktree)))
    _git(worktree, "commit", "-qm", "chore: a record the target never received")
    meta_before = _meta_bytes(mission)

    result = _reclaim(mission)

    combined = result.stdout + result.stderr
    assert result.returncode == 1, _output(result)
    assert "RECLAIM_UNABSORBED" in combined, _output(result)
    assert mission.coord_branch in combined, _output(result)
    _assert_triple_kept(mission, meta_before)


def test_reclaim_refuses_a_mission_without_coordination_topology(tmp_path: Path) -> None:
    mission = _init_fixture_repo(tmp_path, mid8="01M4041S", slug="solo-01M4041S", target_branch="main")
    mission.feature_dir.mkdir(parents=True)
    meta = {
        "mission_slug": mission.slug,
        "mission_id": mission.mission_id,
        "mid8": mission.mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "topology": "single_branch",
    }
    (mission.feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for idx, (from_lane, to_lane) in enumerate(_DONE_CHAIN):
        seed_status_event(
            mission.feature_dir,
            StatusEvent(
                event_id=f"01M4041S{idx:018d}",
                mission_slug=mission.slug,
                mission_id=mission.mission_id,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-11-12T12:{idx:02d}:00+00:00",
                actor="operator",
                force=False,
                execution_mode="worktree",
            ),
        )
    _git(mission.repo, "add", "kitty-specs")
    _git(mission.repo, "commit", "-qm", "chore: a single_branch Mission")
    _archive(mission)
    meta_before = _meta_bytes(mission)

    result = _reclaim(mission)

    assert result.returncode == 1, _output(result)
    assert "RECLAIM_NO_COORDINATION" in result.stdout + result.stderr, _output(result)
    assert _meta_bytes(mission) == meta_before


def test_archive_create_points_at_reclaim_while_the_coordination_triple_remains(tmp_path: Path) -> None:
    mission = _landed_coord_mission(tmp_path, "01M4041C")

    archived = _archive(mission)

    assert f"spec-kitty archive reclaim {mission.slug}" in archived.stdout, _output(archived)
