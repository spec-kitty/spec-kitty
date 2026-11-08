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

from specify_cli.cli.commands.agent.tasks_status_cmd import _st_declared_dependencies

pytestmark = pytest.mark.fast


def _write_wp(tasks_dir: Path, wp_id: str, dependencies_yaml: str) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Example\ndependencies: {dependencies_yaml}\nhistory: []\n---\n\n# Body\n",
        encoding="utf-8",
    )


def _load(tmp_path: Path, tasks_dir: Path) -> dict[str, list[str]]:
    """The board's dependency map, built the way ``_st_load_work_packages`` builds it.

    The loader keys ``wp_dependencies`` by WP id from ``_st_declared_dependencies(wp_file)``;
    calling that seam directly keeps these parser cases free of the read-door fixture
    (meta.json, event log) the full board load needs since #7431.
    """
    del tmp_path
    return {path.stem.split("-")[0]: _st_declared_dependencies(path) for path in sorted(tasks_dir.glob("WP*.md"))}


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


def test_unknown_frontmatter_key_keeps_declared_dependencies(tmp_path: Path) -> None:
    """A key the strict schema does not know must not erase real dependencies.

    The strict ``WPMetadata`` forbids extra keys; reading the board through it
    turned one unknown key into ``[]`` dependencies, so the board showed the WP
    as ready while the dependency gate refused it. The lenient reader drops only
    the unknown key and keeps every known field.
    """
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True)
    wp = tasks_dir / "WP02.md"
    wp.write_text(
        "---\nwork_package_id: WP02\ntitle: Example\ndependencies: [WP01]\nestimated_lines: 40\nhistory: []\n---\n\n# Body\n",
        encoding="utf-8",
    )

    assert _st_declared_dependencies(wp) == ["WP01"]


def test_malformed_yaml_still_degrades_to_no_dependencies(tmp_path: Path) -> None:
    """Genuinely malformed frontmatter keeps the board's degrade-to-empty fallback."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True)
    wp = tasks_dir / "WP03.md"
    wp.write_text("---\nwork_package_id: WP03\ndependencies: [WP01\n---\n\n# Body\n", encoding="utf-8")

    assert _st_declared_dependencies(wp) == []
