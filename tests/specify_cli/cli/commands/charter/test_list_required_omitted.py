"""``charter list`` marks an org-required id an explicit allow list omits (FR-023, R12; WP09 T057).

Core semantics are unchanged (ruling ``required_always_active_divergence``):
an explicit ``activated_<kind>`` list is still the allow list. ``charter list``
only says so, naming the requiring pack(s): the human table shows
``required (not in force: explicit allow list omits it)``, and ``--json``
gains ``required_not_in_force: {<plural>: [{id, packs}]}`` only when non-empty.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_REQUIRED_STEM = "001-architectural-integrity-standard"
_OTHER = "003-decision-documentation-requirement"


def _project(root: Path, **ledger: list[str]) -> Path:
    pack = root / "org-packs" / "acme"
    pack.mkdir(parents=True)
    (pack / "org-charter.yaml").write_text("schema_version: 1\nrequired_directives: [DIRECTIVE_001]\n", encoding="utf-8")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: org-packs/acme\n", encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _list(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, ["list", "--repo-root", str(root), *args])


def test_json_names_the_required_id_and_its_pack(tmp_path: Path) -> None:
    result = _list(_project(tmp_path, activated_directives=[_OTHER]), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["required_not_in_force"] == {"directives": [{"id": _REQUIRED_STEM, "packs": ["acme"]}]}


def test_human_table_marks_the_omitted_required_id(tmp_path: Path) -> None:
    result = _list(_project(tmp_path, activated_directives=[_OTHER]))

    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "required (not in force: explicit allow list omits it)" in flat
    assert "'acme'" in flat
    assert _REQUIRED_STEM in flat


@pytest.mark.parametrize("ledger", [{}, {"activated_directives": ["DIRECTIVE_001", _OTHER]}])
def test_no_key_when_the_required_id_is_in_force(tmp_path: Path, ledger: dict[str, list[str]]) -> None:
    """Positive control: an absent allow list, or one naming the id (any spelling), omits nothing."""
    result = _list(_project(tmp_path, **ledger), "--json")

    assert result.exit_code == 0, result.output
    assert "required_not_in_force" not in json.loads(result.stdout)
