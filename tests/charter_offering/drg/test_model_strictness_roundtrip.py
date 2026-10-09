"""Strict DRG/profile models + field-derived writers (WP04, FR-004 / C-001 / SC-003).

Two silences, and they only close together
------------------------------------------
A field can go missing at either end of the same trip, and closing one end alone
ships a worse bug than leaving both open:

**Read end.** ``DRGNode``, ``DRGEdge`` and ``AgentProfile`` declared no
``extra`` policy, so Pydantic v2's ``extra="ignore"`` default applied: an
authored key the model does not declare was dropped on load with no warning.
Every sibling model under ``src/charter/offering/**/models.py`` already declares
``extra="forbid"`` (``tactics``, ``directives``, ``procedures``, ``paradigms``,
``missions``, ``styleguides``, ``toolguides``, ``assets``, ``glossary_packs``,
``model_task_routing``, ``import_candidates``) —
``drg/models.py`` and ``AgentProfile`` were the outliers, not the innovation.
(The former ``ContextSources`` value object was retired in mission
doctrine-drg-silent-drop-boundary-01M0PE7E; ``AgentProfile`` itself now carries
the ``extra="forbid"`` boundary for the whole profile.)

**Write end.** The extractor's ``_node_to_dict`` / ``_edge_to_dict`` restated
their model's field names by hand. A field added to the model but not to the
writer loads fine, is reachable in memory, and is deleted the next time the
graph is written.

C-009 requires the model change and the writer change in one commit for exactly
that reason. Landing ``extra="forbid"`` alone would make an authored ``impacts``
key *load* — and still vanish on the next regeneration, now with a passing model
test to vouch for it. That is a strictly worse failure than today's, because it
buys a green assertion.

What the round-trip test actually proves
----------------------------------------
"A new field survives write→read" is only meaningful if the new field is *new*.
Asserting on ``when`` or ``reason`` proves nothing: a hand-written writer that
names them passes. So this module attacks it from both sides:

1. :func:`test_every_declared_edge_field_is_emitted_unless_explicitly_withheld`
   pins the *real* ``DRGEdge``: the emitted key set must equal
   ``model_fields`` minus a named withholding set. That is total over the model,
   so a field added tomorrow must either be emitted or be explicitly withheld —
   there is no third outcome where it is quietly absent.
2. :class:`_DRGEdgeWithNewField` adds a genuinely undeclared-today field and
   drives it through ``_edge_to_dict`` → YAML → re-validate. This is the
   behavioural half; it fails against a writer that restates field names, which
   :func:`test_the_hand_written_writer_shape_would_drop_the_new_field` proves by
   running the replaced writer shape against the same edge (T022 — the
   round-trip must not be green for free).

The withholding set is not an escape hatch
------------------------------------------
``provenance`` is deliberately not serialised: it is a merge-time marker
(FR-013) that is ``None`` for every extractor-built node, and emitting it would
churn the shipped graph. That exclusion is a *declaration*, not a silence — it
lives in one named frozenset, every member is asserted to be a real model field
(so it cannot rot into a typo that silently withholds nothing), and the
withholding itself is asserted rather than assumed.

Why ``_KIND_MAP`` is here and not in WP03
-----------------------------------------
``_KIND_MAP`` mapped 11 of ``NodeKind``'s 16 members, dropping ``anti_pattern``,
``asset``, ``glossary``, ``glossary_pack`` and ``glossary_scope``. It is
``str``-keyed, which is why the ``NodeKind``-keyed totality guard in
``test_kind_mapping_totality.py`` could not see it — a hand-restated table one
step outside the gate that exists to catch hand-restated tables. Closing it by
*deriving* the table from ``NodeKind`` removes the restatement rather than
lengthening it.

Measured graph-neutral on this branch: regenerating with the total map moves the
extractor graph by zero nodes and zero edges (305/757 before and after; the
shipped 311/774 adds the hand-authored ``anti_pattern`` fragment the extractor
does not produce). The gap is latent, not live — it goes live when mission C
authors anti-patterns and assets that other artefacts *reference*. The shipped
311/774 invariant is pinned once, by WP03's
``test_unknown_kind_fails_loudly.py``; it is deliberately not restated here.

Why extractor symbols are reached through the module
----------------------------------------------------
``from ... extractor import _KIND_MAP, ...`` would make this module fail to
*import* on the planning base, and a collection error is a poor ATDD red: it
says "one of these names is missing" and nothing about which behaviours are
broken. Reaching them as ``extractor.<name>`` keeps the module importable, so
the red-first commit produces a per-test failure map that names each defect
separately.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError
from ruamel.yaml import YAML

from charter.offering.agent_profiles.profile import AgentProfile
from charter.offering.drg import loader as drg_loader
from charter.offering.drg import models as drg_models
from charter.offering.drg.loader import DRGLoadError
from charter.offering.drg.migration import extractor
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

# Relocated built-in pack root (mission relocate-builtin-doctrine-packs-01KYT87F):
# the shipped ``*.graph.yaml`` fragments and the built-in agent profiles now live
# under the flattened ``packs/built-in/`` tree (the inner ``built-in`` segment is
# dropped — profiles are at ``packs/built-in/agent_profiles/``).
_BUILT_IN_PACK = Path(__file__).resolve().parents[3] / "packs" / "built-in"

#: Floors for the shipped-tree scans below. Every assertion that walks the tree
#: is satisfied by an empty walk, so relocating ``packs/built-in`` or renaming the
#: fragment/profile conventions would leave those tests green while covering
#: nothing. Counts as measured on this branch: 14 fragments, 18 profiles.
_MINIMUM_SHIPPED_FRAGMENTS = 14
_MINIMUM_SHIPPED_PROFILES = 18

_VALID_NODE: dict[str, Any] = {"urn": "tactic:some-tactic", "kind": "tactic"}
_VALID_EDGE: dict[str, Any] = {
    "source": "tactic:some-tactic",
    "target": "directive:DIRECTIVE_001",
    "relation": "requires",
}
_VALID_PROFILE: dict[str, Any] = {
    "profile-id": "test-profile",
    "name": "Test Profile",
    "purpose": "Exercise the model.",
    "specialization": {"primary-focus": "Testing"},
    "roles": ["implementer"],
}

#: A field name no model declares today — the probe for "undeclared key".
_UNDECLARED_KEY = "a_key_no_model_declares"


class _DRGEdgeWithNewField(DRGEdge):
    """``DRGEdge`` plus one field — B1's ``impacts`` / ``is_symmetric`` in miniature.

    Declaring the extra field on a subclass rather than mutating the shipped
    model keeps this test from having to edit production code to run, and it
    exercises precisely the mechanism under test: a writer that reads
    ``type(model).model_fields`` picks the field up, and a writer that restates
    names does not. The complementary half — that the *real* ``DRGEdge``'s
    emitted keys are derived from its own ``model_fields`` — is asserted
    separately, so neither test stands alone.
    """

    audit_note: str | None = None


def _hand_written_edge_dict(edge: DRGEdge) -> dict[str, Any]:
    """The writer shape WP04 replaces, restated verbatim as the self-mutation foil.

    Kept here rather than in the extractor so the round-trip assertion has
    something to fail against. If this and ``_edge_to_dict`` ever agree on an
    edge carrying an undeclared-today field, the round-trip test has gone
    vacuous.
    """
    out: dict[str, Any] = {
        "source": edge.source,
        "target": edge.target,
        "relation": edge.relation.value,
    }
    if edge.when is not None:
        out["when"] = edge.when.strip()
    if edge.reason is not None:
        out["reason"] = edge.reason.strip()
    return out


# ---------------------------------------------------------------------------
# T018-T020 -- an undeclared field is a load error, on all three models
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        pytest.param(DRGNode, _VALID_NODE, id="DRGNode"),
        pytest.param(DRGEdge, _VALID_EDGE, id="DRGEdge"),
        pytest.param(AgentProfile, _VALID_PROFILE, id="AgentProfile"),
    ],
)
def test_an_undeclared_field_is_a_load_error(
    model: type[BaseModel], payload: dict[str, Any]
) -> None:
    """SC-003. The positive control runs first so a red here cannot be a broken payload.

    Without the control, a typo in ``payload`` would make the ``raises`` block
    pass for the wrong reason and this test would vouch for nothing.
    """
    model.model_validate(payload)

    with pytest.raises(ValidationError, match="[Ee]xtra"):
        model.model_validate({**payload, _UNDECLARED_KEY: "a value"})


def test_a_stale_scalar_role_alongside_roles_is_a_load_error() -> None:
    """The one behaviour ``extra="forbid"`` on ``AgentProfile`` actually changes.

    ``role:``-alone still coerces to ``roles:`` with a DeprecationWarning (the
    documented migration path, unchanged). Authoring *both* used to resolve
    silently in favour of ``roles`` — a contradictory profile whose discarded
    half nobody was ever told about. Measured: no shipped or fixture profile
    authors both, so nothing in the tree depends on the old resolution.
    """
    with pytest.raises(ValidationError) as excinfo:
        AgentProfile.model_validate(
            {**_VALID_PROFILE, "roles": ["architect"], "role": "implementer"}
        )

    message = str(excinfo.value)
    assert "role" in message
    assert "roles" in message


def test_the_documented_scalar_role_migration_path_still_works() -> None:
    """Guard against over-tightening: ``role:`` alone must keep coercing."""
    payload = {k: v for k, v in _VALID_PROFILE.items() if k != "roles"}

    with pytest.deprecated_call():
        profile = AgentProfile.model_validate({**payload, "role": "implementer"})

    assert [str(role) for role in profile.roles] == ["implementer"]


# ---------------------------------------------------------------------------
# Blast radius -- the shipped tree must still load under the strict models
# ---------------------------------------------------------------------------


def test_every_shipped_drg_fragment_still_loads_under_the_strict_models() -> None:
    """``extra="forbid"`` is only correct if nothing shipped relies on the silence."""
    fragments = sorted(_BUILT_IN_PACK.glob("*.graph.yaml"))
    assert len(fragments) >= _MINIMUM_SHIPPED_FRAGMENTS, (
        f"expected at least {_MINIMUM_SHIPPED_FRAGMENTS} shipped graph fragments; "
        f"found {len(fragments)} -- this assertion passes vacuously on an empty walk"
    )

    yaml_safe = YAML(typ="safe")
    for fragment in fragments:
        document = yaml_safe.load(fragment.read_text(encoding="utf-8")) or {}
        for raw in document.get("nodes") or []:
            DRGNode.model_validate(raw)
        for raw in document.get("edges") or []:
            DRGEdge.model_validate(raw)


def test_every_shipped_agent_profile_still_loads_under_the_strict_model() -> None:
    """Same check for the 18 built-in profiles."""
    profiles = sorted((_BUILT_IN_PACK / "agent_profiles").glob("*.agent.yaml"))
    assert len(profiles) >= _MINIMUM_SHIPPED_PROFILES, (
        f"expected at least {_MINIMUM_SHIPPED_PROFILES} built-in profiles; "
        f"found {len(profiles)} -- this assertion passes vacuously on an empty walk"
    )

    yaml_safe = YAML(typ="safe")
    for profile in profiles:
        AgentProfile.model_validate(yaml_safe.load(profile.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# T016 -- the writers are derived from the model, not restated
# ---------------------------------------------------------------------------


def test_every_declared_edge_field_is_emitted_unless_explicitly_withheld() -> None:
    """Total over ``DRGEdge.model_fields``: a new field is emitted or declared withheld."""
    edge = DRGEdge(
        source="tactic:a",
        target="tactic:b",
        relation=Relation.REQUIRES,
        when="a condition",
        reason="a rationale",
        provenance="org:acme",
    )

    emitted = set(extractor._edge_to_dict(edge))

    assert emitted == set(DRGEdge.model_fields) - extractor._FIELDS_WITHHELD_FROM_GRAPH_OUTPUT


def test_every_declared_node_field_is_emitted_unless_explicitly_withheld() -> None:
    """Same totality for ``DRGNode``."""
    node = DRGNode(
        urn="anti_pattern:big-ball-of-mud",
        kind=NodeKind.ANTI_PATTERN,
        label="Big Ball of Mud",
        provenance="org:acme",
        tags=["smell"],
    )

    emitted = set(extractor._node_to_dict(node))

    assert emitted == set(DRGNode.model_fields) - extractor._FIELDS_WITHHELD_FROM_GRAPH_OUTPUT


# ---------------------------------------------------------------------------
# T001 -- the derived serialisation helper is a public, exported surface
# ---------------------------------------------------------------------------


def test_the_derived_helper_is_public_on_the_extractor() -> None:
    """Every sibling writer needs the derived helper; a private name cannot be shared.

    Promoting ``_model_to_dict`` to ``model_to_graph_dict`` (and the withholding
    set to ``FIELDS_WITHHELD_FROM_GRAPH_OUTPUT``) is the T001 export. The private
    aliases stay so internal call sites keep working, and both names must point
    at the same object -- a copy would let the two drift.
    """
    assert extractor.model_to_graph_dict is extractor._model_to_dict
    assert (
        extractor.FIELDS_WITHHELD_FROM_GRAPH_OUTPUT
        is extractor._FIELDS_WITHHELD_FROM_GRAPH_OUTPUT
    )


def test_the_derived_helper_is_reexported_through_the_charter_facade() -> None:
    """T001: ``rewrite_opposed_by`` (specify_cli) reaches doctrine only through
    ``charter.drg`` (ADR ``2026-03-27-1``), so the helper must be on that surface.

    The re-export is identity, not a re-implementation, and it is named in the
    facade's ``__all__`` so the public contract is explicit.
    """
    import charter.drg as charter_drg

    assert charter_drg.model_to_graph_dict is extractor.model_to_graph_dict
    assert (
        charter_drg.FIELDS_WITHHELD_FROM_GRAPH_OUTPUT
        is extractor.FIELDS_WITHHELD_FROM_GRAPH_OUTPUT
    )
    assert "model_to_graph_dict" in charter_drg.__all__
    assert "FIELDS_WITHHELD_FROM_GRAPH_OUTPUT" in charter_drg.__all__


# ---------------------------------------------------------------------------
# T002 (contract W-1a) -- the derivation is total over VALUES, not only names
# ---------------------------------------------------------------------------


class _DRGEdgeWithEmptyNovelFields(DRGEdge):
    """``DRGEdge`` plus two novel fields whose *default* values are empty.

    ``impacts``-shaped: a ``None`` optional and an empty ``list``. These are the
    exact shapes W-1a says the derived writer dropped silently — ``impacts:
    list[str] = []`` vanished while ``is_symmetric: bool = False`` survived. A
    completeness gate over a *populated* fixture is vacuous for them, so the
    fixture here leaves both at their empty defaults.
    """

    novel_optional: str | None = None
    novel_list: list[str] = Field(default_factory=list)


def test_a_novel_field_with_an_empty_value_is_not_dropped_silently() -> None:
    """W-1a: a field the withholding/omit sets do not name is emitted even when empty.

    ``novel_optional`` (``None``) and ``novel_list`` (``[]``) are neither
    withheld nor named in the omit-when-empty allowlist, so the derived writer
    must emit both — the case that silently dropped B1's ``impacts`` today.
    """
    edge = _DRGEdgeWithEmptyNovelFields(
        source="tactic:a", target="tactic:b", relation=Relation.REQUIRES
    )

    emitted = extractor.model_to_graph_dict(edge)

    assert "novel_optional" in emitted
    assert emitted["novel_optional"] is None
    assert "novel_list" in emitted
    assert emitted["novel_list"] == []


def test_the_omit_when_empty_set_is_a_shrink_only_allowlist() -> None:
    """W-1a: omitting an empty value is opt-in, and the opt-in list cannot be padded.

    The allowlist names exactly the pre-existing optionals whose empty form was
    already absent from every shipped fragment. Adding a member here re-opens the
    silent-drop hole for that field — precisely the escape mission B1's ``impacts``
    must not have — so this pin makes that a deliberate, diff-visible edit.
    """
    assert frozenset(
        {"label", "tags", "when", "reason"}
    ) == extractor._FIELDS_OMITTED_WHEN_EMPTY


def test_the_omit_when_empty_set_names_only_real_model_fields() -> None:
    """Anti-rot twin of the withholding-set guard: no member may be a typo."""
    declared = set(DRGNode.model_fields) | set(DRGEdge.model_fields)

    assert extractor._FIELDS_OMITTED_WHEN_EMPTY
    assert declared >= extractor._FIELDS_OMITTED_WHEN_EMPTY


def test_the_withholding_set_names_only_real_model_fields() -> None:
    """Anti-rot: a typo in the withholding set withholds nothing and says nothing."""
    declared = set(DRGNode.model_fields) | set(DRGEdge.model_fields)

    assert extractor._FIELDS_WITHHELD_FROM_GRAPH_OUTPUT
    assert declared >= extractor._FIELDS_WITHHELD_FROM_GRAPH_OUTPUT


def test_the_withholding_set_is_exactly_provenance_and_nothing_else() -> None:
    """Shrink-only: the withholding set is an allowlist, so it must not be paddable.

    Without this, the totality assertion above has a free escape. An author who
    adds a field to :class:`DRGEdge` meets a red
    ``test_every_declared_edge_field_is_emitted_unless_explicitly_withheld`` and
    has two ways to answer it: emit the field (correct), or name it here (which
    silently reinstates the exact write-side drop this module exists to close).
    Review found that padding the set with a *new* field passed all 277 tests in
    ``tests/charter_offering/drg/`` — the second answer was free, and the module docstring
    legitimises it as one of two valid responses without saying it reinstates the
    bug.

    Pinning the content makes that answer cost a deliberate, diff-visible edit to
    this assertion with a written rationale, which is what Standing Order 5's
    shrink-only allowlist requires. ``provenance`` is the only legitimate member:
    no shipped node or edge carries the key, and no writer reachable from
    ``_dump_graph_document`` sets it, so withholding it is lossless today.
    """
    assert frozenset({"provenance"}) == extractor._FIELDS_WITHHELD_FROM_GRAPH_OUTPUT, (
        "The withholding set is an allowlist against silent write-side field "
        "drops. Adding a member here re-opens that hole for the named field — "
        "if that is genuinely intended, change this assertion in the same commit "
        "and say why the field must never reach *.graph.yaml."
    )


def test_provenance_is_withheld_so_graph_output_stays_stable() -> None:
    """FR-013's merge-time marker must not leak into ``*.graph.yaml``."""
    node = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC, provenance="org:acme")
    edge = DRGEdge(
        source="tactic:a",
        target="tactic:b",
        relation=Relation.REQUIRES,
        provenance="org:acme",
    )

    assert "provenance" not in extractor._node_to_dict(node)
    assert "provenance" not in extractor._edge_to_dict(edge)


