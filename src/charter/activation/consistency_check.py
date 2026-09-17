"""Charter pack consistency check — validates activated artifact IDs (FR-011)."""

from __future__ import annotations

import contextvars
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.bundle import CHARTER_YAML
from charter.activation.catalog import resolve_doctrine_root
from charter.activation.charter_yaml_io import load_charter_yaml
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import (
    ArtifactKind,
    MissionTypeNotAnArtifactKind,
    UnknownArtifactIdError,
    resolve_artifact_urn,
)
from charter.activation.pack_context import CharterPackConfigError, PackContext, resolve_charter_yaml_pointer
from charter.activation.pack_manager import YAML_KEY_MAP, CharterPackManager

if TYPE_CHECKING:  # pragma: no cover -- static-typing only, see lazy-import note below.
    from charter.drg import DRGEdge, DRGGraph
    from charter.offering.directives.models import Directive
    from charter.offering.directives.repository import DirectiveRepository

__all__ = [
    "run_consistency_check",
    "scan_unreconciled_tensions",
]

# ConsistencyReport / TensionFinding: kept out of __all__ per the symbol-level
# dead-code gate (test_no_dead_symbols.py) -- no external caller imports
# either by name (both are consumed via attribute access on
# run_consistency_check()'s return value, same precedent as
# CharterYamlCorruptError above).
#
# scan_enforcement_lattice_violations (FR-002, mission
# governance-at-the-gate WP01): same rationale -- no OTHER src/ module wires
# it as a runtime caller yet (only ``run_consistency_check`` itself, via
# ``_check_enforcement_lattice``, and this module's own tests import it
# directly). Kept out of __all__ for the same reason; wiring a dedicated CLI
# surface for the lattice gate is out of WP01's scope.
#
# scan_decision_documentation_scoped_on_implement (FR-004, mission
# governance-at-the-gate WP03): same rationale as the lattice scan above --
# only ``run_consistency_check`` (via
# ``_check_decision_documentation_on_implement``) and this module's own
# tests call it directly.

#: FR-010/SC-001: the two resolution-path strings, verbatim, for a
#: ``tension_unreconciled`` finding (contracts/tension-finding.md). Hoisted to
#: a module constant (Sonar S1192) since both :class:`TensionFinding`'s
#: default and any future re-render of the same pair must never drift from
#: these exact strings.
_TENSION_RESOLUTION_PATHS: tuple[str, str] = (
    "deactivate one side",
    "activate a reconciler",
)


# Internal-only (not exported): raised and caught within this module to route a
# corrupt/unreadable charter.yaml (activation lists or catalog) into the
# fail-closed verification_errors path. Kept out of __all__ per the
# symbol-level dead-code gate — no external caller imports it (the
# fail-closed tests trigger it via corrupt input).
class CharterYamlCorruptError(RuntimeError):
    """``charter.yaml`` exists but is unreadable or structurally invalid (#2530).

    IC-04 re-home: originally named ``ReferencesCorruptError`` and scoped to
    ``references.yaml`` alone. WP04 re-points ``_load_reference_ids_by_kind``
    (the catalog parity read) onto ``charter.yaml``, so this is now raised
    when a resolved ``charter.yaml`` is present but unparseable, not a
    mapping, or missing a valid ``catalog.references`` list. (The SIBLING
    activation-list read, :func:`_load_raw_activation_lists`, fails closed
    with :class:`charter.activation.pack_context.CharterPackConfigError` instead --
    reused directly rather than re-invented, since a dangling ``charter:``
    pointer is exactly the condition ``PackContext.from_config`` (WP02)
    already raises that same exception for.) Deliberately distinct from the
    ``None`` return of :func:`_load_reference_ids_by_kind`, which signals the
    legitimate "no charter synthesis has run yet" no-op skip. Callers must
    fail closed on this exception (surface a
    ``ConsistencyReport.verification_errors`` entry and treat the report as
    NOT coherent), never treat it the same as the ``None``/skip case --
    an empty finding list must mean "verified coherent", never "could not
    verify".
    """


# ---------------------------------------------------------------------------
# DRG source kinds: these carry edges to other kinds in the DRG (Pattern A).
# ---------------------------------------------------------------------------
_DRG_SOURCE_KINDS: frozenset[str] = frozenset({"directive", "tactic", "styleguide", "toolguide"})

# ---------------------------------------------------------------------------
# Map from CLI kind names (in YAML_KEY_MAP) to DRG URN singular kind prefixes.
# Not all CLI kinds have a DRG representation; absent entries are skipped in
# DRG traversal.
# ---------------------------------------------------------------------------
_CLI_KIND_TO_DRG_SINGULAR: dict[str, str] = {
    "directive": "directive",
    "tactic": "tactic",
    "styleguide": "styleguide",
    "toolguide": "toolguide",
    "paradigm": "paradigm",
    "procedure": "procedure",
    "agent-profile": "agent_profile",
    "mission-step-contract": "mission_step_contract",
    "glossary-pack": "glossary_pack",
    # "mission-type" has no DRG singular; omitted intentionally.
}

# Inverse: DRG singular → CLI kind (for DRG edge traversal lookups).
_DRG_SINGULAR_TO_CLI_KIND: dict[str, str] = {v: k for k, v in _CLI_KIND_TO_DRG_SINGULAR.items()}


# ---------------------------------------------------------------------------
# TensionFinding (T024, FR-009/FR-010, contracts/tension-finding.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TensionFinding:
    """A co-activated, unreconciled ``in_tension_with`` pair (FR-009).

    Attributes:
        pair: The sorted URN pair (lexicographically smaller first) --
            authoring the tension in either direction, or discovering it from
            either endpoint, produces exactly one ``TensionFinding`` keyed on
            this same sorted tuple (INV-001, Edge Case: symmetric authoring
            drift).
        resolution_paths: Exactly two entries, always these verbatim strings
            (SC-001) -- deliberately not free text, so both consumers
            (consistency-check JSON, ``charter activate`` warning) render an
            identical resolution vocabulary.
    """

    pair: tuple[str, str]
    resolution_paths: tuple[str, str] = _TENSION_RESOLUTION_PATHS

    def to_json_dict(self) -> dict[str, Any]:
        """Serialise to the JSON shape from ``contracts/tension-finding.md``."""
        return {
            "type": "tension_unreconciled",
            "pair": list(self.pair),
            "resolution_paths": list(self.resolution_paths),
        }


