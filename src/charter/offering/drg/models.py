"""Pydantic v2 models for the Doctrine Reference Graph (DRG).

Defines ``NodeKind``, ``Relation`` enums and ``DRGNode``, ``DRGEdge``,
``DRGGraph`` models with URN validation and graph convenience methods.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# ---------------------------------------------------------------------------
# URN regex -- anchored, no spaces, only lower-alpha + underscore for kind
# ---------------------------------------------------------------------------

_URN_RE = re.compile(r"^[a-z_]+:[A-Za-z0-9_/.\-]+$")


def is_valid_urn(value: str) -> bool:
    """Return whether *value* is a syntactically valid DRG URN.

    The single public read of :data:`_URN_RE` (FR-010, WP08). Callers that
    build a URN before handing it to :class:`DRGNode` / :class:`DRGEdge` use
    this to fail with their own typed, domain-appropriate error instead of
    letting a raw ``pydantic_core.ValidationError`` escape from the middle of
    an unrelated operation — the org→DRG bridge is the motivating case.

    Validity is *syntactic only*: it says nothing about whether the URN's kind
    prefix is a :class:`NodeKind` member or whether a node with that URN
    exists. Both are separate, deliberately independent checks.
    """
    return bool(_URN_RE.match(value))


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class NodeKind(StrEnum):
    """Canonical DRG node kinds.

    Superset of ``ArtifactKind`` plus action and glossary node kinds.
    """

    DIRECTIVE = "directive"
    TACTIC = "tactic"
    PARADIGM = "paradigm"
    STYLEGUIDE = "styleguide"
    TOOLGUIDE = "toolguide"
    PROCEDURE = "procedure"
    AGENT_PROFILE = "agent_profile"
    MISSION_STEP_CONTRACT = "mission_step_contract"
    TEMPLATE = "template"
    ASSET = "asset"
    ACTION = "action"
    # -- Retiring runtime glossary-term nodes (deleted in Mission C) ---------
    # ``GLOSSARY_SCOPE`` and ``GLOSSARY`` are the *runtime* glossary-term node
    # kinds. They are slated for deletion in Mission C; keep them fenced off
    # from the offering-owned kind below so that deletion is a clean, isolated
    # excision and does not disturb ``GLOSSARY_PACK``.
    GLOSSARY_SCOPE = "glossary_scope"
    GLOSSARY = "glossary"           # URN prefix: "glossary:<id>"
    # -- Offering-owned node (keep) -----------------------------------------
    # ``GLOSSARY_PACK`` is a first-order, charter-activatable doctrine kind
    # addressed by the underscore URN ``glossary_pack:<id>``. It is NOT part of
    # the retiring runtime term nodes above and survives Mission C.
    GLOSSARY_PACK = "glossary_pack"  # URN prefix: "glossary_pack:<id>"
    MISSION_TYPE = "mission_type"   # URN prefix: "mission_type:<id>"; carries `requires`->action_sequence steps, `scope`->type-wide governance (#3604)
    # URN prefix: "anti_pattern:<id>"; `rejects` targets only (D2) -- never
    # activated as a live rule; finer marking (e.g. "smell") lives in
    # `DRGNode.tags`, not a second `NodeKind` member.
    ANTI_PATTERN = "anti_pattern"
    # URN prefix: "skill:<id>"; a pack skill (thin entry point) addressed in
    # org/project DRG fragments with `requires`/`suggests` edges to the
    # procedures/directives carrying the substance.
    SKILL = "skill"


class Relation(StrEnum):
    """Typed edge relations in the DRG.

    Lineage vs. delegation vs. augmentation are three distinct concepts and
    MUST NOT be conflated (FR-001, FR-002):

    - ``SPECIALIZES_FROM`` (lineage): a profile/artifact derives from a parent,
      narrowing or extending it. This is a *static composition* relation used
      for inheritance/specialization (FR-001). It is deliberately separate from
      ``DELEGATES_TO`` so lineage never leaks into runtime handoff traversal.
    - ``DELEGATES_TO`` (delegation): a *runtime handoff* relation -- one agent
      hands work to another at execution time (FR-002). It is never inferred
      from lineage.
    - ``ENHANCES`` / ``OVERRIDES`` (augmentation pair, FR-014, mission
      ``charter-ux-and-org-pack-vocabulary-01KSAF14``): a pack artifact declares
      ``enhances: <id>`` to field-merge into a built-in, or ``overrides: <id>``
      to declare a full replacement.
    - ``REPLACES`` is retained for backward compatibility with existing
      hand-authored fragments (R-2).
    - ``REFINES`` (refinement, #2079): an artifact narrows or sharpens the
      applicability or meaning of the target (a parent or built-in) without
      replacing it. It is distinct from ``APPLIES`` (an action applies a
      directive/tactic) and from ``SPECIALIZES_FROM`` (static profile/artifact
      lineage): a refinement is a first-class, traversable relation, never a
      synonym for ``APPLIES``. Previously the org→DRG bridge silently downgraded
      ``refines`` to ``APPLIES`` (a dead sink); it is now preserved end-to-end.
    - ``IN_TENSION_WITH`` / ``RECONCILES_TENSION`` / ``REJECTS`` (tension
      vocabulary, mission ``doctrine-tension-edges-01KY1WPC``, FR-001/002/003):
      three distinct relations that must not be confused with each other or
      with the relations above.

      - ``IN_TENSION_WITH`` is **symmetric and non-transitive**: two co-valid,
        co-activatable artefacts compete on the same decision, and neither is
        deprecated by the other. It is stored as a single canonical edge
        (lexicographically-smaller URN as source, C-002) and queried from
        either endpoint via :meth:`DRGGraph.edges_from`/:meth:`DRGGraph.edges_to`.
        It must NOT be confused with ``REPLACES``/supersession -- tension does
        not mean one side wins or is retired.
      - ``RECONCILES_TENSION`` is **directional**, from an active
        reconciliation artefact to one side of a tension pair. A pair counts
        as resolved only when an active artefact carries this edge to BOTH
        sides; a single edge to one side leaves the pair "half-reconciled"
        and still flagged (FR-002). It is never synthesized from
        ``IN_TENSION_WITH`` -- it must be authored explicitly.
      - ``REJECTS`` is **directional**, from a good artefact to a marked
        anti-pattern/smell node (``NodeKind.ANTI_PATTERN``). Unlike
        ``IN_TENSION_WITH`` the target is not a competing equal -- it is a
        named bad practice, not a co-valid rule -- and unlike ``REPLACES`` the
        target was never a valid rule the rejecting artefact supersedes.
    """

    REQUIRES = "requires"
    SUGGESTS = "suggests"
    APPLIES = "applies"
    SCOPE = "scope"
    VOCABULARY = "vocabulary"
    INSTANTIATES = "instantiates"
    REPLACES = "replaces"
    DELEGATES_TO = "delegates_to"
    SPECIALIZES_FROM = "specializes_from"
    ENHANCES = "enhances"
    OVERRIDES = "overrides"
    REFINES = "refines"
    IN_TENSION_WITH = "in_tension_with"
    RECONCILES_TENSION = "reconciles_tension"
    REJECTS = "rejects"


#: Canonical relation-description registry (single authority, FR-012/A2).
#: Covers all 15 ``Relation`` members (FR-005/FR-007, mission
#: ``drg-relation-parity-activation-gate-01KY48PD``); completeness is
#: enforced by ``tests/doctrine/drg/test_models.py``. This is the ONE seam
#: that both a future ``describe(relation)`` call site and the doc-parity
#: check (``docs/architecture/doctrine-relationships.md``) read from -- do
#: not duplicate this mapping anywhere else.
RELATION_DESCRIPTIONS: dict[Relation, str] = {
    # re-pinned 2026-08-12: +2 requires / +5 suggests from the #3009 curated
    # edges (#3342) -- measured against the shipped built-in graph.
    Relation.REQUIRES: (
        "A directional, hard-dependency edge: resolving or activating the "
        "source artifact pulls in the target as a mandatory prerequisite. "
        "``resolve_action_context`` walks ``requires`` edges transitively, "
        "with no depth limit, from an action's ``scope``-resolved artifacts; "
        "``charter activate --cascade`` follows the same edge to pull in "
        "artifacts that must also be active. It is the second-most-emitted "
        "relation in the built-in graph (323 edges) and is the mandatory "
        "counterpart to ``suggests``, not a stronger synonym for it."
    ),
    Relation.SUGGESTS: (
        "A directional, soft-recommendation edge: the source artifact points "
        "at content that is relevant but not mandatory. ``resolve_action_"
        "context`` walks ``suggests`` edges only up to a bounded hop depth -- "
        "unlike the unbounded transitive walk used for ``requires`` -- and "
        "the charter cascade treats a ``suggests`` target as optional, "
        "something an operator may accept or skip. It is the most-emitted "
        "relation in the built-in graph (450 edges); the boundedness of the "
        "walk, not the edge count, is what distinguishes it from ``requires``."
    ),
    Relation.APPLIES: (
        "Names the edge from an agent profile to the concrete procedure or "
        "tactic that profile executes as its operating workflow. Zero edges "
        "exist in the built-in graph, and authoring one is refused by "
        "``tests/architectural/test_no_authored_applies_edge.py``: no context "
        "resolution, no charter cascade and no reference walk follows "
        "``applies``, so an authored one names a relationship nothing "
        "traverses. The single shipped example "
        "(``agent_profile:doctrine-daphne`` --applies--> "
        "``procedure:onboard-external-agent-to-pack``) was retyped to "
        "``requires`` because it was that procedure's only inbound edge and "
        "left the profile's own operating procedure unreachable. The relation "
        "itself is not dead -- ``charter.activation.synthesizer.project_drg`` emits it "
        "during project-tier synthesis and the orphan lint accepts it as an "
        "inbound edge on a ``directive`` node -- so what is forbidden is "
        "authoring one into the shipped tree, not the relation existing. "
        "Distinct from ``scope``, which names the "
        "action-to-governance-artifact edge role, not a profile's own "
        "operating procedure -- the two are never interchangeable."
    ),
    Relation.SCOPE: (
        "Names the edge from a mission-step action node to the directives "
        "and tactics that govern performing that action, or -- since #3604 -- "
        "from a mission_type node to the type-wide governance its "
        "governance-profile.yaml selects. The action-sourced edges are the "
        "entry point walked at depth 1 by ``resolve_action_context`` before "
        "it expands through ``requires``/``suggests``; the mission_type-"
        "sourced edges are instead the entry point the charter cascade "
        "(``REFERENCE_RELATIONS``) walks when activating a mission type. It "
        "is the most heavily emitted action-adjacent relation in the "
        "built-in graph -- 204 edges as measured by a live extraction after "
        "#3604 (165 action-sourced, unchanged from before #3604 since this "
        "pass is purely additive, plus 39 mission_type-sourced); this "
        "count is not enforced by any test against the graph, so treat it "
        "as directional, not exact. Distinct from ``applies``: ``scope`` "
        "says an action -- or a mission type's own type-wide selections -- "
        "is governed by an artifact; ``applies`` says a profile executes a "
        "workflow artifact. Despite both linking guidance content to a "
        "governed node, they name different edge-roles and are never "
        "interchangeable.\n\n"
        "DELIBERATE ACCEPTED DEBT (#3633): one ``Relation.SCOPE`` member now "
        "carries two distinct source-node grains (action-sourced and "
        "mission_type-sourced, above) instead of two separate relations. "
        "This is a deliberate decision, not an oversight -- splitting the "
        "grain into e.g. ``scope`` / ``type_scope`` would churn every "
        "consumer's relation vocabulary (query filters, the charter "
        "cascade's ``REFERENCE_RELATIONS``, doctrine docs) and force a DRG "
        "merge/projection migration for a purely cosmetic grain "
        "distinction the graph already encodes structurally (a scope "
        "edge's source-node kind -- ``action`` vs ``mission_type`` -- tells "
        "a consumer which grain it is without a second relation name). Do "
        "NOT split this relation to \"fix\" the overload; if a genuine "
        "behavioral need for two distinct relations ever arises, that is a "
        "new decision to make explicitly, not a refactor of this one."
    ),
    Relation.VOCABULARY: (
        "Names the edge from a resolved doctrine artifact to a "
        "``glossary_scope`` node, walked at depth 1 by "
        "``resolve_action_context`` to surface which glossary sections apply "
        "to an action's resolved context. Intended-but-dormant: zero edges "
        "exist in the built-in graph today, so no action currently pulls in "
        "glossary scope through this relation -- the walk is implemented and "
        "exercised by tests, but no artifact author has emitted one yet."
    ),
    Relation.INSTANTIATES: (
        "A directional edge from a mission-step action node to the template "
        "it produces as its concrete output artifact, e.g. "
        "``action:documentation/design`` --instantiates--> "
        "``template:documentation/documentation-plan-template.md``. Emitted "
        "11 times in the built-in graph, exclusively from ``action`` nodes to "
        "``template`` nodes. Distinct from ``scope``, which links an action "
        "to governance content it must follow, not content it produces."
    ),
    Relation.REPLACES: (
        "A directional supersession edge: the source artifact fully "
        "supersedes the target, which is no longer applicable once the "
        "source is active. Retained for backward compatibility with "
        "existing hand-authored fragments; zero edges exist in the built-in "
        "graph by design -- new supersession is expressed by deactivating "
        "the superseded artifact directly, or, for pack overlays, via "
        "``overrides``. Distinct from ``in_tension_with``, which never "
        "implies that either side is deprecated or wrong."
    ),
    Relation.DELEGATES_TO: (
        "A directional, runtime handoff edge: one agent profile hands work "
        "to another at execution time (e.g. an implementer profile "
        "delegating a review to a reviewer profile). Deliberately kept "
        "separate from ``specializes_from`` so a static lineage relationship "
        "is never conflated with a live work handoff. Intended-but-dormant: "
        "zero edges exist in the built-in graph today -- delegation is "
        "currently expressed through a profile's ``collaboration."
        "handoff_to`` prose field, not a graph edge."
    ),
    Relation.SPECIALIZES_FROM: (
        "A directional, static lineage edge: a profile or artifact derives "
        "from a parent, narrowing or extending it. Emitted 4 times in the "
        "built-in graph, exclusively ``agent_profile`` -> ``agent_profile`` "
        "(e.g. ``python-pedro`` --specializes_from--> ``implementer-ivan``). "
        "Resolved via ``AgentProfileRepository.resolve_profile`` graph "
        "traversal at composition time, and deliberately distinct from "
        "``delegates_to`` so inheritance never leaks into runtime handoff "
        "traversal."
    ),
    Relation.ENHANCES: (
        "A directional org-pack overlay edge: a pack artifact field-merges "
        "additional content into a built-in artifact, preserving the "
        "built-in's action sequence and step I/O rather than replacing "
        "them. Zero edges exist in the built-in graph by design -- "
        "``enhances`` only ever originates from an org- or project-tier "
        "pack fragment layered on top of a shipped artifact, never between "
        "two built-in nodes. Distinct from ``overrides``, which replaces "
        "rather than merges."
    ),
    Relation.OVERRIDES: (
        "A directional org-pack overlay edge: a pack artifact declares a "
        "full replacement of a built-in artifact's content, rather than a "
        "field-merge. Zero edges exist in the built-in graph by design, for "
        "the same reason as ``enhances`` -- it only ever originates from an "
        "org- or project-tier overlay, never between two built-in nodes. "
        "Silently dropping steps or stripping step I/O when applying an "
        "``overrides`` edge is rejected by the loader."
    ),
    Relation.REFINES: (
        "A directional edge: an artifact narrows or sharpens the "
        "applicability or meaning of its target (a parent or built-in "
        "artifact) without replacing it -- a first-class, traversable "
        "relation, never a synonym for ``applies`` or ``specializes_from``. "
        "The built-in graph uses it for fixed-lens specialisations: the "
        "five-paradigm-parallel-debugging and "
        "paula-patterns-architecture-scout-review tactics refine the "
        "adversarial-squad-deployment procedure. Charter cascade follows "
        "``refines``; action-context delivery does not. The org-to-DRG "
        "bridge previously downgraded authored ``refines`` edges to "
        "``applies`` silently; that lossy downgrade has been removed, so "
        "``refines`` survives end-to-end."
    ),
    Relation.IN_TENSION_WITH: (
        "Marks two co-valid, co-activatable artefacts that compete on the "
        "same decision. The relation is symmetric and non-transitive: it is "
        "stored as a single canonical edge (lexicographically-smaller URN as "
        "source) and is queryable from either endpoint. It does not imply "
        "that either side is deprecated, superseded, or wrong -- both remain "
        "valid rules until an operator deactivates one side or activates a "
        "reconciler."
    ),
    Relation.RECONCILES_TENSION: (
        "Links an active reconciliation artefact to one side of a declared "
        "tension pair. A tension pair is treated as resolved only when an "
        "active artefact carries this edge to BOTH sides of the pair -- an "
        "edge to just one side leaves the pair half-reconciled and still "
        "flagged. It is authored explicitly and is never inferred from an "
        "``in_tension_with`` edge."
    ),
    Relation.REJECTS: (
        "A directional edge from a good artefact to a marked anti-pattern or "
        "smell node (``NodeKind.ANTI_PATTERN``), expressing rejection of a "
        "named bad practice. It is distinct from ``in_tension_with`` -- the "
        "target is not a competing equal, it is a bad practice -- and from "
        "``replaces``/supersession, since the target was never a valid rule "
        "to begin with."
    ),
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DRGNode(BaseModel):
    """A single addressable doctrine artifact node."""

    # FR-004: an authored key this model does not declare is a load error, not a
    # silent discard. Pydantic v2's default is ``extra="ignore"``, which is how a
    # graph fragment can carry a key nobody reads and nobody is told about.
    # Every sibling model under ``src/charter/offering/**/models.py`` already forbids
    # extras; this brings the DRG models in line rather than inventing a policy.
    model_config = ConfigDict(extra="forbid")

    urn: str
    kind: NodeKind
    label: str | None = None
    # Merge-time provenance marker ("built-in" | "org:<pack>" | "project").
    # Declared optional field (FR-013, D2-revised) replacing the former
    # ``object.__setattr__`` sidecar. ``None`` for nodes that never pass
    # through the three-layer merge (e.g. the extractor-built shipped graph),
    # so the field is excluded from ``graph.yaml`` serialisation by the
    # extractor's explicit field-by-field writer — graph output stays stable.
    provenance: str | None = None
    # Free-form markers (e.g. ["smell"]) for finer-grained distinctions within
    # a single NodeKind -- e.g. NodeKind.ANTI_PATTERN nodes use this to
    # distinguish "smell" from a bare anti-pattern without a second NodeKind
    # member. Explicitly modelled (not left to Pydantic v2's extra="ignore"
    # default) so an authored `tags: [...]` key round-trips instead of being
    # silently dropped on load.
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_urn(self) -> Self:
        if not _URN_RE.match(self.urn):
            raise ValueError(
                f"URN {self.urn!r} does not match pattern "
                f"{_URN_RE.pattern}"
            )
        prefix = self.urn.split(":", 1)[0]
        if prefix != self.kind.value:
            raise ValueError(
                f"URN prefix {prefix!r} does not match kind {self.kind.value!r}"
            )
        return self


class DRGEdge(BaseModel):
    """A typed, directed relationship between two nodes."""

    # FR-004 -- see ``DRGNode.model_config``. This is the half that makes B1's
    # ``impacts`` / ``is_symmetric`` real: without it a typo'd or unmerged edge
    # field is accepted and discarded on load.
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relation: Relation
    when: str | None = None
    reason: str | None = None
    # Merge-time provenance marker; see ``DRGNode.provenance``. Named
    # ``provenance`` (NOT ``source``) to avoid colliding with the source
    # endpoint URN above.
    provenance: str | None = None

    @model_validator(mode="after")
    def _validate_urns(self) -> Self:
        for field_name in ("source", "target"):
            value = getattr(self, field_name)
            if not _URN_RE.match(value):
                raise ValueError(
                    f"Edge {field_name} {value!r} does not match URN pattern "
                    f"{_URN_RE.pattern}"
                )
        return self


class DRGGraph(BaseModel):
    """Top-level DRG graph document (``graph.yaml``)."""

    # FR-001 / contract W-4 -- the container matches its members. ``DRGNode``
    # and ``DRGEdge`` already forbid extras; without the same policy here an
    # unknown *top-level* key (a typo'd or unmerged document field) was accepted
    # and silently discarded on load. This is a deliberate, consumer-facing
    # read-path break: an org-pack graph document with a stray top-level key now
    # fails to load rather than degrading. The load boundary translates the raw
    # ``ValidationError`` into :class:`DRGGraphSchemaError`, which names the file
    # and the offending key (see :func:`load_graph_document`).
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0$")
    generated_at: str
    generated_by: str
    nodes: list[DRGNode]
    edges: list[DRGEdge]

    # -- Convenience methods (efficient lookups) ----------------------------

    def node_urns(self) -> set[str]:
        """Return the set of all node URNs in the graph."""
        return {n.urn for n in self.nodes}

    def edges_from(
        self,
        urn: str,
        relation: Relation | None = None,
    ) -> list[DRGEdge]:
        """Return outgoing edges from *urn*, optionally filtered by *relation*."""
        return [
            e
            for e in self.edges
            if e.source == urn and (relation is None or e.relation == relation)
        ]

    def edges_to(
        self,
        urn: str,
        relation: Relation | None = None,
    ) -> list[DRGEdge]:
        """Return incoming edges to *urn*, optionally filtered by *relation*.

        Reverse-adjacency mirror of :meth:`edges_from`: an edge is incoming when
        its ``target`` equals *urn*. Used by cascade traversal (e.g. Wave 3
        deactivation) that needs to find every node pointing *at* a given URN.

        Implemented as an O(E) scan for parity with :meth:`edges_from`; no
        reverse index is pre-built.
        """
        return [
            e
            for e in self.edges
            if e.target == urn and (relation is None or e.relation == relation)
        ]

    def get_node(self, urn: str) -> DRGNode | None:
        """Look up a node by URN, or ``None`` if not found."""
        for n in self.nodes:
            if n.urn == urn:
                return n
        return None


# ---------------------------------------------------------------------------
# Strict graph-document load boundary (FR-001 / contract W-4 / NFR-006)
# ---------------------------------------------------------------------------


class DRGGraphSchemaError(Exception):
    """A graph document declared a top-level key ``DRGGraph`` does not define.

    Raised at the load boundary (:func:`load_graph_document`) in place of the raw
    :class:`pydantic.ValidationError`, so the diagnostic names the offending
    *document* and *key* a consumer must fix rather than dumping a nested pydantic
    trace.

    Deliberately **not** a subclass of ``charter.offering.drg.loader.DRGLoadError``:
    several call sites ``except DRGLoadError`` and degrade to an empty graph, and
    a stray top-level key must fail *closed* past those handlers (NFR-006), not be
    swallowed into a silently-degraded read -- the exact silence this closes.
    """

    def __init__(self, *, source: str, unknown_keys: tuple[str, ...]) -> None:
        self.source = source
        self.unknown_keys = unknown_keys
        rendered = ", ".join(repr(key) for key in unknown_keys)
        super().__init__(
            f"{source}: graph document declares unknown top-level key(s) "
            f"{rendered}. DRGGraph accepts only {sorted(DRGGraph.model_fields)}. "
            "Remove the stray key(s); or, if the field is intended, declare it on "
            "DRGGraph in the same commit as the writer that emits it."
        )


def _unknown_top_level_keys(exc: ValidationError) -> tuple[str, ...]:
    """Return the top-level ``extra_forbidden`` keys *exc* names, in first-seen order.

    Only single-element locations (top-level document fields) count: a nested
    node/edge ``extra_forbidden`` (location length > 1) must not masquerade as a
    document-level stray key -- that case stays on the ordinary
    :class:`ValidationError` path so callers wrap it as they already do.
    """
    keys: list[str] = []
    for error in exc.errors():
        location = error.get("loc", ())
        if error.get("type") != "extra_forbidden" or len(location) != 1:
            continue
        key = location[0]
        if isinstance(key, str) and key not in keys:
            keys.append(key)
    return tuple(keys)


def load_graph_document(data: object, *, source: str) -> DRGGraph:
    """Validate *data* as a :class:`DRGGraph`, naming *source* on a stray key.

    The single strict load boundary for a graph *document*. An unknown top-level
    key raises :class:`DRGGraphSchemaError` naming *source* and the key (T009 /
    NFR-006). Any other validation failure propagates as the raw
    :class:`pydantic.ValidationError`, so an existing caller keeps wrapping it as
    it already does.
    """
    try:
        return DRGGraph.model_validate(data)
    except ValidationError as exc:
        unknown = _unknown_top_level_keys(exc)
        if unknown:
            raise DRGGraphSchemaError(source=source, unknown_keys=unknown) from exc
        raise