def test_the_writers_still_omit_unset_optionals_and_empty_lists() -> None:
    """Field-derived does not mean field-dumping: the output shape is unchanged."""
    node = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC)
    edge = DRGEdge(source="tactic:a", target="tactic:b", relation=Relation.REQUIRES)

    assert extractor._node_to_dict(node) == {"urn": "tactic:a", "kind": "tactic"}
    assert extractor._edge_to_dict(edge) == {
        "source": "tactic:a",
        "target": "tactic:b",
        "relation": "requires",
    }


def test_the_writers_still_strip_surrounding_whitespace() -> None:
    """Wrapped YAML scalars arrive padded; the shipped graph carries them trimmed."""
    node = DRGNode(urn="tactic:a", kind=NodeKind.TACTIC, label="  Padded Label\n")
    edge = DRGEdge(
        source="tactic:a",
        target="tactic:b",
        relation=Relation.REQUIRES,
        when="  padded when\n",
        reason="\n padded reason ",
    )

    assert extractor._node_to_dict(node)["label"] == "Padded Label"
    assert extractor._edge_to_dict(edge)["when"] == "padded when"
    assert extractor._edge_to_dict(edge)["reason"] == "padded reason"


def test_the_field_derived_writers_reproduce_the_shipped_graph_exactly() -> None:
    """NFR-004: deriving from ``model_fields`` must not move one key of the graph.

    Runs the replaced hand-written shape against every shipped edge and requires
    agreement. This is the graph-neutrality claim as an executable assertion
    rather than a sentence in the PR body.
    """
    fragments = sorted(_BUILT_IN_PACK.glob("*.graph.yaml"))
    assert len(fragments) >= _MINIMUM_SHIPPED_FRAGMENTS

    yaml_safe = YAML(typ="safe")
    compared = 0
    for fragment in fragments:
        document = yaml_safe.load(fragment.read_text(encoding="utf-8")) or {}
        for raw in document.get("edges") or []:
            edge = DRGEdge.model_validate(raw)
            assert extractor._edge_to_dict(edge) == _hand_written_edge_dict(edge)
            compared += 1

    assert compared > 0, "no shipped edges were compared -- the walk found nothing"


