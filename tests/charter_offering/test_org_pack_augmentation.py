"""WP04 — augmentation auto-emit single-source + parity (FR-028..FR-032).

Covers:

* T013 — single-source augmentation kind set (loader + validator derive from one).
* T014 — fragment-authored ``enhances`` / ``overrides`` / ``specializes_from``
  emission; field projection is data-driven from a single relation constant.
* T015 — augmentation eligibility extended to directive / toolguide /
  mission-step-contract (mission-type handled by T017).
* T016 — validator intent-aware parity for the newly-covered kinds via
  fragment edges.
* T017 — mission-type universe expansion (FR-032, decision locked). The former
  hand-kept lockstep drift guard is superseded by the structural
  single-authority gate (#5409,
  ``tests/architectural/test_charter_kind_vocabulary_single_authority.py``); the
  doctrine-local ``test_kind_vocabulary_mirrors_derive_from_one_authority``
  keeps the by-construction relationships.
* T018 — topology field-merge semantics for step contracts / mission types.

Note: the T-numbers above are from the ``org-doctrine-profile-integrity-
activation-closure`` mission that authored this file. Mission
``glossary-pack-doctrine-kind-01KY30SW`` WP04/T022 added the sibling
``test_glossary_packs_ship_active_by_default`` positive default-on assertion —
see its docstring for the RED-first rationale. Issue #5409 then collapsed the
three drift mirrors onto the single ``ArtifactKind`` authority.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.models import Relation
from charter.offering.drg.org_pack_loader import (
    AUGMENTATION_ELIGIBLE_KINDS,
    AUGMENTATION_RELATIONS,
    TOPOLOGY_KINDS,
    TopologyMergeError,
    _MISSION_TYPE_UNIVERSE_EXTENSION,
    _ORG_DRG_CANONICAL_KINDS,
    _merge_action_sequence_step,
    augmentation_plural_kinds,
    load_org_pack,
    merge_topology_artifact,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_fragment(pack_root: Path, *, edges: str = "edges: []\n") -> Path:
    drg_dir = pack_root / "drg"
    drg_dir.mkdir(parents=True, exist_ok=True)
    fragment = drg_dir / "fragment.yaml"
    fragment.write_text(
        'pack_name: testpack\nsource_kind: local_path\nsource_ref: "/nonexistent/pack"\nlayer_index: 1\nnodes: []\n' + edges,
        encoding="utf-8",
    )
    return fragment


# ---------------------------------------------------------------------------
# T013 — single-source augmentation kind set (FR-030)
# ---------------------------------------------------------------------------


def test_loader_and_validator_share_one_augmentation_source() -> None:
    """FR-030: the validator set is *derived* from the loader's single source."""
    from charter.offering.packs.pack_validator import _AUGMENTATION_PLURAL_KINDS

    assert augmentation_plural_kinds() == _AUGMENTATION_PLURAL_KINDS


def test_eligible_set_is_artifactkind_minus_template_plus_mission_type() -> None:
    """FR-030/FR-028/FR-032/FR-011: one definition covering all eligible kinds.

    The set is the ``ArtifactKind`` members minus
    ``_NON_AUGMENTATION_ELIGIBLE_KINDS`` (``template``, ``asset``) plus the
    mission-type extension; adding a kind is a one-line change.
    """
    from charter.offering.artifact_kinds import _NON_AUGMENTATION_ELIGIBLE_KINDS

    expected_singulars = {k.value for k in ArtifactKind if k not in _NON_AUGMENTATION_ELIGIBLE_KINDS} | {"mission_type"}
    assert set(AUGMENTATION_ELIGIBLE_KINDS) == expected_singulars
    assert ArtifactKind.TEMPLATE.value not in AUGMENTATION_ELIGIBLE_KINDS
    assert ArtifactKind.ASSET.value not in AUGMENTATION_ELIGIBLE_KINDS


