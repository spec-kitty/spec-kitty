"""The one WP task-file matching rule (#7443, spec-kitty-events R26)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.wp_task_files import match_wp_task_files, non_regular

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _tasks(tmp_path: Path, *names: str) -> Path:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    for name in names:
        (tasks_dir / name).write_text("---\n---\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "name",
    ["WP04.md", "WP04-slug.md", "WP04_slug.md", "WP04.x.md", "wp04-x.md", "Wp04-x.md"],
)
def test_names_that_belong_to_the_wp(tmp_path: Path, name: str) -> None:
    feature_dir = _tasks(tmp_path, name)
    assert [path.name for path in match_wp_task_files(feature_dir, "WP04")] == [name]


@pytest.mark.parametrize("name", ["WP04b.md", "WP040-x.md", "WP4-x.md", "WP04-x.txt", "notes-WP04.md"])
def test_names_that_do_not_belong_to_the_wp(tmp_path: Path, name: str) -> None:
    feature_dir = _tasks(tmp_path, name)
    assert match_wp_task_files(feature_dir, "WP04") == []


@pytest.mark.parametrize("readme", ["README.md", "readme.md", "ReadMe.md"])
def test_readme_is_excluded_in_any_case(tmp_path: Path, readme: str) -> None:
    feature_dir = _tasks(tmp_path, readme)
    assert match_wp_task_files(feature_dir, "README") == []
    assert match_wp_task_files(feature_dir, "readme") == []


def test_missing_tasks_directory_is_no_match(tmp_path: Path) -> None:
    assert match_wp_task_files(tmp_path, "WP01") == []


def test_matches_are_sorted_and_include_every_candidate(tmp_path: Path) -> None:
    feature_dir = _tasks(tmp_path, "wp02-b.md", "WP02-a.md", "WP03.md")
    assert [path.name for path in match_wp_task_files(feature_dir, "WP02")] == ["WP02-a.md", "wp02-b.md"]


def test_a_directory_match_is_returned_and_flagged_non_regular(tmp_path: Path) -> None:
    feature_dir = _tasks(tmp_path, "WP05-file.md")
    (feature_dir / "tasks" / "WP06-dir.md").mkdir()

    matches = match_wp_task_files(feature_dir, "WP06")

    assert [path.name for path in matches] == ["WP06-dir.md"]
    assert non_regular(matches) == matches
    assert non_regular(match_wp_task_files(feature_dir, "WP05")) == []


def test_links_count_by_their_target(tmp_path: Path) -> None:
    feature_dir = _tasks(tmp_path, "WP07-real.md")
    tasks_dir = feature_dir / "tasks"
    (tasks_dir / "WP08-link.md").symlink_to(tasks_dir / "WP07-real.md")
    (tasks_dir / "WP09-dangling.md").symlink_to(tasks_dir / "absent.md")

    assert non_regular(match_wp_task_files(feature_dir, "WP08")) == []
    dangling = match_wp_task_files(feature_dir, "WP09")
    assert [path.name for path in dangling] == ["WP09-dangling.md"]
    assert non_regular(dangling) == dangling