# ---------------------------------------------------------------------------
# T021/T022 -- a newly declared field survives write -> read, non-vacuously
# ---------------------------------------------------------------------------


def _new_field_edge() -> _DRGEdgeWithNewField:
    return _DRGEdgeWithNewField(
        source="tactic:a",
        target="tactic:b",
        relation=Relation.REQUIRES,
        audit_note="ledger-42",
    )


def test_a_newly_declared_edge_field_survives_write_then_read(tmp_path: Path) -> None:
    """SC-003, through the real transport: writer → YAML file → loader → model."""
    fragment = tmp_path / "planted.graph.yaml"
    written = extractor._edge_to_dict(_new_field_edge())

    yaml_writer = YAML()
    yaml_writer.default_flow_style = False
    with fragment.open("w", encoding="utf-8") as handle:
        yaml_writer.dump({"edges": [written]}, handle)

    reloaded = YAML(typ="safe").load(fragment.read_text(encoding="utf-8"))
    restored = _DRGEdgeWithNewField.model_validate(reloaded["edges"][0])

    assert restored.audit_note == "ledger-42"
    assert restored == _new_field_edge()


# ---------------------------------------------------------------------------
# T006 -- the document-level writer derives its keys from DRGGraph.model_fields
# ---------------------------------------------------------------------------