def test_template_and_asset_are_node_declarable_but_not_augmentation_eligible() -> None:
    """FR-001/FR-007/FR-011: templates/assets are node-declarable DRG kinds.

    They must resolve as valid ``kind`` values on an org-pack DRG node (i.e.
    an org pack may declare a template/asset node and reference it in edges)
    while remaining excluded from the augmentation vocabulary — the loader
    must route both exclusions through the single canonical set imported from
    ``artifact_kinds`` rather than a private ``is not TEMPLATE`` check.
    """
    assert "templates" in _ORG_DRG_CANONICAL_KINDS
    assert "assets" in _ORG_DRG_CANONICAL_KINDS
    assert "template" not in AUGMENTATION_ELIGIBLE_KINDS
    assert "asset" not in AUGMENTATION_ELIGIBLE_KINDS
    assert "templates" not in augmentation_plural_kinds()
    assert "assets" not in augmentation_plural_kinds()


def test_relations_single_source_includes_specializes_from() -> None:
    """T014: one relation constant incl. lineage ``specializes_from``."""
    assert set(AUGMENTATION_RELATIONS) == {
        Relation.ENHANCES,
        Relation.OVERRIDES,
        Relation.SPECIALIZES_FROM,
    }


# ---------------------------------------------------------------------------
# T014 — fragment-authored emission incl. lineage
# ---------------------------------------------------------------------------


def test_fragment_authored_augmentation_and_lineage_edges_survive(tmp_path: Path) -> None:
    """T014: fragment-authored enhances/overrides/specializes_from flow through.

    The DRG fragment is the authoring authority (data-model §3). Edges the pack
    author writes directly are preserved by the loader without depending on
    artifact fields.
    """
    pack_root = tmp_path / "pack"
    _write_fragment(
        pack_root,
        edges=(
            "edges:\n"
            "  - source: tactic:pack-tactic\n"
            "    target: tactic:builtin-tactic\n"
            "    relation: enhances\n"
            "  - source: directive:pack-dir\n"
            "    target: directive:builtin-dir\n"
            "    relation: overrides\n"
            "  - source: agent_profile:child\n"
            "    target: agent_profile:parent\n"
            "    relation: specializes_from\n"
        ),
    )

    fragment = load_org_pack("testpack", pack_root, layer_index=1)
    relations = {(e.source, e.target, e.relation) for e in fragment.edges}
    assert ("tactic:pack-tactic", "tactic:builtin-tactic", "enhances") in relations
    assert ("directive:pack-dir", "directive:builtin-dir", "overrides") in relations
    assert (
        "agent_profile:child",
        "agent_profile:parent",
        "specializes_from",
    ) in relations


def test_specializes_from_field_projects_lineage_edge(tmp_path: Path) -> None:
    """T014: lineage auto-emits via the single relation list (FR-001 plumbing).

    During the migration window the field projection remains; ``specializes_from``
    is now in the relation list, so an agent profile carrying that field emits a
    lineage edge with no per-relation special-casing.
    """
    pack_root = tmp_path / "pack"
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "child.agent.yaml").write_text("id: child\nspecializes_from: parent\n", encoding="utf-8")
    _write_fragment(pack_root)

    fragment = load_org_pack("testpack", pack_root, layer_index=1)
    lineage = [
        e for e in fragment.edges if e.relation == Relation.SPECIALIZES_FROM.value and e.source == "agent_profile:child" and e.target == "agent_profile:parent"
    ]
    assert lineage, f"lineage edge not auto-emitted. edges={fragment.edges}"


# ---------------------------------------------------------------------------
# T015 — augmentation eligibility for the 4 newly-covered kinds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "plural",
    ["directives", "toolguides", "mission_step_contracts", "mission_types"],
)
def test_newly_covered_kinds_are_augmentation_eligible(plural: str) -> None:
    """T015/FR-028/FR-032: the four new kinds joined the eligible set."""
    assert plural in augmentation_plural_kinds()


def test_directive_field_projection_emits_edge(tmp_path: Path) -> None:
    """T015: a directive declaring ``enhances`` projects an ENHANCES edge."""
    pack_root = tmp_path / "pack"
    directives_dir = pack_root / "directives"
    directives_dir.mkdir(parents=True)
    (directives_dir / "d.directive.yaml").write_text("id: DIRECTIVE_900\nenhances: DIRECTIVE_001\n", encoding="utf-8")
    _write_fragment(pack_root)

    fragment = load_org_pack("testpack", pack_root, layer_index=1)
    assert any(e.source == "directive:DIRECTIVE_900" and e.target == "directive:DIRECTIVE_001" and e.relation == Relation.ENHANCES.value for e in fragment.edges)


