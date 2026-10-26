"""``charter list`` names the org-required ids in force on a row with no allow list of its own (#6417).

An absent ``activated_<kind>`` key leaves the org required floor in force, and
``doctor charter-packs`` already says so; the listing used to print only
``(All built-ins — no explicit activation)``. The table now adds one
``<id> (required by <pack>)`` line per in-force required id, and ``--json``
(contract ``schema_version: "2"``) carries those ids in ``activated`` with
``allow_list_present: false``. An id no layer provides is not claimed in force,
and the explicit-allow-list marker of FR-023 is unchanged.

The scenario-shaped fixture ports ``CharterSteps`` (acceptance-jvm,
``PR-CHARTER-GOVERNANCE-002``) with the rule where an org layer reads it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_ALL_BUILT_INS = "(All built-ins — no explicit activation)"
_NOT_IN_FORCE = "required (not in force: explicit allow list omits it)"
_REQUIRED_STEM = "001-architectural-integrity-standard"
_OTHER = "003-decision-documentation-requirement"
_TEAM_RULE = "team-rule"

_TEAM_PACK_DIR = ".kittify/team-pack"
_RULE_FILE = "directives/team-rule.directive.yaml"
_DRIFTED_RULE_FILE = "directive/team-rule.directive.yaml"
_TEAM_RULE_BODY = 'schema_version: "1.0"\nid: TEAM_RULE\ntitle: Team rule\nscope: docs\nintent: >\n  the team-wide default\nenforcement: required\n'


def _acme_project(root: Path, **ledger: list[str]) -> Path:
    """An org pack ``acme`` requiring the built-in ``DIRECTIVE_001``."""
    pack = root / "org-packs" / "acme"
    pack.mkdir(parents=True)
    (pack / "org-charter.yaml").write_text("schema_version: 1\nrequired_directives: [DIRECTIVE_001]\n", encoding="utf-8")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: org-packs/acme\n", encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _team_pack_project(root: Path, rule_file: str) -> Path:
    """The ``CharterSteps`` team pack requiring ``team-rule``, with the rule body at *rule_file*."""
    pack = root / _TEAM_PACK_DIR
    (pack / "drg").mkdir(parents=True)
    (pack / "pack.yaml").write_text(
        "pack_id: 01M4P01D5TWB5FKZGNNQG3900A\nparent_pack: null\nname: team-pack\npack_level: org\nactive_charter: org-charter.yaml\npack_drg: drg/fragment.yaml\n",
        encoding="utf-8",
    )
    (pack / "org-charter.yaml").write_text("org_name: team\nskill_namespace: team\nrequired_directives:\n  - team-rule\n", encoding="utf-8")
    (pack / "drg" / "fragment.yaml").write_text(
        f"pack_name: team-pack\nsource_kind: local_path\nsource_ref: {_TEAM_PACK_DIR}\nlayer_index: 1\nprovenance_marker: org\n"
        f"nodes:\n  - id: team-rule\n    kind: directives\n    title: Team rule\n    body_path: {rule_file}\n",
        encoding="utf-8",
    )
    rule = pack / rule_file
    rule.parent.mkdir(parents=True)
    rule.write_text(_TEAM_RULE_BODY, encoding="utf-8")
    (root / ".kittify" / "config.yaml").write_text(
        f"charter_packs:\n  org:\n    packs:\n    - name: team-pack\n      local_path: {_TEAM_PACK_DIR}\n", encoding="utf-8"
    )
    seed_activation_ledger(root, mission_type_activations=["software-dev"])
    return root


def _list(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, ["list", "--repo-root", str(root), *args])


def _flat(result: Result) -> str:
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split())


def _payload(root: Path) -> dict[str, Any]:
    result = _list(root, "--json")
    assert result.exit_code == 0, result.output
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def _row(payload: dict[str, Any], kind: str) -> dict[str, Any]:
    rows = {row["kind"]: row for row in payload["kinds"]}
    row: dict[str, Any] = rows[kind]
    return row


def _directive_line(flat_table: str) -> str:
    """The directive row of the flattened table (up to the next kind row)."""
    start = flat_table.index("│ directive ")
    end = flat_table.index("│ tactic ", start)
    return flat_table[start:end]


def test_the_table_names_a_built_in_required_directive_in_force(tmp_path: Path) -> None:
    flat = _flat(_list(_acme_project(tmp_path)))

    directive = _directive_line(flat)
    assert _ALL_BUILT_INS in directive
    assert _REQUIRED_STEM in directive
    assert "required by 'acme'" in directive


def test_json_carries_the_in_force_required_ids_and_the_contract_version(tmp_path: Path) -> None:
    payload = _payload(_acme_project(tmp_path))

    assert payload["schema_version"] == "2"
    directive = _row(payload, "directive")
    assert directive["activated"] == [_REQUIRED_STEM]
    assert directive["allow_list_present"] is False


def test_every_row_says_whether_the_project_has_its_own_allow_list(tmp_path: Path) -> None:
    payload = _payload(_acme_project(tmp_path, activated_tactics=["tdd-red-green-refactor"]))

    for row in payload["kinds"]:
        assert isinstance(row["allow_list_present"], bool), row
    assert _row(payload, "tactic") == {**_row(payload, "tactic"), "activated": ["tdd-red-green-refactor"], "allow_list_present": True}
    assert _row(payload, "mission-type")["allow_list_present"] is True
    styleguide = _row(payload, "styleguide")
    assert styleguide["allow_list_present"] is False
    assert styleguide["activated"] is None, "a row without in-force required ids keeps activated: null"


def test_an_explicit_list_keeps_the_fr023_marker_and_names_nothing_in_force(tmp_path: Path) -> None:
    root = _acme_project(tmp_path, activated_directives=[_OTHER])

    directive = _directive_line(_flat(_list(root)))
    assert _NOT_IN_FORCE in directive
    assert "(required by 'acme')" not in directive
    row = _row(_payload(root), "directive")
    assert row["activated"] == [_OTHER]
    assert row["allow_list_present"] is True


def test_the_team_pack_rule_is_in_force_on_the_default_directive_row(tmp_path: Path) -> None:
    """``PR-CHARTER-GOVERNANCE-002``: the org pack provides the rule it requires."""
    root = _team_pack_project(tmp_path, _RULE_FILE)

    directive = _directive_line(_flat(_list(root)))
    assert _TEAM_RULE in directive
    assert "required by 'team-pack'" in directive
    assert _row(_payload(root), "directive")["activated"] == [_TEAM_RULE]


def test_a_required_rule_no_layer_provides_is_not_claimed_in_force(tmp_path: Path) -> None:
    """Negative control (#6417 fixture drift): ``directive/`` (singular) is no layer, so nothing is in force."""
    root = _team_pack_project(tmp_path, _DRIFTED_RULE_FILE)

    directive = _directive_line(_flat(_list(root)))
    assert _TEAM_RULE not in directive
    row = _row(_payload(root), "directive")
    assert row["activated"] is None
    assert row["allow_list_present"] is False


_TEAM_SKILL_BODY = (
    'schema_version: "1.0"\nid: team-report\ntitle: Team report\nnamespace: acme\n'
    "command:\n  summary: Produce the team report\nbody: >\n  Produce the team report.\n"
)


def test_a_required_skill_the_pack_provides_is_named_once_on_the_skill_row(tmp_path: Path) -> None:
    """FR-007: ``skill`` materialises its floor as the allow state; the row still names it once."""
    root = _acme_project(tmp_path)
    pack = root / "org-packs" / "acme"
    (pack / "org-charter.yaml").write_text("schema_version: 1\nskill_namespace: acme\nrequired_skills: [team-report]\n", encoding="utf-8")
    (pack / "skills").mkdir()
    (pack / "skills" / "team-report.skill.yaml").write_text(_TEAM_SKILL_BODY, encoding="utf-8")

    flat = _flat(_list(root))
    skill_line = flat[flat.index("│ skill ") :]
    assert skill_line.count("team-report") == 1, skill_line
    assert "required by 'acme'" in skill_line
    row = _row(_payload(root), "skill")
    assert row["activated"] == ["team-report"]
    assert row["allow_list_present"] is False
