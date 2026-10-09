"""``spec-kitty doctor charter-packs`` (#3732, FR-006).

Renamed from ``doctor doctrine`` with its JSON keys unchanged; the old spelling
is not registered (no alias, C-001).
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app

pytestmark = [pytest.mark.unit]

runner = CliRunner()

_CLI_BEFORE = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "charter_pack_cutover" / "cli_before.json"


def _recorded_keys() -> list[str]:
    keys = json.loads(_CLI_BEFORE.read_text(encoding="utf-8"))["leaves"]["doctor"]["json_keys"]
    assert keys, "the recorded key set is vacuous"
    return sorted(keys)


def _project(root: Path, *, org_pack: bool) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    config = "mission_type_activations:\n  - software-dev\n"
    if org_pack:
        config += "charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: acme-pack\n"
    (kittify / "config.yaml").write_text(config, encoding="utf-8")
    return root


def test_json_keys_equal_the_recorded_doctor_doctrine_keys(tmp_path: Path) -> None:
    project = _project(tmp_path, org_pack=True)
    with contextlib.chdir(project):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"])
    # The org pack is declared but never fetched: unhealthy, exit 1 (recorded at base).
    assert result.exit_code == 1, result.output
    assert sorted(json.loads(result.stdout)) == _recorded_keys()


def test_no_org_packs_human_output(tmp_path: Path) -> None:
    project = _project(tmp_path, org_pack=False)
    with contextlib.chdir(project):
        result = runner.invoke(doctor_app, ["charter-packs"])
    assert result.exit_code == 0, result.output
    assert "No org charter packs configured." in result.output
    assert "No org doctrine configured." not in result.output


def test_old_spelling_is_not_registered(tmp_path: Path) -> None:
    project = _project(tmp_path, org_pack=False)
    with contextlib.chdir(project):
        old = runner.invoke(doctor_app, ["doctrine", "--json"])
        new = runner.invoke(doctor_app, ["charter-packs", "--json"])
    assert old.exit_code == 2 and "No such command" in old.output, old.output
    assert new.exit_code == 0, new.output  # control