# ---------------------------------------------------------------------------
# T016 — validator intent-aware parity for new kinds (fragment edges)
# ---------------------------------------------------------------------------


def _fragment_intent(drg_dir: Path):
    from charter.offering.packs.pack_validator import _collect_fragment_edge_intent

    return _collect_fragment_edge_intent(drg_dir, None)


def test_fragment_edge_intent_unknown_target_hard_errors(tmp_path: Path) -> None:
    """T016/FR-031: a fragment ``overrides`` of an unknown built-in hard-errors."""
    from charter.offering.packs.pack_validator import (
        _intent_aware_collision_messages_from_edges,
    )

    drg_dir = tmp_path / "drg"
    drg_dir.mkdir()
    (drg_dir / "f.graph.yaml").write_text(
        'schema_version: "1.0"\n'
        'generated_at: "2026-06-01T00:00:00+00:00"\n'
        'generated_by: "test"\n'
        "nodes: []\n"
        "edges:\n"
        '  - source: "directive:pack-dir"\n'
        '    target: "directive:does-not-exist"\n'
        '    relation: "overrides"\n',
        encoding="utf-8",
    )
    intent = _fragment_intent(drg_dir)
    errors, advisories = _intent_aware_collision_messages_from_edges(intent, {"directives": {"DIRECTIVE_001"}}, {})
    assert any(e.category == "unknown_target" for e in errors)
    assert advisories == []


def test_fragment_edge_intent_conflict_when_both_declared(tmp_path: Path) -> None:
    """T016/FR-031: enhances + overrides on one source -> intent_conflict."""
    from charter.offering.packs.pack_validator import (
        _intent_aware_collision_messages_from_edges,
    )

    drg_dir = tmp_path / "drg"
    drg_dir.mkdir()
    (drg_dir / "f.graph.yaml").write_text(
        'schema_version: "1.0"\n'
        'generated_at: "2026-06-01T00:00:00+00:00"\n'
        'generated_by: "test"\n'
        "nodes: []\n"
        "edges:\n"
        '  - source: "toolguide:pack-tg"\n'
        '    target: "toolguide:builtin-tg"\n'
        '    relation: "enhances"\n'
        '  - source: "toolguide:pack-tg"\n'
        '    target: "toolguide:builtin-tg"\n'
        '    relation: "overrides"\n',
        encoding="utf-8",
    )
    intent = _fragment_intent(drg_dir)
    errors, _ = _intent_aware_collision_messages_from_edges(intent, {"toolguides": {"builtin-tg"}}, {})
    assert any(e.category == "intent_conflict" for e in errors)


def test_fragment_edge_valid_intent_suppresses_advisory(tmp_path: Path) -> None:
    """T016/FR-031: a valid declared intent emits no error and no advisory."""
    from charter.offering.packs.pack_validator import (
        _intent_aware_collision_messages_from_edges,
    )

    drg_dir = tmp_path / "drg"
    drg_dir.mkdir()
    (drg_dir / "f.graph.yaml").write_text(
        'schema_version: "1.0"\n'
        'generated_at: "2026-06-01T00:00:00+00:00"\n'
        'generated_by: "test"\n'
        "nodes: []\n"
        "edges:\n"
        '  - source: "directive:pack-dir"\n'
        '    target: "directive:DIRECTIVE_001"\n'
        '    relation: "enhances"\n',
        encoding="utf-8",
    )
    intent = _fragment_intent(drg_dir)
    errors, advisories = _intent_aware_collision_messages_from_edges(intent, {"directives": {"DIRECTIVE_001"}}, {})
    assert errors == []
    assert advisories == []


