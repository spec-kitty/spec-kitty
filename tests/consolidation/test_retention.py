"""Tests for mission retention-contract enforcement."""

from __future__ import annotations

import pytest
from pathlib import Path

from specify_cli.consolidation.retention import (
    MissionRetention,
    load_mission_retention,
    retention_cleanup_conflicts,
)
from tests.reliability.fixtures import create_mission_fixture
from tests.reliability.fixtures.mission import MissionFixture


def _write_spec(tmp_path: Path, constraint: str, status: str) -> MissionFixture:
    return _write_spec_rows(tmp_path, [(constraint, status)])


def _write_spec_rows(tmp_path: Path, rows: list[tuple[str, str]]) -> MissionFixture:
    constraint_rows = [
        f"| C-{index:03d} | Retention {index} | {constraint} | Operational | High | {status} |" for index, (constraint, status) in enumerate(rows, start=1)
    ]
    mission = create_mission_fixture(tmp_path)
    (mission.mission_dir / "spec.md").write_text(
        "\n".join(
            [
                "# Mission",
                "",
                "## Constraints",
                "",
                "| ID | Title | Constraint | Category | Priority | Status |",
                "|----|-------|------------|----------|----------|--------|",
                *constraint_rows,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return mission


@pytest.mark.parametrize(
    ("constraint", "retains_branch", "retains_worktree"),
    [
        ("Keep branches and worktrees after merge.", True, True),
        ("Keep branches after merge.", True, False),
        ("Preserve worktrees after merging.", False, True),
        ("Never delete branches or worktrees after merge.", True, True),
        (
            "Keep branches after merge; do not keep worktrees after merge.",
            True,
            False,
        ),
        ("Keep branches and delete worktrees after merge.", True, False),
        ("Keep branches but delete worktrees after merge.", True, False),
        ("Keep branches (e.g. lane branches) and delete worktrees after merge.", True, False),
        ("Keep branches (i.e. lane branches) and delete worktrees after merge.", True, False),
        ("Keep branches, etc. and delete worktrees after merge.", True, False),
    ],
)
def test_load_mission_retention_detects_each_retained_artifact(
    tmp_path: Path,
    constraint: str,
    retains_branch: bool,
    retains_worktree: bool,
) -> None:
    mission = _write_spec(tmp_path, constraint, "Accepted")
    retention = load_mission_retention(mission.repo_root, mission.mission_slug)
    assert retention is not None
    assert retention.retains_branch is retains_branch
    assert retention.retains_worktree is retains_worktree


@pytest.mark.parametrize(
    ("first_constraint", "second_constraint", "retains_branch", "retains_worktree"),
    [
        ("Keep branches after merge.", "Keep worktrees after merge.", True, True),
        ("Keep worktrees after merge.", "Keep branches after merge.", True, True),
    ],
)
def test_load_mission_retention_combines_terminal_rows(
    tmp_path: Path,
    first_constraint: str,
    second_constraint: str,
    retains_branch: bool,
    retains_worktree: bool,
) -> None:
    mission = _write_spec_rows(
        tmp_path,
        [
            (first_constraint, "Accepted"),
            (second_constraint, "Accepted"),
        ],
    )
    retention = load_mission_retention(mission.repo_root, mission.mission_slug)
    assert retention is not None
    assert retention.constraint_id == "C-001"
    assert retention.constraint == first_constraint
    assert retention.retains_branch is retains_branch
    assert retention.retains_worktree is retains_worktree


@pytest.mark.parametrize("status", ["Open", "Approved", "Confirmed", "Binding", "Locked"])
def test_load_mission_retention_reads_terminal_constraint_statuses(tmp_path: Path, status: str) -> None:
    mission = _write_spec(
        tmp_path,
        "Keep branches after merge.",
        status,
    )
    retention = load_mission_retention(mission.repo_root, mission.mission_slug)
    if status == "Open":
        assert retention is None
    else:
        assert retention is not None
        assert retention.retains_branch is True


def test_load_mission_retention_ignores_negated_retention(
    tmp_path: Path,
) -> None:
    mission = _write_spec(
        tmp_path,
        "Do not keep branches and worktrees after merge.",
        "Accepted",
    )
    assert load_mission_retention(mission.repo_root, mission.mission_slug) is None


def test_retention_cleanup_conflicts_requires_each_explicit_choice() -> None:
    retention = MissionRetention(
        constraint_id="C-005",
        constraint="Keep branches and worktrees after merge.",
        retains_branch=True,
        retains_worktree=True,
    )
    assert (
        retention_cleanup_conflicts(
            None,
            delete_branch=None,
            remove_worktree=None,
        )
        == ()
    )

    branch_only = MissionRetention(
        constraint_id="C-006",
        constraint="Keep branches after merge.",
        retains_branch=True,
        retains_worktree=False,
    )
    assert retention_cleanup_conflicts(
        branch_only,
        delete_branch=None,
        remove_worktree=None,
    ) == ("branch",)
    assert retention_cleanup_conflicts(
        retention,
        delete_branch=None,
        remove_worktree=None,
    ) == ("branch", "worktree")
    assert retention_cleanup_conflicts(
        retention,
        delete_branch=True,
        remove_worktree=None,
    ) == ("worktree",)
    assert (
        retention_cleanup_conflicts(
            retention,
            delete_branch=False,
            remove_worktree=True,
        )
        == ()
    )