class _DRGGraphWithNovelField(DRGGraph):
    """``DRGGraph`` plus a novel top-level field — the fourth writer's probe.

    ``_dump_graph_document`` owns the five document-level keys. Restated by hand,
    a top-level field added to :class:`DRGGraph` is dropped on write; deriving
    them from ``model_fields`` closes it.
    """

    novel_document_key: str = "planted-document-value"


def test_graph_document_to_dict_derives_the_document_level_keys() -> None:
    """W-2: the derived document writer emits every ``DRGGraph`` field, incl. novel."""
    graph = _DRGGraphWithNovelField(
        schema_version="1.0", generated_at="STATIC", generated_by="test",
        nodes=[], edges=[],
    )
    emitted = set(extractor.graph_document_to_dict(graph))
    expected = set(DRGGraph.model_fields) - extractor.FIELDS_WITHHELD_FROM_GRAPH_OUTPUT

    assert expected <= emitted
    assert "novel_document_key" in emitted


def test_the_production_dump_graph_document_does_not_drop_a_novel_field(
    tmp_path: Path,
) -> None:
    """T006: the *file-writing* path must be derived too, not just the helper.

    ``_dump_graph_document`` restated the five keys inline; this drives the real
    write path with a novel-field graph and reads the file back. Red until the
    production writer routes through ``graph_document_to_dict``.
    """
    fragment = tmp_path / "planted.graph.yaml"
    graph = _DRGGraphWithNovelField(
        schema_version="1.0", generated_at="STATIC", generated_by="test",
        nodes=[], edges=[],
    )

    extractor._dump_graph_document(graph, fragment)

    reloaded = YAML(typ="safe").load(fragment.read_text(encoding="utf-8"))
    assert reloaded["novel_document_key"] == "planted-document-value"


