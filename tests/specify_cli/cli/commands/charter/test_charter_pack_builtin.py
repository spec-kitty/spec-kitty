"""Tests for `spec-kitty charter pack {list,path}` (#3732 WP08).

Covers:
- `pack list` — one row per offering pack with its presets.
- `pack path <pack> [--preset <preset>]` — the pack root or the preset file;
  fails closed (exit 1, PACK_NOT_FOUND) on an unknown pack.

Presets are applied with `spec-kitty charter activate --preset` (WP08 owns those
tests); the former `pack apply` is gone (#3732 WP13,
`test_charter_pack_apply_removed.py`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parents[5]


# ---------------------------------------------------------------------------
# `pack list` (#3732 WP08: one row per offering pack with its presets)
# ---------------------------------------------------------------------------

_BUILT_IN_PRESETS = _REPO_ROOT / "packs" / "built-in" / "presets"


def _list(repo_root: Path, *extra: str) -> object:
    return runner.invoke(charter_app, ["pack", "list", "--repo-root", str(repo_root), *extra], catch_exceptions=False)


def test_list_shows_built_in_pack_with_default_and_minimal_presets(tmp_path: Path) -> None:
    result = _list(tmp_path)

    assert result.exit_code == 0, result.output
    assert "built-in" in result.output
    assert "default" in result.output
    assert "minimal" in result.output


def test_list_json_rows_are_packs_with_preset_paths(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    result = _list(tmp_path, "--json")

    assert result.exit_code == 0, result.output
    rows = {row["name"]: row for row in json.loads(result.output)["packs"]}
    assert set(rows) == {"built-in", "project"}
    presets = {preset["name"]: Path(preset["path"]) for preset in rows["built-in"]["presets"]}
    assert presets["minimal"] == _BUILT_IN_PRESETS / "minimal.yaml"
    assert presets["default"] == _BUILT_IN_PRESETS / "default.yaml"
    assert rows["project"] == {"name": "project", "tier": "project", "root": str(tmp_path.resolve() / ".kittify" / "charter-packs"), "presets": []}


def test_list_outside_a_project_has_no_project_row(tmp_path: Path) -> None:
    result = _list(tmp_path, "--json")

    assert result.exit_code == 0, result.output
    assert [row["name"] for row in json.loads(result.output)["packs"]] == ["built-in"]


# ---------------------------------------------------------------------------
# `pack path <pack> [--preset <preset>]`
# ---------------------------------------------------------------------------


def _path(repo_root: Path, *args: str) -> object:
    return runner.invoke(charter_app, ["pack", "path", *args, "--repo-root", str(repo_root)], catch_exceptions=False)


def test_path_built_in_resolves_to_the_pack_root(tmp_path: Path) -> None:
    result = _path(tmp_path, "built-in")

    assert result.exit_code == 0, result.output
    assert Path(result.output.strip()) == _REPO_ROOT / "packs" / "built-in"


def test_path_preset_minimal_resolves_to_the_preset_file(tmp_path: Path) -> None:
    result = _path(tmp_path, "built-in", "--preset", "minimal")

    assert result.exit_code == 0, result.output
    resolved = Path(result.output.strip())
    assert resolved == _BUILT_IN_PRESETS / "minimal.yaml"
    assert resolved.is_file()


def test_path_json_built_in_minimal(tmp_path: Path) -> None:
    result = _path(tmp_path, "built-in", "--preset", "minimal", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {"pack": "built-in", "path": str(_BUILT_IN_PRESETS / "minimal.yaml"), "preset": "minimal"}


def test_path_unknown_pack_fails_closed(tmp_path: Path) -> None:
    result = _path(tmp_path, "no-such-pack")

    assert result.exit_code == 1
    assert "PACK_NOT_FOUND" in result.output
    assert "no-such-pack" in result.output
    assert "built-in" in result.output


def test_path_unknown_pack_json_fails_closed(tmp_path: Path) -> None:
    result = _path(tmp_path, "no-such-pack", "--json")

    assert result.exit_code == 1
    error = json.loads(result.output)["error"]
    assert error["code"] == "PACK_NOT_FOUND"
    assert error["pack"] == "no-such-pack"
    assert "built-in" in error["available"]
