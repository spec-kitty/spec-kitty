"""Unit tests for ``specify_cli.lanes.checkout_occupancy`` (#5100 WP04 T018).

``in_progress_wps_in_write_checkout`` and ``dirty_paths`` are the two pure(ish)
reads the repo-root-lane implement refusal path composes -- see
``contracts/single-branch-execution.md`` "Implement: refusals".
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.checkout_occupancy import (
    dirty_paths,
    in_progress_wps_in_write_checkout,
)
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from tests.utils import _seed_canonical_wp_state, write_wp

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_single_branch_meta(repo: Path, mission_slug: str, mission_id: str) -> None:
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "mid8": mission_id[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "main",
                "topology": "single_branch",
                "created_at": "2026-09-28T00:00:00+00:00",
                "friendly_name": mission_slug,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_lanes(repo: Path, mission_slug: str, lanes: dict[str, tuple[str, ...]]) -> None:
    """Write a ``lanes.json`` mapping each lane id to its WP ids."""
    manifest = LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=None,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=lane_id,
                wp_ids=wp_ids,
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
            for lane_id, wp_ids in lanes.items()
        ],
        computed_at="2026-09-28T00:00:00+00:00",
        computed_from="test",
    )
    write_lanes_json(repo / "kitty-specs" / mission_slug, manifest)


def _write_repo_root_lane(repo: Path, mission_slug: str, *wp_ids: str) -> None:
    """Assign *wp_ids* to the mission's repo-root (``lane-planning``) lane."""
    _write_lanes(repo, mission_slug, {PLANNING_LANE_ID: tuple(wp_ids)})


# ---------------------------------------------------------------------------
# in_progress_wps_in_write_checkout
# ---------------------------------------------------------------------------


def test_returns_empty_when_write_checkout_is_not_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    other = tmp_path / "elsewhere"
    other.mkdir()

    assert in_progress_wps_in_write_checkout(repo, other) == []


