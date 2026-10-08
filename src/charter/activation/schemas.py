"""Pydantic schemas for charter config extraction.

Defines the output schema for:
- governance.yaml (testing, quality, performance, branch strategy)
- directives.yaml (numbered rules and enforcement)
- metadata.yaml (extraction provenance and statistics)
"""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML

from charter.activation.activations import ActivationEntry

__all__ = [
    "BranchStrategyConfig",
    "CharterCatalog",
    "CharterCatalogReference",
    "CharterTestingConfig",
    "CharterYaml",
    "CharterYamlMetadata",
    "CommitConfig",
    "Directive",
    "DirectivesConfig",
    "GovernanceCharterConfig",
    "ExtractionMetadata",
    "GovernanceConfig",
    "PerformanceConfig",
    "QualityConfig",
    "RetrospectiveGovernance",
    "SectionsParsed",
    "emit_yaml",
]
# NOTE (WP06 of doctrine-charter-split-unification, closing the WP05 note):
# ``RetrospectiveGovernance`` is now public — FR-005c's resolver
# (``specify_cli.retrospective.policy._load_charter_yaml_retrospective_block``)
# imports it directly to validate the authored ``governance.retrospective``
# block, so it has a real src/ caller and no longer trips the symbol-level
# dead-code gate (``tests/architectural/test_no_dead_symbols.py``).
# ``RetrospectiveGovernancePermissions`` stays OUT: it is still reached only
# through ``RetrospectiveGovernance.permissions`` (composition, same module)
# and has zero direct importers.


# Header comment for all emitted YAML files
YAML_HEADER = (
    "# Auto-generated from charter.md — do not edit directly.\n"
    "# Run 'spec-kitty charter sync' to regenerate.\n\n"
)


class CharterTestingConfig(BaseModel):
    """Testing requirements extracted from charter."""

    min_coverage: int = 0
    tdd_required: bool = False
    framework: str = ""
    type_checking: str = ""


class QualityConfig(BaseModel):
    """Code quality requirements."""

    linting: str = ""
    pr_approvals: int = 1
    pre_commit_hooks: bool = False


class CommitConfig(BaseModel):
    """Commit message conventions."""

    convention: str | None = None


class PerformanceConfig(BaseModel):
    """Performance and scale requirements."""

    cli_timeout_seconds: float = 2.0
    dashboard_max_wps: int = 100


class BranchStrategyConfig(BaseModel):
    """Git branch strategy and rules."""

    main_branch: str = "main"
    dev_branch: str | None = None
    rules: list[str] = Field(default_factory=list)


class GovernanceCharterConfig(BaseModel):
    """The ``governance.charter`` block: the charter-authored selection of governance artifacts.

    Field naming mirrors the corresponding ``ActiveCharterService`` property
    name (e.g. ``selected_styleguides`` mirrors
    ``ActiveCharterService.styleguides``). The ``selected_<kind>`` field set is
    pinned against the ``ArtifactKind``-derived kind tables by
    ``tests/architectural/test_kind_table_derivation.py``
    (``test_overlayable_is_the_selected_fields_minus_the_non_overlaid_kinds``).
    The former property-introspection guard
    (``test_artifact_selection_completeness.py``) no longer exists.
    """

    selected_paradigms: list[str] = Field(default_factory=list)
    selected_directives: list[str] = Field(default_factory=list)
    selected_tactics: list[str] = Field(default_factory=list)
    selected_styleguides: list[str] = Field(default_factory=list)
    """Charter-active styleguide IDs (mirrors ``ActiveCharterService.styleguides``).
    Default empty preserves backwards compatibility (NFR-005)."""
    selected_toolguides: list[str] = Field(default_factory=list)
    """Charter-active toolguide IDs (mirrors ``ActiveCharterService.toolguides``).
    Default empty preserves backwards compatibility (NFR-005)."""
    selected_procedures: list[str] = Field(default_factory=list)
    """Charter-active procedure IDs (mirrors ``ActiveCharterService.procedures``).
    Default empty preserves backwards compatibility (NFR-005)."""
    selected_agent_profiles: list[str] = Field(default_factory=list)
    """Charter-active agent-profile IDs (mirrors
    ``ActiveCharterService.agent_profiles``). Default empty preserves backwards
    compatibility (NFR-005)."""
    selected_mission_step_contracts: list[str] = Field(default_factory=list)
    """Charter-active mission-step-contract IDs (mirrors
    ``ActiveCharterService.mission_step_contracts``). Default empty preserves
    backwards compatibility (NFR-005)."""
    selected_glossary_packs: list[str] = Field(default_factory=list)
    """Charter-active glossary-pack IDs (mirrors
    ``ActiveCharterService.glossary_packs``). Default empty preserves backwards
    compatibility (NFR-005)."""
    selected_assets: list[str] = Field(default_factory=list)
    """Charter-active asset IDs (mirrors ``ActiveCharterService.assets``).
    Default empty preserves backwards compatibility (NFR-005)."""
    available_tools: list[str] = Field(default_factory=list)
    template_set: str | None = None
    authority_paths: list[str] = Field(default_factory=list)
    """Repository-relative directories surfaced as authority pointers
    (e.g. ``docs/context/``). Populated by WP02 (charter sync) from the
    charter's fenced YAML block; consumed by WP04 renderer when building the
    ``Project authority paths:`` section. Default empty preserves backwards
    compatibility (NFR-005): existing YAML without this key parses unchanged."""
    governance_references: list[str] = Field(default_factory=list)
    """Repository-relative supporting governance documents that should be
    included in charter context as required reading (e.g.
    ``spec/constitution.md``). These are supporting references only:
    ``.kittify/charter/charter.md`` remains the runtime governance center."""


