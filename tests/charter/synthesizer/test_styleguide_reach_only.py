"""#6442 -- synthesized testing / quality-gate / documentation styleguides are reach-only.

A styleguide sourced from its directive (``testing_philosophy`` -> DIRECTIVE_034,
``quality_gates`` -> DIRECTIVE_030, ``documentation_policy`` -> DIRECTIVE_037) is linked
FROM that directive by ``directive --suggests--> styleguide`` and reaches action context
only while the directive is in force. An operator's removal sticks.

Every test runs the production path at the narrowest seam: interview mapping ->
``build_targets`` -> ``emit_project_layer`` for the edge; the real overlay on disk for
``_direct_root_urns`` and the action bundle; the real append helper for removal-sticks.
Each absence assertion is paired with a positive control on the same fixture.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from charter.activation.action_governance_bundle import _load_action_governance_bundle
from charter.activation.compiler import ConfigActivatedRoots, _direct_root_urns
from charter.activation.pack_context import PackContext
from charter.activation.synthesizer.interview_mapping import resolve_sections
from charter.activation.synthesizer.project_drg import emit_project_layer
from charter.activation.synthesizer.request import SynthesisTarget
from charter.activation.synthesizer.targets import build_targets
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast, pytest.mark.regression]

_MISSION_TYPE = "software-dev"
_ACTION = "implement"
_ACTION_URN = f"action:{_MISSION_TYPE}/{_ACTION}"

_TESTING_DIRECTIVE = "DIRECTIVE_034"
_TESTING_DIRECTIVE_STEM = "034-test-first-development"
_TESTING_STYLEGUIDE = "testing-style-guide"
_LANGUAGE_STYLEGUIDE = "python-style-guide"
_SOURCE_BY_SECTION = {
    "testing_philosophy": ("DIRECTIVE_034", "testing-style-guide"),
    "quality_gates": ("DIRECTIVE_030", "quality-gates-style-guide"),
    "documentation_policy": ("DIRECTIVE_037", "documentation-policy-style-guide"),
}
_CONTROL = "adversarial-qa-handoff"
_ALL_KINDS = frozenset({"directives", "tactics", "paradigms", "styleguides", "toolguides", "procedures"})
_GENERATED_AT = "2026-10-19T00:00:00+00:00"

_SNAPSHOT = {
    "testing_philosophy": "test-driven development",
    "quality_gates": "ruff and mypy must pass",
    "documentation_policy": "ADR for every decision",
    "language_scope": ["python"],
}


def _shipped_graph(directives: tuple[str, ...]) -> DRGGraph:
    nodes = [DRGNode(urn=f"directive:{d}", kind=NodeKind.DIRECTIVE, label=d) for d in directives]
    return DRGGraph(schema_version="1.0", generated_at=_GENERATED_AT, generated_by="test", nodes=nodes, edges=[])


def _drg_snapshot(directives: tuple[str, ...]) -> dict[str, object]:
    return {"nodes": [{"urn": f"directive:{d}", "kind": "directive"} for d in directives], "edges": [], "schema_version": "1.0"}


def _targets(directives: tuple[str, ...]) -> list[SynthesisTarget]:
    return build_targets(_SNAPSHOT, resolve_sections(_SNAPSHOT), _drg_snapshot(directives))


def _overlay(directives: tuple[str, ...] = tuple(d for d, _ in _SOURCE_BY_SECTION.values())) -> DRGGraph:
    """The project overlay synthesis really emits for the full interview."""
    return emit_project_layer(_targets(directives), "test", _shipped_graph(directives))


def _install_with_sourced(repo_root: Path, slug: str) -> None:
    """Install the full overlay plus *slug* as one more styleguide sourced from DIRECTIVE_034 (reach-only)."""
    from charter.activation.synthesizer.reconcile import synthesized_edge_reason

    overlay = _overlay()
    node = DRGNode(urn=f"styleguide:{slug}", kind=NodeKind.STYLEGUIDE, label=slug)
    edge = DRGEdge(
        source=f"directive:{_TESTING_DIRECTIVE}",
        target=node.urn,
        relation=Relation.SUGGESTS,
        reason=synthesized_edge_reason("styleguide", slug),
    )
    _install_overlay(repo_root, overlay.model_copy(update={"nodes": [*overlay.nodes, node], "edges": [*overlay.edges, edge]}))


def _install_overlay(repo_root: Path, overlay: DRGGraph) -> None:
    """Write *overlay* as the project pack and register its styleguides in the synthesis manifest."""
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, ManifestArtifactEntry, SynthesisManifest, finalize_manifest

    pack = repo_root / ".kittify" / "charter-packs"
    (pack / "styleguide").mkdir(parents=True, exist_ok=True)
    for node in overlay.nodes:
        if node.kind is NodeKind.STYLEGUIDE:  # the identity index resolves activation tokens through real artifacts
            slug = node.urn.split(":", 1)[1]
            body = {"id": slug, "schema_version": "1.0", "title": slug, "scope": "testing", "principles": ["Fixture principle."]}
            (pack / "styleguide" / f"{slug}.styleguide.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")
    (pack / "graph.yaml").write_text(yaml.safe_dump(overlay.model_dump(mode="json", exclude_none=True)), encoding="utf-8")
    entries = [
        ManifestArtifactEntry(
            kind=node.kind.value,
            slug=node.urn.split(":", 1)[1],
            path=f".kittify/charter-packs/{node.kind.value}/{node.urn.split(':', 1)[1]}.yaml",
            provenance_path=f".kittify/charter/provenance/{node.kind.value}-{node.urn.split(':', 1)[1]}.yaml",
            content_hash="a" * 64,
        )
        for node in overlay.nodes
        if node.kind in (NodeKind.STYLEGUIDE, NodeKind.TACTIC)
    ]
    manifest = finalize_manifest(
        SynthesisManifest(
            mission_id=None,
            created_at=_GENERATED_AT,
            run_id="01TESTRUNID0000000000000001",
            adapter_id="test",
            adapter_version="0.0.0",
            synthesizer_version="0.0.0",
            manifest_hash="0" * 64,
            artifacts=entries,
        )
    )
    target = repo_root / MANIFEST_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(manifest.model_dump(mode="json")), encoding="utf-8")


def _roots(**kinds: list[str]) -> ConfigActivatedRoots:
    empty = {f.name: [] for f in dataclasses.fields(ConfigActivatedRoots)}
    return ConfigActivatedRoots(**{**empty, **kinds})


def _edges_into(overlay: DRGGraph, urn: str) -> list[DRGEdge]:
    return [e for e in overlay.edges if e.target == urn]


# --------------------------------------------------------------------------
# Edge emission (scenarios 1, 6) and no dangling URN
# --------------------------------------------------------------------------


@pytest.mark.parametrize("section", sorted(_SOURCE_BY_SECTION))
def test_table_section_emits_directive_suggests_styleguide_edge(section: str) -> None:
    directive, slug = _SOURCE_BY_SECTION[section]

    overlay = _overlay()

    edges = _edges_into(overlay, f"styleguide:{slug}")
    assert [(e.source, e.relation) for e in edges] == [(f"directive:{directive}", Relation.SUGGESTS)]
    assert edges[0].reason  # stamped as a synthesized edge


def test_testing_tactic_gets_no_directive_source() -> None:
    """Control: the same section's tactic is unsourced; only the styleguide carries the table source."""
    overlay = _overlay()

    assert _edges_into(overlay, "tactic:testing-philosophy-tactic") == []
    assert _edges_into(overlay, f"styleguide:{_TESTING_STYLEGUIDE}") != []


