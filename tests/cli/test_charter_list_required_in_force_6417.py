"""#6417: ``charter list`` shows the org-required ids in force under an absent allow list.

An absent ``activated_<kind>`` key leaves the org packs' required floor in force
(``required_not_in_force`` only reports omissions by a *present* list), so the
listing names each such id beside the absent-key label, with its requiring pack.
``--json`` gains ``required_in_force: {<plural>: [{id, packs}]}`` only when non-empty.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_RUNNER = CliRunner()
_BUILT_IN_STEM = "001-architectural-integrity-standard"
_OTHER = "003-decision-documentation-requirement"
_TEAM_RULE = "team-rule"


def _register(root: Path, name: str, local_path: str) -> None:
    (root / ".kittify").mkdir(exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(
        f"charter_packs:\n  org:\n    packs:\n      - name: {name}\n        local_path: {local_path}\n", encoding="utf-8"
    )


def _built_in_required(root: Path, *, required: str = "DIRECTIVE_001", **ledger: list[str]) -> Path:
    """An org pack ``acme`` requiring the built-in DIRECTIVE_001 (plus any other *required* ids)."""
    pack = root / "org-packs" / "acme"
    pack.mkdir(parents=True)
    (pack / "org-charter.yaml").write_text(f"schema_version: 1\nrequired_directives: [{required}]\n", encoding="utf-8")
    _register(root, "acme", "org-packs/acme")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _team_rule_required(root: Path) -> Path:
    """The governance-in-force scenario's team pack: it requires its own directive ``team-rule``."""
    pack = root / ".kittify" / "team-pack"
    (pack / "drg").mkdir(parents=True)
    (pack / "directives").mkdir()
    (pack / "pack.yaml").write_text(
        "pack_id: 01M4P01D5TWB5FKZGNNQG3900A\nparent_pack: null\nname: team-pack\npack_level: org\nactive_charter: org-charter.yaml\npack_drg: drg/fragment.yaml\n",
        encoding="utf-8",
    )
    (pack / "org-charter.yaml").write_text("org_name: team\nskill_namespace: team\nrequired_directives:\n  - team-rule\n", encoding="utf-8")
    (pack / "drg" / "fragment.yaml").write_text(
        "pack_name: team-pack\nsource_kind: local_path\nsource_ref: .kittify/team-pack\nlayer_index: 1\nprovenance_marker: org\n"
        "nodes:\n  - id: team-rule\n    kind: directives\n    title: Team rule\n    body_path: directives/team-rule.directive.yaml\n",
        encoding="utf-8",
    )
    (pack / "directives" / "team-rule.directive.yaml").write_text(
        'schema_version: "1.0"\nid: TEAM_RULE\ntitle: Team rule\nscope: docs\nintent: >\n  the team-wide default\nenforcement: required\n',
        encoding="utf-8",
    )
    _register(root, "team-pack", ".kittify/team-pack")
    seed_activation_ledger(root, mission_type_activations=["software-dev"])
    return root


def _list(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, ["list", "--repo-root", str(root), *args])


def _flat(result: Result) -> str:
    return " ".join(result.output.split())


def test_human_table_names_the_org_required_id_in_force(tmp_path: Path) -> None:
    result = _list(_built_in_required(tmp_path))

    assert result.exit_code == 0, result.output
    flat = _flat(result)
    assert "(All built-ins — no explicit activation)" in flat
    assert f"{_BUILT_IN_STEM} (DIRECTIVE_001) — in force: required by 'acme'" in flat


@pytest.mark.parametrize("required", ["DIRECTIVE_001", "DIRECTIVE_001, DIRECTIVE_999"], ids=["provided", "id-no-layer-provides-is-not-claimed"])
def test_json_names_the_org_required_id_in_force_and_its_pack(tmp_path: Path, required: str) -> None:
    result = _list(_built_in_required(tmp_path, required=required), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["required_in_force"] == {"directives": [{"id": _BUILT_IN_STEM, "packs": ["acme"]}]}
    directive_row = next(row for row in payload["kinds"] if row["kind"] == "directive")
    assert directive_row["activated"] is None  # the allow list itself stays absent


def test_a_pack_own_required_directive_is_shown_in_force(tmp_path: Path) -> None:
    """The PR-CHARTER-GOVERNANCE-002 shape: the pack requires a directive it defines itself."""
    result = _list(_team_rule_required(tmp_path))

    assert result.exit_code == 0, result.output
    assert f"{_TEAM_RULE} (TEAM_RULE) — in force: required by 'team-pack'" in _flat(result)


def test_an_explicit_allow_list_reports_only_its_omission(tmp_path: Path) -> None:
    """A present list keeps the FR-023 marker; nothing is claimed in force (ruling required_always_active_divergence)."""
    result = _list(_built_in_required(tmp_path, activated_directives=[_OTHER]), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert "required_in_force" not in payload
    assert payload["required_not_in_force"] == {"directives": [{"id": _BUILT_IN_STEM, "packs": ["acme"]}]}


def test_no_org_pack_leaves_the_listing_unchanged(tmp_path: Path) -> None:
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"])

    result = _list(tmp_path, "--json")

    assert result.exit_code == 0, result.output
    assert "required_in_force" not in json.loads(result.stdout)
    assert "in force: required by" not in _list(tmp_path).output