class RetrospectiveGovernancePermissions(BaseModel):
    """Granular retrospective capability flags, as authored in ``charter.yaml``.

    PURE DATA (mission ``doctrine-charter-split-unification`` FR-005a,
    research.md D3): the runtime counterpart
    ``specify_cli.retrospective.policy.RetrospectivePermissions`` is deliberately
    NOT imported here — the charter layer must not depend upward on
    ``specify_cli`` (policed by the FR-008 architectural gate). The two shapes
    are kept key-for-key aligned instead, and the resolver reads this block as a
    plain dict.

    Every flag is three-state ``bool | None``: ``None`` == "the charter does not
    claim this key", which is what keeps ``charter.md`` frontmatter a
    *contributing* secondary source (C-003) rather than being wholesale
    overridden by invented defaults. The runtime defaults live in
    ``retrospective.policy.default_policy`` and are applied there, never here.
    """

    write_record: bool | None = None
    inspect_mission_artifacts: bool | None = None
    propose_glossary_changes: bool | None = None
    propose_drg_changes: bool | None = None
    propose_doctrine_changes: bool | None = None
    apply_low_risk_changes: bool | None = None
    apply_structural_changes: bool | None = None


class RetrospectiveGovernance(BaseModel):
    """The authored ``governance.retrospective:`` block of ``charter.yaml``.

    FR-005a of mission ``doctrine-charter-split-unification``. Before this
    model existed, ``GovernanceConfig`` had no ``retrospective`` field, so an
    operator-authored block was silently DROPPED on
    ``GovernanceConfig.model_validate`` and the retrospective policy could only
    resolve from ``charter.md`` YAML frontmatter — a *resolving* read of the
    display-only companion, the invariant violation FR-005 closes.

    Keys mirror ``retrospective.policy._KNOWN_KEYS`` exactly so the block can be
    handed to ``_apply_block_to_policy`` verbatim. As with
    :class:`RetrospectiveGovernancePermissions`, every field is optional and
    defaults to ``None`` (== unclaimed), so a partial charter block overrides
    only the keys it actually authors.
    """

    enabled: bool | None = None
    timing: Literal["post_completion", "before_completion"] | None = None
    failure_policy: Literal["warn", "block"] | None = None
    write_record: bool | None = None
    generate_proposals: bool | None = None
    apply_proposals: Literal["require_human", "low_risk_auto"] | None = None
    permissions: RetrospectiveGovernancePermissions | None = None
    precedence: Literal["charter", "config"] | None = None
    generator: Literal["python"] | None = None
    strict_keys: bool | None = None


