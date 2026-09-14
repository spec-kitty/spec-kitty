"""Directive identities map to activation stems across the full layer chain."""

from pathlib import Path

import pytest

from charter.activation.catalog import resolve_doctrine_root
from charter.activation.kind_vocabulary import ArtifactKind, UnknownArtifactIdError, resolve_artifact_urn, resolve_config_id
from specify_cli.doctrine.org_charter import _normalize_required_ids
from specify_cli.upgrade.migrations.m_unify_charter_activation import resolve_selected_id_to_stem

pytestmark = pytest.mark.unit


def _directive(directory: Path, stem: str, identity: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.directive.yaml").write_text(f'schema_version: "1.0"\nid: {identity}\ntitle: {stem}\nintent: Apply policy.\nenforcement: required\n')


@pytest.mark.parametrize("project_override", [False, True])
def test_declared_id_maps_to_highest_layer_stem(tmp_path: Path, project_override: bool) -> None:
    orgs = [tmp_path / "company", tmp_path / "team"]
    identity = "ACME-001-FOO"
    for org in orgs:
        _directive(org / "directives", org.name, identity)
    project = tmp_path / ".kittify"
    if project_override:
        _directive(project / "doctrine/directive", "project", identity)
    kwargs = {"doctrine_root": resolve_doctrine_root(), "org_roots": orgs, "layer_roots": {"project": project}}
    expected = "project" if project_override else "team"
    assert resolve_config_id(f"directive:{identity}", **kwargs) == expected
    assert resolve_selected_id_to_stem(ArtifactKind.DIRECTIVE, identity, **kwargs) == expected
    assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, identity, **kwargs) == f"directive:{identity}"


def test_unknown_activated_directive_still_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(UnknownArtifactIdError, match="no-such-policy"):
        resolve_artifact_urn(ArtifactKind.DIRECTIVE, "no-such-policy", doctrine_root=tmp_path)


def test_other_kind_does_not_accept_declared_id_as_config_stem(tmp_path: Path) -> None:
    (tmp_path / "paradigms").mkdir()
    (tmp_path / "paradigms/policy.paradigm.yaml").write_text("id: DECLARED-PARADIGM\n")
    with pytest.raises(UnknownArtifactIdError, match="DECLARED-PARADIGM"):
        resolve_artifact_urn(ArtifactKind.PARADIGM, "DECLARED-PARADIGM", doctrine_root=tmp_path, org_roots=[tmp_path])


def test_selection_distinguishes_declared_identity_from_coincident_stem(tmp_path: Path) -> None:
    _directive(tmp_path / "directives", "chosen", "ACME-001-FOO")
    _directive(tmp_path / "directives", "ACME-001-FOO", "OTHER-POLICY")
    kwargs = {"doctrine_root": resolve_doctrine_root(), "org_roots": [tmp_path]}
    assert resolve_selected_id_to_stem(ArtifactKind.DIRECTIVE, "ACME-001-FOO", **kwargs) == "chosen"
    # Already-persisted stems keep their established meaning during compilation.
    assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, "ACME-001-FOO", **kwargs) == "directive:OTHER-POLICY"


def test_other_kind_selection_keeps_stem_first_contract(tmp_path: Path) -> None:
    (tmp_path / "paradigms").mkdir()
    (tmp_path / "paradigms/chosen.paradigm.yaml").write_text("id: DECLARED-PARADIGM\n")
    (tmp_path / "paradigms/DECLARED-PARADIGM.paradigm.yaml").write_text("id: OTHER-PARADIGM\n")
    assert resolve_selected_id_to_stem(ArtifactKind.PARADIGM, "DECLARED-PARADIGM", doctrine_root=tmp_path, org_roots=[tmp_path]) == "DECLARED-PARADIGM"


@pytest.mark.parametrize("raw_id", ["", "UNKNOWN-DIRECTIVE"])
def test_unresolvable_selection_returns_none(tmp_path: Path, raw_id: str) -> None:
    assert resolve_selected_id_to_stem(ArtifactKind.DIRECTIVE, raw_id, doctrine_root=tmp_path) is None


def test_project_identity_wins_regardless_of_layer_map_order(tmp_path: Path) -> None:
    project = tmp_path / ".kittify"
    org = tmp_path / "org"
    _directive(project / "doctrine/directive", "project", "ACME-001-FOO")
    _directive(org / "doctrine/directives/org", "org", "ACME-001-FOO")
    assert (
        resolve_config_id(
            "directive:ACME-001-FOO",
            doctrine_root=tmp_path,
            layer_roots={"project": project, "org": org},
        )
        == "project"
    )


@pytest.mark.parametrize("project_override", [False, True])
def test_colliding_highest_layer_stem_uses_representable_lower_stem(tmp_path: Path, project_override: bool) -> None:
    orgs = [tmp_path / "company", tmp_path / "team"]
    _directive(orgs[0] / "directives", "original", "CHOSEN-POLICY")
    _directive(orgs[0] / "directives", "shared", "OTHER-POLICY")
    _directive(orgs[1] / "directives", "shared", "CHOSEN-POLICY")
    project = tmp_path / ".kittify"
    if project_override:
        _directive(project / "doctrine/directive", "shared", "CHOSEN-POLICY")
    kwargs = {"doctrine_root": tmp_path / "builtin", "org_roots": orgs, "layer_roots": {"project": project}}
    token = resolve_config_id("directive:CHOSEN-POLICY", **kwargs)
    assert token == "original"
    assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, token, **kwargs) == "directive:CHOSEN-POLICY"


@pytest.mark.parametrize("identity_also_stem", [False, True])
def test_unrepresentable_directive_stem_is_rejected(tmp_path: Path, identity_also_stem: bool) -> None:
    orgs = [tmp_path / "company", tmp_path / "team"]
    _directive(orgs[0] / "directives", "shared", "OTHER-POLICY")
    _directive(orgs[1] / "directives", "shared", "CHOSEN-POLICY")
    if identity_also_stem:
        _directive(orgs[0] / "directives", "CHOSEN-POLICY", "OTHER-POLICY")
    kwargs = {"doctrine_root": tmp_path / "builtin", "org_roots": orgs}
    with pytest.raises(ValueError, match="cannot represent"):
        resolve_config_id("directive:CHOSEN-POLICY", **kwargs)
    with pytest.raises(ValueError, match="cannot represent"):
        resolve_selected_id_to_stem(ArtifactKind.DIRECTIVE, "CHOSEN-POLICY", **kwargs)
    with pytest.raises(ValueError, match="cannot represent"):
        _normalize_required_ids("directives", ["CHOSEN-POLICY"], layer_roots={}, **kwargs)
