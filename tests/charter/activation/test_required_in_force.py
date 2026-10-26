"""``required_in_force``: the org-required ids in force while a kind's allow key is absent (#6417).

``charter list`` renders this reader on a row whose kind has no allow list of its
own. In force is decided by the effective-set authority
(:meth:`PackContext.effective_ids`) over what the layers provide, never by a
second membership computation: the required floor beats an exclusion, and a
required id no layer provides is not claimed in force. An explicit allow list is
FR-023's case (:func:`required_not_in_force`), so it yields nothing here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.activation_ledger import RequiredInForce, required_in_force
from charter.activation.pack_manager import ActiveCharterManager
from charter.offering.artifact_kinds import ArtifactKind
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_BUILT_IN_REQUIRED = "001-architectural-integrity-standard"
_OTHER = "003-decision-documentation-requirement"
_ORG_RULE = "team-rule"
_ORG_RULE_BODY = 'schema_version: "1.0"\nid: TEAM_RULE\ntitle: Team rule\nintent: >\n  the team-wide default\nenforcement: required\n'
_ORG_SKILL_BODY = (
    'schema_version: "1.0"\nid: team-report\ntitle: Team report\nnamespace: acme\n'
    "command:\n  summary: Produce the team report\nbody: >\n  Produce the team report.\n"
)


def _project(root: Path, org_charter: str, **ledger: list[str]) -> Path:
    """A project with the org pack ``acme`` (``org-packs/acme``) whose ``org-charter.yaml`` is *org_charter*."""
    pack = root / "org-packs" / "acme"
    pack.mkdir(parents=True)
    (pack / "org-charter.yaml").write_text(org_charter, encoding="utf-8")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text(
        "charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: org-packs/acme\n", encoding="utf-8"
    )
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _ids(entries: tuple[RequiredInForce, ...]) -> list[tuple[ArtifactKind, str]]:
    return [(entry.kind, entry.artifact_id) for entry in entries]


def test_an_absent_key_puts_the_built_in_required_directive_in_force(tmp_path: Path) -> None:
    entries = required_in_force(_project(tmp_path, "schema_version: 1\nrequired_directives: [DIRECTIVE_001]\n"))

    assert _ids(entries) == [(ArtifactKind.DIRECTIVE, _BUILT_IN_REQUIRED)]
    assert entries[0].pack_names == ("acme",)
    assert entries[0].describe_packs() == "'acme'"


def test_an_explicit_allow_list_is_not_this_readers_case(tmp_path: Path) -> None:
    """FR-023 owns a present list, even one that omits the required id."""
    root = _project(tmp_path, "schema_version: 1\nrequired_directives: [DIRECTIVE_001]\n", activated_directives=[_OTHER])

    assert required_in_force(root) == ()


def test_the_required_floor_beats_an_exclusion(tmp_path: Path) -> None:
    root = _project(tmp_path, "schema_version: 1\nrequired_directives: [DIRECTIVE_001]\n", deactivated_directives=[_BUILT_IN_REQUIRED])

    assert _ids(required_in_force(root)) == [(ArtifactKind.DIRECTIVE, _BUILT_IN_REQUIRED)]


def test_a_required_id_no_layer_provides_is_not_claimed_in_force(tmp_path: Path) -> None:
    root = _project(tmp_path, "schema_version: 1\nrequired_directives: [DIRECTIVE_001, 999-nowhere]\n")

    assert _ids(required_in_force(root)) == [(ArtifactKind.DIRECTIVE, _BUILT_IN_REQUIRED)]


def test_a_directive_the_org_pack_provides_is_in_force_by_its_stem(tmp_path: Path) -> None:
    root = _project(tmp_path, f"schema_version: 1\nrequired_directives: [{_ORG_RULE}]\n")
    directives = root / "org-packs" / "acme" / "directives"
    directives.mkdir()
    (directives / f"{_ORG_RULE}.directive.yaml").write_text(_ORG_RULE_BODY, encoding="utf-8")

    assert _ids(required_in_force(root)) == [(ArtifactKind.DIRECTIVE, _ORG_RULE)]


def test_an_org_pack_rule_in_an_unread_folder_is_not_in_force(tmp_path: Path) -> None:
    """Negative control for the fixture drift of #6417: ``directive/`` (singular) is no layer."""
    root = _project(tmp_path, f"schema_version: 1\nrequired_directives: [{_ORG_RULE}]\n")
    unread = root / "org-packs" / "acme" / "directive"
    unread.mkdir()
    (unread / f"{_ORG_RULE}.directive.yaml").write_text(_ORG_RULE_BODY, encoding="utf-8")

    assert required_in_force(root) == ()


def test_no_floor_reads_no_availability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("availability scanned without a required floor")

    monkeypatch.setattr(ActiveCharterManager, "list_available_detailed", _refuse)

    assert required_in_force(_project(tmp_path, "schema_version: 1\norg_name: acme\n")) == ()


def test_an_unreadable_floor_is_lenient_when_not_strict(tmp_path: Path) -> None:
    root = _project(tmp_path, "required_directives: [DIRECTIVE_001\n  : : not yaml\n")

    assert required_in_force(root, strict=False) == ()


def test_a_required_skill_the_pack_provides_is_listed_once(tmp_path: Path) -> None:
    root = _project(tmp_path, "schema_version: 1\nskill_namespace: acme\nrequired_skills: [team-report]\n")
    skills = root / "org-packs" / "acme" / "skills"
    skills.mkdir()
    (skills / "team-report.skill.yaml").write_text(_ORG_SKILL_BODY, encoding="utf-8")

    assert _ids(required_in_force(root)) == [(ArtifactKind.SKILL, "team-report")]


def test_a_required_skill_no_layer_provides_is_not_in_force(tmp_path: Path) -> None:
    root = _project(tmp_path, "schema_version: 1\nskill_namespace: acme\nrequired_skills: [team-report]\n")

    assert required_in_force(root) == ()
