"""``spec-kitty charter pack list`` / ``pack path <pack> [--preset]`` over the offering (FR-004, FR-006; #3732 WP08).

Fixture: the built-in pack, org pack A (``acme``, ships ``presets/team.yaml``),
org pack B (``acme-two``, no ``presets/``: the negative control) and the
``project`` layer, which ships no presets (US3 AS-3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.fast]

runner = CliRunner()

_BUILT_IN = Path(__file__).resolve().parents[5] / "packs" / "built-in"


def _dump(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)
    return path


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    _dump(tmp_path / "org-packs" / "acme" / "presets" / "team.yaml", {"name": "team", "description": "Team start", "mission_type_activations": ["software-dev"]})
    (tmp_path / "org-packs" / "acme-two").mkdir(parents=True)
    packs = [{"name": "acme", "local_path": "org-packs/acme"}, {"name": "acme-two", "local_path": "org-packs/acme-two"}]
    _dump(tmp_path / ".kittify" / "config.yaml", {"charter_packs": {"org": {"packs": packs}}, "mission_type_activations": ["software-dev"]})
    return tmp_path


def _pack(root: Path, *args: str) -> Any:
    return runner.invoke(charter_app, ["pack", *args, "--repo-root", str(root)], catch_exceptions=False)


def test_list_json_one_row_per_pack_with_its_presets(project: Path) -> None:
    result = _pack(project, "list", "--json")

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["packs"]
    assert [(row["name"], row["tier"]) for row in rows] == [("built-in", "built-in"), ("acme", "org"), ("acme-two", "org"), ("project", "project")]
    by_name = {row["name"]: row for row in rows}
    assert {preset["name"] for preset in by_name["built-in"]["presets"]} >= {"default", "minimal"}
    assert by_name["acme"]["presets"] == [
        {"name": "team", "description": "Team start", "path": str(project.resolve() / "org-packs" / "acme" / "presets" / "team.yaml")}
    ]
    assert by_name["acme-two"]["presets"] == [], "negative control: a pack without presets lists none"
    assert by_name["project"]["presets"] == []


def test_list_text_is_a_table_of_packs(project: Path) -> None:
    result = _pack(project, "list")

    assert result.exit_code == 0, result.output
    for name in ("built-in", "acme", "acme-two", "project", "team", "minimal"):
        assert name in result.output
    assert "—" in result.output, "a pack without presets shows a dash"


def test_list_refuses_a_malformed_preset(project: Path) -> None:
    _dump(project / "org-packs" / "acme" / "presets" / "bad.yaml", {"name": "bad", "description": "x", "unknown_key": 1})

    result = _pack(project, "list", "--json")

    assert result.exit_code == 1
    error = json.loads(result.output)["error"]
    assert error["code"] == "PRESET_INVALID" and "bad.yaml" in error["message"]


@pytest.mark.parametrize(
    ("pack", "relative"), [("built-in", None), ("acme", "org-packs/acme"), ("acme-two", "org-packs/acme-two"), ("project", ".kittify/charter-packs")]
)
def test_path_prints_each_pack_root(project: Path, pack: str, relative: str | None) -> None:
    result = _pack(project, "path", pack, "--json")

    assert result.exit_code == 0, result.output
    expected = _BUILT_IN if relative is None else project.resolve() / relative
    assert json.loads(result.output) == {"pack": pack, "path": str(expected)}


def test_path_preset_of_an_org_pack(project: Path) -> None:
    result = _pack(project, "path", "acme", "--preset", "team")

    assert result.exit_code == 0, result.output
    assert Path(result.output.strip()) == project.resolve() / "org-packs" / "acme" / "presets" / "team.yaml"


def test_path_unknown_preset_names_the_pack_and_its_presets(project: Path) -> None:
    result = _pack(project, "path", "acme", "--preset", "nope")

    assert result.exit_code == 1
    assert "Error (PRESET_NOT_FOUND)" in result.output
    assert "acme" in result.output and "team" in result.output


def test_path_preset_of_a_pack_without_presets(project: Path) -> None:
    result = _pack(project, "path", "acme-two", "--preset", "team", "--json")

    assert result.exit_code == 1
    error = json.loads(result.output)["error"]
    assert error["code"] == "PRESET_NOT_FOUND" and error["available"] == []


def test_path_malformed_preset_fails_with_the_fallback_code(project: Path) -> None:
    _dump(project / "org-packs" / "acme" / "presets" / "bad.yaml", {"name": "bad", "description": "x", "unknown_key": 1})

    result = _pack(project, "path", "acme", "--preset", "bad")

    assert result.exit_code == 1
    assert "Error (PRESET_INVALID)" in result.output


def test_path_unknown_pack_lists_available_packs(project: Path) -> None:
    result = _pack(project, "path", "nope")

    assert result.exit_code == 1
    assert "Error (PACK_NOT_FOUND)" in result.output
    for name in ("built-in", "acme", "acme-two", "project"):
        assert name in result.output