def test_language_scope_styleguide_has_no_source_edge() -> None:
    overlay = _overlay()

    assert f"styleguide:{_LANGUAGE_STYLEGUIDE}" in {n.urn for n in overlay.nodes}
    assert _edges_into(overlay, f"styleguide:{_LANGUAGE_STYLEGUIDE}") == []
    assert [e for e in overlay.edges if e.source == f"styleguide:{_LANGUAGE_STYLEGUIDE}"] == []


def test_snapshot_without_the_table_directive_omits_the_edge_and_does_not_raise() -> None:
    overlay = _overlay(directives=("DIRECTIVE_030", "DIRECTIVE_037"))  # DIRECTIVE_034 absent

    assert f"styleguide:{_TESTING_STYLEGUIDE}" in {n.urn for n in overlay.nodes}
    assert _edges_into(overlay, f"styleguide:{_TESTING_STYLEGUIDE}") == []
    assert _edges_into(overlay, "styleguide:quality-gates-style-guide") != []  # control: present directives still link


# --------------------------------------------------------------------------
# The red-first case: the compiled-references root (scenario 2, 6)
# --------------------------------------------------------------------------


def test_explicit_list_styleguide_is_not_a_compiled_reference_root(tmp_path: Path) -> None:
    """Explicit ``activated_styleguides`` containing the synthesized styleguide, DIRECTIVE_034 not active."""
    _install_overlay(tmp_path, _overlay())
    roots = _roots(styleguides=[_TESTING_STYLEGUIDE, _LANGUAGE_STYLEGUIDE, _CONTROL], directives=[])

    urns = _direct_root_urns(roots, tmp_path)

    assert f"styleguide:{_TESTING_STYLEGUIDE}" not in urns
    assert f"styleguide:{_LANGUAGE_STYLEGUIDE}" in urns  # unsourced language styleguide is still rooted
    assert f"styleguide:{_CONTROL}" in urns  # hand-authored styleguide is still rooted


