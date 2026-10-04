"""Seam units for ``workflow._partition_paths_by_primary_kind`` (#4905, #5619).

``_commit_via_coordination_transaction`` funnels every staged path through this
partition so a PRIMARY-partition artifact (``tasks/WP*.md``, spec/plan/tasks,
...) is committed to the mission's primary target branch and NEVER reaches the
coordination worktree, while STATUS_STATE bookkeeping (and any path that does
not classify as a mission artifact) stays coord-bound.

These tests pin that decision directly, without the slow git-DAG CLI fixtures
of ``test_issue_4905_coord_staging.py``. They need no repository on disk: the
classifier is purely path-shaped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.workflow import _partition_paths_by_primary_kind

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "coord-staging-4905-0123abcd"
_SPECS = Path("repo") / "kitty-specs" / _SLUG


def _partition(*paths: Path, mission_slug: str = _SLUG) -> tuple[list[Path], list[Path]]:
    primary_bound, coord_bound = _partition_paths_by_primary_kind(list(paths), mission_slug=mission_slug)
    return primary_bound, coord_bound


@pytest.mark.parametrize(
    "relative",
    [
        "tasks/WP01-first.md",
        "tasks/WP02-second.md",
        "spec.md",
        "plan.md",
        "tasks.md",
        "lanes.json",
    ],
)
def test_primary_partition_artifact_is_primary_bound(relative: str) -> None:
    path = _SPECS / relative

    primary_bound, coord_bound = _partition(path)

    assert primary_bound == [path]
    assert coord_bound == []


@pytest.mark.parametrize("name", ["status.events.jsonl", "status.json"])
def test_status_state_bookkeeping_is_coord_bound(name: str) -> None:
    path = _SPECS / name

    primary_bound, coord_bound = _partition(path)

    assert primary_bound == []
    assert coord_bound == [path]


@pytest.mark.parametrize(
    "path",
    [
        Path("repo") / "meta.json",
        Path("repo") / ".kittify" / "config.yaml",
        Path("repo") / "README.md",
    ],
    ids=["repo-root-meta", "kittify-config", "readme"],
)
def test_non_mission_path_defaults_to_coord_bound(path: Path) -> None:
    primary_bound, coord_bound = _partition(path)

    assert primary_bound == []
    assert coord_bound == [path]


def test_other_missions_primary_artifact_is_not_primary_bound() -> None:
    other = Path("repo") / "kitty-specs" / "some-other-mission-99999999" / "tasks" / "WP01-x.md"

    primary_bound, coord_bound = _partition(other)

    assert primary_bound == []
    assert coord_bound == [other]


def test_mixed_paths_are_split_and_keep_input_order() -> None:
    wp01 = _SPECS / "tasks" / "WP01-first.md"
    events = _SPECS / "status.events.jsonl"
    spec = _SPECS / "spec.md"
    status = _SPECS / "status.json"
    root_meta = Path("repo") / "meta.json"

    primary_bound, coord_bound = _partition(events, wp01, root_meta, spec, status)

    assert primary_bound == [wp01, spec]
    assert coord_bound == [events, root_meta, status]


def test_empty_input_yields_two_empty_partitions() -> None:
    assert _partition() == ([], [])


def test_partitions_are_disjoint_and_exhaustive() -> None:
    paths = [
        _SPECS / "tasks" / "WP01-first.md",
        _SPECS / "status.events.jsonl",
        _SPECS / "plan.md",
        Path("repo") / "meta.json",
    ]

    primary_bound, coord_bound = _partition(*paths)

    assert sorted(primary_bound + coord_bound) == sorted(paths)
    assert not set(primary_bound) & set(coord_bound)