def test_the_hand_written_writer_shape_would_drop_the_new_field() -> None:
    """T022: the round-trip above must be able to fail.

    The replaced writer shape is run against the same edge. It drops the field —
    so the round-trip assertion is testing the change, not the language.
    """
    edge = _new_field_edge()

    assert "audit_note" not in _hand_written_edge_dict(edge)
    assert extractor._edge_to_dict(edge)["audit_note"] == "ledger-42"


def test_the_strict_model_rejects_what_the_hand_written_writer_left_behind() -> None:
    """The two halves interlock — this is why C-009 puts them in one commit.

    Read the hand-written writer's output back into the model that declares the
    field and the value is simply gone: no error, no warning, a silently
    downgraded edge. That is the outcome ``extra="forbid"`` alone cannot prevent,
    because there is nothing extra left to forbid.
    """
    dropped = _DRGEdgeWithNewField.model_validate(
        _hand_written_edge_dict(_new_field_edge())
    )

    assert dropped.audit_note is None

    with pytest.raises(ValidationError, match="[Ee]xtra"):
        DRGEdge.model_validate(extractor._edge_to_dict(_new_field_edge()))


# ---------------------------------------------------------------------------
# T015 -- _KIND_MAP is total, and its subscript read sites are safe
# ---------------------------------------------------------------------------


