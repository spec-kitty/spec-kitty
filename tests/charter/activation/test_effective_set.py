"""The one public effective-set seam, ``charter.activation.effective_set`` (FR-015, #4400).

Fixture: a project declaring **two** org packs under ``charter_packs.org.packs``
(each a flat pack with a directive, a tactic and a procedure; pack 2's procedure
and directive declare an ``id:`` that differs from the file stem) plus one
project-layer tactic. The seam must union built-in, both org packs and the
project layer, emit id≠stem artifacts in their ``id:`` spelling, keep directives
in stem spelling, and fail closed (``resolved=False`` + reason) whenever the
offering cannot be determined.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation import effective_set as seam
from charter.activation.activation_engine import EffectiveSet
from charter.activation.effective_set import resolve_effective_sets
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import ActiveCharterManager
from kernel.charter_pack_paths import PROJECT_PACK_ROOT

pytestmark = pytest.mark.unit

ORG1 = "org-packs/acme"
ORG2 = "org-packs/acme-two"
ORG2_PROCEDURE_ID = "acme-release-procedure"
ORG2_PROCEDURE_STEM = "release-procedure"
ORG2_DIRECTIVE_ID = "ACME-002-RELEASE-TRAIN"
ORG2_DIRECTIVE_STEM = "release-train"
PROJECT_TACTIC = "project-local-tactic"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _directive(pack: Path, stem: str, artifact_id: str) -> None:
    _write(
        pack / "directives" / f"{stem}.directive.yaml",
        f'schema_version: "1.0"\nid: {artifact_id}\ntitle: {stem}\nintent: Apply org policy.\nenforcement: required\n',
    )


def _tactic(directory: Path, tactic_id: str) -> None:
    _write(
        directory / f"{tactic_id}.tactic.yaml",
        f'schema_version: "1.0"\nid: {tactic_id}\nname: {tactic_id}\npurpose: Fixture tactic.\nsteps:\n  - title: Act\n    description: Do the thing.\n',
    )


def _procedure(pack: Path, stem: str, procedure_id: str) -> None:
    _write(
        pack / "procedures" / f"{stem}.procedure.yaml",
        'schema_version: "1.0"\n'
        f"id: {procedure_id}\n"
        f"name: {procedure_id} fixture procedure\n"
        "purpose: Fixture procedure.\n"
        "entry_condition: Always.\n"
        "exit_condition: Done.\n"
        "steps:\n  - title: Act\n    description: Do the thing.\n    actor: agent\n",
    )


def _config(project: Path, packs: object) -> None:
    yaml = YAML()
    path = project / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump({"charter_packs": {"org": {"packs": packs}}, "mission_type_activations": ["software-dev"]}, fh)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    _directive(root / ORG1, "acme-001-review-gate", "ACME-001-REVIEW-GATE")
    _tactic(root / ORG1 / "tactics", "acme-pairing")
    _procedure(root / ORG1, "acme-intake", "acme-intake")
    _directive(root / ORG2, ORG2_DIRECTIVE_STEM, ORG2_DIRECTIVE_ID)
    _tactic(root / ORG2 / "tactics", "acme-two-tactic")
    _procedure(root / ORG2, ORG2_PROCEDURE_STEM, ORG2_PROCEDURE_ID)
    _tactic(root / PROJECT_PACK_ROOT / "tactic", PROJECT_TACTIC)
    _config(root, [{"name": "acme", "local_path": ORG1}, {"name": "acme-two", "local_path": ORG2}])
    return root


def _builtin_ids(token: str) -> frozenset[str]:
    return frozenset(ActiveCharterManager().list_available(ProjectContext(), token))


def _resolve(project: Path, keys: Iterable[str]) -> dict[str, EffectiveSet]:
    return dict(resolve_effective_sets(project, keys))


def test_directives_union_builtin_and_both_org_packs_in_stem_spelling(project: Path) -> None:
    result = _resolve(project, ["activated_directives"])["activated_directives"]

    assert result.resolved and result.reason is None
    assert _builtin_ids("directive") <= result.ids
    assert {"acme-001-review-gate", ORG2_DIRECTIVE_STEM} <= result.ids
    assert not [i for i in result.ids if i.startswith("DIRECTIVE_")], "directives stay in config-stem spelling"
    assert ORG2_DIRECTIVE_ID not in result.ids


def test_tactics_union_builtin_org_packs_and_project(project: Path) -> None:
    result = _resolve(project, ["activated_tactics"])["activated_tactics"]

    assert result.resolved
    assert _builtin_ids("tactic") <= result.ids
    assert {"acme-pairing", "acme-two-tactic", PROJECT_TACTIC} <= result.ids


def test_procedure_whose_id_differs_from_its_stem_appears_in_id_spelling(project: Path) -> None:
    result = _resolve(project, ["activated_procedures"])["activated_procedures"]

    assert result.resolved
    assert _builtin_ids("procedure") <= result.ids
    assert {"acme-intake", ORG2_PROCEDURE_ID} <= result.ids


def test_agent_profiles_cover_the_builtin_catalogue(project: Path) -> None:
    result = _resolve(project, ["activated_agent_profiles"])["activated_agent_profiles"]

    assert result.resolved
    assert _builtin_ids("agent-profile") <= result.ids
    assert "architect-alphonso" in result.ids


def test_one_call_resolves_several_keys_and_deduplicates(project: Path) -> None:
    results = _resolve(project, ["activated_tactics", "activated_paradigms", "activated_tactics"])

    assert list(results) == ["activated_tactics", "activated_paradigms"]
    assert all(entry.resolved for entry in results.values())
    assert results["activated_paradigms"].kind == "paradigm"


def test_skill_is_never_resolvable(project: Path) -> None:
    result = _resolve(project, ["activated_skills"])["activated_skills"]

    assert not result.resolved
    assert result.ids == frozenset()
    assert result.reason is not None and "required-only" in result.reason


def test_mission_type_is_never_resolvable_but_carries_the_chain_fallback(project: Path) -> None:
    for name in ("acme", "acme-two"):
        _write(project / "org-packs" / name / "mission_types" / f"{name}-mt.yaml", f"schema_version: 1\nid: {name}-mt\ndisplay_name: {name}\n")

    result = _resolve(project, ["mission_type_activations"])["mission_type_activations"]

    assert not result.resolved and result.ids == frozenset()
    assert result.reason is not None and "activation ledger" in result.reason
    assert {"software-dev", "acme-mt", "acme-two-mt"} <= result.fallback_ids


def test_unknown_key_is_refused(project: Path) -> None:
    with pytest.raises(ValueError, match="Unknown activation key"):
        _resolve(project, ["activated_nonsense"])


def test_resolved_set_and_skill_carry_no_fallback(project: Path) -> None:
    results = _resolve(project, ["activated_tactics", "activated_skills"])

    assert results["activated_tactics"].fallback_ids == frozenset()
    assert results["activated_skills"].fallback_ids == frozenset(), "a required-only kind never seeds the catalogue"


def test_missing_middle_org_root_fallback_spans_every_readable_root(project: Path) -> None:
    _tactic(project / "org-packs" / "c" / "tactics", "org-c-tactic")
    _config(project, [{"name": "acme", "local_path": ORG1}, {"name": "gone", "local_path": "org-packs/does-not-exist"}, {"name": "c", "local_path": "org-packs/c"}])

    result = _resolve(project, ["activated_tactics"])["activated_tactics"]

    assert not result.resolved
    assert _builtin_ids("tactic") <= result.fallback_ids
    assert {"acme-pairing", "org-c-tactic", PROJECT_TACTIC} <= result.fallback_ids


def test_service_build_failure_fallback_spans_both_org_packs(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import charter.activation.active_charter_service_builder as builder

    def broken(repo_root: Path) -> None:
        raise RuntimeError(f"cannot build for {repo_root.name}")

    monkeypatch.setattr(builder, "build_active_charter_service", broken)

    result = _resolve(project, ["activated_tactics"])["activated_tactics"]

    assert not result.resolved
    assert {"acme-pairing", "acme-two-tactic", PROJECT_TACTIC} <= result.fallback_ids


def test_malformed_registry_fallback_keeps_builtin_and_project(project: Path) -> None:
    _config(project, 7)

    result = _resolve(project, ["activated_tactics"])["activated_tactics"]

    assert not result.resolved
    assert _builtin_ids("tactic") | {PROJECT_TACTIC} <= result.fallback_ids


def test_fallback_skips_an_org_root_that_raises_on_scan(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = ActiveCharterManager.list_available

    def exploding(self: ActiveCharterManager, ctx: ProjectContext, kind: str, *, layer_roots: dict[str, Path] | None = None) -> frozenset[str]:
        if layer_roots and "org" in layer_roots and layer_roots["org"].name == "acme-two":
            raise OSError("permission denied")
        return frozenset(real(self, ctx, kind, layer_roots=layer_roots))

    monkeypatch.setattr(ActiveCharterManager, "list_available", exploding)

    result = _resolve(project, ["activated_tactics"])["activated_tactics"]

    assert not result.resolved
    assert result.reason is not None and "permission denied" in result.reason
    # One unreadable root does not drop the rest; the service (which built) still contributes.
    assert {"acme-pairing", PROJECT_TACTIC} <= result.fallback_ids
    assert _builtin_ids("tactic") <= result.fallback_ids


def test_malformed_org_registry_is_unresolved(project: Path) -> None:
    _config(project, 7)

    result = _resolve(project, ["activated_tactics"])["activated_tactics"]

    assert not result.resolved
    assert result.reason is not None and "org pack registry" in result.reason


def test_missing_declared_org_root_is_unresolved(project: Path) -> None:
    _config(project, [{"name": "acme", "local_path": ORG1}, {"name": "gone", "local_path": "org-packs/does-not-exist"}])

    results = _resolve(project, ["activated_directives", "activated_tactics"])

    for entry in results.values():
        assert not entry.resolved
        assert entry.reason is not None and "does-not-exist" in entry.reason


def test_org_root_that_raises_on_scan_is_unresolved(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = ActiveCharterManager.list_available

    def exploding(self: ActiveCharterManager, ctx: ProjectContext, kind: str, *, layer_roots: dict[str, Path] | None = None) -> frozenset[str]:
        if layer_roots and "org" in layer_roots and layer_roots["org"].name == "acme-two":
            raise OSError("permission denied")
        return frozenset(real(self, ctx, kind, layer_roots=layer_roots))

    monkeypatch.setattr(ActiveCharterManager, "list_available", exploding)

    result = _resolve(project, ["activated_tactics"])["activated_tactics"]

    assert not result.resolved
    assert result.reason is not None and "permission denied" in result.reason


def test_service_build_failure_is_unresolved(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import charter.activation.active_charter_service_builder as builder

    def broken(repo_root: Path) -> None:
        raise RuntimeError(f"cannot build for {repo_root.name}")

    monkeypatch.setattr(builder, "build_active_charter_service", broken)

    result = _resolve(project, ["activated_procedures"])["activated_procedures"]

    assert not result.resolved
    assert result.reason is not None and "doctrine service" in result.reason


def test_directives_alone_do_not_build_the_service(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import charter.activation.active_charter_service_builder as builder

    def broken(repo_root: Path) -> None:
        raise AssertionError(f"service built for {repo_root.name}")

    monkeypatch.setattr(builder, "build_active_charter_service", broken)

    assert _resolve(project, ["activated_directives"])["activated_directives"].resolved


def test_layer_root_failure_is_unresolved(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(repo_root: Path) -> dict[str, Path]:
        raise OSError(f"unreadable {repo_root.name}")

    monkeypatch.setattr(seam, "resolve_layer_roots", broken)

    result = _resolve(project, ["activated_directives"])["activated_directives"]

    assert not result.resolved
    assert result.reason is not None and "layer roots" in result.reason


def test_empty_set_while_builtins_ship_is_unresolved(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActiveCharterManager, "list_available", lambda self, ctx, kind, *, layer_roots=None: frozenset())

    result = _resolve(project, ["activated_directives"])["activated_directives"]

    assert not result.resolved
    assert result.reason == "empty effective set while built-in artifacts of directive ship"


def test_kind_without_shipped_content_resolves_empty(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActiveCharterManager, "list_available", lambda self, ctx, kind, *, layer_roots=None: frozenset())
    monkeypatch.setattr(seam, "_service_ids", lambda offering, yaml_key: set())

    result = _resolve(project, ["activated_mission_step_contracts"])["activated_mission_step_contracts"]

    assert result.resolved
    assert result.ids == frozenset()


def test_service_attribute_that_is_not_a_mapping_contributes_nothing(project: Path) -> None:
    offering = seam._Offering(layer_roots={}, org_roots=(), service=object())

    assert seam._service_ids(offering, "activated_procedures") == set()


def test_project_without_org_packs_resolves(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()

    result = resolve_effective_sets(tmp_path, ["activated_paradigms"])["activated_paradigms"]

    assert result.resolved
    assert _builtin_ids("paradigm") <= result.ids