def test_fragment_intent_ignores_lineage_relation(tmp_path: Path) -> None:
    """``specializes_from`` is lineage, not augmentation intent — never folded in."""
    drg_dir = tmp_path / "drg"
    drg_dir.mkdir()
    (drg_dir / "f.graph.yaml").write_text(
        'schema_version: "1.0"\n'
        'generated_at: "2026-06-01T00:00:00+00:00"\n'
        'generated_by: "test"\n'
        "nodes: []\n"
        "edges:\n"
        '  - source: "agent_profile:child"\n'
        '    target: "agent_profile:parent"\n'
        '    relation: "specializes_from"\n',
        encoding="utf-8",
    )
    assert _fragment_intent(drg_dir) == {}


# ---------------------------------------------------------------------------
# T017 — mission-type universe expansion + lockstep drift guard (FR-032)
# ---------------------------------------------------------------------------


def test_mission_types_in_canonical_universe() -> None:
    """FR-032 (DIRECTIVE_003): mission types joined the canonical universe."""
    assert "mission_types" in _ORG_DRG_CANONICAL_KINDS
    # The legacy mission-step-contract alias is still accepted on input.
    assert "mission_step_contracts" in _ORG_DRG_CANONICAL_KINDS


def test_mission_type_fragment_augmentation_validates(tmp_path: Path) -> None:
    """FR-032: a mission-type fragment node validates (not silently dropped)."""
    from charter.offering.drg.org_pack_loader import OrgDRGFragment

    fragment = OrgDRGFragment.model_validate(
        {
            "pack_name": "acme",
            "source_kind": "local_path",
            "source_ref": "/nonexistent/acme",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": [{"id": "custom-mission", "kind": "mission_types", "title": "Custom"}],
            "edges": [
                {
                    "source": "mission_type:custom-mission",
                    "target": "mission_type:software-dev",
                    "relation": "enhances",
                }
            ],
        }
    )
    node = fragment.nodes[0]
    assert node.kind == "mission_types"
    assert fragment.edges[0].relation == "enhances"


def test_mission_type_singular_alias_resolves_to_plural() -> None:
    """FR-032: the ``mission_type`` singular input form resolves to the plural."""
    from charter.offering.drg.org_pack_loader import OrgDRGFragment

    fragment = OrgDRGFragment.model_validate(
        {
            "pack_name": "acme",
            "source_kind": "local_path",
            "source_ref": "/nonexistent/acme",
            "layer_index": 1,
            "nodes": [{"id": "x", "kind": "mission_type", "title": "X"}],
            "edges": [],
        }
    )
    assert fragment.nodes[0].kind == "mission_types"


def test_template_and_asset_fragment_nodes_validate_but_do_not_augment() -> None:
    """FR-001/FR-007/FR-011: template/asset nodes are node-declarable.

    A fragment may declare ``template``/``asset`` kind nodes (they resolve
    through :class:`_OrgDRGNode` like every other kind) even though neither
    kind carries augmentation vocabulary — an ``enhances``/``overrides`` edge
    against one is not auto-emitted by the loader (only fragment-authored
    edges reach ``fragment.edges`` for these kinds).
    """
    from charter.offering.drg.org_pack_loader import OrgDRGFragment

    fragment = OrgDRGFragment.model_validate(
        {
            "pack_name": "acme",
            "source_kind": "local_path",
            "source_ref": "/nonexistent/acme",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": [
                {"id": "pr-template", "kind": "templates", "title": "PR template"},
                {"id": "logo", "kind": "assets", "title": "Logo asset"},
            ],
            "edges": [],
        }
    )
    kinds = {node.kind for node in fragment.nodes}
    assert kinds == {"templates", "assets"}