def test_kind_map_names_every_node_kind() -> None:
    """Derived from ``NodeKind``, so a new member cannot be dropped by omission."""
    assert set(extractor._KIND_MAP) == {kind.value for kind in NodeKind}
    assert all(extractor._KIND_MAP[kind.value] is kind for kind in NodeKind)


def test_kind_for_type_resolves_every_node_kind() -> None:
    """The five previously-dropped kinds resolve through the public helper."""
    assert [extractor._kind_for_type(kind.value) for kind in NodeKind] == list(NodeKind)


def test_kind_for_type_still_returns_none_for_an_unrecognised_type() -> None:
    """Totality closes the kind hole without turning an authoring typo into a crash.

    Inherited from ``test_extractor_asset.py``, which used ``asset`` as its
    "unknown type" probe. ``asset`` is a ``NodeKind`` and now resolves, so the
    probe moved to a string that is genuinely not a kind — the contract it was
    guarding (``.get``-based, never a raising subscript) is unchanged.
    """
    assert extractor._kind_for_type("some-future-kind-not-yet-registered") is None
    assert extractor._kind_for_type("") is None


def test_every_action_scope_field_kind_resolves_to_a_node_kind() -> None:
    """The scope-field walk subscripts ``_KIND_MAP``; prove the subscript is safe.

    The read site used ``.get(kind, NodeKind.GLOSSARY_SCOPE)``, so an unmapped
    scope-field kind produced a *wrongly-kinded* node instead of an error — a
    silent corruption rather than a silent omission. It is now a subscript, and
    this derives the safety from the declaration rather than restating the seven
    kinds.
    """
    assert extractor._ACTION_SCOPE_FIELDS
    unmapped = [kind for _, kind in extractor._ACTION_SCOPE_FIELDS if kind not in extractor._KIND_MAP]

    assert unmapped == []


