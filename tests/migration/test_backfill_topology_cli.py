"""CLI tests for ``spec-kitty migrate backfill-topology`` (T013 / FR-003).

Covers the typer surface: clean exit 0, exit 1 on a corrupt-meta fixture, stable
JSON shape, dry-run writes nothing, idempotent second run, and --mission scoping.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.migrate_cmd import app as migrate_app

pytestmark = [pytest.mark.integration]

_LOCATE_ROOT = "specify_cli.cli.commands.migrate_cmd.locate_project_root"


def _write_meta(feature_dir: Path, meta: dict[str, Any]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture()
def specs_root(tmp_path: Path) -> Path:
    (tmp_path / "kitty-specs").mkdir()
    (tmp_path / ".kittify").mkdir()
    return tmp_path


def _invoke(specs_root: Path, *args: str):
    runner = CliRunner()
    with patch(_LOCATE_ROOT, return_value=specs_root):
        return runner.invoke(migrate_app, ["backfill-topology", *args])


def test_help_surface(specs_root: Path) -> None:
    result = CliRunner().invoke(migrate_app, ["backfill-topology", "--help"])
    assert result.exit_code == 0
    assert "topology" in result.stdout.lower()


def test_clean_repo_exit_zero_json_shape(specs_root: Path) -> None:
    _write_meta(specs_root / "kitty-specs" / "mission-a", {"coordination_branch": "kitty/a"})

    result = _invoke(specs_root, "--json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is False
    assert set(payload["summary"]) == {"total", "wrote", "skip", "error"}
    assert payload["summary"]["wrote"] == 1
    row = payload["results"][0]
    assert set(row) == {"slug", "action", "topology", "reason"}
    assert row["topology"] == "coord"


def test_corrupt_meta_exits_one(specs_root: Path) -> None:
    feature_dir = specs_root / "kitty-specs" / "mission-corrupt"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{ not json", encoding="utf-8")

    result = _invoke(specs_root, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["summary"]["error"] == 1


def test_dry_run_writes_nothing(specs_root: Path) -> None:
    feature_dir = specs_root / "kitty-specs" / "mission-dry"
    _write_meta(feature_dir, {"coordination_branch": "kitty/x"})

    result = _invoke(specs_root, "--dry-run", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["summary"]["wrote"] == 1
    persisted = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "topology" not in persisted


def test_idempotent_second_run_all_skip(specs_root: Path) -> None:
    feature_dir = specs_root / "kitty-specs" / "mission-idem"
    _write_meta(feature_dir, {"coordination_branch": None})

    first = _invoke(specs_root, "--json")
    assert json.loads(first.stdout)["summary"]["wrote"] == 1

    second = _invoke(specs_root, "--json")
    assert second.exit_code == 0
    summary = json.loads(second.stdout)["summary"]
    assert summary["wrote"] == 0
    assert summary["skip"] == 1


def _write_lanes(feature_dir: Path, lanes: list[dict[str, Any]]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "mission_slug": feature_dir.name,
        "mission_branch": f"kitty/mission-{feature_dir.name}",
        "target_branch": "main",
        "lanes": lanes,
        "computed_at": "2026-09-28T00:00:00+00:00",
        "computed_from": "dependency_graph+ownership",
    }
    (feature_dir / "lanes.json").write_text(json.dumps(manifest), encoding="utf-8")


# ---------------------------------------------------------------------------
# --restamp-single-branch (#5100 IC-02, WP03 T013 operator CLI)
# ---------------------------------------------------------------------------


def test_restamp_single_branch_dry_run_reports_without_writing(specs_root: Path) -> None:
    feature_dir = specs_root / "kitty-specs" / "mission-restamp"
    _write_meta(feature_dir, {"topology": "single_branch"})
    _write_lanes(feature_dir, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])
    meta_before = (feature_dir / "meta.json").read_bytes()

    result = _invoke(specs_root, "--restamp-single-branch", "--dry-run", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["summary"]["restamped"] == 1
    assert (feature_dir / "meta.json").read_bytes() == meta_before, "dry-run must write nothing"


def test_restamp_single_branch_live_run_writes_lanes(specs_root: Path) -> None:
    feature_dir = specs_root / "kitty-specs" / "mission-restamp"
    _write_meta(feature_dir, {"topology": "single_branch"})
    _write_lanes(feature_dir, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    result = _invoke(specs_root, "--restamp-single-branch", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["restamped"] == 1
    written = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert written["topology"] == "lanes"


def test_restamp_single_branch_skips_clean_mission(specs_root: Path) -> None:
    feature_dir = specs_root / "kitty-specs" / "mission-clean"
    _write_meta(feature_dir, {"topology": "single_branch"})
    _write_lanes(feature_dir, [{"lane_id": "lane-planning", "wp_ids": ["WP01"]}])

    result = _invoke(specs_root, "--restamp-single-branch", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["restamped"] == 0
    assert payload["summary"]["skip"] == 1


def test_restamp_single_branch_honours_mission_scoping(specs_root: Path) -> None:
    """Review cycle-1 nit 4: --restamp-single-branch --mission must not be silently ignored."""
    dir_a = specs_root / "kitty-specs" / "mission-a"
    _write_meta(dir_a, {"topology": "single_branch"})
    _write_lanes(dir_a, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])
    dir_b = specs_root / "kitty-specs" / "mission-b"
    _write_meta(dir_b, {"topology": "single_branch"})
    _write_lanes(dir_b, [{"lane_id": "lane-a", "wp_ids": ["WP01"]}])

    result = _invoke(specs_root, "--restamp-single-branch", "--mission", "mission-b", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["total"] == 1
    assert payload["results"][0]["slug"] == "mission-b"
    # mission-a is scoped out entirely -- untouched, still single_branch.
    assert json.loads((dir_a / "meta.json").read_text())["topology"] == "single_branch"
    assert json.loads((dir_b / "meta.json").read_text())["topology"] == "lanes"


def test_mission_scoping(specs_root: Path) -> None:
    _write_meta(specs_root / "kitty-specs" / "mission-a", {"coordination_branch": "kitty/a"})
    _write_meta(specs_root / "kitty-specs" / "mission-b", {"coordination_branch": None})

    result = _invoke(specs_root, "--mission", "mission-b", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["total"] == 1
    assert payload["results"][0]["slug"] == "mission-b"
    assert "topology" not in json.loads((specs_root / "kitty-specs" / "mission-a" / "meta.json").read_text())
