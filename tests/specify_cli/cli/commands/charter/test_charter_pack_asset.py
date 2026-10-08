"""``spec-kitty charter pack asset list|path`` (#3732, FR-006).

The asset surface moved from ``doctrine asset`` to ``charter pack asset``
(``charter/pack_asset.py``). The JSON shapes are unchanged: the transitional
``doctrine`` group mounts the same Typer sub-app, so its output is the oracle.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter._app import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

_SHIPPED_ASSET_ID = "common-docs-structural-lint"


def test_asset_list_json_shape(tmp_path: Path) -> None:
    with contextlib.chdir(tmp_path):
        result = runner.invoke(charter_app, ["pack", "asset", "list", "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)
    assert rows and all(set(row) == {"id", "tier", "path"} for row in rows)
    assert _SHIPPED_ASSET_ID in {row["id"] for row in rows}


def test_asset_list_human_table(tmp_path: Path) -> None:
    with contextlib.chdir(tmp_path):
        result = runner.invoke(charter_app, ["pack", "asset", "list"])
    assert result.exit_code == 0, result.output
    assert _SHIPPED_ASSET_ID in result.output


def test_asset_path_resolves_a_shipped_asset(tmp_path: Path) -> None:
    with contextlib.chdir(tmp_path):
        result = runner.invoke(charter_app, ["pack", "asset", "path", _SHIPPED_ASSET_ID])
    assert result.exit_code == 0, result.output
    resolved = Path(result.stdout.strip())
    assert resolved.is_file() and resolved.name == "docs_structural_lint.py"


def test_asset_path_unknown_id_exits_non_zero_naming_the_id(tmp_path: Path) -> None:
    with contextlib.chdir(tmp_path):
        known = runner.invoke(charter_app, ["pack", "asset", "path", _SHIPPED_ASSET_ID, "--json"])
        unknown = runner.invoke(charter_app, ["pack", "asset", "path", "no-such-asset", "--json"])
    assert known.exit_code == 0 and json.loads(known.stdout)["id"] == _SHIPPED_ASSET_ID  # control
    assert unknown.exit_code == 1, unknown.output
    payload = json.loads(unknown.stdout)
    assert payload["id"] == "no-such-asset" and "no-such-asset" in payload["error"]


def test_asset_path_help_names_the_charter_spelling() -> None:
    result = runner.invoke(charter_app, ["pack", "asset", "path", "--help"])
    assert result.exit_code == 0, result.output
    # Rich wraps help inside a box: compare with whitespace and box rules removed.
    flat = "".join(result.output.replace("\u2502", " ").split())
    assert "charterpackassetlist" in flat
    assert "doctrineassetlist" not in flat