# ---------------------------------------------------------------------------
# T023a -- the retired-relationship error must name a path that exists
# ---------------------------------------------------------------------------


def test_the_retired_relationship_error_does_not_point_at_a_dead_path() -> None:
    """``src/charter/offering/graph.yaml`` was retired for per-kind fragments (DD-7/DD-8).

    An error message whose "do this instead" names a file that does not exist
    sends the reader looking for it. Pinned against the filesystem rather than
    against the message text, so the assertion tracks the layout instead of the
    wording.
    """
    assert not (_BUILT_IN_PACK / "graph.yaml").exists()
    assert sorted(_BUILT_IN_PACK.glob("*.graph.yaml"))

    with pytest.raises(ValidationError) as excinfo:
        AgentProfile.model_validate({**_VALID_PROFILE, "specializes-from": "other"})

    message = str(excinfo.value)
    assert "src/charter/offering/graph.yaml" not in message
    assert ".graph.yaml" in message


# ---------------------------------------------------------------------------
# Landing fold (#2977) -- the FOURTH writer is bound to the model too
# ---------------------------------------------------------------------------


def test_the_migration_writer_also_emits_every_declared_edge_field() -> None:
    """``rewrite_opposed_by`` restates the edge field list by hand (#2977).

    The extractor's writers were derived from ``model_fields`` by this mission, so
    a new field survives that path by construction. ``rewrite_opposed_by`` was
    reported rather than swept, and it is the *org-pack migration* path -- a
    dropped field there lands in a downstream consumer's tree, not ours.

    Unifying the two writers is deliberately NOT done here: ``rewrite_opposed_by``
    lives under ``src/specify_cli/`` and reaches doctrine only through the
    ``charter.*`` facade (ADR ``2026-03-27-1``), so consuming the extractor's
    private serializer would breach that boundary. Promoting a public serializer
    across it is the architectural call #2977 asks for.

    What this test does instead is remove the *silence*. It is GREEN today -- the
    hand-restated list is currently complete -- and goes RED the moment mission B1
    adds ``impacts`` / ``is_symmetric`` or B2 adds ``aliases``, which is precisely
    when the decision has to be made. Without it that addition ships as a silent
    drop with no test to notice: the mission's own defect class, surviving in the
    one writer the mission did not close.
    """
    from specify_cli.migration import rewrite_opposed_by

    edge = DRGEdge(
        source="tactic:a",
        target="tactic:b",
        relation=Relation.REQUIRES,
        when="a condition",
        reason="a rationale",
        provenance="org:acme",
    )

    emitted = set(rewrite_opposed_by._edge_to_dict(edge))

    assert emitted == set(DRGEdge.model_fields) - extractor._FIELDS_WITHHELD_FROM_GRAPH_OUTPUT


def test_the_migration_writer_also_emits_every_declared_node_field() -> None:
    """Same binding for ``rewrite_opposed_by._node_to_dict`` (see the sibling above)."""
    from specify_cli.migration import rewrite_opposed_by

    node = DRGNode(
        urn="anti_pattern:big-ball-of-mud",
        kind=NodeKind.ANTI_PATTERN,
        label="Big Ball of Mud",
        provenance="org:acme",
        tags=["smell"],
    )

    emitted = set(rewrite_opposed_by._node_to_dict(node))

    assert emitted == set(DRGNode.model_fields) - extractor._FIELDS_WITHHELD_FROM_GRAPH_OUTPUT


# ---------------------------------------------------------------------------
# T008 (WP02, contract W-4) -- the DRGGraph *container* forbids unknown
# top-level keys, closing the last read-path silence: ``DRGNode`` and
# ``DRGEdge`` already carry ``extra="forbid"``, but the document that holds them
# did not, so a stray top-level key was accepted-and-discarded on load.
# ---------------------------------------------------------------------------

_VALID_GRAPH_DOCUMENT: dict[str, Any] = {
    "schema_version": "1.0",
    "generated_at": "STATIC",
    "generated_by": "test",
    "nodes": [],
    "edges": [],
}


def test_an_undeclared_top_level_graph_key_is_a_load_error() -> None:
    """W-4. The positive control runs first so a red cannot be a broken payload."""
    DRGGraph.model_validate(_VALID_GRAPH_DOCUMENT)

    with pytest.raises(ValidationError, match="[Ee]xtra"):
        DRGGraph.model_validate({**_VALID_GRAPH_DOCUMENT, _UNDECLARED_KEY: "a value"})