def test_kind_vocabulary_mirrors_derive_from_one_authority() -> None:
    """#5409: the three former drift mirrors now derive from ``ArtifactKind``.

    The hand-kept three-way equality guard (which had to special-case the
    ``mission_step_contracts``→``mission_steps`` rename and could only catch
    drift *after* it was hand-authored) is superseded by the structural
    single-authority gate in
    ``tests/architectural/test_charter_kind_vocabulary_single_authority.py``,
    which forbids any hand-authored kind-vocabulary literal under ``src/charter``
    outright. This test keeps a doctrine-local check that the mirrors relate to
    the authority exactly as designed — every kind (incl. ``anti_patterns``) is
    registry-addressable and default-on, and the org-pack universe is the enum
    plurals (with the mission-step rename) plus the mission-type extension.
    """
    from charter.activation.activations import _ALLOWED_KINDS
    from charter.activation.pack_context import _BUILTIN_ARTIFACT_KINDS

    all_plurals = frozenset(k.plural for k in ArtifactKind)
    # Registry-addressable == default-on == every ArtifactKind plural (#5409).
    assert all_plurals == _ALLOWED_KINDS
    assert all_plurals == _BUILTIN_ARTIFACT_KINDS
    assert "anti_patterns" in _ALLOWED_KINDS

    # Org-pack universe == enum plurals (mission_step_contracts → mission_steps)
    # plus the mission-type extension, retaining the backward-compat aliases.
    canonical_universe = _ORG_DRG_CANONICAL_KINDS - {"mission_step_contracts", "mission_type"}
    # ``anti_patterns`` is registry-addressable but NOT a file-backed org-pack
    # node kind (it has no standalone artifact file), so the org-pack universe
    # is the enum plurals MINUS anti_patterns (mission_step_contracts→mission_steps)
    # plus the mission-type extension.
    enum_universe_with_rename = (all_plurals - {"mission_step_contracts", "anti_patterns"}) | {"mission_steps"}
    assert canonical_universe == enum_universe_with_rename | _MISSION_TYPE_UNIVERSE_EXTENSION
    assert frozenset({"mission_types"}) == _MISSION_TYPE_UNIVERSE_EXTENSION
    assert "anti_patterns" not in _ORG_DRG_CANONICAL_KINDS
    assert "anti_patterns" in _ALLOWED_KINDS  # registry-addressable, the #5409 fix


def test_glossary_packs_ship_active_by_default() -> None:
    """Positive default-on assertion (T022, squad F3 RED-first anchor).

    ``"glossary_packs"`` must be a member of
    ``charter.activation.pack_context._BUILTIN_ARTIFACT_KINDS`` — the list consulted
    when a project's ``.kittify/config.yaml`` (or ``charter.yaml``) has no
    explicit ``activated_kinds`` key. Without this membership, the built-in
    ``spec-kitty-core`` glossary pack would resolve as a DRG node (WP03) but
    never surface through the charter-mediated activation filter — silently
    inactive on every project that has not explicitly opted in, which is
    the exact default-on regression this mission exists to prevent.

    This assertion is authored RED-first: it fails until WP04's T019 adds
    ``"glossary_packs"`` to ``_BUILTIN_ARTIFACT_KINDS``. Unlike the
    three-way equality above (which could be green-on-arrival if authored
    after all the kind-lists are already consistent), this single-membership
    check is unambiguously RED before T019 lands and unambiguously GREEN
    after — the demonstrable RED-before-wiring-commit evidence the DoD
    requires.
    """
    from charter.activation.pack_context import _BUILTIN_ARTIFACT_KINDS

    assert "glossary_packs" in _BUILTIN_ARTIFACT_KINDS


# ---------------------------------------------------------------------------
# T018 — topology field-merge semantics (FR-029, ADR 2026-05-16-1)
# ---------------------------------------------------------------------------


def test_topology_kinds_are_step_contract_and_mission_type() -> None:
    assert frozenset({"mission_step_contract", "mission_type"}) == TOPOLOGY_KINDS


def test_overrides_is_full_replacement() -> None:
    """FR-029: ``overrides`` fully replaces the base topology artifact."""
    base = {"id": "s", "steps": [{"id": "a"}, {"id": "b"}]}
    overlay = {"id": "s", "steps": [{"id": "z"}]}
    merged = merge_topology_artifact(base, overlay, mode=Relation.OVERRIDES)
    assert merged == overlay
    assert merged is not overlay  # deep-copied, inputs untouched


def test_enhances_preserves_base_sequence_when_overlay_omits_it() -> None:
    """FR-029: an enhances overlay that omits ``steps`` keeps base ordering."""
    base = {"id": "s", "title": "Base", "steps": [{"id": "a"}, {"id": "b"}]}
    overlay = {"id": "s", "title": "Enhanced"}
    merged = merge_topology_artifact(base, overlay, mode=Relation.ENHANCES)
    assert merged["title"] == "Enhanced"  # field-level override
    assert [s["id"] for s in merged["steps"]] == ["a", "b"]  # ordering preserved