def test_org_required_synthesized_styleguide_stays_a_root(tmp_path: Path) -> None:
    _install_overlay(tmp_path, _overlay())
    roots = _roots(styleguides=[_TESTING_STYLEGUIDE])

    with patch("charter.activation.synthesizer.reach_only.read_org_required_ids", return_value=[_TESTING_STYLEGUIDE]):
        assert f"styleguide:{_TESTING_STYLEGUIDE}" in _direct_root_urns(roots, tmp_path)
    assert f"styleguide:{_TESTING_STYLEGUIDE}" not in _direct_root_urns(roots, tmp_path)  # control: not org-required


# --------------------------------------------------------------------------
# New delivery through the action bundle (scenario 7)
# --------------------------------------------------------------------------


def _merged_with_overlay_edges(overlay: DRGGraph) -> DRGGraph:
    nodes = [
        DRGNode(urn=_ACTION_URN, kind=NodeKind.ACTION),
        DRGNode(urn=f"directive:{_TESTING_DIRECTIVE}", kind=NodeKind.DIRECTIVE),
        DRGNode(urn=f"styleguide:{_CONTROL}", kind=NodeKind.STYLEGUIDE),
        *overlay.nodes,
    ]
    edges = [
        DRGEdge(source=f"action:{_MISSION_TYPE}/{_ACTION}", target=f"directive:{_TESTING_DIRECTIVE}", relation=Relation.SCOPE),
        *overlay.edges,
    ]
    return DRGGraph(schema_version="1.0", generated_at=_GENERATED_AT, generated_by="test", nodes=nodes, edges=edges)


