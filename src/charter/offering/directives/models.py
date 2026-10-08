"""
Directive domain model and value objects.

Defines the Directive Pydantic model with all governance fields including
optional enrichment fields and typed cross-artifact references.

Cross-artifact relationships (directive → tactic, directive → paradigm, etc.)
are expressed **exclusively** via edges in ``packs/built-in/*.graph.yaml`` as of
Phase 1 excision (see mission
``excise-doctrine-curation-and-inline-references-01KP54J6`` WP02). The legacy
inline ``tactic_refs`` / ``applies_to`` fields have been removed from this
model; the graph is now the sole authority.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from charter.offering.artifact_kinds import ArtifactKind


#: Single ranking authority for :class:`Enforcement` ordering (FR-001).
#:
#: Keyed on the plain ``str`` value (not the enum member) so the map can be
#: defined ahead of the class body and so a test can monkeypatch a single
#: entry to prove comparison consults this map rather than falling back to
#: ``StrEnum``'s inherited lexical ``str`` comparison (SC-009). Higher rank
#: is stricter: ``required`` (2) > ``lenient-adherence`` (1) > ``advisory``
#: (0). This is deliberately explicit rather than derived from declaration
#: order or alphabetical value -- the two coincide today only by accident
#: (alphabetically "advisory" < "lenient-adherence" < "required" already
#: matches the intended rank), and a future rename (e.g. ``required`` ->
#: ``mandatory``) must not silently flip the order.
_ENFORCEMENT_RANK: dict[str, int] = {
    "advisory": 0,
    "lenient-adherence": 1,
    "required": 2,
}


class Enforcement(StrEnum):
    """Enforcement level for a directive.

    Ordering is rank-driven (:data:`_ENFORCEMENT_RANK`), not the lexical
    ``str`` comparison ``StrEnum`` would otherwise inherit -- see
    :meth:`__lt__`. ``==``, hashing, and JSON/str serialization are
    untouched: only the four ordering dunders are overridden, so
    ``Enforcement.REQUIRED == "required"`` and
    ``json.dumps(Enforcement.REQUIRED)``-style value serialization keep
    working exactly as before (FR-001).
    """

    REQUIRED = "required"
    LENIENT_ADHERENCE = "lenient-adherence"
    ADVISORY = "advisory"

    @property
    def rank(self) -> int:
        """This level's position in the explicit total order (higher = stricter)."""
        return _ENFORCEMENT_RANK[self.value]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Enforcement):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Enforcement):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Enforcement):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Enforcement):
            return NotImplemented
        return self.rank >= other.rank


class DirectiveReference(BaseModel):
    """Cross-artifact reference within a directive.

    ``when``/``reason`` are optional curated edge metadata carried symmetrically
    with the DRG edge the extractor mints from this reference
    (:class:`charter.offering.drg.models.DRGEdge`): ``when`` is the activation trigger and
    ``reason`` the rationale. They exist so a defensible relationship can live in
    source-artifact frontmatter (single canonical authority) rather than the
    hand-authored overlay — the #3009 residual promotions
    (mission ``kind-complete-cascade-orphan-wiring-01M0FQCD``). Both default to
    ``None`` so every pre-existing ``{type, id}`` reference is unchanged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: ArtifactKind
    id: str
    when: str | None = None
    reason: str | None = None


class Directive(BaseModel):
    """
    A constraint-oriented governance rule.

    Directives define WHAT must be done (or avoided) with an enforcement
    level. Relationships to the tactics that describe HOW live in
    ``packs/built-in/*.graph.yaml`` as typed edges; they are no longer embedded
    as inline ``tactic_refs`` on this model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    # Required fields
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_-]*$")
    schema_version: str = Field(pattern=r"^1\.0$", alias="schema_version")
    title: str
    intent: str
    enforcement: Enforcement

    # Optional enrichment fields
    scope: str | None = None
    procedures: list[str] = Field(default_factory=list)
    integrity_rules: list[str] = Field(default_factory=list, alias="integrity_rules")
    validation_criteria: list[str] = Field(
        default_factory=list, alias="validation_criteria"
    )
    explicit_allowances: list[str] = Field(
        default_factory=list, alias="explicit_allowances"
    )
    references: list[DirectiveReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lenient_adherence(self) -> "Directive":
        if (
            self.enforcement == Enforcement.LENIENT_ADHERENCE
            and not self.explicit_allowances
        ):
            raise ValueError(
                "explicit_allowances must be provided when enforcement is lenient-adherence"
            )
        return self