# ---------------------------------------------------------------------------
# T009 (WP02, NFR-006) -- the load boundary translates the raw pydantic
# ``ValidationError`` into a typed, *named* error identifying the offending file
# and the stray key, so a consumer can act on it. The typed error must NOT be a
# ``DRGLoadError`` subclass: many call sites ``except DRGLoadError`` and degrade
# silently to an empty graph, which is exactly the silence this WP closes. A
# stray top-level key must fail *closed*, past those handlers.
# ---------------------------------------------------------------------------

_STRAY_SOURCE = "acme-org-pack/directive.graph.yaml"


def test_load_graph_document_accepts_a_valid_document() -> None:
    """Positive control: a clean document round-trips through the typed loader."""
    graph = drg_models.load_graph_document(
        dict(_VALID_GRAPH_DOCUMENT), source=_STRAY_SOURCE
    )
    assert isinstance(graph, DRGGraph)


def test_load_graph_document_raises_a_typed_named_error_for_a_stray_key() -> None:
    """NFR-006: fail-closed with a diagnostic that names the file and the key."""
    with pytest.raises(drg_models.DRGGraphSchemaError) as excinfo:
        drg_models.load_graph_document(
            {**_VALID_GRAPH_DOCUMENT, _UNDECLARED_KEY: "a value"},
            source=_STRAY_SOURCE,
        )

    error = excinfo.value
    assert error.source == _STRAY_SOURCE
    assert error.unknown_keys == (_UNDECLARED_KEY,)
    message = str(error)
    assert _STRAY_SOURCE in message, "diagnostic must name the offending document"
    assert _UNDECLARED_KEY in message, "diagnostic must name the stray key"


def test_the_typed_error_is_not_swallowed_by_the_degrade_handlers() -> None:
    """The break is only fail-closed if it escapes ``except DRGLoadError``."""
    assert not issubclass(drg_models.DRGGraphSchemaError, DRGLoadError)


def test_a_valid_document_forbidding_extras_is_unchanged_by_the_loader() -> None:
    """The typed loader is a pure add-on: valid documents behave as before."""
    graph = drg_models.load_graph_document(
        dict(_VALID_GRAPH_DOCUMENT), source=_STRAY_SOURCE
    )
    assert graph.nodes == []
    assert graph.edges == []


# ---------------------------------------------------------------------------
# T011 (WP02) -- consumer-facing regression: the *production* file-load boundary
# (``load_graph``) surfaces the typed error, and its diagnostic is actionable.
# A node/edge-level extra key keeps the ordinary ``DRGLoadError`` path -- the
# typed error is scoped to the document container, not a catch-all.
# ---------------------------------------------------------------------------


def _write_graph_yaml(path: Path, extra: str = "") -> None:
    path.write_text(
        "schema_version: '1.0'\n"
        "generated_at: STATIC\n"
        "generated_by: acme\n"
        "nodes: []\n"
        "edges: []\n" + extra,
        encoding="utf-8",
    )


def test_load_graph_surfaces_the_typed_error_for_a_stray_top_level_key(
    tmp_path: Path,
) -> None:
    """T011: a consumer graph document with a stray key fails loud and named."""
    graph_file = tmp_path / "directive.graph.yaml"
    _write_graph_yaml(graph_file, extra="unexpected_top_key: oops\n")

    with pytest.raises(drg_models.DRGGraphSchemaError) as excinfo:
        drg_loader.load_graph(graph_file)

    error = excinfo.value
    assert str(graph_file) in error.source
    assert error.unknown_keys == ("unexpected_top_key",)
    assert "unexpected_top_key" in str(error)


def test_a_clean_consumer_graph_document_still_loads(tmp_path: Path) -> None:
    """Blast-radius floor: the typed boundary does not reject valid documents."""
    graph_file = tmp_path / "directive.graph.yaml"
    _write_graph_yaml(graph_file)

    assert drg_loader.load_graph(graph_file).nodes == []


def test_a_node_level_extra_key_still_raises_the_ordinary_load_error(
    tmp_path: Path,
) -> None:
    """The typed error is document-scoped: nested extras stay ``DRGLoadError``."""
    graph_file = tmp_path / "directive.graph.yaml"
    graph_file.write_text(
        "schema_version: '1.0'\n"
        "generated_at: STATIC\n"
        "generated_by: acme\n"
        "nodes:\n"
        "  - urn: directive:X\n"
        "    kind: directive\n"
        "    bogus_node_key: nope\n"
        "edges: []\n",
        encoding="utf-8",
    )

    with pytest.raises(DRGLoadError):
        drg_loader.load_graph(graph_file)