class GovernanceConfig(BaseModel):
    """Top-level governance configuration."""

    testing: CharterTestingConfig = Field(default_factory=CharterTestingConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    commits: CommitConfig = Field(default_factory=CommitConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    branch_strategy: BranchStrategyConfig = Field(default_factory=BranchStrategyConfig)
    charter: GovernanceCharterConfig = Field(default_factory=GovernanceCharterConfig)
    """Charter-level selection of governance artifacts (CR-01: field
    renamed from ``doctrine`` -- ``kitty-specs/retire-doctrine-term-
    01M0JMK9/inventory.md`` line 163). The value class was renamed
    separately (#3732: ``DoctrineSelectionConfig`` -> ``GovernanceCharterConfig``).
    No populate-by-name alias: the legacy ``doctrine`` key is read via a dict-level compat shim in
    ``charter.activation.sync.load_governance_config``, not a pydantic alias (a silent
    alias remap would defeat that shim's warn-once contract)."""
    activations: list[ActivationEntry] = Field(default_factory=list)
    """Charter-level activation registry (FR-006 / WP01 T008). The registry
    lives on :class:`GovernanceConfig` (the top-level governance namespace),
    NOT on :class:`GovernanceCharterConfig`, because activations pair
    artifacts with runtime contexts rather than selecting global defaults.
    Default empty preserves backwards compatibility (NFR-005): existing
    ``governance.yaml`` files without this key parse unchanged, and the
    emitter omits the block via :data:`_OPTIONAL_EMPTY_OMIT_KEYS`."""
    retrospective: RetrospectiveGovernance | None = None
    """The authored retrospective policy block (FR-005a of mission
    ``doctrine-charter-split-unification``). ``None`` — NOT a
    ``default_factory`` — is load-bearing: an unset charter must carry no
    ``retrospective`` block at all, both so ``charter.md`` frontmatter keeps
    resolving for legacy projects (C-003) and so emitted YAML stays
    byte-identical (NFR-005). ``None``/``{}`` is dropped on the way out by
    :data:`_OPTIONAL_EMPTY_OMIT_KEYS`."""
    enforcement: dict[str, str] = Field(default_factory=dict)


class Directive(BaseModel):
    """A single numbered directive from the charter.

    Cross-artifact applicability is now expressed via graph edges in
    the ``packs/built-in/*.graph.yaml`` fragments rather than an inline
    ``applies_to`` field
    (Phase 1 excision — mission
    ``excise-doctrine-curation-and-inline-references-01KP54J6`` WP02).
    """

    id: str
    title: str
    description: str = ""
    severity: str = "warn"
    references: list[str] = Field(default_factory=list)
    """Catalog IDs (e.g. ``["DIRECTIVE_032"]`` or tactic-id slugs) cross-linked
    from the body of a charter-extracted directive. Populated by WP02 (charter
    sync) from cited catalog IDs detected in the directive body; consumed by
    WP03/WP04 resolver/renderer via ``ActiveCharterService``. Default empty preserves
    backwards compatibility (NFR-005): existing YAML without this key parses
    unchanged."""


class DirectivesConfig(BaseModel):
    """Collection of directives extracted from charter."""

    directives: list[Directive] = Field(default_factory=list)


class SectionsParsed(BaseModel):
    """Statistics about parsed sections."""

    structured: int = 0
    ai_assisted: int = 0
    skipped: int = 0


class ExtractionMetadata(BaseModel):
    """Metadata tracking extraction provenance."""

    schema_version: str = "1.0.0"
    extracted_at: str = ""  # ISO 8601 timestamp
    charter_hash: str = ""  # "sha256:..."
    source_path: str = ".kittify/charter/charter.md"
    extraction_mode: str = "deterministic"  # "deterministic" | "hybrid" | "ai_only"
    sections_parsed: SectionsParsed = Field(default_factory=SectionsParsed)
    bundle_schema_version: int | None = None


# ---------------------------------------------------------------------------
# consolidate-charter-bundle (WP01 / T001): structured charter.yaml (v2.0.0)
# ---------------------------------------------------------------------------
#
# Contract: kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/
# charter-yaml-schema.md. Data model: ../data-model.md (Landmine 1/2/3,
# INV-1..9). ``CharterYaml`` nests the EXISTING ``GovernanceConfig`` /
# ``DirectivesConfig`` above verbatim (validation inherited, not re-authored)
# — it does not replace ``ExtractionMetadata``/the legacy governance.yaml /
# directives.yaml / metadata.yaml emitters, which remain in place until the
# WPs that retire them land.


class CharterCatalogReference(BaseModel):
    """One reference item inside the charter.yaml ``catalog`` projection.

    Mirrors the retired ``references.yaml`` reference-item shape (charter
    contract G2): ``catalog`` is byte-equivalent in content to that file's
    body, so parity/resolving consumers (``consistency_check.py``) see
    identical data.
    """

    id: str
    kind: str
    title: str
    summary: str
    source_path: str
    local_path: str


class CharterCatalog(BaseModel):
    """The DERIVED-but-committed ``catalog`` projection (charter contract G2).

    Mirrors the retired ``references.yaml`` body verbatim: ``mission``,
    ``template_set``, ``languages``, ``references``. Kept honest by the
    catalog<->activation parity check (``consistency_check.py``) plus
    freshness (data-model.md Landmine 2 extension).

    ``languages`` is nullable (issue #3292 fix): ``None`` distinguishes "no
    active-language signal was found at compile time" from a genuinely
    persisted empty list. ``charter.activation.language_scope.infer_repo_languages``
    (the single authority both this compiler and the active charter
    service's language gate consume) treats a ``None``/absent field as "keep looking,
    then admit all" and a present-but-empty list as authoritative "admit
    none" — collapsing the former into the latter on write is exactly the
    compile-then-read feedback loop #3292 closes. See that function's
    docstring for the full resolution contract.
    """

    mission: str
    template_set: str
    languages: list[str] | None = Field(default=None)
    references: list[CharterCatalogReference] = Field(default_factory=list)


class CharterYamlMetadata(BaseModel):
    """``charter.yaml``'s ``metadata`` block (charter contract G4).

    Deliberately narrower than :class:`ExtractionMetadata`: Landmine 2
    (data-model.md) retires the self-referential ``charter_hash`` (a hash of
    ``charter.yaml`` cannot live *inside* ``charter.yaml`` — chicken-egg)
    along with ``extraction_mode``/``sections_parsed``, which have no
    meaning once ``governance``/``directives``/activation are hand-authored
    rather than extracted. ``bundle_schema_version`` is KEPT — read by
    ``versioning.py``.
    """

    model_config = ConfigDict(extra="forbid")

    generated_at: str = ""
    bundle_schema_version: int = 2


class CharterYaml(BaseModel):
    """The structured shape of the git-tracked, authorable ``charter.yaml``.

    Contract: ``kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/
    charter-yaml-schema.md``.

    ⚠ Activation is FLAT AT THE ROOT (paula BLOCKER-1) — the ten
    ``activated_*`` / ``mission_type_activations`` fields below are NOT
    nested under an ``activation:`` key, matching the activation presets
    (``packs/built-in/presets/<name>.yaml``), so
    ``pack_context._read_activated_*`` / ``_read_list_key`` and
    ``activation_engine.commit_plan`` read/write them unchanged.
    ``model_config`` forbids extra fields, which doubles as the structural
    guard against a stray nested ``activation:`` mapping creeping back in
    (a nested mapping is not a declared field on this model, so
    ``extra="forbid"`` rejects it).

    Each ``activated_*`` field is three-state (charter contract G3):
    ``None`` == absent key == the kind is unrestricted (every available
    artifact of it is effective); ``[]`` == explicit fail-closed empty; a
    non-empty list == the activated set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="2.0.0", pattern=r"^\d+\.\d+\.\d+$")
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)
    directives: DirectivesConfig = Field(default_factory=DirectivesConfig)
    catalog: CharterCatalog

    activated_kinds: list[str] | None = None
    mission_type_activations: list[str] | None = None
    activated_directives: list[str] | None = None
    activated_tactics: list[str] | None = None
    activated_styleguides: list[str] | None = None
    activated_toolguides: list[str] | None = None
    activated_paradigms: list[str] | None = None
    activated_procedures: list[str] | None = None
    activated_agent_profiles: list[str] | None = None
    activated_mission_step_contracts: list[str] | None = None

    overrides: dict[str, Any] = Field(default_factory=dict)
    metadata: CharterYamlMetadata = Field(default_factory=CharterYamlMetadata)


# WP02: keys that are NEW additions in this mission and MUST be omitted
# from emitted YAML when their value is empty, so existing serialized
# fixtures and user charters stay byte-identical pre-/post-mission
# (NFR-005). Anchored centrally so future "additive optional" fields can
# join the same allow-list without touching the writer logic.
_OPTIONAL_EMPTY_OMIT_KEYS: frozenset[str] = frozenset({
    "references",                        # Directive.references (cross-link list)
    "authority_paths",                   # GovernanceCharterConfig.authority_paths
    "governance_references",             # GovernanceCharterConfig.governance_references
    # WP01 (charter-mediated-doctrine-selection): additive `selected_<kind>`
    # parity fields. Keep empty values out of emitted YAML so existing
    # serialized fixtures and user charters stay byte-identical pre-/post-
    # mission (NFR-005).
    "selected_styleguides",
    "selected_toolguides",
    "selected_procedures",
    "selected_agent_profiles",
    "selected_mission_step_contracts",
    # WP04 (glossary-pack-doctrine-kind): same additive-optional treatment for
    # the glossary-pack selection field so a fresh project doesn't start
    # emitting `selected_glossary_packs: []` into every charter (NFR-005).
    "selected_glossary_packs",
    # Wave B landing fold (write-side-seam-matrix-tracer): the ASSET kind's
    # selection field gets the same additive-optional treatment so a fresh
    # project doesn't start emitting `selected_assets: []` into every
    # charter (NFR-005).
    "selected_assets",
    # WP01 T008 (charter-mediated-doctrine-selection): activation registry
    # block on GovernanceConfig — empty list ⇒ omit from emitted YAML so
    # the default-config fixture remains byte-stable (NFR-005).
    "activations",
    # WP05 (doctrine-charter-split-unification, FR-005a): the authored
    # retrospective policy block on GovernanceConfig. This entry is the one
    # that forced the allow-list to widen past "empty list" — the field is
    # `RetrospectiveGovernance | None`, so an unset charter serializes it as
    # `None` (and an explicitly empty block as an all-unclaimed mapping),
    # neither of which the pre-WP05 list-only rule could drop. Without it a
    # bare `retrospective:` key leaks into every emitted governance document
    # (NFR-005).
    "retrospective",
})


def _is_omittable_empty(value: Any) -> bool:
    """Return ``True`` when an allow-listed key's value carries no information.

    Three empty shapes qualify, matching the three ways an additive optional
    field can serialize:

    * ``None`` — an unset ``X | None`` field (e.g. ``GovernanceConfig.
      retrospective``).
    * an empty list — the original (and still the most common) case.
    * a mapping whose values are *all* themselves omittable — an authored-but-
      empty block such as ``retrospective: {}``, which pydantic materializes as
      a model with every field ``None`` (and a nested all-``None`` sub-model),
      not as a literal empty dict.

    Everything else is information: ``0``, ``False`` and ``''`` are values the
    operator may legitimately have authored and are never pruned.
    """
    if value is None:
        return True
    if isinstance(value, list):
        return not value
    if isinstance(value, dict):
        return all(_is_omittable_empty(item) for item in value.values())
    return False


def _prune_optional_empties(node: Any) -> Any:
    """Recursively drop optional additive fields whose value is empty.

    Walks dicts/lists and removes entries whose key is in
    :data:`_OPTIONAL_EMPTY_OMIT_KEYS` AND whose value is empty per
    :func:`_is_omittable_empty`. Leaves all other keys untouched so existing
    required defaults (e.g. empty strings, zero ints, the non-allow-listed
    ``enforcement: {}``) remain serialized for downstream consumers that rely
    on them.
    """
    if isinstance(node, dict):
        pruned: dict[str, Any] = {}
        for key, value in node.items():
            if key in _OPTIONAL_EMPTY_OMIT_KEYS and _is_omittable_empty(value):
                continue
            pruned[key] = _prune_optional_empties(value)
        return pruned
    if isinstance(node, list):
        return [_prune_optional_empties(item) for item in node]
    return node


def emit_yaml(model: BaseModel, path: Path) -> None:
    """Write a Pydantic model to a YAML file with header comment.

    Args:
        model: Pydantic model instance to serialize
        path: Output file path

    Example:
        >>> config = GovernanceConfig(testing=TestingConfig(min_coverage=90))
        >>> emit_yaml(config, Path("governance.yaml"))
    """
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.width = 4096  # Prevent line wrapping

    # Convert model to dict using Pydantic v2 API, then prune optional empty
    # additive fields so the on-disk bytes stay backward compatible
    # (NFR-005).
    data = _prune_optional_empties(model.model_dump(mode="json"))

    # Write with header comment
    with open(path, "w", encoding="utf-8") as f:
        f.write(YAML_HEADER)
        yaml.dump(data, f)
