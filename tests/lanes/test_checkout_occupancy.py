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
    write_wp(repo, "occ-mission-a", "in_progress", "WP01")

    occupied = in_progress_wps_in_write_checkout(repo, repo)

    assert occupied == [("occ-mission-a", "WP01")]


def test_excludes_the_callers_own_wp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mission-b", "01OCCMISSIONB00000000000B")
    write_wp(repo, "occ-mission-b", "in_progress", "WP01")

    occupied = in_progress_wps_in_write_checkout(repo, repo, exclude=("occ-mission-b", "WP01"))

    assert occupied == []


def test_two_missions_sharing_a_checkout_both_surface(tmp_path: Path) -> None:
    """US2.7: two single_branch missions share the SAME repo-root checkout."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mission-c1", "01OCCMISSIONC100000000C1")
    write_wp(repo, "occ-mission-c1", "in_progress", "WP01")
    _write_single_branch_meta(repo, "occ-mission-c2", "01OCCMISSIONC200000000C2")
    write_wp(repo, "occ-mission-c2", "in_progress", "WP01")

    occupied = in_progress_wps_in_write_checkout(repo, repo)

    assert set(occupied) == {("occ-mission-c1", "WP01"), ("occ-mission-c2", "WP01")}


def test_non_in_progress_lanes_are_not_reported(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, "occ-mission-d", "01OCCMISSIOND00000000000D")
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
    write_wp(repo, "occ-mission-f", "in_progress", "WP01")

    occupied = in_progress_wps_in_write_checkout(repo, repo)

    assert occupied == [("occ-mission-f", "WP01")]


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