def _delivered_styleguides(repo_root: Path, *, directives: frozenset[str], styleguides: frozenset[str] | None) -> frozenset[str]:
    overlay = _overlay()
    _install_overlay(repo_root, overlay)
    context = PackContext(
        activated_kinds=_ALL_KINDS,
        activated_mission_types=frozenset({_MISSION_TYPE}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        activated_directives=directives,
        activated_styleguides=styleguides,
    )
    with patch("charter.activation._drg_helpers.load_validated_graph", return_value=_merged_with_overlay_edges(overlay)):
        bundle = _load_action_governance_bundle(
            repo_root=repo_root,
            action=_ACTION,
            effective_depth=2,
            mission_type=_MISSION_TYPE,
            pack_context=context,
        )
    return frozenset(bundle.styleguide_ids)


_EXPLICIT = frozenset({_TESTING_STYLEGUIDE, _LANGUAGE_STYLEGUIDE})
_DIRECTIVE_ON = frozenset({_TESTING_DIRECTIVE_STEM})


def test_styleguide_is_delivered_while_its_directive_is_in_force(tmp_path: Path) -> None:
    on = _delivered_styleguides(tmp_path, directives=_DIRECTIVE_ON, styleguides=_EXPLICIT)
    off = _delivered_styleguides(tmp_path, directives=frozenset(), styleguides=_EXPLICIT)

    assert _TESTING_STYLEGUIDE in on
    assert _TESTING_STYLEGUIDE not in off  # an explicit list entry does not make it a root


def test_styleguide_is_delivered_with_the_key_absent_only_while_directive_in_force(tmp_path: Path) -> None:
    on = _delivered_styleguides(tmp_path, directives=_DIRECTIVE_ON, styleguides=None)
    off = _delivered_styleguides(tmp_path, directives=frozenset(), styleguides=None)

    assert _TESTING_STYLEGUIDE in on
    assert _TESTING_STYLEGUIDE not in off


def test_action_bundle_seeds_no_styleguide_root(tmp_path: Path) -> None:
    """Pin: with the directive off, no explicit list entry seeds a styleguide into the bundle."""
    off = _delivered_styleguides(tmp_path, directives=frozenset(), styleguides=_EXPLICIT | {_CONTROL})

    assert not (off & {_TESTING_STYLEGUIDE, "quality-gates-style-guide", "documentation-policy-style-guide"})


# --------------------------------------------------------------------------
# Removal sticks (scenarios 3, 4, 8) -- per-kind record
# --------------------------------------------------------------------------

_CHARTER_YAML = "schema_version: '2.0.0'\ngovernance: {}\ndirectives: {}\nmetadata:\n  generated_at: '2026-10-19T00:00:00Z'\n  bundle_schema_version: 2\n"
_NEW_STYLEGUIDE = "brand-new-style-guide"


def _seed_project(repo: Path, **activated: list[str] | None) -> Path:
    kittify = repo / ".kittify"
    (kittify / "charter").mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("vcs:\n  type: git\ncharter: .kittify/charter/charter.yaml\n", encoding="utf-8")
    present = {key: value for key, value in activated.items() if value is not None}
    body = _CHARTER_YAML + (yaml.safe_dump(present) if present else "")
    path = kittify / "charter" / "charter.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _list(charter_yaml: Path, key: str) -> object:
    return (yaml.safe_load(charter_yaml.read_text(encoding="utf-8")) or {}).get(key)


def _record(repo: Path) -> dict[str, list[str]]:
    from charter.activation.synthesizer.reach_only import CREATED_ARTIFACTS_PATH

    return yaml.safe_load((repo / CREATED_ARTIFACTS_PATH).read_text(encoding="utf-8"))


def _append(repo: Path, **created: list[str]) -> list[str]:
    from charter.activation.synthesizer.reach_only import append_synthesized_activations

    with patch("charter.activation.bundle_restamp.restamp_bundle_hash"):
        return append_synthesized_activations(repo, created)


def test_first_creation_appends_to_an_explicit_styleguide_list(tmp_path: Path) -> None:
    charter_yaml = _seed_project(tmp_path, activated_styleguides=[_CONTROL], activated_tactics=[_CONTROL])
    _install_with_sourced(tmp_path, _NEW_STYLEGUIDE)

    _append(tmp_path, styleguide=[_NEW_STYLEGUIDE], tactic=["new-tactic"])

    assert _list(charter_yaml, "activated_styleguides") == [_CONTROL, _NEW_STYLEGUIDE]
    assert _list(charter_yaml, "activated_tactics") == [_CONTROL, "new-tactic"]
    record = _record(tmp_path)  # also holds the manifest's other sourced styleguides and tactics
    assert _NEW_STYLEGUIDE in record["created_styleguides"]
    assert "new-tactic" in record["created_tactics"]
    assert _LANGUAGE_STYLEGUIDE not in record["created_styleguides"]


def test_removed_styleguide_is_not_re_appended(tmp_path: Path) -> None:
    charter_yaml = _seed_project(tmp_path, activated_styleguides=[_CONTROL])
    _install_with_sourced(tmp_path, _NEW_STYLEGUIDE)
    _append(tmp_path, styleguide=[_NEW_STYLEGUIDE])
    assert _list(charter_yaml, "activated_styleguides") == [_CONTROL, _NEW_STYLEGUIDE]  # control: first creation appended

    charter_yaml.write_text(charter_yaml.read_text(encoding="utf-8").replace(_NEW_STYLEGUIDE, "operator-kept"), encoding="utf-8")
    _append(tmp_path, styleguide=[_NEW_STYLEGUIDE])

    assert _list(charter_yaml, "activated_styleguides") == [_CONTROL, "operator-kept"]


def test_absent_keys_stay_absent_but_creation_is_recorded(tmp_path: Path) -> None:
    charter_yaml = _seed_project(tmp_path)
    _install_with_sourced(tmp_path, _NEW_STYLEGUIDE)

    _append(tmp_path, styleguide=[_NEW_STYLEGUIDE], tactic=["new-tactic"])

    config = yaml.safe_load(charter_yaml.read_text(encoding="utf-8"))
    assert "activated_styleguides" not in config
    assert "activated_tactics" not in config
    assert _NEW_STYLEGUIDE in _record(tmp_path)["created_styleguides"]


def test_styleguides_already_in_the_manifest_are_recorded_not_appended(tmp_path: Path) -> None:
    """A styleguide the manifest registered before a recording run is not created for the first time.

    The first run creates only a new one; the pre-existing one is recorded without being appended, so
    a later run that regenerates it (after a prune) does not append it either.
    """
    charter_yaml = _seed_project(tmp_path, activated_styleguides=[_CONTROL])
    _install_with_sourced(tmp_path, _NEW_STYLEGUIDE)  # the manifest registers testing-style-guide and its siblings

    _append(tmp_path, styleguide=[_NEW_STYLEGUIDE])

    assert _list(charter_yaml, "activated_styleguides") == [_CONTROL, _NEW_STYLEGUIDE]
    assert _TESTING_STYLEGUIDE in _record(tmp_path)["created_styleguides"]

    _append(tmp_path, styleguide=[_TESTING_STYLEGUIDE])  # regenerated later

    assert _list(charter_yaml, "activated_styleguides") == [_CONTROL, _NEW_STYLEGUIDE]


def test_unreadable_record_appends_nothing_for_any_kind_and_warns(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import CREATED_ARTIFACTS_PATH

    charter_yaml = _seed_project(tmp_path, activated_styleguides=[_CONTROL], activated_tactics=[_CONTROL])
    (tmp_path / CREATED_ARTIFACTS_PATH).write_text("created_styleguides: [unterminated\n", encoding="utf-8")
    before = charter_yaml.read_bytes()

    warnings = _append(tmp_path, styleguide=[_NEW_STYLEGUIDE], tactic=["new-tactic"])

    assert charter_yaml.read_bytes() == before
    assert len(warnings) == 1
    assert "synthesized-artifacts.yaml is unreadable" in warnings[0]


def test_legacy_tactic_record_is_read_never_written_and_other_keys_are_preserved(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import CREATED_ARTIFACTS_PATH

    charter_yaml = _seed_project(tmp_path, activated_tactics=[_CONTROL])
    _install_with_sourced(tmp_path, _NEW_STYLEGUIDE)
    legacy = tmp_path / ".kittify" / "charter" / "synthesized-tactics.yaml"
    legacy.write_text("created_tactics:\n- removed-earlier\n", encoding="utf-8")
    new_record = tmp_path / CREATED_ARTIFACTS_PATH
    new_record.write_text("created_styleguides:\n- older-style-guide\nowner_note: keep-me\n", encoding="utf-8")
    legacy_before = legacy.read_bytes()

    _append(tmp_path, tactic=["removed-earlier", "new-tactic"], styleguide=[_NEW_STYLEGUIDE])

    assert _list(charter_yaml, "activated_tactics") == [_CONTROL, "new-tactic"]  # the legacy record blocks re-adding
    assert legacy.read_bytes() == legacy_before
    record = yaml.safe_load((tmp_path / CREATED_ARTIFACTS_PATH).read_text(encoding="utf-8"))
    assert record["owner_note"] == "keep-me"
    assert {"brand-new-style-guide", "older-style-guide"} <= set(record["created_styleguides"])


def test_created_slugs_filters_the_manifest_delta_by_kind() -> None:
    from types import SimpleNamespace

    from charter.activation.synthesizer.reach_only import created_slugs
    from charter.activation.synthesizer.reconcile import ManifestDelta, ManifestEntryRef, ReconciliationDelta

    delta = ReconciliationDelta(
        manifest_delta=ManifestDelta(
            retained=(ManifestEntryRef(kind="styleguide", slug="kept-old", backing_artifact="p"),),
            added=(
                ManifestEntryRef(kind="styleguide", slug="s1", backing_artifact="p"),
                ManifestEntryRef(kind="tactic", slug="t1", backing_artifact="p"),
                ManifestEntryRef(kind="directive", slug="d1", backing_artifact="p"),
            ),
        )
    )

    assert created_slugs(delta, "styleguide") == ["s1"]
    assert created_slugs(delta, "tactic") == ["t1"]
    assert created_slugs(None, "styleguide") == []
    assert created_slugs(SimpleNamespace(manifest_delta=delta.manifest_delta), "styleguide") == []  # foreign delta


# --------------------------------------------------------------------------
# Legacy edge stripped (scenario 5)
# --------------------------------------------------------------------------


def test_legacy_styleguide_applies_edge_is_stripped_and_reported() -> None:
    """An untargeted synthesized styleguide's legacy ``applies`` edge is dropped by a full run and reported."""
    from charter.activation.synthesizer.reconcile import legacy_applies_edges, merge_project_overlay

    regenerated = DRGNode(urn=f"styleguide:{_TESTING_STYLEGUIDE}", kind=NodeKind.STYLEGUIDE, label="s")
    untargeted = DRGNode(urn="styleguide:quality-gates-style-guide", kind=NodeKind.STYLEGUIDE, label="q")
    legacy = DRGEdge(source=untargeted.urn, target="directive:DIRECTIVE_030", relation=Relation.APPLIES)
    existing = DRGGraph(schema_version="1.0", generated_at="S", generated_by="t", nodes=[regenerated, untargeted], edges=[legacy])
    updated = DRGGraph(schema_version="1.0", generated_at="S", generated_by="t", nodes=[regenerated], edges=[])
    synthesized = {regenerated.urn, untargeted.urn}

    full = merge_project_overlay(existing_overlay=existing, updated_overlay=updated, synthesized_urns=synthesized)
    scoped = merge_project_overlay(existing_overlay=existing, updated_overlay=updated, synthesized_urns=synthesized, topic_scoped=True)

    assert full.edges == []
    assert scoped.edges == [legacy]  # control: a topic-scoped run leaves an untargeted node's edge alone
    assert legacy_applies_edges(existing, synthesized) == (legacy,)
    assert legacy_applies_edges(existing, set()) == ()  # control: an unsynthesized styleguide keeps it


# --------------------------------------------------------------------------
# Edge-less styleguides keep today's activation semantics (scenario 6, review cycle 1)
# --------------------------------------------------------------------------


def test_only_reach_only_styleguides_are_appended_to_an_explicit_list(tmp_path: Path) -> None:
    """The language_scope styleguide has no source edge: it is never appended (it would become a root)."""
    charter_yaml = _seed_project(tmp_path, activated_styleguides=[_CONTROL])
    _install_overlay(tmp_path, _overlay())

    _append(tmp_path, styleguide=[_TESTING_STYLEGUIDE, _LANGUAGE_STYLEGUIDE])

    assert _list(charter_yaml, "activated_styleguides") == [_CONTROL, _TESTING_STYLEGUIDE]
    assert _LANGUAGE_STYLEGUIDE not in _record(tmp_path)["created_styleguides"]


def test_table_styleguide_without_its_directive_is_not_appended(tmp_path: Path) -> None:
    """DIRECTIVE_034 absent from the snapshot: no edge, so the testing styleguide is not reach-only."""
    charter_yaml = _seed_project(tmp_path, activated_styleguides=[_CONTROL])
    _install_overlay(tmp_path, _overlay(directives=("DIRECTIVE_030", "DIRECTIVE_037")))

    _append(tmp_path, styleguide=[_TESTING_STYLEGUIDE, "quality-gates-style-guide"])

    assert _list(charter_yaml, "activated_styleguides") == [_CONTROL, "quality-gates-style-guide"]


def test_created_slugs_by_kind_names_every_reach_only_kind() -> None:
    from charter.activation.synthesizer.reach_only import created_slugs_by_kind
    from charter.activation.synthesizer.reconcile import REACH_ONLY_KINDS, ManifestDelta, ManifestEntryRef, ReconciliationDelta

    delta = ReconciliationDelta(
        manifest_delta=ManifestDelta(
            retained=(),
            added=(
                ManifestEntryRef(kind="styleguide", slug="s1", backing_artifact="p"),
                ManifestEntryRef(kind="tactic", slug="t1", backing_artifact="p"),
            ),
        )
    )

    assert created_slugs_by_kind(delta) == {"tactic": ["t1"], "styleguide": ["s1"]}
    assert set(created_slugs_by_kind(None)) == set(REACH_ONLY_KINDS)