def test_returns_empty_with_no_missions(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    assert in_progress_wps_in_write_checkout(repo, repo) == []


def test_finds_in_progress_wp_of_a_single_branch_mission(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mission-a", "01OCCMISSIONA00000000000A")
    _write_repo_root_lane(repo, "occ-mission-a", "WP01")
    write_wp(repo, "occ-mission-a", "in_progress", "WP01")

    occupied = in_progress_wps_in_write_checkout(repo, repo)

    assert occupied == [("occ-mission-a", "WP01")]


def test_excludes_the_callers_own_wp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mission-b", "01OCCMISSIONB00000000000B")
    _write_repo_root_lane(repo, "occ-mission-b", "WP01")
    write_wp(repo, "occ-mission-b", "in_progress", "WP01")

    occupied = in_progress_wps_in_write_checkout(repo, repo, exclude=("occ-mission-b", "WP01"))

    assert occupied == []


def test_two_missions_sharing_a_checkout_both_surface(tmp_path: Path) -> None:
    """US2.7: two single_branch missions share the SAME repo-root checkout."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mission-c1", "01OCCMISSIONC100000000C1")
    _write_repo_root_lane(repo, "occ-mission-c1", "WP01")
    write_wp(repo, "occ-mission-c1", "in_progress", "WP01")
    _write_single_branch_meta(repo, "occ-mission-c2", "01OCCMISSIONC200000000C2")
    _write_repo_root_lane(repo, "occ-mission-c2", "WP01")
    write_wp(repo, "occ-mission-c2", "in_progress", "WP01")

    occupied = in_progress_wps_in_write_checkout(repo, repo)

    assert set(occupied) == {("occ-mission-c1", "WP01"), ("occ-mission-c2", "WP01")}


def test_non_in_progress_lanes_are_not_reported(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mission-d", "01OCCMISSIOND00000000000D")
    _write_repo_root_lane(repo, "occ-mission-d", "WP01", "WP02")
    write_wp(repo, "occ-mission-d", "for_review", "WP01")
    write_wp(repo, "occ-mission-d", "planned", "WP02")

    assert in_progress_wps_in_write_checkout(repo, repo) == []


def test_non_single_branch_missions_are_never_scanned(tmp_path: Path) -> None:
    """A `lanes`-topology mission's WPs execute in their OWN `.worktrees/`
    worktree, never the repo-root checkout -- it must not be reported here
    even if it happens to have an `in_progress` WP."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / "occ-mission-e"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01OCCMISSIONE00000000000E",
                "mission_slug": "occ-mission-e",
                "mid8": "01occmis",
                "mission_type": "software-dev",
                "target_branch": "main",
                "topology": "lanes",
                "created_at": "2026-09-28T00:00:00+00:00",
                "friendly_name": "occ-mission-e",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_wp(repo, "occ-mission-e", "in_progress", "WP01")

    assert in_progress_wps_in_write_checkout(repo, repo) == []


def test_mission_with_unreadable_meta_is_skipped_not_fatal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / "occ-mission-corrupt"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")
    (feature_dir / "spec.md").write_text("# corrupt mission\n", encoding="utf-8")
    _write_single_branch_meta(repo, "occ-mission-f", "01OCCMISSIONF00000000000F")
    _write_repo_root_lane(repo, "occ-mission-f", "WP01")
    write_wp(repo, "occ-mission-f", "in_progress", "WP01")

    occupied = in_progress_wps_in_write_checkout(repo, repo)

    assert occupied == [("occ-mission-f", "WP01")]


def test_legacy_single_branch_mission_without_lanes_json_is_not_an_occupant(tmp_path: Path) -> None:
    """A flat legacy mission (no ``lanes.json``) is *derived* single_branch, but
    its WPs never ran in the repo-root checkout -- an ``in_progress`` WP there
    must not read as write-checkout occupancy (it refused every implement on
    a repo full of historical missions)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-legacy", "01OCCLEGACY0000000000000L")
    write_wp(repo, "occ-legacy", "in_progress", "WP01")

    assert in_progress_wps_in_write_checkout(repo, repo) == []


def test_completed_single_branch_mission_is_not_an_occupant(tmp_path: Path) -> None:
    """A mission carrying the ``merged_at`` completion marker is done with the checkout."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-merged", "01OCCMERGED000000000000M")
    meta_path = repo / "kitty-specs" / "occ-merged" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["merged_at"] = "2026-09-29T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    _write_repo_root_lane(repo, "occ-merged", "WP01")
    write_wp(repo, "occ-merged", "in_progress", "WP01")

    assert in_progress_wps_in_write_checkout(repo, repo) == []


def _set_meta_fields(repo: Path, mission_slug: str, **fields: object) -> None:
    """Overwrite (or, with ``None``, drop) top-level ``meta.json`` fields."""
    meta_path = repo / "kitty-specs" / mission_slug / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    for key, value in fields.items():
        if value is None:
            meta.pop(key, None)
        else:
            meta[key] = value
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def _in_progress_occupant(repo: Path, mission_slug: str, mission_id: str, **meta_fields: object) -> None:
    _write_single_branch_meta(repo, mission_slug, mission_id)
    _set_meta_fields(repo, mission_slug, **meta_fields)
    _write_repo_root_lane(repo, mission_slug, "WP01")
    write_wp(repo, mission_slug, "in_progress", "WP01")


def test_mission_writing_to_another_branch_is_not_an_occupant(tmp_path: Path) -> None:
    """#5680: a status copy on a branch that is not the mission's write branch is not live."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _in_progress_occupant(repo, "occ-landed", "01OCCLANDED000000000000L", target_branch="fix/landed-elsewhere")

    assert _git(repo, "branch", "--show-current") == "main"
    assert in_progress_wps_in_write_checkout(repo, repo) == []


def test_mission_writing_to_the_current_branch_is_an_occupant(tmp_path: Path) -> None:
    """Control for the #5680 filter: the same fixture with the write branch set to the current branch."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    _in_progress_occupant(repo, "occ-live", "01OCCLIVE00000000000000V", target_branch="topic")

    assert in_progress_wps_in_write_checkout(repo, repo) == [("occ-live", "WP01")]


def test_protected_target_mint_is_the_write_branch(tmp_path: Path) -> None:
    """A recorded ``mission_branch`` (protected-target mint) wins over ``target_branch``."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-q", "-b", "kitty/mission-occ-mint")
    _in_progress_occupant(repo, "occ-mint", "01OCCMINT00000000000000T", mission_branch="kitty/mission-occ-mint")
    _in_progress_occupant(repo, "occ-target-only", "01OCCTARGETONLY000000000O")

    # occ-target-only writes to ``main`` and is skipped; occ-mint writes to the mint it sits on.
    assert in_progress_wps_in_write_checkout(repo, repo) == [("occ-mint", "WP01")]


def test_unknown_write_branch_fails_closed(tmp_path: Path) -> None:
    """No ``target_branch`` in ``meta.json``: the mission still counts as an occupant."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _in_progress_occupant(repo, "occ-no-target", "01OCCNOTARGET0000000000N", target_branch=None)

    assert in_progress_wps_in_write_checkout(repo, repo) == [("occ-no-target", "WP01")]


def test_detached_head_fails_closed(tmp_path: Path) -> None:
    """A detached write checkout cannot be compared, so every candidate still counts."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _in_progress_occupant(repo, "occ-elsewhere", "01OCCELSEWHERE000000000E", target_branch="fix/landed-elsewhere")
    _git(repo, "checkout", "-q", "--detach")

    assert in_progress_wps_in_write_checkout(repo, repo) == [("occ-elsewhere", "WP01")]


def test_wp_in_a_code_lane_of_a_single_branch_mission_is_not_an_occupant(tmp_path: Path) -> None:
    """An unmigrated single_branch mission keeps its WPs in CODE lanes (own worktree)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-code-lane", "01OCCCODELANE00000000000C")
    _write_lanes(repo, "occ-code-lane", {"lane-a": ("WP01",)})
    write_wp(repo, "occ-code-lane", "in_progress", "WP01")

    assert in_progress_wps_in_write_checkout(repo, repo) == []


def test_only_the_repo_root_lane_wps_of_a_mixed_manifest_count(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mixed", "01OCCMIXED0000000000000X")
    _write_lanes(repo, "occ-mixed", {PLANNING_LANE_ID: ("WP01",), "lane-a": ("WP02",)})
    write_wp(repo, "occ-mixed", "in_progress", "WP01")
    write_wp(repo, "occ-mixed", "in_progress", "WP02")

    assert in_progress_wps_in_write_checkout(repo, repo) == [("occ-mixed", "WP01")]


# ---------------------------------------------------------------------------
# dirty_paths
# ---------------------------------------------------------------------------


def test_dirty_paths_clean_checkout_is_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    assert dirty_paths(repo, owned_prefixes=()) == []


def test_dirty_paths_reports_a_real_user_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "src.py").write_text("VALUE = 1\n", encoding="utf-8")

    paths = dirty_paths(repo, owned_prefixes=())

    assert paths == ["src.py"]


def test_dirty_paths_excludes_owned_status_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mission-g", "01OCCMISSIONG0000000000G")
    write_wp(repo, "occ-mission-g", "in_progress", "WP01")
    # Commit the mission scaffolding (meta.json + WP task file + the status
    # log write_wp's seed_canonical=True already produced) -- in the real
    # implement flow these are already-committed planning artifacts by the
    # time a WP is claimed; only the status transition below and the real
    # code change happen "live".
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: seed occ-mission-g")
    _seed_canonical_wp_state(
        repo,
        "occ-mission-g",
        "WP01",
        "for_review",
        actor="claude",
        assignee="Owner",
        shell_pid="1234",
        timestamp="2026-09-28T01:00:00Z",
    )
    (repo / "real_change.py").write_text("X = 1\n", encoding="utf-8")

    owned_prefixes = (
        "kitty-specs/occ-mission-g/status.events.jsonl",
        "kitty-specs/occ-mission-g/status.json",
        ".kittify/",
    )
    paths = dirty_paths(repo, owned_prefixes=owned_prefixes)

    assert paths == ["real_change.py"]


def test_dirty_paths_excludes_dot_kittify_directory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "workspaces").mkdir()
    (repo / ".kittify" / "workspaces" / "some-context.json").write_text("{}\n", encoding="utf-8")

    assert dirty_paths(repo, owned_prefixes=(".kittify/",)) == []
