"""``agent tasks status`` reads declared dependencies through the typed parser (#5435).

``extract_scalar`` returns raw frontmatter text, so the old reader reported a WP
with ``dependencies: []`` as depending on a WP named ``"[]"`` and collapsed a
YAML list into one bogus dependency. The board must render the same dependency
set the dependency gate reads (``WPMetadata.dependencies``), for every authored
form: empty flow list, flow list, and block list.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.tasks_status_cmd import (
    _StatusState,
    _st_declared_dependencies,
    _st_load_work_packages,
)

pytestmark = pytest.mark.fast


def _write_wp(tasks_dir: Path, wp_id: str, dependencies_yaml: str) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Example\ndependencies: {dependencies_yaml}\nhistory: []\n---\n\n# Body\n",
        encoding="utf-8",
    )


def _load(tmp_path: Path, tasks_dir: Path) -> dict[str, list[str]]:
    st = _StatusState(mission="mission", json_output=True, stale_threshold=10)
    st.mission_slug = "mission"
    st.main_repo_root = tmp_path
    st.feature_dir = tmp_path
    st.tasks_dir = tasks_dir
    _st_load_work_packages(st)
    return st.wp_dependencies


def test_empty_flow_list_has_no_dependencies(tmp_path: Path) -> None:
    """``dependencies: []`` must not become a dependency named ``"[]"``."""
    tasks_dir = tmp_path / "tasks"
    _write_wp(tasks_dir, "WP01", "[]")

    assert _load(tmp_path, tasks_dir) == {"WP01": []}


def test_flow_list_yields_each_dependency(tmp_path: Path) -> None:
    """``dependencies: [WP01, WP02]`` splits into two dependency ids."""
    tasks_dir = tmp_path / "tasks"
    _write_wp(tasks_dir, "WP02", "[WP01]")
    _write_wp(tasks_dir, "WP03", "[WP01, WP02]")

    assert _load(tmp_path, tasks_dir) == {"WP02": ["WP01"], "WP03": ["WP01", "WP02"]}


def test_block_list_yields_each_dependency(tmp_path: Path) -> None:
    """A block list (the canonical authored form) yields every dependency."""
    tasks_dir = tmp_path / "tasks"
    _write_wp(tasks_dir, "WP02", "\n  - WP01")
    _write_wp(tasks_dir, "WP03", "\n  - WP01\n  - WP02")

    assert _load(tmp_path, tasks_dir) == {"WP02": ["WP01"], "WP03": ["WP01", "WP02"]}


def test_unparseable_wp_degrades_to_no_dependencies(tmp_path: Path) -> None:
    """A WP file the typed parser refuses must not abort the whole board."""
    tasks_dir = tmp_path / "tasks"
    _write_wp(tasks_dir, "WP02", "[WP01]")
    tasks_dir.joinpath("WP01.md").write_text("---\nwork_package_id: WP01\ntitle: Example\ndependencies: [\n---\n", encoding="utf-8")

    assert _load(tmp_path, tasks_dir) == {"WP01": [], "WP02": ["WP01"]}


def test_dependency_read_never_touches_the_status_log(tmp_path: Path) -> None:
    """Dependencies are authored frontmatter, so a corrupt event log cannot fail the read.

    The runtime frontmatter reader re-points runtime fields from the event log;
    reading dependencies through it made one corrupt log raise on a dependency
    read. The board already degrades a corrupt log, so this read must not depend
    on it at all.
    """
    tasks_dir = tmp_path / "tasks"
    _write_wp(tasks_dir, "WP02", "[WP01]")
    (tmp_path / "status.events.jsonl").write_text("{not json\n", encoding="utf-8")

    assert _st_declared_dependencies(tasks_dir / "WP02.md") == ["WP01"]