# ---------------------------------------------------------------------------
# ConsistencyReport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsistencyReport:
    """Result of a consistency check against activated doctrine artifacts.

    Attributes:
        coherent: True when no unknown references, missing cross-references,
            kind violations, duplicates, config<->derived parity
            divergences, or verification failures were found.
        unknown_references: IDs activated for a kind that do not exist in doctrine.
        missing_from_doctrine: IDs referenced by DRG edges but absent from the
            target kind's activation set.
        kind_violations: IDs that appear in the wrong kind's activation set, or
            duplicate IDs within a single activation set.
        reference_id_divergences: FR-005/T017 -- ID-level parity findings
            between ``config.activated_*`` and the compiled reference set
            (IC-04: ``.kittify/charter/charter.yaml``'s ``catalog.references``
            -- formerly the retired ``references.yaml``). Forward direction
            (every kind): a config-activated ID that does not resolve in the
            compiled reference set is the #2524 dangler class. Reverse
            direction (paradigms only -- the one kind rendered 1:1 with no
            DRG-transitive expansion): a compiled paradigm reference with no
            matching config activation.
        graph_kind_gaps: FR-005/T018 -- per-ID parity findings (T007
            re-point) between ``config.activated_*`` and the
            activation-filtered DRG graph. A config-activated stem that
            resolves to a canonical doctrine id but whose node does not
            survive in the activation-filtered graph is reported as
            ``{cli_kind}/{stem}``. Formerly KIND-granular (a whole-kind
            dangler when zero nodes of a kind survived); T007 re-pointed
            this onto the WP01-corrected
            ``charter.activation.drg_activation.filter_graph_by_activation`` gate, which resolves
            the config-stem<->DRG-URN-id mismatch that made per-ID
            unsuitable before (see ``_check_graph_kind_parity``).
        verification_errors: #2530 -- fail-closed signal distinct from every
            other (empty) finding list above. Populated when a parity check
            could not run at all because its input was unreadable or
            structurally invalid (a corrupt/truncated ``charter.yaml``, a
            dangling config.yaml ``charter:`` pointer, or a DRG
            load/validation failure) -- as opposed to the legitimate "not
            yet synthesized" no-op skip (no ``charter.yaml`` on disk yet).
            An empty finding list must mean "verified coherent", never
            "could not verify"; this field is how the guard reports the
            latter instead of silently reporting the former.
        unreconciled_tensions: FR-009/FR-010 -- co-activated
            ``in_tension_with`` pairs (directive/tactic/styleguide/toolguide
            nodes) with no active reconciler bridging both sides
            (contracts/tension-finding.md). Deliberately additive/advisory
            (NFR-001): unlike every other field above, this one is NEVER
            folded into the ``coherent`` reduction below -- a tension is a
            competing-doctrine signal for the operator to weigh, not a
            config<->doctrine defect. Populated on the same fail-closed DRG
            load as :attr:`graph_kind_gaps`; a scan failure lands in
            ``verification_errors`` instead of silently reporting ``[]``.
        enforcement_lattice_violations: FR-002 -- for every active
            ``reconciles_tension`` directive->directive edge, a violation of
            ``rank(enforcement(reconciler)) >= rank(enforcement(operand))``
            or of the "reconciler is never `required`" bound (FR-003).
            Unlike ``unreconciled_tensions``, this IS folded into
            ``coherent`` below -- a lattice violation is a genuine
            doctrine-authoring defect, not an advisory signal.
        decision_documentation_on_implement_violations: FR-004 -- for the
            ``implement`` action's FULL delivered directive bundle (the same
            scope+requires+suggests resolution
            :func:`charter.offering.drg.query.resolve_context` produces for
            ``charter context --action implement --json``, per SC-002's
            "bundle directive_ids" framing -- not merely implement's direct
            DRG ``scope`` edges), one entry per ``required``
            decision-documentation directive delivered there. The class-level
            durable-teeth counterpart to FR-005's one-time removal: this gate
            guards against a *future* ``required`` decision-documentation
            directive re-entering ``implement``, however it re-enters
            (a direct scope edge OR a transitive ``requires`` chain through
            an in-scope procedure/tactic/directive). Folded into
            ``coherent`` below, same as ``enforcement_lattice_violations``
            -- a genuine doctrine-authoring defect, not an advisory signal.
        suggestions: Human-readable resolution instructions for each finding.
    """

    coherent: bool
    unknown_references: list[str] = field(default_factory=list)
    missing_from_doctrine: list[str] = field(default_factory=list)
    kind_violations: list[str] = field(default_factory=list)
    reference_id_divergences: list[str] = field(default_factory=list)
    graph_kind_gaps: list[str] = field(default_factory=list)
    verification_errors: list[str] = field(default_factory=list)
    unreconciled_tensions: list[TensionFinding] = field(default_factory=list)
    enforcement_lattice_violations: list[str] = field(default_factory=list)
    decision_documentation_on_implement_violations: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialise to a JSON string (FR-011 JSON output surface)."""
        return json.dumps(
            {
                "coherent": self.coherent,
                "unknown_references": self.unknown_references,
                "missing_from_doctrine": self.missing_from_doctrine,
                "kind_violations": self.kind_violations,
                "reference_id_divergences": self.reference_id_divergences,
                "graph_kind_gaps": self.graph_kind_gaps,
                "verification_errors": self.verification_errors,
                "unreconciled_tensions": [t.to_json_dict() for t in self.unreconciled_tensions],
                "enforcement_lattice_violations": self.enforcement_lattice_violations,
                "decision_documentation_on_implement_violations": (self.decision_documentation_on_implement_violations),
                "suggestions": self.suggestions,
            },
            indent=2,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_activation_set(
    activated_by_kind: dict[str, frozenset[str] | None],
    kind: str,
) -> frozenset[str] | None:
    """Return the activated ID set for *kind*, or None when absent.

    ``None`` means no explicit activation in config.yaml — backward-compat.
    """
    return activated_by_kind.get(kind)


def _get_raw_activation_list(
    raw_activated_by_kind: dict[str, list[str] | None],
    kind: str,
) -> list[str] | None:
    """Return the raw list of IDs for *kind*, or None when absent.

    The consistency check needs the un-deduplicated YAML list so duplicate
    activation entries remain observable.
    """
    return raw_activated_by_kind.get(kind)


def _load_config_yaml_mapping(config_path: Path) -> dict[str, Any]:
    """Parse ``.kittify/config.yaml`` into a plain mapping (``{}`` if absent)."""
    if not config_path.exists():
        return {}
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        raise CharterPackConfigError(f"Cannot read configuration {config_path}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _load_raw_activation_source(repo_root: Path) -> dict[str, Any]:
    """Resolve the mapping raw activation lists are read from (IC-04).

    Mirrors :meth:`charter.activation.pack_context.PackContext.from_config`'s two-state
    INV-2/INV-5 resolution, so this guard and the activation engine never
    diverge on which source is authoritative (closing the WP02<->WP04
    transient-parity coupling):

    * ``charter:`` pointer absent in ``config.yaml`` -> legacy/un-migrated
      project. Activation is read directly from ``config.yaml`` (the
      pre-relocation behavior, unchanged).
    * Pointer present -> ``charter.yaml`` MUST resolve to a readable
      mapping; a dangling pointer or unparseable/non-mapping ``charter.yaml``
      is a fail-loud :class:`CharterPackConfigError` (#2530 re-homed onto
      charter.yaml), never a silent fallback to the legacy config-embedded
      keys.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    config_data = _load_config_yaml_mapping(config_path)

    charter_path = resolve_charter_yaml_pointer(repo_root, config_data)
    if charter_path is None:
        return config_data
    if not charter_path.exists():
        raise CharterPackConfigError(f".kittify/config.yaml 'charter:' pointer names {charter_path}, which does not exist.")
    try:
        loaded = load_charter_yaml(charter_path)
    except Exception as exc:  # noqa: BLE001  # re-raised as a typed, fail-closed signal.
        raise CharterPackConfigError(f"Invalid YAML in {charter_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise CharterPackConfigError(f"{charter_path} root must be a mapping.")
    return dict(loaded)


def _load_raw_activation_lists(ctx: ProjectContext) -> dict[str, list[str] | None]:
    """Read activation lists from charter.yaml, without deduplicating entries.

    IC-04: re-pointed from a direct ``config.yaml`` read onto the same
    charter.yaml activation source :class:`charter.activation.pack_context.PackContext`
    resolves (via the ``charter:`` pointer) -- see
    :func:`_load_raw_activation_source`.
    """
    data = _load_raw_activation_source(ctx.require_repo_root())

    result: dict[str, list[str] | None] = {}
    for kind, yaml_key in YAML_KEY_MAP.items():
        raw = data.get(yaml_key)
        if raw is None:
            result[kind] = None
        elif isinstance(raw, list):
            result[kind] = [str(item) for item in raw]
        else:
            result[kind] = []
    return result


def _collect_all_doctrine_ids(
    ctx: ProjectContext,
    manager: CharterPackManager,
) -> dict[str, frozenset[str]]:
    """Return a mapping of CLI kind → frozenset of doctrine IDs (loaded once).

    Invalid/missing doctrine dirs return an empty frozenset per kind.
    """
    all_ids: dict[str, frozenset[str]] = {}
    for kind in YAML_KEY_MAP:
        try:
            all_ids[kind] = manager.list_available(ctx, kind)
        except ValueError:
            all_ids[kind] = frozenset()
    return all_ids


def _has_explicit_activation(raw_activated_by_kind: dict[str, list[str] | None]) -> bool:
    """Return True when config.yaml contains at least one activation key."""
    return any(raw is not None for raw in raw_activated_by_kind.values())


def _split_urn(urn: str) -> tuple[str, str]:
    """Split ``"<kind>:<id>"`` into ``(kind, id)``.

    Returns ``(urn, "")`` when the URN has no colon.
    """
    head, _sep, tail = urn.partition(":")
    return (head, tail)


def _check_unknown_references(
    activated_by_kind: dict[str, frozenset[str] | None],
    all_doctrine_ids: dict[str, frozenset[str]],
    unknown_references: list[str],
    suggestions: list[str],
) -> None:
    """Populate *unknown_references* and *suggestions* for unknown IDs (FR-011)."""
    for kind in YAML_KEY_MAP:
        activated = _get_activation_set(activated_by_kind, kind)
        if activated is None:
            continue
        known_ids = all_doctrine_ids.get(kind, frozenset())
        for activated_id in sorted(activated):
            if activated_id not in known_ids:
                unknown_references.append(f"{kind}/{activated_id}")
                suggestions.append(f"{kind}/{activated_id}: Not found in doctrine. Run 'charter deactivate {kind} {activated_id}' to remove.")


def _check_drg_cross_kind_refs(
    ctx: ProjectContext,
    activated_by_kind: dict[str, frozenset[str] | None],
    missing_from_doctrine: list[str],
    suggestions: list[str],
) -> None:
    """Populate *missing_from_doctrine* for cross-kind DRG edge gaps (FR-012).

    Background: The DRG uses numeric URN IDs (e.g. ``directive:DIRECTIVE_001``)
    while config.yaml uses human-readable IDs (e.g.
    ``001-architectural-integrity-standard``). There is currently no
    canonical mapping between the two ID systems. The cross-kind check
    therefore operates at the KIND level: if a source artifact of an
    activated kind has a DRG edge to a target kind, and that target kind's
    activation set is explicitly set to empty (``[]``), the reference is
    unresolvable and the target kind is flagged as missing.

    ``None`` activation means backward-compat (all active) — no finding.
    A non-empty activation set satisfies the check regardless of specific IDs.
    """
    try:
        from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415
        from charter.activation.drg_activation import filter_graph_by_activation

        repo_root = ctx.require_repo_root()
        pack_context = ctx.require_pack_context()
        full_drg = load_validated_graph(repo_root)
        activated_drg = filter_graph_by_activation(full_drg, pack_context)

        reported_kind_pairs: set[tuple[str, str]] = set()
        for edge in activated_drg.edges:
            _inspect_drg_edge(
                edge,
                activated_by_kind,
                missing_from_doctrine,
                suggestions,
                reported_kind_pairs,
            )
    except Exception:  # noqa: BLE001
        # DRG load is best-effort; failures are surfaced by other tooling.
        pass


def _inspect_drg_edge(
    edge: object,
    activated_by_kind: dict[str, frozenset[str] | None],
    missing_from_doctrine: list[str],
    suggestions: list[str],
    reported_kind_pairs: set[tuple[str, str]],
) -> None:
    """Check one DRG edge for cross-kind activation gaps."""
    src_singular, _src_id = _split_urn(getattr(edge, "source", ""))
    tgt_singular, _tgt_id = _split_urn(getattr(edge, "target", ""))

    if src_singular not in _DRG_SOURCE_KINDS:
        return
    if src_singular == tgt_singular:
        # Same-kind edge: ID systems don't align; skip.
        return

    tgt_cli_kind = _DRG_SINGULAR_TO_CLI_KIND.get(tgt_singular)
    if tgt_cli_kind is None:
        return

    target_activated = _get_activation_set(activated_by_kind, tgt_cli_kind)
    if target_activated is None or len(target_activated) > 0:
        # None = backward-compat (all active); non-empty = satisfied.
        return

    src_cli_kind = _DRG_SINGULAR_TO_CLI_KIND.get(src_singular, src_singular)
    pair_key = (src_cli_kind, tgt_cli_kind)
    if pair_key in reported_kind_pairs:
        return
    reported_kind_pairs.add(pair_key)

    entry = f"{tgt_cli_kind}/<all>"
    if entry not in missing_from_doctrine:
        missing_from_doctrine.append(entry)
        suggestions.append(
            f"{tgt_cli_kind}/<all>: Kind '{tgt_cli_kind}' is referenced by "
            f"activated '{src_cli_kind}' artifacts via DRG edges but its "
            f"activation set is empty. "
            f"Run 'charter activate {tgt_cli_kind} <id>' "
            f"or add --cascade when activating the source."
        )


def _check_duplicates(
    raw_activated_by_kind: dict[str, list[str] | None],
    kind_violations: list[str],
) -> None:
    """Detect duplicate IDs within a single activation set."""
    for kind in YAML_KEY_MAP:
        raw_list = _get_raw_activation_list(raw_activated_by_kind, kind)
        if raw_list is None:
            continue
        seen: set[str] = set()
        for item in raw_list:
            if item in seen:
                kind_violations.append(f"{kind}/{item}: Duplicate entry in activation set.")
            seen.add(item)


def _check_kind_violations(
    activated_by_kind: dict[str, frozenset[str] | None],
    all_doctrine_ids: dict[str, frozenset[str]],
    unknown_references: list[str],
    kind_violations: list[str],
) -> None:
    """Detect IDs that belong to the wrong kind's activation set."""
    for kind in YAML_KEY_MAP:
        activated = _get_activation_set(activated_by_kind, kind)
        if activated is None:
            continue
        own_ids = all_doctrine_ids.get(kind, frozenset())
        for artifact_id in sorted(activated):
            _check_kind_violation_for_artifact(
                kind,
                artifact_id,
                own_ids,
                all_doctrine_ids,
                unknown_references,
                kind_violations,
            )


def _check_kind_violation_for_artifact(
    kind: str,
    artifact_id: str,
    own_ids: frozenset[str],
    all_doctrine_ids: dict[str, frozenset[str]],
    unknown_references: list[str],
    kind_violations: list[str],
) -> None:
    """Record a kind-mismatch violation for one activated *artifact_id*, if any."""
    if f"{kind}/{artifact_id}" in unknown_references:
        return  # Already flagged; avoid double-reporting.
    if artifact_id in own_ids:
        return  # Correct kind.
    other_kind = _find_owning_kind(artifact_id, kind, all_doctrine_ids)
    if other_kind is not None:
        kind_violations.append(f"{kind}/{artifact_id}: ID belongs to kind '{other_kind}', not '{kind}'.")


def _find_owning_kind(
    artifact_id: str,
    exclude_kind: str,
    all_doctrine_ids: dict[str, frozenset[str]],
) -> str | None:
    """Return the first kind (other than *exclude_kind*) whose id set contains *artifact_id*."""
    for other_kind, other_ids in all_doctrine_ids.items():
        if other_kind == exclude_kind:
            continue
        if artifact_id in other_ids:
            return other_kind  # Report once per misplaced ID.
    return None


def _resolve_charter_yaml_path(repo_root: Path) -> Path:
    """Resolve the ``charter.yaml`` path for the catalog/reference read (INV-5).

    Honors the ``.kittify/config.yaml`` ``charter:`` pointer when present
    (:func:`charter.activation.pack_context.resolve_charter_yaml_pointer` -- the one
    shared pointer-resolution implementation); defaults to the canonical
    ``.kittify/charter/charter.yaml`` location otherwise. Unlike activation
    (:func:`_load_raw_activation_source`), there is no "legacy" fallback
    source for the catalog -- ``references.yaml`` (the file this replaces)
    was never pointer-resolved, so a pointer-absent project simply reads the
    canonical default location.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    config_data = _load_config_yaml_mapping(config_path)
    # Explicit annotation: the ``charter.*`` mypy override (pyproject.toml
    # [[tool.mypy.overrides]]) sets follow_imports="skip" for intra-package
    # imports, which erases resolve_charter_yaml_pointer's declared
    # "-> Path | None" return type to Any at this call site. Annotating
    # recovers the real type without a suppression comment.
    pointer: Path | None = resolve_charter_yaml_pointer(repo_root, config_data)
    return pointer if pointer is not None else repo_root / CHARTER_YAML


def _load_reference_ids_by_kind(ctx: ProjectContext) -> dict[str, frozenset[str]] | None:
    """Parse ``charter.yaml``'s ``catalog.references``, grouped by kind.

    IC-04: re-pointed from the retired ``references.yaml`` onto
    ``charter.yaml``'s ``catalog`` section, which mirrors the retired
    file's body verbatim (``charter.activation.schemas.CharterCatalog`` docstring,
    charter contract G2).

    Returns ``None`` only when ``charter.yaml`` has not been materialised
    yet -- a legitimate no-op skip (nothing to check against), NOT a
    corruption signal.

    Raises:
        CharterYamlCorruptError: ``charter.yaml`` exists but cannot be
            trusted -- unparseable YAML, a non-mapping document root, or a
            missing/malformed ``catalog.references`` list (#2530).
            Fail-closed: a guard that cannot read its own input must never
            report a silent pass by treating "corrupt" the same as
            "not yet synthesized".
    """
    charter_yaml_path = _resolve_charter_yaml_path(ctx.require_repo_root())
    if not charter_yaml_path.exists():
        return None

    try:
        data = load_charter_yaml(charter_yaml_path)
    except Exception as exc:  # noqa: BLE001  # re-raised as a typed, fail-closed signal below.
        raise CharterYamlCorruptError(f"{charter_yaml_path} could not be parsed: {exc}") from exc

    if not isinstance(data, dict):
        raise CharterYamlCorruptError(f"{charter_yaml_path} does not contain a YAML mapping at its document root.")

    catalog = data.get("catalog")
    if not isinstance(catalog, dict):
        raise CharterYamlCorruptError(f"{charter_yaml_path} is missing a valid 'catalog' mapping.")

    entries = catalog.get("references")
    if not isinstance(entries, list):
        raise CharterYamlCorruptError(f"{charter_yaml_path} catalog is missing a valid 'references' list.")

    by_kind: dict[str, set[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        ref_id = entry.get("id")
        if not isinstance(kind, str) or not isinstance(ref_id, str):
            continue
        _, _, bare_id = ref_id.partition(":")
        by_kind.setdefault(kind, set()).add(bare_id)
    return {kind: frozenset(ids) for kind, ids in by_kind.items()}


def _check_reference_id_parity(
    ctx: ProjectContext,
    raw_activated_by_kind: dict[str, list[str] | None],
    reference_id_divergences: list[str],
    verification_errors: list[str],
    suggestions: list[str],
) -> None:
    """FR-005/T017: config.activated_* <-> references.yaml, at ID level.

    Forward direction (every kind): every explicitly-activated config stem
    MUST resolve to a canonical id in the compiled reference set, using the
    same ``resolve_artifact_urn`` canonicalization ``compiler.py`` itself
    uses to build ``references.yaml``. A config-activated stem that does not
    resolve is the exact #2524 dangler class (an artefact live in config but
    missing from the derived output).

    Reverse direction (paradigms only): paradigms are rendered 1:1 from
    ``config.activated_paradigms`` with no DRG-transitive expansion
    (``compiler._build_references_from_service`` -- "Selection-only ...
    never DRG-reachable"), so a paradigm resolving in references.yaml with
    no matching config activation is unambiguously stale. The reverse check
    is deliberately NOT extended to directive/tactic/styleguide/toolguide/
    procedure/agent-profile: those kinds are DRG-transitively expanded (a
    directive can pull in a tactic via a ``requires`` edge with no direct
    ``config.activated_tactics`` entry), so "extra" entries there are
    expected, not a divergence -- flagging them would be a false-positive
    machine, not a regression guard.

    Org/project overlay resolution (#2529): ``resolve_artifact_urn`` must be
    given the SAME ``org_roots`` that ``compiler.py``'s equivalent resolver
    call threads through (``list(pack_context.pack_roots[1:])`` --
    ``pack_roots`` is ``(builtin_root, *org_pack_roots)``, so slicing off
    index 0 leaves only the configured org/project overlay roots; empty for
    a project with no org packs, so behaviour is unchanged there). Without
    this, a config-activated ORG-only artefact raises
    ``UnknownArtifactIdError`` here, is swallowed by the ``except`` below,
    and the guard silently skips it -- while the compiler's un-caught
    resolver call crashes on the exact same stem. That is a false negative,
    not a best-effort skip.

    Fail-closed on corrupt input (#2530, re-homed onto charter.yaml by
    IC-04): a ``charter.yaml`` that exists but cannot be parsed/trusted
    raises :class:`CharterYamlCorruptError` from
    :func:`_load_reference_ids_by_kind`; that is caught here and surfaced as
    a *verification_errors* entry (not silently treated as "nothing to
    check against", which is reserved for the file genuinely not existing
    yet).

    Campsite note (#2759/T010): the forward and reverse directions are
    pre-extracted into :func:`_check_reference_id_forward_parity` and
    :func:`_check_reference_id_reverse_parity` so this orchestrator stays
    well under the complexity ceiling once
    ``specify_cli.charter_runtime.freshness.computer`` gains a read-path
    consumer of this whole check (WP03) -- pure refactor, no behavior change.
    """
    try:
        references_by_kind = _load_reference_ids_by_kind(ctx)
    except CharterYamlCorruptError as exc:
        verification_errors.append(f"charter.yaml: {exc}")
        suggestions.append(
            f"charter.yaml: Could not verify config<->references parity "
            f"({exc}). Run 'spec-kitty charter synthesize' (or "
            f"resynthesize) to regenerate .kittify/charter/charter.yaml's "
            f"catalog, or restore it from version control."
        )
        return
    if references_by_kind is None:
        return  # No compiled reference set yet -- nothing to check against.

    doctrine_root = resolve_doctrine_root()
    pack_context = ctx.require_pack_context()
    org_roots = list(pack_context.pack_roots[1:])

    _check_reference_id_forward_parity(
        raw_activated_by_kind,
        references_by_kind,
        doctrine_root=doctrine_root,
        org_roots=org_roots,
        reference_id_divergences=reference_id_divergences,
        suggestions=suggestions,
    )
    _check_reference_id_reverse_parity(
        raw_activated_by_kind,
        references_by_kind,
        reference_id_divergences=reference_id_divergences,
        suggestions=suggestions,
    )


def _check_reference_id_forward_parity(
    raw_activated_by_kind: dict[str, list[str] | None],
    references_by_kind: dict[str, frozenset[str]],
    *,
    doctrine_root: Path,
    org_roots: list[Path],
    reference_id_divergences: list[str],
    suggestions: list[str],
) -> None:
    """Forward direction (every kind): config.activated_* -> references.yaml.

    Every explicitly-activated config stem MUST resolve to a canonical id in
    the compiled reference set (the #2524 dangler class). See
    :func:`_check_reference_id_parity` for the full contract.
    """
    for cli_kind in YAML_KEY_MAP:
        try:
            kind_enum = ArtifactKind.from_operator_token(cli_kind)
        except MissionTypeNotAnArtifactKind:
            continue  # "mission-type" has no ArtifactKind / DRG representation.

        raw_list = raw_activated_by_kind.get(cli_kind)
        if not raw_list:
            continue  # None (backward-compat all-active) or [] (nothing activated).

        known_ref_ids = references_by_kind.get(kind_enum.value, frozenset())
        for stem in sorted(set(raw_list)):
            try:
                urn = resolve_artifact_urn(kind_enum, stem, doctrine_root=doctrine_root, org_roots=org_roots)
            except UnknownArtifactIdError:
                continue  # Already reported by _check_unknown_references.
            _, _, canonical_id = urn.partition(":")
            if canonical_id not in known_ref_ids:
                reference_id_divergences.append(f"{cli_kind}/{stem}")
                suggestions.append(
                    f"{cli_kind}/{stem}: Activated in config.yaml but does not "
                    f"resolve in .kittify/charter/charter.yaml's catalog. Run "
                    f"'spec-kitty charter synthesize' (or resynthesize) to "
                    f"regenerate the compiled reference set."
                )


def _check_reference_id_reverse_parity(
    raw_activated_by_kind: dict[str, list[str] | None],
    references_by_kind: dict[str, frozenset[str]],
    *,
    reference_id_divergences: list[str],
    suggestions: list[str],
) -> None:
    """Reverse direction (paradigms only): references.yaml -> config.activated_paradigms.

    Paradigms are rendered 1:1 with no DRG-transitive expansion, so a
    compiled paradigm reference with no matching config activation is
    unambiguously stale. See :func:`_check_reference_id_parity` for why this
    is scoped to paradigms only.
    """
    paradigm_list = raw_activated_by_kind.get("paradigm")
    if paradigm_list is None:
        return
    known_paradigm_stems = frozenset(paradigm_list)
    for ref_id in references_by_kind.get("paradigm", frozenset()):
        if ref_id not in known_paradigm_stems:
            reference_id_divergences.append(f"paradigm/{ref_id}")
            suggestions.append(
                f"paradigm/{ref_id}: Resolves in "
                f".kittify/charter/charter.yaml's catalog but is not in "
                f"config.activated_paradigms. Run 'charter deactivate "
                f"paradigm {ref_id}' or reconcile config.yaml."
            )


def _resolve_graph_kind_parity_stem(
    cli_kind: str,
    kind_enum: ArtifactKind,
    stem: str,
    surviving_urns: frozenset[str],
    *,
    doctrine_root: Path,
    org_roots: list[Path],
    graph_kind_gaps: list[str],
    verification_errors: list[str],
    suggestions: list[str],
) -> None:
    """Resolve one activated stem and check its per-ID DRG-graph survival (T007).

    Narrow catch (``except UnknownArtifactIdError``, never broad ``except
    Exception``): this check's contract is "config<->graph parity", so a stem
    it cannot resolve is itself a "could not verify parity for this id"
    condition and is reported by name into *verification_errors* -- in
    addition to (not instead of) the separate "unknown to doctrine at all"
    report :func:`_check_unknown_references` already produces for the same
    stem. A non-``UnknownArtifactIdError`` failure here (a genuine
    programming bug, not a config-drift condition) is deliberately left
    uncaught and propagates -- collapsing this into a broad ``except
    Exception`` would silently misreport a real bug as ordinary drift.
    """
    try:
        urn = resolve_artifact_urn(kind_enum, stem, doctrine_root=doctrine_root, org_roots=org_roots)
    except UnknownArtifactIdError as exc:
        verification_errors.append(f"{cli_kind}/{stem}: {exc}")
        suggestions.append(
            f"{cli_kind}/{stem}: Could not resolve to a canonical doctrine "
            f"id while checking config<->graph parity ({exc}). Run "
            f"'charter deactivate {cli_kind} {stem}' to remove, or fix the "
            f"stem."
        )
        return
    if urn not in surviving_urns:
        graph_kind_gaps.append(f"{cli_kind}/{stem}")
        suggestions.append(
            f"{cli_kind}/{stem}: Activated in config.yaml but does not "
            f"survive in the activation-filtered DRG graph. Regenerate "
            f"graph.yaml / run 'spec-kitty charter resynthesize' and check "
            f"'activated_kinds' in config.yaml."
        )


def _check_graph_kind_parity(
    ctx: ProjectContext,
    raw_activated_by_kind: dict[str, list[str] | None],
    graph_kind_gaps: list[str],
    verification_errors: list[str],
    suggestions: list[str],
) -> None:
    """FR-005/T018: config.activated_* <-> DRG graph, at per-ID level (T007).

    T007 (workaround collapse, plan.md IC-02): re-pointed from KIND-granular
    to per-ID, consuming the WP01-corrected
    :func:`charter.activation.drg_activation.filter_graph_by_activation` gate directly instead of
    reproducing a hand-rolled kind-membership check. Before WP01, this
    function deliberately avoided that gate because its per-artifact-ID Step
    3 compared a DRG node's canonical id against config *stems* without
    resolving the stem<->canonical-id mismatch -- WP01 closed that mismatch
    (the gate now resolves stems to canonical URNs internally and compares on
    full URN), so the workaround this function used to need no longer
    applies. This is a deliberate **behavior upgrade**, not a pure refactor: a
    config-activated stem that resolves to doctrine but does not survive in
    the activation-filtered graph is now flagged by its own id (``{cli_kind}/
    {stem}``), not merely by "some id of this kind is missing" (the old
    whole-kind-dangler granularity).

    For each explicitly-activated stem this resolves it to a canonical URN
    via :func:`charter.activation.kind_vocabulary.resolve_artifact_urn` (the same
    resolver :func:`_check_reference_id_parity` uses for the identical
    stem<->canonical bridge) and checks membership in the activation-filtered
    graph's surviving node URNs -- see
    :func:`_resolve_graph_kind_parity_stem`.

    NOTE: this function deliberately does NOT import
    ``specify_cli.*freshness*`` (layer rule -- ``freshness/computer.py`` is a
    ``specify_cli`` module that imports ``charter``, so ``charter`` cannot
    import it back) and asserts a disjoint property from freshness (temporal
    staleness vs config<->derived set parity).

    Fail-closed on DRG-load failure (#2530): the built-in DRG graph is
    always bundled with the package, so a failure loading/validating it
    (``load_validated_graph`` raises on ``assert_valid`` rejection) or
    resolving ``ctx``'s required fields is a genuine "could not verify"
    condition, never a legitimate "not yet synthesized" skip -- unlike
    ``charter.yaml``, there is no not-yet-materialised state for the DRG.
    A failure here is therefore surfaced as a *verification_errors* entry
    instead of a silent early return. This catch stays broad (``except
    Exception``) -- it guards graph load/validate, a structurally different
    failure mode from the narrow per-stem resolution catch in
    :func:`_resolve_graph_kind_parity_stem`; collapsing the two would let a
    genuine per-stem programming bug masquerade as a DRG-load failure.
    """
    try:
        from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415
        from charter.activation.drg_activation import filter_graph_by_activation

        repo_root = ctx.require_repo_root()
        pack_context = ctx.require_pack_context()
        full_drg = load_validated_graph(repo_root)
        activated_drg = filter_graph_by_activation(full_drg, pack_context)
    except Exception as exc:  # noqa: BLE001  # fail-closed signal below, not a silent pass.
        verification_errors.append(f"drg: Could not verify config<->graph kind parity ({type(exc).__name__}: {exc}).")
        suggestions.append(
            f"drg: Could not verify config<->graph kind parity "
            f"({type(exc).__name__}: {exc}). Regenerate graph.yaml / run "
            f"'spec-kitty charter resynthesize' and retry."
        )
        return

    surviving_urns = frozenset(node.urn for node in activated_drg.nodes)
    doctrine_root = resolve_doctrine_root()
    org_roots = list(pack_context.org_roots)

    for cli_kind in _CLI_KIND_TO_DRG_SINGULAR:
        raw_list = raw_activated_by_kind.get(cli_kind)
        if not raw_list:
            continue  # None (backward-compat all-active) or [] (nothing activated).
        kind_enum = ArtifactKind.from_operator_token(cli_kind)
        for stem in sorted(set(raw_list)):
            _resolve_graph_kind_parity_stem(
                cli_kind,
                kind_enum,
                stem,
                surviving_urns,
                doctrine_root=doctrine_root,
                org_roots=org_roots,
                graph_kind_gaps=graph_kind_gaps,
                verification_errors=verification_errors,
                suggestions=suggestions,
            )


# ---------------------------------------------------------------------------
# Shared gate resources (T009, #3808): one DRG load + one DoctrineService
# build per ``run_consistency_check`` invocation, shared by the three
# DRG-backed always-on gates below (``_check_unreconciled_tensions`` /
# ``_check_enforcement_lattice`` / ``_check_decision_documentation_on_implement``)
# instead of each independently calling ``load_validated_graph()`` (and, for
# the latter two, ``_build_doctrine_service()``) -- the DRG loaded 3x per run
# before this WP.
# ---------------------------------------------------------------------------


@dataclass
class _GateResources:
    """Per-``run_consistency_check`` cache: the DRG graph + ``DoctrineService``
    directives, each loaded/built at most once and shared by the three
    DRG-backed gates below (#3808 dedup).

    A load/build FAILURE is memoized too, not just the success case -- so a
    failing first gate does not trigger a second (or third) physical load
    attempt for the next gate that needs the same resource; "loaded once"
    holds on both the pass and the fail arm. Every subsequent
    :meth:`full_drg`/:meth:`directives` call within the SAME cache instance
    re-raises the identical exception object rather than re-attempting the
    load -- filesystem state cannot drift mid-``run_consistency_check``, so
    replaying the first outcome is exactly what re-attempting would have
    produced anyway, just without the second/third physical call.
    """

    repo_root: Path
    pack_context: PackContext
    _full_drg_loaded: bool = False
    _full_drg: DRGGraph | None = None
    _full_drg_error: Exception | None = None
    _directives_loaded: bool = False
    _directives: DirectiveRepository | None = None
    _directives_error: Exception | None = None

    def full_drg(self) -> DRGGraph:
        """Return the validated DRG graph, loading it at most once."""
        if not self._full_drg_loaded:
            self._full_drg_loaded = True
            from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415

            try:
                self._full_drg = load_validated_graph(self.repo_root)
            except Exception as exc:  # noqa: BLE001  # memoized; re-raised below to every caller in this run.
                self._full_drg_error = exc
        if self._full_drg_error is not None:
            raise self._full_drg_error
        if self._full_drg is None:  # pragma: no cover -- guarded by the load-or-store-error branch above.
            raise RuntimeError("_GateResources.full_drg: unreachable -- neither a graph nor an error was recorded.")
        return self._full_drg

    def directives(self) -> DirectiveRepository:
        """Return the ``DoctrineService.directives`` repository, built at most once."""
        if not self._directives_loaded:
            self._directives_loaded = True
            from charter.activation.doctrine_service_builder import _build_doctrine_service  # noqa: PLC0415

            try:
                self._directives = _build_doctrine_service(self.repo_root, org_roots=list(self.pack_context.org_roots)).directives
            except Exception as exc:  # noqa: BLE001  # memoized; re-raised below to every caller in this run.
                self._directives_error = exc
        if self._directives_error is not None:
            raise self._directives_error
        if self._directives is None:  # pragma: no cover -- guarded by the build-or-store-error branch above.
            raise RuntimeError("_GateResources.directives: unreachable -- neither directives nor an error was recorded.")
        return self._directives


#: Active per-``run_consistency_check`` :class:`_GateResources`, established by
#: :func:`_gate_resources_scope` and consulted by :func:`_resolve_full_drg` /
#: :func:`_resolve_directives`. ``None`` outside that scope -- the default
#: (unshared, load-directly) behavior every scan_* function already had.
_GATE_RESOURCES: contextvars.ContextVar[_GateResources | None] = contextvars.ContextVar("_charter_consistency_check_gate_resources", default=None)


@contextmanager
def _gate_resources_scope(ctx: ProjectContext) -> Iterator[None]:
    """Establish one shared :class:`_GateResources` for the DRG-backed gates
    ``run_consistency_check`` is about to call (#3808 T009).

    Scoped strictly to this context manager's lifetime: :func:`_resolve_full_drg`
    and :func:`_resolve_directives` consult the active cache ONLY while inside
    this ``with`` block, so ``scan_unreconciled_tensions`` /
    ``scan_enforcement_lattice_violations`` /
    ``scan_decision_documentation_scoped_on_implement`` called directly --
    ``charter activate``'s tension warning (FR-010), or this module's own
    scan_* unit tests -- are completely unaffected and keep loading
    independently, exactly as before.
    """
    resources = _GateResources(repo_root=ctx.require_repo_root(), pack_context=ctx.require_pack_context())
    token = _GATE_RESOURCES.set(resources)
    try:
        yield
    finally:
        _GATE_RESOURCES.reset(token)


def _resolve_full_drg(repo_root: Path) -> DRGGraph:
    """Load the validated DRG graph, reusing the active :class:`_GateResources`
    cache when ``run_consistency_check`` has established one (#3808);
    otherwise loads directly -- unchanged standalone behavior for scan_*
    callers outside ``run_consistency_check``.

    When the cache is active the ``repo_root`` argument is not re-read -- the
    scope's DRG is returned. Safe because every gate in a ``_gate_resources_scope``
    derives from one ``ctx`` (same ``repo_root``); revisit if a caller ever passes
    a divergent ``repo_root`` into a scan while a scope is active.
    """
    resources = _GATE_RESOURCES.get()
    if resources is not None:
        return resources.full_drg()
    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415

    return load_validated_graph(repo_root)


def _resolve_directives(repo_root: Path, pack_context: PackContext) -> DirectiveRepository:
    """Build the ``DoctrineService.directives`` repository, reusing the active
    :class:`_GateResources` cache when established (#3808); otherwise builds
    directly -- unchanged standalone behavior for scan_* callers outside
    ``run_consistency_check``.

    When the cache is active the ``repo_root``/``pack_context`` arguments are not
    re-read -- the scope's directives are returned. Safe for the same one-``ctx``
    reason as ``_resolve_full_drg``.
    """
    resources = _GATE_RESOURCES.get()
    if resources is not None:
        return resources.directives()
    from charter.activation.doctrine_service_builder import _build_doctrine_service  # noqa: PLC0415

    # Explicit local annotation (not a bare `return ...`): under this file's
    # `charter.*` mypy override (pyproject.toml [[tool.mypy.overrides]],
    # follow_imports="skip"), `_build_doctrine_service(...).directives`
    # resolves to Any at the call site -- see `_GateResources.directives`'s
    # same pattern above, where storing through an annotated field has the
    # same Any-narrowing effect. A bare `return` here would trip
    # mypy's `no-any-return` (this module carries zero pre-existing mypy
    # findings; this narrows the value instead of suppressing the check).
    directives: DirectiveRepository = _build_doctrine_service(repo_root, org_roots=list(pack_context.org_roots)).directives
    return directives


_GateFindingT = TypeVar("_GateFindingT")


def _run_fail_closed_gate(
    scan: Callable[[], list[_GateFindingT]],
    target: list[_GateFindingT],
    verification_errors: list[str],
    suggestions: list[str],
    *,
    message_stem: str,
) -> None:
    """Shared fail-closed shape backing the three DRG-backed consistency gates
    (#3808 T010).

    ``_check_unreconciled_tensions`` / ``_check_enforcement_lattice`` /
    ``_check_decision_documentation_on_implement`` each ran the IDENTICAL
    ``try: target.extend(scan()) except Exception -> append to
    (verification_errors, suggestions)`` shape, differing only in *scan*'s
    thunk, the *target* list being populated, and the *message_stem* naming
    which check failed. Collapsed here WITHOUT changing any gate's distinct
    failure literals: every caller supplies its own verbatim *message_stem*
    (e.g. ``"tension reconciliation"``, ``"enforcement lattice"``,
    ``"decision-documentation-on-implement gate"``); the ``{type(exc).__name__}:
    {exc}`` interpolation and the "Regenerate graph.yaml / run 'spec-kitty
    charter resynthesize' and retry." suggestion tail were ALREADY
    byte-identical across all three call sites pre-refactor, so sharing them
    here changes no gate's verdict.

    Whether *target*'s findings fold into ``ConsistencyReport.coherent`` is
    NOT a parameter of this wrapper -- that fold is computed once, explicitly,
    in ``run_consistency_check``'s final boolean expression (the single
    source of truth for coherence; see ``NFR-001`` there for why
    ``unreconciled_tensions`` is excluded while the other two are included).
    Threading a second "fold flag" through here would duplicate that
    decision in two places with no shared enforcement between them --  a
    latent-drift risk this refactor deliberately avoids introducing.
    """
    try:
        target.extend(scan())
    except Exception as exc:  # noqa: BLE001  # fail-closed signal below, not a silent pass.
        verification_errors.append(f"drg: Could not verify {message_stem} ({type(exc).__name__}: {exc}).")
        suggestions.append(
            f"drg: Could not verify {message_stem} ({type(exc).__name__}: {exc}). Regenerate graph.yaml / run 'spec-kitty charter resynthesize' and retry."
        )


# ---------------------------------------------------------------------------
# Tension scan (T025/T026/T027, FR-009/FR-010)
# ---------------------------------------------------------------------------
#
# T006 (workaround collapse, plan.md IC-02): this used to reimplement its own
# kind-level + per-ID activation gate (the deleted
# ``_resolve_activated_urns_for_kind``/``_node_is_tension_scan_active`` pair)
# because ``charter.activation.drg_activation.filter_graph_by_activation``'s per-artifact-ID Step 3
# compared a DRG node's canonical id directly against config *stems* without
# resolving the stem<->canonical-id mismatch -- reusing the gate would have
# made every directive node vanish regardless of what was actually activated,
# a NO-OP for directive/directive tensions (the exact defect NFR-001 exists to
# prevent). WP01 closed that mismatch inside the gate itself, so this scan now
# consumes :func:`charter.activation.drg_activation.filter_graph_by_activation` directly, exactly as
# :func:`_check_drg_cross_kind_refs` (above) already does.


def _build_tension_active_urns(
    full_drg: DRGGraph,
    pack_context: PackContext,
) -> frozenset[str]:
    """Return the set of node URNs active for tension-scan purposes.

    Re-pointed (T006) onto the WP01-corrected
    :func:`charter.activation.drg_activation.filter_graph_by_activation` gate -- see the module
    note above for why the previous hand-rolled resolution trio is no longer
    needed.
    """
    from charter.activation.drg_activation import filter_graph_by_activation

    activated_drg = filter_graph_by_activation(full_drg, pack_context)
    return frozenset(node.urn for node in activated_drg.nodes)


def _tension_candidate_pairs(
    full_drg: DRGGraph,
    active_urns: frozenset[str],
) -> set[tuple[str, str]]:
    """T025: every co-activated ``in_tension_with`` edge, keyed on sorted pair.

    Only ever iterates declared edges directly (no reachability/closure
    step) -- ``A<->B`` + ``B<->C`` never synthesizes ``A<->C`` (INV-002).
    """
    from charter.drg import Relation  # noqa: PLC0415

    pairs: set[tuple[str, str]] = set()
    for edge in full_drg.edges:
        if edge.relation != Relation.IN_TENSION_WITH:
            continue
        if edge.source in active_urns and edge.target in active_urns:
            smaller, larger = sorted((edge.source, edge.target))
            pairs.add((smaller, larger))
    return pairs


def _active_reconciles_tension_edges(
    full_drg: DRGGraph,
    active_urns: frozenset[str],
) -> list[DRGEdge]:
    """Single walk over active ``reconciles_tension`` edges (T026 traversal).

    Shared by :func:`_tension_reconciled_urns` (needs only the target URNs)
    and :func:`scan_enforcement_lattice_violations` (FR-002, needs the full
    edge to compare source/target enforcement) -- WP01 constraint: no second
    ``reconciles_tension`` walk over the graph.
    """
    from charter.drg import Relation  # noqa: PLC0415

    return [edge for edge in full_drg.edges if edge.relation == Relation.RECONCILES_TENSION and edge.source in active_urns and edge.target in active_urns]


def _tension_reconciled_urns(
    full_drg: DRGGraph,
    active_urns: frozenset[str],
) -> set[str]:
    """T026: URNs with an active ``reconciles_tension`` edge from an active source.

    General rule (not a single-reconciler special case): a side counts as
    bridged when ANY active artefact carries a ``reconciles_tension`` edge to
    it -- the same side being bridged by two different active reconcilers is
    equivalent to being bridged by one.
    """
    return {edge.target for edge in _active_reconciles_tension_edges(full_drg, active_urns)}


def scan_unreconciled_tensions(ctx: ProjectContext) -> list[TensionFinding]:
    """Scan the activation-filtered DRG for unreconciled tension pairs (FR-009).

    Single canonical authority for the tension-finding shape: both
    ``run_consistency_check`` (JSON surface) and ``charter activate``'s
    warning (FR-010) call this same function so the two surfaces can never
    render the finding differently (SC-001).

    Returns:
        One :class:`TensionFinding` per co-activated, unreconciled
        ``in_tension_with`` pair, sorted for deterministic output. A pair is
        omitted only when some active artefact(s) carry a
        ``reconciles_tension`` edge to BOTH sides -- a single-sided edge
        (half-reconciled) still produces a finding (US2 sc2).

    Raises:
        Exception: Propagates any DRG load/validation failure untouched --
            callers MUST fail closed (surface it in
            ``ConsistencyReport.verification_errors``, never treat a raised
            exception the same as a legitimately empty result).
    """
    repo_root = ctx.require_repo_root()
    pack_context = ctx.require_pack_context()
    full_drg = _resolve_full_drg(repo_root)

    active_urns = _build_tension_active_urns(full_drg, pack_context)
    candidate_pairs = _tension_candidate_pairs(full_drg, active_urns)
    if not candidate_pairs:
        return []

    reconciled_urns = _tension_reconciled_urns(full_drg, active_urns)
    return [TensionFinding(pair=pair) for pair in sorted(candidate_pairs) if not (pair[0] in reconciled_urns and pair[1] in reconciled_urns)]


def _check_unreconciled_tensions(
    ctx: ProjectContext,
    unreconciled_tensions: list[TensionFinding],
    verification_errors: list[str],
    suggestions: list[str],
) -> None:
    """FR-009: fail-closed wrapper around :func:`scan_unreconciled_tensions`.

    A DRG load/traversal failure is a genuine "could not verify" condition
    and lands in *verification_errors*, never a silent empty
    *unreconciled_tensions* masquerading as "checked, found nothing"
    (contracts/tension-finding.md, Error case). Shares its fail-closed shape
    with the other two DRG-backed gates via :func:`_run_fail_closed_gate`
    (#3808 T010) -- only the *message_stem* below is this gate's own.
    """
    _run_fail_closed_gate(
        lambda: scan_unreconciled_tensions(ctx),
        unreconciled_tensions,
        verification_errors,
        suggestions,
        message_stem="tension reconciliation",
    )


# ---------------------------------------------------------------------------
# Enforcement lattice gate (FR-001/FR-002, mission governance-at-the-gate WP01)
# ---------------------------------------------------------------------------


def _urn_is_directive(urn: str) -> bool:
    """Return whether *urn* addresses a directive node (URN prefix ``directive:``).

    ``DRGNode._validate_urn`` (``charter.offering.drg.models``) enforces the
    URN-prefix<->kind invariant at load time, so the prefix alone is a safe,
    O(1) kind check here -- no separate node lookup by URN is needed.
    """
    return urn.split(":", 1)[0] == "directive"


def _urn_bare_id(urn: str) -> str:
    """Return the ``<id>`` half of a ``<kind>:<id>`` URN."""
    return urn.split(":", 1)[1]


def scan_enforcement_lattice_violations(ctx: ProjectContext) -> list[str]:
    """FR-002: structural gate over the directive enforcement lattice.

    For every active ``reconciles_tension`` edge ``R -> X`` where BOTH
    endpoints are directives, asserts ``rank(enforcement(R)) >=
    rank(enforcement(X))`` (:class:`~charter.offering.directives.models.Enforcement`,
    FR-001) -- a reconciling directive must never be *weaker* than the
    tension operand it reconciles. An edge whose target is a non-directive
    (e.g. a tactic, which carries no ``enforcement`` field) is SKIPPED by a
    documented rule: the lattice is a directive-only ordering, and a tactic
    operand has nothing to rank against. Symmetrically, an edge whose
    *source* is not a directive is also skipped (an equally undefined rank).

    Bounded (FR-003/C-...): a reconciler is never itself ``required``,
    reported as its own violation independent of the rank comparison above
    -- a rank check alone cannot express this bound, since promoting the
    reconciler to ``required`` would trivially satisfy
    ``rank(R) >= rank(X)`` against every possible operand.

    Reuses the SAME active-``reconciles_tension``-edge traversal as
    :func:`_tension_reconciled_urns` (via
    :func:`_active_reconciles_tension_edges`) -- no second graph walk over
    ``reconciles_tension`` edges (WP01 constraint).

    Returns:
        One human-readable violation string per offending edge/rule, naming
        the edge. An empty list means the lattice holds.

    Raises:
        Exception: Propagates any DRG/doctrine load failure untouched --
            callers MUST fail closed (see :func:`_check_enforcement_lattice`).
    """
    from charter.offering.directives.models import Enforcement  # noqa: PLC0415

    repo_root = ctx.require_repo_root()
    pack_context = ctx.require_pack_context()
    full_drg = _resolve_full_drg(repo_root)

    active_urns = _build_tension_active_urns(full_drg, pack_context)
    edges = _active_reconciles_tension_edges(full_drg, active_urns)
    directive_edges = [edge for edge in edges if _urn_is_directive(edge.source) and _urn_is_directive(edge.target)]
    if not directive_edges:
        return []

    # Raw (activation-UNfiltered) doctrine service, id-keyed: active_urns
    # already gates *which* URNs are in scope via the DRG's own stem<->
    # canonical-id resolution (filter_graph_by_activation); the activation-
    # aware wrapper's per-kind dict properties, by contrast, filter on raw
    # config *stems* (charter.activation.pack_context._read_activated_directives), which
    # do not match a Directive's canonical `.id` -- using that wrapper here
    # would silently empty the lookup for every directive endpoint.
    directives = _resolve_directives(repo_root, pack_context)
    violations: list[str] = []
    for edge in directive_edges:
        reconciler = directives.get(_urn_bare_id(edge.source))
        operand = directives.get(_urn_bare_id(edge.target))
        if reconciler is None or operand is None:
            # active_urns already gated membership on both endpoints via the
            # DRG; a miss here means the doctrine repository and the DRG
            # graph disagree on what exists -- a genuine "could not verify"
            # condition, not a legitimate "nothing to rank" skip.
            missing = edge.source if reconciler is None else edge.target
            raise RuntimeError(
                f"reconciles_tension edge {edge.source} -> {edge.target} names {missing}, which the DRG reports active but the directive repository cannot resolve."
            )
        if reconciler.enforcement == Enforcement.REQUIRED:
            violations.append(f"reconciles_tension {edge.source} -> {edge.target}: reconciler {edge.source} must never be promoted to 'required'.")
            continue
        if reconciler.enforcement < operand.enforcement:
            violations.append(
                f"reconciles_tension {edge.source} -> {edge.target}: reconciler "
                f"rank ({reconciler.enforcement.value}) is below operand rank "
                f"({operand.enforcement.value})."
            )
    return violations


def _check_enforcement_lattice(
    ctx: ProjectContext,
    enforcement_lattice_violations: list[str],
    verification_errors: list[str],
    suggestions: list[str],
) -> None:
    """FR-002: fail-closed wrapper around :func:`scan_enforcement_lattice_violations`.

    Mirrors :func:`_check_unreconciled_tensions`'s fail-closed shape: a
    DRG/doctrine load failure is a genuine "could not verify" condition and
    lands in *verification_errors*, never a silently empty
    *enforcement_lattice_violations* masquerading as "checked, found
    nothing." Unlike the advisory tension scan, a non-empty result here IS
    folded into ``ConsistencyReport.coherent`` -- a lattice violation is a
    genuine doctrine-authoring defect, not a competing-doctrine signal for
    the operator to weigh. Shares its fail-closed shape with the other two
    DRG-backed gates via :func:`_run_fail_closed_gate` (#3808 T010) -- only
    the *message_stem* below is this gate's own.
    """
    _run_fail_closed_gate(
        lambda: scan_enforcement_lattice_violations(ctx),
        enforcement_lattice_violations,
        verification_errors,
        suggestions,
        message_stem="enforcement lattice",
    )


# ---------------------------------------------------------------------------
# Decision-documentation-on-implement gate (FR-004, mission
# governance-at-the-gate WP03)
# ---------------------------------------------------------------------------

#: The one action this gate protects. Only ``software-dev`` ships an
#: ``implement`` action node; hardcoding the single URN (rather than a
#: suffix match across mission types) mirrors FR-004's literal wording --
#: "the ``implement`` action" -- and avoids the cross-kind URN-suffix hijack
#: risk :func:`~charter.offering.drg.migration.calibrator.calibrate_surfaces`
#: already documents (a ``mission_step_contract`` node can share the
#: ``/implement`` suffix).
_IMPLEMENT_ACTION_URN = "action:software-dev/implement"

#: FR-004 identifies the "decision-documentation" directive CLASS by a
#: case-insensitive title-substring match, not a hardcoded id. No directive
#: schema field marks this class -- NFR-001 forbids adding one (the FR-003
#: reconciler's ``enforcement``/``explicit_allowances`` change is the ONLY
#: permitted directive-YAML edit this mission makes) -- so the title is the
#: only signal available. ``DIRECTIVE_003``'s title is literally "Decision
#: Documentation Requirement"; this deliberately also catches a differently
#: -numbered FUTURE directive that reintroduces the same obligation under a
#: title carrying this phrase (SC-004's forward-looking guard), at the
#: acknowledged cost of being evadable by an unrelated rename. A
#: schema-backed classification is future work if this proves insufficient.
_DECISION_DOCUMENTATION_TITLE_MARKER = "decision documentation"


def _is_decision_documentation_directive(directive: Directive) -> bool:
    """Return whether *directive* belongs to the decision-documentation class.

    See :data:`_DECISION_DOCUMENTATION_TITLE_MARKER` for why this is a title
    match rather than a schema field or a hardcoded id.
    """
    return _DECISION_DOCUMENTATION_TITLE_MARKER in directive.title.lower()


def scan_decision_documentation_scoped_on_implement(ctx: ProjectContext) -> list[str]:
    """FR-004: class-level gate -- no ``required`` decision-documentation
    directive is DELIVERED to the ``implement`` action.

    Resolves ``implement``'s FULL delivered directive set via
    :func:`charter.offering.drg.query.resolve_context` -- the same
    scope-edges + unconditional-``requires``-closure + depth-bounded-
    ``suggests`` resolution that backs ``charter context --action implement
    --json`` (SC-002's "bundle ``directive_ids``" framing) -- rather than
    only ``implement``'s direct DRG ``scope`` edges. This distinction is
    load-bearing: mission governance-at-the-gate's own brownfield
    investigation (WP03) found ``DIRECTIVE_003`` delivered to ``implement``
    via a transitive ``requires`` chain from an in-scope procedure even
    after its direct ``scope`` edge was removed (FR-005) -- a direct-edge
    -only gate would have passed the shipped corpus while SC-001/SC-002
    still failed. Reuses ``resolve_context`` (no bespoke second traversal)
    at the SAME effective depth ``charter context`` uses by default
    (:data:`charter.activation.context_state._MIN_EFFECTIVE_DEPTH`), so the gate and
    the CLI surface it protects can never disagree on what "delivered"
    means.

    Bounded to :data:`_IMPLEMENT_ACTION_URN` -- the one action FR-004 names;
    this is a targeted regression guard, not a general "no required
    decision-documentation directive anywhere" rule (``plan``/``specify``/
    ``tasks``/``retrospect``/``review`` legitimately retain ``DIRECTIVE_003``,
    FR-005 edge case).

    Returns:
        One human-readable violation string per offending directive, naming
        the directive id and title. An empty list means the gate holds
        (including the legitimate case where ``implement`` delivers no
        directives at all, or the action node is absent from the graph).

    Raises:
        Exception: Propagates any DRG/doctrine load failure untouched --
            callers MUST fail closed (see
            :func:`_check_decision_documentation_on_implement`).
    """
    from charter.activation.context_state import _MIN_EFFECTIVE_DEPTH  # noqa: PLC0415
    from charter.offering.directives.models import Enforcement  # noqa: PLC0415
    from charter.offering.drg.query import resolve_context  # noqa: PLC0415

    repo_root = ctx.require_repo_root()
    pack_context = ctx.require_pack_context()
    full_drg = _resolve_full_drg(repo_root)

    resolved = resolve_context(full_drg, _IMPLEMENT_ACTION_URN, depth=_MIN_EFFECTIVE_DEPTH)
    directive_urns = sorted(urn for urn in resolved.artifact_urns if _urn_is_directive(urn))
    if not directive_urns:
        return []

    directives = _resolve_directives(repo_root, pack_context)

    violations: list[str] = []
    for urn in directive_urns:
        directive = directives.get(_urn_bare_id(urn))
        if directive is None:
            # implement's resolved bundle already gated membership via the
            # DRG; a miss here means the doctrine repository and the DRG
            # graph disagree on what exists -- a genuine "could not verify"
            # condition, not a legitimate "nothing to check" skip.
            raise RuntimeError(f"{_IMPLEMENT_ACTION_URN} delivers {urn}, which the DRG reports resolvable but the directive repository cannot resolve.")
        if directive.enforcement == Enforcement.REQUIRED and _is_decision_documentation_directive(directive):
            violations.append(
                f"{_IMPLEMENT_ACTION_URN} delivers {urn} ('{directive.title}'), "
                f"a required decision-documentation directive; decision "
                f"documentation must not be delivered to implement."
            )
    return violations


def _check_decision_documentation_on_implement(
    ctx: ProjectContext,
    decision_documentation_on_implement_violations: list[str],
    verification_errors: list[str],
    suggestions: list[str],
) -> None:
    """FR-004: fail-closed wrapper around
    :func:`scan_decision_documentation_scoped_on_implement`.

    Mirrors :func:`_check_enforcement_lattice`'s fail-closed shape: a
    DRG/doctrine load failure is a genuine "could not verify" condition and
    lands in *verification_errors*, never a silently empty
    *decision_documentation_on_implement_violations* masquerading as
    "checked, found nothing." A non-empty result IS folded into
    ``ConsistencyReport.coherent`` -- a genuine doctrine-authoring defect,
    not an advisory signal. Shares its fail-closed shape with the other two
    DRG-backed gates via :func:`_run_fail_closed_gate` (#3808 T010) -- only
    the *message_stem* below is this gate's own.
    """
    _run_fail_closed_gate(
        lambda: scan_decision_documentation_scoped_on_implement(ctx),
        decision_documentation_on_implement_violations,
        verification_errors,
        suggestions,
        message_stem="decision-documentation-on-implement gate",
    )


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def run_consistency_check(ctx: ProjectContext) -> ConsistencyReport:
    """Run a full consistency check for the project's activated charter pack.

    Checks:
      - Unknown references (activated IDs absent from doctrine).
      - Cross-kind DRG edge references where the target kind is empty (FR-012).
      - Kind violations and duplicate IDs within activation sets.
      - Config<->charter.yaml catalog ID parity and config<->DRG kind parity
        (FR-005), fail-closed on unreadable/corrupt input (#2530) rather
        than silently reporting an empty, passing result.

    WP template scanning is explicitly out of scope.

    Args:
        ctx: The project context, used to resolve activation state and doctrine.

    Returns:
        A frozen ConsistencyReport with coherence flag and categorised findings.
    """
    unknown_references: list[str] = []
    missing_from_doctrine: list[str] = []
    kind_violations: list[str] = []
    reference_id_divergences: list[str] = []
    graph_kind_gaps: list[str] = []
    verification_errors: list[str] = []
    unreconciled_tensions: list[TensionFinding] = []
    enforcement_lattice_violations: list[str] = []
    decision_documentation_on_implement_violations: list[str] = []
    suggestions: list[str] = []

    manager = CharterPackManager()
    try:
        raw_activated_by_kind = _load_raw_activation_lists(ctx)
    except CharterPackConfigError as exc:
        # #2530 re-homed onto charter.yaml (IC-04): a dangling/unreadable
        # `charter:` pointer target must fail closed with a
        # verification_errors finding, never raise past this entry point
        # (which would defeat the "coherent report vs exception" contract
        # every other corrupt-input branch in this module honors).
        return ConsistencyReport(
            coherent=False,
            verification_errors=[f"charter.yaml: {exc.body}"],
            suggestions=[
                f"charter.yaml: Could not verify config<->charter.yaml "
                f"activation parity ({exc.body}). Fix the .kittify/config.yaml "
                f"'charter:' pointer, or restore charter.yaml from version "
                f"control."
            ],
        )
    activated_by_kind = {kind: None if raw is None else frozenset(raw) for kind, raw in raw_activated_by_kind.items()}

    if not _has_explicit_activation(raw_activated_by_kind):
        # D3 (decision DM-01KY1XHEH2T9RDX8ZCHCSV2VA0): the unreconciled-tension
        # check is ALWAYS-ON -- it runs even under implicit all-active, with no
        # short-circuit special-case. The parity/kind checks legitimately need
        # an explicit activation set and stay skipped here, but the tension scan
        # reads activation from ``ctx`` directly (scan_unreconciled_tensions), so
        # it is well-defined under all-active. Tensions remain advisory (NFR-001,
        # excluded from ``coherent``); a scan *failure* still fails closed into
        # verification_errors -> coherent=False, matching the explicit path and
        # keeping this surface aligned with the always-on ``charter activate``
        # warning (SC-001).
        #
        # T009 (#3808): the three calls below share ONE DRG load (and, for
        # the latter two, one DoctrineService build) via the
        # ``_gate_resources_scope`` cache -- down from three independent
        # loads pre-refactor.
        with _gate_resources_scope(ctx):
            _check_unreconciled_tensions(ctx, unreconciled_tensions, verification_errors, suggestions)
            # FR-002: the enforcement lattice gate is likewise always-on -- it
            # reuses the same activation read as the tension scan just above
            # (scan_enforcement_lattice_violations resolves activation from
            # ``ctx`` directly) and is well-defined under implicit all-active.
            # Unlike tensions, a lattice violation IS folded into ``coherent``.
            _check_enforcement_lattice(ctx, enforcement_lattice_violations, verification_errors, suggestions)
            # FR-004: the decision-documentation-on-implement gate is likewise
            # always-on -- it resolves ``implement``'s delivered bundle straight
            # from the DRG (not project activation state), so it is equally
            # well-defined under implicit all-active. A violation IS folded into
            # ``coherent``.
            _check_decision_documentation_on_implement(
                ctx,
                decision_documentation_on_implement_violations,
                verification_errors,
                suggestions,
            )
        return ConsistencyReport(
            coherent=not (enforcement_lattice_violations or decision_documentation_on_implement_violations or verification_errors),
            verification_errors=verification_errors,
            unreconciled_tensions=unreconciled_tensions,
            enforcement_lattice_violations=enforcement_lattice_violations,
            decision_documentation_on_implement_violations=(decision_documentation_on_implement_violations),
            suggestions=suggestions,
        )

    all_doctrine_ids = _collect_all_doctrine_ids(ctx, manager)

    _check_unknown_references(activated_by_kind, all_doctrine_ids, unknown_references, suggestions)
    _check_drg_cross_kind_refs(ctx, activated_by_kind, missing_from_doctrine, suggestions)
    _check_duplicates(raw_activated_by_kind, kind_violations)
    _check_kind_violations(activated_by_kind, all_doctrine_ids, unknown_references, kind_violations)
    _check_reference_id_parity(
        ctx,
        raw_activated_by_kind,
        reference_id_divergences,
        verification_errors,
        suggestions,
    )
    _check_graph_kind_parity(ctx, raw_activated_by_kind, graph_kind_gaps, verification_errors, suggestions)
    # T009 (#3808): as in the implicit-all-active branch above, these three
    # calls share ONE DRG load (and one DoctrineService build) via the
    # ``_gate_resources_scope`` cache.
    with _gate_resources_scope(ctx):
        _check_unreconciled_tensions(ctx, unreconciled_tensions, verification_errors, suggestions)
        _check_enforcement_lattice(ctx, enforcement_lattice_violations, verification_errors, suggestions)
        _check_decision_documentation_on_implement(
            ctx,
            decision_documentation_on_implement_violations,
            verification_errors,
            suggestions,
        )

    # NFR-001: unreconciled_tensions is deliberately excluded from this
    # reduction -- a tension finding is additive/advisory, never a
    # config<->doctrine defect on its own (contracts/tension-finding.md).
    # enforcement_lattice_violations and
    # decision_documentation_on_implement_violations ARE included -- both
    # FR-002 and FR-004 are genuine doctrine-authoring defects, not
    # advisory signals.
    coherent = not (
        unknown_references
        or missing_from_doctrine
        or kind_violations
        or reference_id_divergences
        or graph_kind_gaps
        or verification_errors
        or enforcement_lattice_violations
        or decision_documentation_on_implement_violations
    )
    return ConsistencyReport(
        coherent=coherent,
        unknown_references=unknown_references,
        missing_from_doctrine=missing_from_doctrine,
        kind_violations=kind_violations,
        reference_id_divergences=reference_id_divergences,
        graph_kind_gaps=graph_kind_gaps,
        verification_errors=verification_errors,
        unreconciled_tensions=unreconciled_tensions,
        enforcement_lattice_violations=enforcement_lattice_violations,
        decision_documentation_on_implement_violations=(decision_documentation_on_implement_violations),
        suggestions=suggestions,
    )