def test_enhances_merges_step_io_and_keeps_order() -> None:
    """FR-029: step I/O contracts merge; ordering follows the overlay."""
    base = {
        "id": "s",
        "steps": [
            {"id": "a", "inputs": ["x"], "outputs": ["y"]},
            {"id": "b", "inputs": ["p"]},
        ],
    }
    overlay = {
        "id": "s",
        "steps": [
            {"id": "a", "title": "Step A refined"},
            {"id": "b", "inputs": ["p"], "title": "Step B"},
        ],
    }
    merged = merge_topology_artifact(base, overlay, mode=Relation.ENHANCES)
    assert [s["id"] for s in merged["steps"]] == ["a", "b"]
    step_a = merged["steps"][0]
    assert step_a["title"] == "Step A refined"
    # base I/O contract preserved (overlay did not restate it)
    assert step_a["inputs"] == ["x"]
    assert step_a["outputs"] == ["y"]


def test_enhances_rejects_silent_step_drop() -> None:
    """FR-029: an enhances overlay that drops a base step fails closed."""
    base = {"id": "s", "steps": [{"id": "a"}, {"id": "b"}]}
    overlay = {"id": "s", "steps": [{"id": "a"}]}
    with pytest.raises(TopologyMergeError, match="silently drops"):
        merge_topology_artifact(base, overlay, mode=Relation.ENHANCES)


def test_enhances_rejects_stripping_step_io() -> None:
    """FR-029: an enhances overlay may not strip a step's input/output contract."""
    base = {"id": "s", "steps": [{"id": "a", "inputs": ["x"]}]}
    overlay = {"id": "s", "steps": [{"id": "a", "inputs": []}]}
    with pytest.raises(TopologyMergeError, match="strips"):
        merge_topology_artifact(base, overlay, mode=Relation.ENHANCES)


def test_merge_rejects_non_augmentation_relation() -> None:
    with pytest.raises(ValueError, match="ENHANCES / OVERRIDES"):
        merge_topology_artifact({"id": "s"}, {"id": "s"}, mode=Relation.REQUIRES)


# ---------------------------------------------------------------------------
# WP03 T011 — _merge_action_sequence_step (extracted from
# _merge_action_sequence to keep its cognitive complexity within the ruff
# C901 limit)
# ---------------------------------------------------------------------------


def test_merge_action_sequence_step_new_overlay_step_passes_through() -> None:
    """A step id with no base counterpart is deep-copied unchanged."""
    base_by_id: dict[str, object] = {}
    step = {"id": "brand-new", "title": "New Step"}
    merged = _merge_action_sequence_step(step, base_by_id, "steps")
    assert merged == step
    assert merged is not step  # deep-copied


def test_merge_action_sequence_step_non_mapping_step_passes_through() -> None:
    """A non-mapping overlay entry (e.g. a bare string) is copied verbatim."""
    step = "not-a-mapping"
    merged = _merge_action_sequence_step(step, {"a": {"id": "a"}}, "steps")
    assert merged == "not-a-mapping"


def test_merge_action_sequence_step_merges_matching_base_step() -> None:
    """A step sharing an id with a base step is field-merged (base fields survive)."""
    base_by_id = {"a": {"id": "a", "inputs": ["x"], "outputs": ["y"]}}
    step = {"id": "a", "title": "Refined"}
    merged = _merge_action_sequence_step(step, base_by_id, "steps")
    assert merged["title"] == "Refined"
    assert merged["inputs"] == ["x"]
    assert merged["outputs"] == ["y"]


def test_merge_action_sequence_step_raises_on_io_stripping() -> None:
    """Deliberately restating an I/O field empty raises TopologyMergeError."""
    base_by_id = {"a": {"id": "a", "inputs": ["x"]}}
    step = {"id": "a", "inputs": []}
    with pytest.raises(TopologyMergeError, match="strips"):
        _merge_action_sequence_step(step, base_by_id, "steps")
