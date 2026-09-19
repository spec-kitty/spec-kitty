"""Extract inline reference fields from built-in doctrine into DRG nodes + edges.

Public API:
    extract_artifact_edges(doctrine_root) -> (nodes, edges)
    extract_action_edges(doctrine_root)   -> (nodes, edges)
    generate_graph(doctrine_root, output_path) -> DRGGraph

``generate_graph`` composes + validates the graph and writes it to disk as
per-populated-node-kind ``<kind>.graph.yaml`` fragments in ``output_path``'s
directory, retiring any ``graph.yaml`` monolith in that directory atomically
(mission #2680, WP05 — DD-7/DD-8). ``output_path``'s file name is used only to
locate the target directory; the returned in-memory ``DRGGraph`` is unaffected.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from ruamel.yaml import YAML

from charter.offering.drg.migration.calibrator import calibrate_surfaces
from charter.offering.drg.migration.id_normalizer import artifact_to_urn
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.validator import assert_valid
from charter.offering.missions.mission_step_repository import MissionStepRepository
from charter.offering.missions.repository import MissionTemplateRepository
from charter.offering.missions.step_projection import (
    iter_template_refs,
    project_action_sequence,
)
from charter.offering.pack_paths import built_in_root, doctrine_package_dir
from charter.offering.template_catalog import template_id_for, template_urn

SPECIFICATION_BY_EXAMPLE = "paradigm:specification-by-example"

#: Lineage target shared by the four built-in Python/JS/Node/frontend
#: implementer profiles (S1192: this URN is otherwise duplicated 4x below).
_AGENT_PROFILE_IMPLEMENTER_IVAN = "agent_profile:implementer-ivan"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_yaml = YAML(typ="safe")


# ---------------------------------------------------------------------------
# Root resolution (post-flatten: built-in *content* lives in ``packs/built-in/``
# while ``missions/`` stays inside the ``doctrine`` package).
# ---------------------------------------------------------------------------


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _is_pack_root(root: Path) -> bool:
    """True iff *root* is a flattened built-in **pack** root.

    A pack root ships artifact YAML directly under ``<kind>/`` (post-flatten,
    WP03), so a populated ``directives/`` block is a reliable proxy. The
    ``doctrine`` **package** root (``src/doctrine``) fails this test — its
    ``directives/`` holds only Python modules — as does an artifact-free
    synthetic or nonexistent test root. ``Path.glob`` on a missing directory
    yields nothing.
    """
    return any((root / "directives").glob("*.directive.yaml"))


def _is_doctrine_package_root(root: Path) -> bool:
    """True iff *root* is the installed ``doctrine`` package directory itself
    (``src/doctrine`` in a checkout) — the legacy caller shape whose built-in
    artifacts were relocated out to ``packs/built-in``."""
    pkg = doctrine_package_dir()
    return pkg is not None and _same_path(root, pkg)


def _artifacts_root(doctrine_root: Path) -> Path:
    """Resolve the flattened built-in **artifact** pack root for *doctrine_root*.

    Post-flatten, the nine artifact kinds live at ``packs/built-in/<kind>/``
    (WP03) — the inner ``built-in/`` level is gone. Three caller shapes exist:

    * A *flattened pack root* (:func:`_is_pack_root` true) is honoured unchanged
      — this is what the CLI command and the shipped-graph tests pass.
    * The ``doctrine`` **package** root (``src/doctrine``,
      :func:`_is_doctrine_package_root`) no longer carries artifacts — they were
      relocated to ``packs/built-in`` — so the canonical pack root is resolved
      via :func:`built_in_root` (the same fail-closed seam the loader uses).
    * Any **other** root is a synthetic test fixture and is honoured as-is, so a
      unit test can inject artifacts under an arbitrary temp root without the
      resolver silently substituting the real shipped tree.
    """
    if _is_pack_root(doctrine_root):
        return doctrine_root
    if _is_doctrine_package_root(doctrine_root):
        return built_in_root()
    return doctrine_root


def _missions_root(doctrine_root: Path) -> Path:
    """Resolve the ``missions/`` root for *doctrine_root*.

    Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
    (FR-005) relocated the missions data subdirectories out of the
    ``doctrine`` package to ``packs/built-in/missions``, alongside every
    other built-in artifact kind — falsifying this function's previous
    assumption that missions stayed inside the ``doctrine`` package,
    untouched by the WP03 flatten.

    * A flattened **pack** root (``packs/built-in``, :func:`_is_pack_root`)
      now carries ``missions/`` directly, exactly like every other kind
      directory — ``<root>/missions`` needs no further indirection.
    * The ``doctrine`` **package** root (``src/doctrine``,
      :func:`_is_doctrine_package_root`) no longer carries missions data
      (only the 11 ``.py`` logic modules remain there) — resolved via
      :meth:`~charter.offering.missions.repository.MissionTemplateRepository.default_missions_root`,
      the missions-root authority (not :func:`built_in_root`: joining a
      segment onto that bare-root seam locally is the exact drift
      ``test_no_builtin_path_joins_outside_pack_paths_authority`` forbids;
      ``default_missions_root`` resolves the identical
      ``packs/built-in/missions`` directory via the same underlying
      :func:`kernel.sibling_paths.resolve_installed_sibling` primitive,
      anchored on a sibling module within the same ``doctrine`` package).
    * Any **other** root (a synthetic/nonexistent test root) uses its own
      ``<root>/missions`` — so a nonexistent root still resolves to an
      absent, empty missions tree rather than the real shipped one.
    """
    if _is_doctrine_package_root(doctrine_root):
        return MissionTemplateRepository.default_missions_root()
    return doctrine_root / "missions"

# ---------------------------------------------------------------------------
# T027: Path-string reference resolver for styleguide / toolguide ``references``
# ---------------------------------------------------------------------------

#: Ordered list of (compiled-pattern, kind) pairs.  Each pattern captures the
#: filename stem (without kind extension and without any subdirectory prefix) in
#: group 1.  The ``(?:.+/)?`` non-capturing optional subdir fragment ensures that
#: both flat paths (``<kind>/foo.tactic.yaml``) and paths rooted under a
#: subdirectory (``<kind>/testing/foo.tactic.yaml``) resolve to the same stem.
#:
#: **Two path shapes are matched (relocate-builtin-doctrine-packs).** The flatten
#: (WP03) moved artifact *files* from ``src/charter/offering/<kind>/built-in/`` to the
#: flattened ``packs/built-in/<kind>/``, but the ``references:`` path strings
#: authored *inside* the styleguide/toolguide YAML were deliberately **not**
#: rewritten (that move was a pure ``git mv`` — no in-file edits). Those strings
#: are the actual input :func:`_resolve_path_ref` reads, so the legacy
#: ``src/charter/offering/<kind>/built-in/`` branch is load-bearing: dropping it would
#: silently lose every reference-derived ``suggests`` edge and shrink the shipped
#: graph. The flattened ``packs/built-in/<kind>/`` branch (inner ``built-in``
#: dropped) resolves any reference authored in the new home. A path string
#: resolves via **either** branch to the same ``(kind, stem)`` because the URN is
#: keyed on the stem, not the prefix — so the graph is prefix-invariant.
#:
#: Only **built-in** artifact directories are covered; ``_proposed`` profiles and
#: non-artifact files (README, glossary YAML, URLs) will not match any pattern
#: and therefore return ``None`` from :func:`_resolve_path_ref`.


def _kind_path_pattern(kind_dir: str, extension: str) -> re.Pattern[str]:
    """Compile a dual-home path-ref pattern for one artifact *kind_dir*.

    Matches both the legacy ``src/charter/offering/<kind_dir>/built-in/…`` home (the
    format the shipped ``references:`` strings still carry) and the flattened
    ``packs/built-in/<kind_dir>/…`` home (inner ``built-in`` dropped), capturing
    the subdir-stripped filename stem (``*extension*`` = e.g. ``tactic``).
    """
    home = rf"(?:src/charter/offering/{kind_dir}/built-in|packs/built-in/{kind_dir})"
    return re.compile(rf"{home}/(?:.+/)?([^/]+)\.{extension}\.yaml$")


_PATH_KIND_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_kind_path_pattern("tactics", "tactic"), "tactic"),
    (_kind_path_pattern("paradigms", "paradigm"), "paradigm"),
    (_kind_path_pattern("directives", "directive"), "directive"),
    (_kind_path_pattern("styleguides", "styleguide"), "styleguide"),
    (_kind_path_pattern("toolguides", "toolguide"), "toolguide"),
    (_kind_path_pattern("procedures", "procedure"), "procedure"),
    (_kind_path_pattern("agent_profiles", "agent"), "agent_profile"),
]


def _resolve_path_ref(path_str: str) -> tuple[str, str] | None:
    """Return ``(kind, raw_id)`` for a raw path-string reference, or ``None``.

    Styleguide and toolguide ``references`` fields carry plain file paths such as
    ``src/charter/offering/tactics/built-in/tdd-red-green-refactor.tactic.yaml`` (legacy
    home, still authored in the shipped YAML) or
    ``packs/built-in/tactics/tdd-red-green-refactor.tactic.yaml`` (flattened
    home).  This helper maps such a path to the canonical ``(kind, raw_id)`` pair
    that :func:`charter.offering.drg.migration.id_normalizer.artifact_to_urn` can resolve
    into a full URN — the two homes resolve to the same pair.

    Only **built-in** artifact paths (either home) are matched; URLs, glossary
    files, ADR documents, ``_proposed`` profiles, and any other path that
    does not match one of the recognised patterns return ``None`` (fail-closed per
    NFR-003 — never silently infer identity from an unrecognised path).

    Args:
        path_str: A raw path string from a styleguide or toolguide ``references``
            list entry.

    Returns:
        ``(kind, raw_id)`` where *raw_id* is the filename stem (stripped of any
        subdirectory prefix and kind extension).  For directives the caller must
        pass *raw_id* through
        :func:`charter.offering.drg.migration.id_normalizer.artifact_to_urn` for
        ``DIRECTIVE_NNN`` normalisation.  Returns ``None`` if the path does not
        match any known pattern.
    """
    for pattern, kind in _PATH_KIND_PATTERNS:
        m = pattern.search(path_str)
        if m:
            return kind, m.group(1)
    return None

#: Reference-``type`` string / URN prefix -> :class:`NodeKind`.
#:
#: Derived from the enum, so it is total by construction (T015, FR-004). It
#: previously restated 11 of the 16 members by hand and dropped ``anti_pattern``,
#: ``asset``, ``glossary``, ``glossary_pack`` and ``glossary_scope``. Because the
#: table is ``str``-keyed it was invisible to the ``NodeKind``-keyed totality
#: guard in ``tests/doctrine/drg/test_kind_mapping_totality.py`` -- a
#: hand-restated table one step outside the gate that exists to catch
#: hand-restated tables. Deriving it removes the restatement instead of
#: lengthening it: a ``NodeKind`` member added tomorrow is carried with no edit
#: here, and none can be dropped by omission.
#:
#: Measured graph-neutral when closed: the extractor emits the same 305 nodes /
#: 757 edges before and after. The gap was latent, not live -- nothing shipped
#: today *references* one of the five missing kinds by type.
_KIND_MAP: dict[str, NodeKind] = {kind.value: kind for kind in NodeKind}

#: Action-index list field -> the artifact kind its entries name, for the
#: ``scope`` edges emitted by :func:`extract_action_edges`.
#:
#: Hoisted to module scope so the ``_KIND_MAP`` subscript at the read site can be
#: proven safe by a test that derives from *this* declaration rather than
#: restating the seven kinds a third time. The read site previously used
#: ``_KIND_MAP.get(kind, NodeKind.GLOSSARY_SCOPE)``, so an unmapped scope-field
#: kind produced a *wrongly-kinded* node rather than an error -- a silent
#: corruption, which is worse than the silent omission elsewhere in this module.
_ACTION_SCOPE_FIELDS: tuple[tuple[str, str], ...] = (
    ("directives", "directive"),
    ("tactics", "tactic"),
    ("paradigms", "paradigm"),
    ("styleguides", "styleguide"),
    ("toolguides", "toolguide"),
    ("procedures", "procedure"),
    ("agent_profiles", "agent_profile"),
)

# Reference types that are NOT DRG node kinds (skipped during extraction).
_SKIP_REF_TYPES: frozenset[str] = frozenset()

_CURATED_ARTIFACT_EDGES: tuple[tuple[str, str, Relation], ...] = (
    # WP06/WP07 (FR-001/FR-028 hard cutover): built-in profile lineage is now
    # authored directly as DRG ``specializes_from`` edges. The legacy
    # ``specializes-from`` profile field has been retired (and is rejected by the
    # profile model), so these edges are the single source of lineage truth.
    (
        "agent_profile:python-pedro",
        _AGENT_PROFILE_IMPLEMENTER_IVAN,
        Relation.SPECIALIZES_FROM,
    ),
    (
        "agent_profile:java-jenny",
        _AGENT_PROFILE_IMPLEMENTER_IVAN,
        Relation.SPECIALIZES_FROM,
    ),
    (
        "agent_profile:node-norris",
        _AGENT_PROFILE_IMPLEMENTER_IVAN,
        Relation.SPECIALIZES_FROM,
    ),
    (
        "agent_profile:frontend-freddy",
        _AGENT_PROFILE_IMPLEMENTER_IVAN,
        Relation.SPECIALIZES_FROM,
    ),
    (
        "agent_profile:drupal-dries",
        _AGENT_PROFILE_IMPLEMENTER_IVAN,
        Relation.SPECIALIZES_FROM,
    ),
    (
        SPECIFICATION_BY_EXAMPLE,
        "tactic:acceptance-test-first",
        Relation.REQUIRES,
    ),
    (
        SPECIFICATION_BY_EXAMPLE,
        "tactic:atdd-adversarial-acceptance",
        Relation.REQUIRES,
    ),
    (
        SPECIFICATION_BY_EXAMPLE,
        "tactic:usage-examples-sync",
        Relation.REQUIRES,
    ),
    (
        "directive:DIRECTIVE_040",
        "tactic:five-paradigm-parallel-debugging",
        Relation.REQUIRES,
    ),
    (
        "directive:DIRECTIVE_037",
        "tactic:usage-examples-sync",
        Relation.REQUIRES,
    ),
    (
        "directive:DIRECTIVE_001",
        "tactic:paula-patterns-architecture-scout-review",
        Relation.REQUIRES,
    ),
    (
        "directive:DIRECTIVE_003",
        "tactic:traceable-decisions",
        Relation.REQUIRES,
    ),
    # RETIRED (M3: #2994/#3352): the ``doctrine-daphne ->
    # onboard-external-agent-to-pack`` pin (originally the WP09
    # doctrine-silence-guards retype) is now DATA-DRIVEN from daphne's
    # ``operating-procedures`` field via ``_emit_operating_procedure_edges``.
    # The edge still exists in the graph, derived rather than hand-pinned.
    # Landing pass for PR #3007, operator ruling 2026-07-28 (#3009 remedy 4).
    # Seven of the nine ``_ACTIVATED_BUT_ORPHANED`` artefacts are oversights,
    # not design: the charter ACTIVATES them while the graph gives them no inbound
    # edge, so a cascade or context walk reaches none of them. Each edge below
    # follows an existing (source_kind -> target_kind, relation) pattern in the
    # shipped graph rather than inventing one; the relation is ``requires`` where
    # the source MANDATES the target and ``suggests`` where it recommends it.
    #
    # ``toolguide:rtk-search-tooling`` is deliberately absent -- it was deleted
    # outright by the same ruling. ``paradigm:atomic-design`` is also absent and
    # stays an enrolled orphan: it is frontend-interface-specific and no shipped
    # doctrine artefact is a defensible source, so wiring it would mean inventing
    # a relationship rather than recording one. It needs an operator ruling, not
    # a guess.
    #
    # DIRECTIVE_035 IS bulk-edit occurrence classification; this tactic is the
    # workflow it mandates. (#3009 names exactly this pairing.)
    (
        "directive:DIRECTIVE_035",
        "tactic:occurrence-classification-workflow",
        Relation.REQUIRES,
    ),
    # DIRECTIVE_003 (Decision Documentation Requirement) already ``requires``
    # ``tactic:traceable-decisions`` above; marker capture is the other half of
    # the same obligation -- capturing the decision at the point it is made.
    (
        "directive:DIRECTIVE_003",
        "tactic:decision-marker-capture",
        Relation.REQUIRES,
    ),
    # DIRECTIVE_030 (Test and Typecheck Quality Gate). Re-pointed from
    # DIRECTIVE_028 (Efficient Local Tooling) on review: 028 scopes itself to
    # tool SELECTION (ripgrep, pagers, archive tools, git ergonomics) and none of
    # its procedures concern running a suite. This tactic is a discipline on HOW
    # the suite is run and how its result is read, which is 030's subject. The
    # 028 reading argued from a shared side-effect (resource waste), not a shared
    # subject -- the signature of a convenient owner rather than the right one.
    (
        "directive:DIRECTIVE_030",
        "tactic:no-parallel-duplicate-test-runs",
        Relation.SUGGESTS,
    ),
    # DIRECTIVE_030 (Test and Typecheck Quality Gate). The procedure keeps the
    # mainline CI signal honest and authoritative for release, which is the gate
    # this directive governs. Charter standing order #9 is the prose form.
    (
        "directive:DIRECTIVE_030",
        "procedure:red-main-release-discipline",
        Relation.SUGGESTS,
    ),
    # styleguide -> toolguide ``suggests`` is the established pattern (x4). The
    # toolguide is a catalog of automated checks for Python review; the Python
    # styleguide is what sends a reviewer to it.
    (
        "styleguide:python-conventions",
        "toolguide:python-review-checks",
        Relation.SUGGESTS,
    ),
    # ``tactic -> paradigm suggests`` is the most common inbound-to-paradigm
    # pattern in the shipped graph (9 edges, 6 of them this exact shape -- the
    # semantic-compression tactic family each suggesting their paradigm). The
    # checklist's own summary is "respects atomic design level boundaries",
    # so this records a name-identical relationship rather than inventing one.
    # NOTE: this de-orphans the paradigm by incidence but does NOT make it
    # reachable -- the checklist tactic is itself outbound-only. The frontend
    # cluster (checklist + atomic-state-ownership + compositional-stream-
    # boundaries + cross-cutting-state-via-store + the paradigm) is a
    # disconnected island needing one ruling, not one edge. Tracked in #3009.
    (
        "tactic:atomic-design-review-checklist",
        "paradigm:atomic-design",
        Relation.SUGGESTS,
    ),
    # The REASONS canvas is the SPDD artefact, so the SPDD paradigm is its owner
    # (``paradigm -> styleguide suggests``). Without this edge, selecting SPDD
    # reached none of the guidance on writing the canvas it asks for.
    (
        "paradigm:structured-prompt-driven-development",
        "styleguide:reasons-canvas-writing",
        Relation.SUGGESTS,
    ),
    # Mission drg-reachability-metric-wiring-01KZS5VR, WP01 (#3009 point 3 / A2
    # orphan-wiring, six genuine traced edges -- research.md trace table):
    #
    # Edge 1: the refactoring procedure's step 2 ("Select the relevant
    # refactoring tactics") already cites 9 Fowler tactics; the disciplined-
    # refactoring directive holds 7 disjoint ones plus the "name the smell
    # first" discipline (refactoring.procedure.yaml:26-31;
    # disciplined-refactoring.directive.yaml:14-17,26-27). Same doctrinal
    # domain, artificially split -- not a metric-gamed edge (the procedure's
    # own comment at :59-62 blesses inbound wiring here). Action-reachable via
    # the (already action-scoped) refactoring procedure; cascades the seven
    # ``refactoring-*`` Fowler tactics into action context.
    (
        "procedure:refactoring",
        "directive:DISCIPLINED_REFACTORING",
        Relation.SUGGESTS,
    ),
    # Edges 2/3: the reconciler's own scope names both 024 and 025 as its
    # trigger (reconcile-change-scope-tensions.directive.yaml:16-20, "Applies
    # whenever a change is evaluated against DIRECTIVE_024, DIRECTIVE_025...").
    # Enforcement is advisory, so ``suggests``. RECONCILE is a tracked
    # ``_ACTIVATED_BUT_ORPHANED`` member (test_extractor_projection.py) --
    # these two edges are its de-orphaning wiring.
    (
        "directive:DIRECTIVE_024",
        "directive:RECONCILE_CHANGE_SCOPE_TENSIONS",
        Relation.SUGGESTS,
    ),
    (
        "directive:DIRECTIVE_025",
        "directive:RECONCILE_CHANGE_SCOPE_TENSIONS",
        Relation.SUGGESTS,
    ),
    # RECONCILE third trigger (M3): the reconciler's ``scope:`` names three
    # triggers -- DIRECTIVE_024, DIRECTIVE_025, and
    # tactic:change-apply-smallest-viable-diff. The first two have inbound edges
    # above; this wires the still-unwired tactic trigger. ``suggests`` matches the
    # other two (advisory reconciliation). Target is a real shipped tactic node.
    (
        "tactic:change-apply-smallest-viable-diff",
        "directive:RECONCILE_CHANGE_SCOPE_TENSIONS",
        Relation.SUGGESTS,
    ),
    # Edge 4: DIRECTIVE_030 governs the coverage gate; the mutation-testing
    # directive deepens it by critiquing coverage-as-proxy
    # (use-mutation-testing-to-validate-test-quality.directive.yaml:4-11,24-28;
    # 030-test-and-typecheck-quality-gate.directive.yaml:12-13). Lenient
    # adherence, so ``suggests`` -- the same shape as remedy-4's existing
    # ``030--suggests-->`` edges above. Action-reachable via 030; cascades the
    # mutation-testing tactic + toolguide family into action context.
    (
        "directive:DIRECTIVE_030",
        "directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY",
        Relation.SUGGESTS,
    ),
    # Edge 5 RETIRED (M3: #2994/#3352): researcher-robbie's ``spike-timebox-policy``
    # edge is now DATA-DRIVEN from its ``operating-procedures`` field via
    # ``_emit_operating_procedure_edges`` (the field it was originally sourced from).
    # The edge still exists, derived rather than hand-pinned. Edges 6a/6b below stay
    # hand-pinned: lexical-larry and minutes-mahad carry NO operating-procedures
    # field (they are prose-sourced), so nothing data-drives them.
    # Edge 6a: lexical-larry is the diagnostic "feeder into" the
    # glossary-maintenance-workflow (lexical-larry.agent.yaml:53-54);
    # curator-carla owns its acceptance (larry.yaml:39-42). ``suggests``, NOT
    # ``requires`` -- larry feeds the workflow, does not own/depend on it; a
    # ``requires`` relation would overstate the relationship. Profile-channel
    # reachable (``suggests`` is in ``PROFILE_CHANNEL_RELATIONS``).
    (
        "agent_profile:lexical-larry",
        "procedure:glossary-maintenance-workflow",
        Relation.SUGGESTS,
    ),
    # Edge 6b: minutes-mahad's own text states it is "the primary agent
    # for the meeting-minutes-pipeline procedure" (minutes-mahad.agent.
    # yaml) -- explicit prose ownership, so ``requires``. Profile-channel
    # reachable.
    (
        "agent_profile:minutes-mahad",
        "procedure:meeting-minutes-pipeline",
        Relation.REQUIRES,
    ),
)


def _ensure_node(
    nodes_by_urn: dict[str, DRGNode],
    urn: str,
    kind: NodeKind,
    label: str | None = None,
) -> None:
    """Register a node if not already tracked."""
    if urn not in nodes_by_urn:
        nodes_by_urn[urn] = DRGNode(urn=urn, kind=kind, label=label)
    elif label and nodes_by_urn[urn].label is None:
        nodes_by_urn[urn] = nodes_by_urn[urn].model_copy(update={"label": label})


def _load_yaml(path: Path) -> dict[str, Any] | None:
    data: Any = _yaml.load(path)
    if isinstance(data, dict):
        return data
    return None


def _relation_for_ref_type(ref_type: str) -> Relation:
    """Map a reference ``type`` field to a DRG relation.

    Directives get ``requires``; most others get ``suggests``.
    """
    if ref_type == "directive":
        return Relation.REQUIRES
    return Relation.SUGGESTS


def _relation_for_procedure_ref_type(ref_type: str) -> Relation:
    """Map procedure references to relations.

    Procedures orchestrate required operational artifacts. Template/style/tool
    references remain advisory.
    """
    if ref_type in {"directive", "tactic", "procedure"}:
        return Relation.REQUIRES
    return Relation.SUGGESTS


def _kind_for_type(ref_type: str) -> NodeKind | None:
    """Map a reference ``type`` string to a NodeKind, or ``None`` if skipped."""
    if ref_type in _SKIP_REF_TYPES:
        return None
    return _KIND_MAP.get(ref_type)


def _reference_edge_kwargs(ref: dict[str, Any]) -> dict[str, str | None]:
    """Curated edge metadata (``when``/``reason``) for a ``{type, id, when?,
    reason?}`` reference dict, carried symmetrically onto its DRG edge.

    The single authority for the ``when``/``reason``-bearing ``references``
    branches -- **directive, tactic (top- and step-level), paradigm, and
    procedure** -- so none silently drops a field. Before this, the tactic
    branches read only ``when`` while directive/paradigm read both, so a future
    overlay-to-frontmatter promotion (the #3009 residual mechanism) on a tactic
    source would have lost its rationale at the extractor. Both default to
    ``None``, so any bare ``{type, id}`` reference is unchanged.

    The ``procedure`` references branch was wired through this helper in #3605
    (WP01): shipped procedure references already author ``reason`` in YAML,
    which that branch previously dropped at the extractor -- a silent metadata
    loss, not a triple change, and no golden-count update was required for THAT
    change -- the edge (source, target, relation) set was unchanged; only
    ``when``/``reason`` gained values. (The later agent-profile consolidation,
    mission ``doctrine-drg-silent-drop-boundary-01M0PE7E`` WP02 / #3629 p1, DID
    move the profile edge set -- see ledger entry (21) in
    ``tests/doctrine/drg/migration/test_extractor_projection.py`` for that
    re-ledger -- but it re-homed profile *references*, not this procedure
    metadata branch.) Note also that end-to-end frontmatter promotion for a non-directive
    source additionally needs that kind's reference *model* + generated schema
    to accept ``reason`` (only :class:`DirectiveReference` does today); the
    extractor carrying the field is necessary but not sufficient.
    """
    return {"when": ref.get("when"), "reason": ref.get("reason")}


def _add_ref_edge(
    *,
    nodes_by_urn: dict[str, DRGNode],
    add_edge: Any,
    source: str,
    ref_type: str,
    ref_id: str,
    relation: Relation,
    when: str | None = None,
    reason: str | None = None,
) -> None:
    tgt_kind = _kind_for_type(ref_type)
    if tgt_kind is None:
        return
    tgt_urn = artifact_to_urn(ref_type, ref_id)
    _ensure_node(nodes_by_urn, tgt_urn, tgt_kind)
    add_edge(
        DRGEdge(
            source=source,
            target=tgt_urn,
            relation=relation,
            when=when,
            reason=reason,
        )
    )


def _merge_edge_metadata(existing: DRGEdge, incoming: DRGEdge) -> DRGEdge:
    """Preserve deterministic edge metadata when duplicate triples are found."""
    updates: dict[str, str] = {}
    if existing.when is None and incoming.when is not None:
        updates["when"] = incoming.when
    if existing.reason is None and incoming.reason is not None:
        updates["reason"] = incoming.reason
    if not updates:
        return existing
    return existing.model_copy(update=updates)


# ---------------------------------------------------------------------------
# Agent-profile edge projection
# ---------------------------------------------------------------------------


def _project_profile_reference_edges(
    data: dict[str, Any],
    src_urn: str,
    nodes_by_urn: dict[str, DRGNode],
    add_edge: Any,
) -> None:
    """Emit the four ``*-references`` edge families for one agent profile.

    ``directive-references`` and ``tactic-references`` project as ``requires``;
    ``toolguide-references`` and ``styleguide-references`` project as
    ``suggests``. Directive ``requires`` edges are minted *bare* (no ``reason``)
    to match the retired ``context-sources.directives`` projection byte-for-byte
    -- only the tactic/toolguide/styleguide families carry the authored
    rationale, mirroring the pre-consolidation asymmetry.
    """
    for ref in data.get("directive-references", []) or []:
        ref_id = ref.get("code", "")
        if not ref_id:
            continue
        _add_ref_edge(
            nodes_by_urn=nodes_by_urn,
            add_edge=add_edge,
            source=src_urn,
            ref_type="directive",
            ref_id=str(ref_id),
            relation=Relation.REQUIRES,
        )
    for ref in data.get("tactic-references", []) or []:
        ref_id = ref.get("id", "")
        if not ref_id:
            continue
        _add_ref_edge(
            nodes_by_urn=nodes_by_urn,
            add_edge=add_edge,
            source=src_urn,
            ref_type="tactic",
            ref_id=ref_id,
            relation=Relation.REQUIRES,
            reason=ref.get("rationale"),
        )
    for ref_type in ("toolguide", "styleguide"):
        for ref in data.get(f"{ref_type}-references", []) or []:
            ref_id = ref.get("id", "")
            if not ref_id:
                continue
            _add_ref_edge(
                nodes_by_urn=nodes_by_urn,
                add_edge=add_edge,
                source=src_urn,
                ref_type=ref_type,
                ref_id=ref_id,
                relation=Relation.SUGGESTS,
                reason=ref.get("rationale"),
            )


def _emit_agent_profile_edges(
    packs_root: Path,
    nodes_by_urn: dict[str, DRGNode],
    add_edge: Any,
) -> None:
    """Project ``agent_profile`` DRG edges from each profile's canonical
    top-level ``*-references`` surface.

    Consolidated in mission ``doctrine-drg-silent-drop-boundary-01M0PE7E``
    (WP02, #3629 p1): the retired ``context-sources.*`` bare-string surface is
    gone, so directive edges now project from ``directive-references`` (was
    ``context-sources.directives``); ``tactic-references`` is unchanged; and
    ``toolguide-references``/``styleguide-references`` newly project as
    ``suggests`` so every authored reference becomes a first-class DRG edge with
    no silent-drop boundary. Factored out of :func:`extract_artifact_edges`
    (already at the ``# noqa: C901`` ceiling, NFR-004), mirroring
    :func:`_emit_glossary_pack_nodes`.
    """
    profiles_dir = packs_root / "agent_profiles"
    if not profiles_dir.is_dir():
        return
    for path in sorted(profiles_dir.glob("*.agent.yaml")):
        data = _load_yaml(path)
        if data is None:
            continue
        profile_id = data.get("profile-id", "")
        if not profile_id:
            continue
        src_urn = artifact_to_urn("agent_profile", profile_id)
        label = data.get("name", "")
        _ensure_node(nodes_by_urn, src_urn, NodeKind.AGENT_PROFILE, label or None)
        _project_profile_reference_edges(data, src_urn, nodes_by_urn, add_edge)


# ---------------------------------------------------------------------------
# WP03 (glossary-pack-doctrine-kind-01KY30SW): glossary-pack source-node emission
# ---------------------------------------------------------------------------


def _emit_glossary_pack_nodes(
    packs_root: Path, nodes_by_urn: dict[str, DRGNode]
) -> None:
    """Register a ``glossary_pack:<id>`` source node for each built-in pack.

    Mirrors the shape of the per-kind blocks in :func:`extract_artifact_edges`
    (directives, tactics, ...), but is factored into its own helper because
    that function is already at the ``# noqa: C901`` complexity ceiling
    (NFR-004) -- adding this loop inline would raise it further.

    Glossary packs carry no outbound DRG references in Mission A (the
    enforcement fields are inert until Mission B), so only the pack's own
    node is emitted here -- there are no edges to extract.

    *packs_root* is the flattened built-in pack root (``packs/built-in``); the
    packs live directly under ``<packs_root>/glossary_packs/`` (WP03 flatten).
    """
    packs_dir = packs_root / "glossary_packs"
    if not packs_dir.is_dir():
        return
    for path in sorted(packs_dir.glob("*.glossary-pack.yaml")):
        data = _load_yaml(path)
        if data is None:
            continue
        pack_id: str = data.get("id", "")
        if not pack_id:
            continue
        src_urn = artifact_to_urn("glossary_pack", pack_id)
        _ensure_node(nodes_by_urn, src_urn, NodeKind.GLOSSARY_PACK)


# ---------------------------------------------------------------------------
# Operating-procedures data-drive (M3: #2994/#3352)
# ---------------------------------------------------------------------------


def _emit_operating_procedure_edges(
    profiles_dir: Path,
    nodes_by_urn: dict[str, DRGNode],
    add_edge: Any,
) -> None:
    """Emit guarded ``agent_profile --requires--> procedure`` edges from the
    ``operating-procedures`` field, failing closed on any unresolved built-in entry.

    Guarded: an entry is emitted only when its ``procedure:<id>`` target is an
    already-minted procedure node, so an org/project-tier profile cannot mint a
    dangling edge. Every built-in entry must resolve to a procedure-kind node
    present at extraction time — an unresolved one (a fictional or wrong-kind
    reference) raises, converting the old silent drop into a loud build failure.
    Kept in its own helper (its own profile walk) so
    :func:`extract_artifact_edges` complexity is unchanged (NFR-004); the second
    walk is 16 small files. The field harvest is delegated to
    :func:`~charter.offering.agent_profiles.operating_procedures.collect_operating_procedure_entries`
    (the single authority, also read by the architectural gate and ``doctor
    doctrine``) so the three consumers cannot diverge on the falsy-entry policy;
    ``resolve_operating_procedure_entries`` is the single authority for "does
    this entry resolve to a procedure node".
    """
    from charter.offering.agent_profiles.operating_procedures import (
        collect_operating_procedure_entries,
        node_universe,
        resolve_operating_procedure_entries,
    )

    if not profiles_dir.is_dir():
        return
    procedure_urns, urns_by_kind = node_universe(nodes_by_urn.values())
    entries_by_profile = collect_operating_procedure_entries(profiles_dir)
    for profile_id, entries in entries_by_profile.items():
        src_urn = artifact_to_urn("agent_profile", profile_id)
        for entry in entries:
            tgt_urn = artifact_to_urn("procedure", entry)
            if tgt_urn in procedure_urns:
                add_edge(
                    DRGEdge(source=src_urn, target=tgt_urn, relation=Relation.REQUIRES)
                )
    unresolved = resolve_operating_procedure_entries(
        entries_by_profile, procedure_urns, urns_by_kind
    )
    if unresolved:
        detail = ", ".join(f"{u.profile_id}:{u.entry} ({u.reason})" for u in unresolved)
        raise ValueError(
            "built-in operating-procedures entries do not resolve to a procedure "
            f"node (triage required): {detail}"
        )


# ---------------------------------------------------------------------------
# T012: Artifact walker (directives, tactics, paradigms, procedures)
# ---------------------------------------------------------------------------


def extract_artifact_edges(  # noqa: C901
    doctrine_root: Path,
) -> tuple[list[DRGNode], list[DRGEdge]]:
    """Walk built-in directives, tactics, paradigms, and procedures; return (nodes, edges).

    Every inline reference field is converted to a typed DRG edge.
    Nodes are deduplicated by URN.
    """
    nodes_by_urn: dict[str, DRGNode] = {}
    edges_by_triple: dict[tuple[str, str, str], DRGEdge] = {}
    packs_root = _artifacts_root(doctrine_root)

    def _add_edge(edge: DRGEdge) -> None:
        triple = (edge.source, edge.target, edge.relation.value)
        if triple in edges_by_triple:
            edges_by_triple[triple] = _merge_edge_metadata(
                edges_by_triple[triple], edge
            )
        else:
            edges_by_triple[triple] = edge

    # --- Directives ---
    directives_dir = packs_root / "directives"
    if directives_dir.is_dir():
        for path in sorted(directives_dir.glob("*.directive.yaml")):
            data = _load_yaml(path)
            if data is None:
                continue
            directive_id: str = data.get("id", "")
            title: str = data.get("title", "")
            src_urn = artifact_to_urn("directive", directive_id)
            _ensure_node(nodes_by_urn, src_urn, NodeKind.DIRECTIVE, title)

            # tactic_refs
            for tactic_id in data.get("tactic_refs", []) or []:
                tgt_urn = artifact_to_urn("tactic", tactic_id)
                _ensure_node(nodes_by_urn, tgt_urn, NodeKind.TACTIC)
                _add_edge(
                    DRGEdge(
                        source=src_urn,
                        target=tgt_urn,
                        relation=Relation.REQUIRES,
                    )
                )

            # references (top-level list of {type, id, when?, reason?})
            for ref in data.get("references", []) or []:
                ref_type: str = ref.get("type", "")
                ref_id: str = ref.get("id", "")
                if not ref_type or not ref_id:
                    continue
                tgt_kind = _kind_for_type(ref_type)
                if tgt_kind is None:
                    continue  # skip non-DRG types (e.g. template)
                tgt_urn = artifact_to_urn(ref_type, ref_id)
                _ensure_node(nodes_by_urn, tgt_urn, tgt_kind)
                _add_edge(
                    DRGEdge(
                        source=src_urn,
                        target=tgt_urn,
                        relation=_relation_for_ref_type(ref_type),
                        # ``when``/``reason`` carried symmetrically (single
                        # authority :func:`_reference_edge_kwargs`) so a directive
                        # frontmatter reference can hold the curated rationale an
                        # overlay edge used to -- the capability that makes the
                        # #3009 overlay-to-frontmatter promotions lossless.
                        **_reference_edge_kwargs(ref),
                    )
                )

    # --- Tactics ---
    tactics_dir = packs_root / "tactics"
    if tactics_dir.is_dir():
        # Include top-level *.tactic.yaml and any in subdirectories
        tactic_files = sorted(tactics_dir.rglob("*.tactic.yaml"))
        for path in tactic_files:
            data = _load_yaml(path)
            if data is None:
                continue
            tactic_id = data.get("id", "")
            tactic_name: str = data.get("name", "")
            src_urn = artifact_to_urn("tactic", tactic_id)
            _ensure_node(nodes_by_urn, src_urn, NodeKind.TACTIC, tactic_name)

            # top-level references
            for ref in data.get("references", []) or []:
                ref_type = ref.get("type", "")
                ref_id = ref.get("id", "")
                if not ref_type or not ref_id:
                    continue
                tgt_kind = _kind_for_type(ref_type)
                if tgt_kind is None:
                    continue
                tgt_urn = artifact_to_urn(ref_type, ref_id)
                _ensure_node(nodes_by_urn, tgt_urn, tgt_kind)
                _add_edge(
                    DRGEdge(
                        source=src_urn,
                        target=tgt_urn,
                        relation=Relation.SUGGESTS,
                        **_reference_edge_kwargs(ref),
                    )
                )

            # step-level references
            for step in data.get("steps", []) or []:
                for ref in step.get("references", []) or []:
                    ref_type = ref.get("type", "")
                    ref_id = ref.get("id", "")
                    if not ref_type or not ref_id:
                        continue
                    tgt_kind = _kind_for_type(ref_type)
                    if tgt_kind is None:
                        continue
                    tgt_urn = artifact_to_urn(ref_type, ref_id)
                    _ensure_node(nodes_by_urn, tgt_urn, tgt_kind)
                    _add_edge(
                        DRGEdge(
                            source=src_urn,
                            target=tgt_urn,
                            relation=Relation.SUGGESTS,
                            **_reference_edge_kwargs(ref),
                        )
                    )

    # --- Paradigms ---
    paradigms_dir = packs_root / "paradigms"
    if paradigms_dir.is_dir():
        for path in sorted(paradigms_dir.glob("*.paradigm.yaml")):
            data = _load_yaml(path)
            if data is None:
                continue
            paradigm_id: str = data.get("id", "")
            paradigm_name: str = data.get("name", "")
            src_urn = artifact_to_urn("paradigm", paradigm_id)
            _ensure_node(nodes_by_urn, src_urn, NodeKind.PARADIGM, paradigm_name)

            # tactic_refs
            for tactic_id in data.get("tactic_refs", []) or []:
                tgt_urn = artifact_to_urn("tactic", tactic_id)
                _ensure_node(nodes_by_urn, tgt_urn, NodeKind.TACTIC)
                _add_edge(
                    DRGEdge(
                        source=src_urn,
                        target=tgt_urn,
                        relation=Relation.REQUIRES,
                    )
                )

            # directive_refs
            for dir_id in data.get("directive_refs", []) or []:
                tgt_urn = artifact_to_urn("directive", dir_id)
                _ensure_node(nodes_by_urn, tgt_urn, NodeKind.DIRECTIVE)
                _add_edge(
                    DRGEdge(
                        source=src_urn,
                        target=tgt_urn,
                        relation=Relation.REQUIRES,
                    )
                )

            for ref in data.get("references", []) or []:
                ref_type = ref.get("type", "")
                ref_id = ref.get("id", "")
                if not ref_type or not ref_id:
                    continue
                _add_ref_edge(
                    nodes_by_urn=nodes_by_urn,
                    add_edge=_add_edge,
                    source=src_urn,
                    ref_type=ref_type,
                    ref_id=ref_id,
                    relation=_relation_for_procedure_ref_type(ref_type),
                    **_reference_edge_kwargs(ref),
                )

    # --- Procedures ---
    procedures_dir = packs_root / "procedures"
    if procedures_dir.is_dir():
        for path in sorted(procedures_dir.glob("*.procedure.yaml")):
            data = _load_yaml(path)
            if data is None:
                continue
            procedure_id = data.get("id", "")
            procedure_name = data.get("name", "")
            src_urn = artifact_to_urn("procedure", procedure_id)
            _ensure_node(nodes_by_urn, src_urn, NodeKind.PROCEDURE, procedure_name)

            for ref in data.get("references", []) or []:
                ref_type = ref.get("type", "")
                ref_id = ref.get("id", "")
                if not ref_type or not ref_id:
                    continue
                _add_ref_edge(
                    nodes_by_urn=nodes_by_urn,
                    add_edge=_add_edge,
                    source=src_urn,
                    ref_type=ref_type,
                    ref_id=ref_id,
                    relation=_relation_for_procedure_ref_type(ref_type),
                    **_reference_edge_kwargs(ref),
                )

    # --- Agent profiles ---
    _emit_agent_profile_edges(packs_root, nodes_by_urn, _add_edge)

    # --- Styleguides (T027) ---
    # Styleguide ``references`` is a plain ``list[str]`` of file paths — NOT the
    # structured ``{type, id}`` form used by tactics/directives.  Use
    # :func:`_resolve_path_ref` to map each path to a (kind, raw_id) pair.
    styleguides_dir = packs_root / "styleguides"
    if styleguides_dir.is_dir():
        for path in sorted(styleguides_dir.rglob("*.styleguide.yaml")):
            data = _load_yaml(path)
            if data is None:
                continue
            sg_id: str = data.get("id", "")
            sg_title: str = data.get("title", "")
            if not sg_id:
                continue
            src_urn = artifact_to_urn("styleguide", sg_id)
            _ensure_node(nodes_by_urn, src_urn, NodeKind.STYLEGUIDE, sg_title or None)

            for ref_raw in data.get("references", []) or []:
                if not isinstance(ref_raw, str):
                    continue
                resolved = _resolve_path_ref(ref_raw)
                if resolved is None:
                    continue  # URL, glossary path, or unrecognised pattern — skip
                ref_kind, ref_id = resolved
                tgt_kind = _KIND_MAP.get(ref_kind)
                if tgt_kind is None:
                    continue
                tgt_urn = artifact_to_urn(ref_kind, ref_id)
                _ensure_node(nodes_by_urn, tgt_urn, tgt_kind)
                _add_edge(
                    DRGEdge(
                        source=src_urn,
                        target=tgt_urn,
                        relation=Relation.SUGGESTS,
                    )
                )

    # --- Toolguides (T028) ---
    # Toolguides may now carry a ``references`` field (additive schema change per
    # DIRECTIVE_018 — see toolguide.schema.yaml).  Like styleguides, the field is
    # a ``list[str]`` of file paths resolved via :func:`_resolve_path_ref`.
    toolguides_dir = packs_root / "toolguides"
    if toolguides_dir.is_dir():
        for path in sorted(toolguides_dir.rglob("*.toolguide.yaml")):
            data = _load_yaml(path)
            if data is None:
                continue
            tg_id: str = data.get("id", "")
            tg_title: str = data.get("title", "")
            if not tg_id:
                continue
            src_urn = artifact_to_urn("toolguide", tg_id)
            _ensure_node(nodes_by_urn, src_urn, NodeKind.TOOLGUIDE, tg_title or None)

            for ref_raw in data.get("references", []) or []:
                if not isinstance(ref_raw, str):
                    continue
                resolved = _resolve_path_ref(ref_raw)
                if resolved is None:
                    continue
                ref_kind, ref_id = resolved
                tgt_kind = _KIND_MAP.get(ref_kind)
                if tgt_kind is None:
                    continue
                tgt_urn = artifact_to_urn(ref_kind, ref_id)
                _ensure_node(nodes_by_urn, tgt_urn, tgt_kind)
                _add_edge(
                    DRGEdge(
                        source=src_urn,
                        target=tgt_urn,
                        relation=Relation.SUGGESTS,
                    )
                )

    # --- Glossary packs (source-node emission only, WP03) ---
    _emit_glossary_pack_nodes(packs_root, nodes_by_urn)

    # --- Operating-procedures data-drive (M3: #2994/#3352) ---
    # Emit agent_profile --requires--> procedure from the operating-procedures
    # field (guarded), failing closed on any unresolved built-in entry. Runs
    # after every procedure node is minted (procedures block above).
    _emit_operating_procedure_edges(packs_root / "agent_profiles", nodes_by_urn, _add_edge)

    for source, target, relation in _CURATED_ARTIFACT_EDGES:
        source_kind = source.split(":", 1)[0]
        target_kind = target.split(":", 1)[0]
        _ensure_node(nodes_by_urn, source, _KIND_MAP[source_kind])
        _ensure_node(nodes_by_urn, target, _KIND_MAP[target_kind])
        _add_edge(DRGEdge(source=source, target=target, relation=relation))

    return list(nodes_by_urn.values()), list(edges_by_triple.values())


# ---------------------------------------------------------------------------
# T013: Action index walker
# ---------------------------------------------------------------------------


def extract_action_edges(
    doctrine_root: Path,
) -> tuple[list[DRGNode], list[DRGEdge]]:
    """Walk action index files and return action nodes + scope edges."""
    nodes_by_urn: dict[str, DRGNode] = {}
    edges: list[DRGEdge] = []
    seen_triples: set[tuple[str, str, str]] = set()

    def _add_edge(edge: DRGEdge) -> None:
        triple = (edge.source, edge.target, edge.relation.value)
        if triple not in seen_triples:
            seen_triples.add(triple)
            edges.append(edge)

    missions_dir = _missions_root(doctrine_root)
    if not missions_dir.is_dir():
        return [], []

    for index_path in sorted(missions_dir.rglob("actions/*/index.yaml")):
        data = _load_yaml(index_path)
        if data is None:
            continue

        action_name: str = data.get("action", index_path.parent.name)
        # Derive mission name from path: .../missions/<mission>/actions/<action>/index.yaml
        mission_name = index_path.parent.parent.parent.name
        action_urn = f"action:{mission_name}/{action_name}"
        _ensure_node(
            nodes_by_urn, action_urn, NodeKind.ACTION, action_name
        )

        for field_name, kind in _ACTION_SCOPE_FIELDS:
            for raw_id in data.get(field_name, []) or []:
                tgt_urn = artifact_to_urn(kind, raw_id)
                # Subscript, not ``.get(..., GLOSSARY_SCOPE)``: an unmapped kind
                # here is an authoring error in _ACTION_SCOPE_FIELDS, and a node
                # silently registered under the wrong kind is unrecoverable
                # downstream. Safety is pinned by
                # ``test_every_action_scope_field_kind_resolves_to_a_node_kind``.
                _ensure_node(nodes_by_urn, tgt_urn, _KIND_MAP[kind])
                _add_edge(
                    DRGEdge(
                        source=action_urn,
                        target=tgt_urn,
                        relation=Relation.SCOPE,
                    )
                )

    return list(nodes_by_urn.values()), edges


# ---------------------------------------------------------------------------
# T016: Graph generator
# ---------------------------------------------------------------------------


def _discover_built_in_artifact_nodes(
    doctrine_root: Path,
    nodes_by_urn: dict[str, DRGNode],
) -> None:
    """Scan built-in directories for artifacts not yet tracked as nodes.

    This catches styleguides, toolguides, procedures, and agent profiles that
    are referenced in edges but were not walked as part of the primary
    extraction passes.
    """
    # ``rglob`` is used so that artifacts in subdirectories (e.g. toolguides under
    # ``system_tools/``, styleguides under ``writing/``) are always discovered.
    # Each (subdir, kind, node_kind) triple maps to a ``rglob`` pattern; the
    # previous ``glob`` form missed files in second-level subdirectories.
    packs_root = _artifacts_root(doctrine_root)
    scan_dirs: list[tuple[str, str, NodeKind]] = [
        ("styleguides", "styleguide", NodeKind.STYLEGUIDE),
        ("toolguides", "toolguide", NodeKind.TOOLGUIDE),
        ("procedures", "procedure", NodeKind.PROCEDURE),
        ("agent_profiles", "agent_profile", NodeKind.AGENT_PROFILE),
        ("assets", "asset", NodeKind.ASSET),
    ]
    for subdir, kind, node_kind in scan_dirs:
        built_in_dir = packs_root / subdir
        if not built_in_dir.is_dir():
            continue
        _discover_built_in_nodes_in_dir(built_in_dir, kind, node_kind, nodes_by_urn)


def _discover_built_in_nodes_in_dir(
    built_in_dir: Path,
    kind: str,
    node_kind: NodeKind,
    nodes_by_urn: dict[str, DRGNode],
) -> None:
    """Register one node per artifact YAML found under *built_in_dir*.

    Extracted from :func:`_discover_built_in_artifact_nodes` to keep its
    cognitive complexity within the ruff C901 limit (15).
    """
    glob_pattern = "*.agent.yaml" if kind == "agent_profile" else f"*.{kind}.yaml"
    id_key = "profile-id" if kind == "agent_profile" else "id"
    for path in sorted(built_in_dir.rglob(glob_pattern)):
        data = _load_yaml(path)
        if data is None:
            continue
        artifact_id: str = data.get(id_key, "")
        label: str = data.get("name", data.get("title", ""))
        if not artifact_id:
            continue
        urn = artifact_to_urn(kind, artifact_id)
        _ensure_node(nodes_by_urn, urn, node_kind, label or None)


def _iter_mission_type_data(
    doctrine_root: Path,
) -> Iterator[tuple[str, dict[str, Any], Path]]:
    """Yield ``(id, data, path)`` for each shipped mission-type YAML.

    Canonical discovery source for the ``src/charter/offering/missions/mission_types/``
    surface: both :func:`_discover_mission_type_nodes` (nodes) and
    :func:`extract_mission_type_edges` (edges) consume it so the glob is defined
    once. Files without an ``id`` or that fail to parse are skipped.
    """
    mission_types_dir = _missions_root(doctrine_root) / "mission_types"
    if not mission_types_dir.is_dir():
        return
    for path in sorted(mission_types_dir.glob("*.yaml")):
        data = _load_yaml(path)
        if data is None:
            continue
        mission_type_id: str = data.get("id", "")
        if not mission_type_id:
            continue
        yield mission_type_id, data, path


def _discover_mission_type_nodes(
    doctrine_root: Path,
    nodes_by_urn: dict[str, DRGNode],
) -> None:
    """Register a ``mission_type`` node for each shipped mission-type YAML.

    Mirrors :func:`_discover_built_in_artifact_nodes`: one node per
    ``src/charter/offering/missions/mission_types/*.yaml`` file, ``urn=mission_type:<id>``,
    labelled with the file's ``display_name``. Edges from each mission_type to
    its ``action_sequence`` steps are emitted by
    :func:`extract_mission_type_edges`, so ``_KIND_MAP`` now carries a
    ``mission_type`` entry.

    Raises:
        ValueError: if two mission-type YAMLs declare the same ``id``. Left
            unchecked, ``_ensure_node`` would silently collapse the pair onto
            one URN (masking a real authoring collision behind a freshness-clean
            graph); the loud failure mirrors ``MissionTypeRepository``'s
            id/stem invariant.
    """
    seen_ids: dict[str, Path] = {}
    for mission_type_id, data, path in _iter_mission_type_data(doctrine_root):
        if mission_type_id in seen_ids:
            msg = (
                f"Duplicate mission_type id {mission_type_id!r} declared by "
                f"both {seen_ids[mission_type_id].name} and {path.name} in "
                f"{path.parent}"
            )
            raise ValueError(msg)
        seen_ids[mission_type_id] = path
        label: str = data.get("display_name", "")
        urn = artifact_to_urn("mission_type", mission_type_id)
        _ensure_node(nodes_by_urn, urn, NodeKind.MISSION_TYPE, label or None)


def _discover_mission_step_contract_nodes(
    doctrine_root: Path,
    nodes_by_urn: dict[str, DRGNode],
) -> None:
    """Register a ``mission_step_contract`` node per built-in step contract.

    Authoritative source: ``missions/built_in_step_contracts/*.step-contract.yaml``.
    Each shipped contract carries ``mission`` + ``action`` fields; this mints one
    ``mission_step_contract:<mission>/<action>`` node (labelled with the action)
    so a node exists **iff** a contract exists. Mirrors how
    :func:`extract_action_edges` mints ``action:<mission>/<action>`` nodes.

    These nodes are what the pre-review activation ⋈ binding join
    (``review/gate_bindings.py``) resolves against: without
    ``mission_step_contract:software-dev/review`` the transition gate resolves
    NOT_ACTIVATED and never fires. Because the node's owning mission type is
    active by default, the node is default-activated, which makes the reference
    cut (``software-dev/review`` → ``in_progress->for_review``) fire.

    Raises:
        ValueError: if two contracts declare the same ``mission``/``action``
            pair. Left unchecked, ``_ensure_node`` would silently collapse the
            pair onto one URN, masking an authoring collision behind a
            freshness-clean graph.
    """
    contracts_dir = _missions_root(doctrine_root) / "built_in_step_contracts"
    if not contracts_dir.is_dir():
        return
    seen_urns: dict[str, Path] = {}
    for path in sorted(contracts_dir.glob("*.step-contract.yaml")):
        data = _load_yaml(path)
        if data is None:
            continue
        mission: str = data.get("mission", "")
        action: str = data.get("action", "")
        if not mission or not action:
            continue
        urn = artifact_to_urn("mission_step_contract", f"{mission}/{action}")
        if urn in seen_urns:
            msg = (
                f"Duplicate mission_step_contract {urn!r} declared by both "
                f"{seen_urns[urn].name} and {path.name} in {path.parent}"
            )
            raise ValueError(msg)
        seen_urns[urn] = path
        _ensure_node(
            nodes_by_urn, urn, NodeKind.MISSION_STEP_CONTRACT, action
        )


def _resolve_action_sequence(
    step_repo: MissionStepRepository, mission_type_id: str, data: dict[str, Any]
) -> list[str]:
    """Resolve *mission_type_id*'s action sequence via the WP02 projection seam.

    Builtin-only (``pack_context=None``): org/project overrides never leak into
    the shipped graph -- those apply through the separate runtime consumer
    switch (WP06), not this repository-load-time extraction. Steps are read
    through :meth:`MissionStepRepository.resolve_all_for_mission_type` (never a
    raw ``mission-steps/`` directory listing at this call site -- a naive
    listing would blow ``software-dev`` from 5 to 12 edges by including its 7
    non-sequence steps).

    Mirrors the transitional fallback in
    :func:`~charter.offering.missions.mission_type_repository._inject_projected_fields`:
    an empty projection -- mission types whose steps are not yet annotated
    with ``sequence_index``/``in_action_sequence`` (pending WP05) -- falls
    back to the still-authored raw YAML ``action_sequence`` so the shipped
    graph stays byte-identical (NFR-002) until the full cutover (WP07).
    """
    steps = step_repo.resolve_all_for_mission_type(
        mission_type_id, pack_context=None
    ).values()
    projected = project_action_sequence(steps)
    return projected or list(data.get("action_sequence", []) or [])


def extract_mission_type_edges(doctrine_root: Path) -> list[DRGEdge]:
    """Emit ``mission_type:<id> --requires--> action:<id>/<step>`` edges.

    For each shipped mission-type YAML, resolve its action sequence through
    the WP02 projection seam (see :func:`_resolve_action_sequence`) and emit
    one :attr:`Relation.REQUIRES` edge per step to the matching
    ``action:<id>/<step>`` node minted by :func:`extract_action_edges`. Steps
    absent from every action sequence (e.g. ``retrospect``, and
    ``software-dev``'s 7 non-sequence steps) get no edge; they remain
    non-orphan via their own ``scope`` edges. Each edge is emitted exactly
    once (steps within a sequence are unique), so no dedup is needed here --
    duplicate/dangling/cycle safety is enforced by ``assert_valid``.
    """
    edges: list[DRGEdge] = []
    step_repo = MissionStepRepository(_missions_root(doctrine_root) / "mission-steps")
    for mission_type_id, data, _path in _iter_mission_type_data(doctrine_root):
        source_urn = artifact_to_urn("mission_type", mission_type_id)
        sequence = _resolve_action_sequence(step_repo, mission_type_id, data)
        for step in sequence:
            edges.append(
                DRGEdge(
                    source=source_urn,
                    target=artifact_to_urn("action", f"{mission_type_id}/{step}"),
                    relation=Relation.REQUIRES,
                )
            )
    return edges


#: ``governance-profile.yaml`` ``selected_*`` list field name -> the artifact
#: kind its bare-id entries name, for the ``scope`` edges emitted by
#: :func:`extract_governance_profile_scope_edges` (#3604). Mirrors
#: ``_ACTION_SCOPE_FIELDS`` (action-index scope fields) but keyed on the
#: ``selected_*`` field names declared by
#: :class:`charter.mission_type_profiles.MissionTypeProfile` -- the two field
#: sets are named differently (one is action-grain, the other type-grain) so a
#: single shared table would obscure which grain a field belongs to.
_GOVERNANCE_PROFILE_SCOPE_FIELDS: tuple[tuple[str, str], ...] = (
    ("selected_directives", "directive"),
    ("selected_tactics", "tactic"),
    ("selected_paradigms", "paradigm"),
    ("selected_styleguides", "styleguide"),
    ("selected_toolguides", "toolguide"),
    ("selected_procedures", "procedure"),
    ("selected_agent_profiles", "agent_profile"),
    ("selected_mission_step_contracts", "mission_step_contract"),
)


def extract_governance_profile_scope_edges(doctrine_root: Path) -> list[DRGEdge]:
    """Emit ``mission_type:<id> --scope--> <gov>`` edges from each shipped
    ``governance-profile.yaml``'s ``selected_*`` lists (#3604).

    Before this pass, no extraction step ever read
    ``packs/built-in/missions/<type>/governance-profile.yaml`` -- a type's
    *type-wide* governance selections (as distinct from its *action-grain*
    ``actions/*/index.yaml`` selections, which :func:`extract_action_edges`
    already projects) reached no DRG edge at all. ``mission_type:plan``
    authors ONLY type-wide governance (1 directive, 9 tactics, 3 paradigms, 1
    styleguide; empty action grains -- research.md grounding), so its cascade
    was silently empty. This closes that gap identically for all four
    built-in mission types (documentation, plan, research, software-dev).

    Every ``selected_*`` entry is a **bare id** (a plain string, not a
    ``{type, id, when?, reason?}`` reference dict), so the target URN is built
    directly via :func:`~charter.offering.drg.migration.id_normalizer.artifact_to_urn`
    rather than routed through :func:`_reference_edge_kwargs` (which expects a
    reference *dict* to pull optional ``when``/``reason`` metadata from --
    metadata a bare string never carries).

    Mints no nodes: every target kind here (directive, tactic, paradigm,
    procedure, agent_profile via :func:`extract_artifact_edges`; styleguide,
    toolguide via :func:`_discover_built_in_artifact_nodes`;
    mission_step_contract via :func:`_discover_mission_step_contract_nodes`)
    and the ``mission_type:<id>`` source (via
    :func:`_discover_mission_type_nodes`) are minted by earlier passes in
    :func:`generate_graph`, mirroring :func:`extract_mission_type_edges`'s
    same node-free edge-only shape.
    """
    edges: list[DRGEdge] = []
    seen_triples: set[tuple[str, str, str]] = set()
    missions_dir = _missions_root(doctrine_root)
    if not missions_dir.is_dir():
        return edges

    for profile_path in sorted(missions_dir.glob("*/governance-profile.yaml")):
        data = _load_yaml(profile_path)
        if data is None:
            continue
        mission_type_id: str = data.get("mission_type", profile_path.parent.name)
        source_urn = artifact_to_urn("mission_type", mission_type_id)

        for field_name, kind in _GOVERNANCE_PROFILE_SCOPE_FIELDS:
            for raw_id in data.get(field_name, []) or []:
                target_urn = artifact_to_urn(kind, raw_id)
                triple = (source_urn, target_urn, Relation.SCOPE.value)
                if triple in seen_triples:
                    continue
                seen_triples.add(triple)
                edges.append(
                    DRGEdge(
                        source=source_urn,
                        target=target_urn,
                        relation=Relation.SCOPE,
                    )
                )

    return edges


#: Reverse of :data:`_GOVERNANCE_PROFILE_SCOPE_FIELDS` (kind -> field name),
#: used only to phrase :func:`assert_governance_scope_edges_resolve`'s error
#: message in terms of the authoring surface (the ``selected_*`` field name),
#: not the internal edge/kind vocabulary.
_GOVERNANCE_SCOPE_KIND_TO_FIELD: dict[str, str] = {
    kind: field_name for field_name, kind in _GOVERNANCE_PROFILE_SCOPE_FIELDS
}


def assert_governance_scope_edges_resolve(
    edges: list[DRGEdge], nodes_by_urn: dict[str, DRGNode]
) -> None:
    """Fail loud on any governance-profile ``scope`` edge whose target is not
    an already-minted node (#3629).

    Mirrors :func:`_emit_operating_procedure_edges`'s fail-closed contract:
    :func:`extract_governance_profile_scope_edges` mints no nodes of its own
    (see its docstring) -- every ``selected_*`` target is documented as
    minted by an earlier :func:`generate_graph` pass. Before this check, a
    fictional id in any ``selected_*`` list (a typo, a renamed/removed
    artifact) reached no error at all: :func:`generate_graph`'s own
    calibration-target loop (the ``all_urns``-driven ``_ensure_node`` pass
    after :func:`~charter.offering.drg.migration.calibrator.calibrate_surfaces`)
    silently minted a phantom node for it instead, fabricating a real-looking
    DRG node + edge pair for a governance selection that names nothing.

    Must be called with *edges* being exactly
    :func:`extract_governance_profile_scope_edges`'s own return value and
    *nodes_by_urn* the node universe built by every :func:`generate_graph`
    pass that already ran (artifact/action/discovery/mission-type/
    mission-step-contract/template) -- i.e. everything the docstring above
    promises has already minted these targets.
    """
    unresolved: list[str] = []
    for edge in edges:
        if edge.target in nodes_by_urn:
            continue
        _, _, mission_type_id = edge.source.partition(":")
        target_kind, _, target_id = edge.target.partition(":")
        field_name = _GOVERNANCE_SCOPE_KIND_TO_FIELD.get(target_kind, target_kind)
        unresolved.append(f"{mission_type_id}:{field_name}={target_id}")
    if unresolved:
        detail = ", ".join(unresolved)
        raise ValueError(
            "governance-profile.yaml selected_* entries do not resolve to an "
            f"existing node (triage required): {detail}"
        )


def extract_template_instantiation_edges(
    doctrine_root: Path,
) -> tuple[list[DRGNode], list[DRGEdge]]:
    """Emit ``template:<mission>/<file>`` nodes + ``action --instantiates--> template`` edges.

    Graphs-back the ``mission_type -> step -> template`` chain (FR-009): a
    step's ``template`` field is a structured :class:`MissionStepTemplateRef`,
    not a ``references:`` list entry, so no existing pass ever traverses it --
    unlike :func:`extract_mission_type_edges` (modelled on here), this is a
    genuinely new pass rather than an unskip of ``_SKIP_REF_TYPES`` (which is
    empty).

    For each shipped mission-type YAML, resolve its steps through the same
    builtin-only :meth:`MissionStepRepository.resolve_all_for_mission_type`
    seam :func:`extract_mission_type_edges` uses, then walk
    :func:`~charter.offering.missions.step_projection.iter_template_refs` -- the
    **sole traversal** of ``MissionStep.template`` (C-003) -- rather than
    re-checking ``step.template`` independently here.

    Each ``(step, template_ref)`` pair mints:

    - a mission-qualified ``template:<mission_type>/<template_file>`` node
      (via :func:`charter.offering.template_catalog.template_urn`), deduplicated by
      URN (two steps in the same mission type never share a template file
      today, but a future one might);
    - one :attr:`Relation.INSTANTIATES` edge from the step's own
      ``action:<mission_type>/<step_id>`` node (already minted by
      :func:`extract_action_edges`) to that template node.

    Edges are emitted sorted by ``(source, target)`` (FR-011) so the pass is
    deterministic independent of the composing ``generate_graph`` sort.
    Callers land the returned edges in ``action.graph.yaml`` (action-sourced)
    and the returned nodes in ``template.graph.yaml`` (nodes only) -- the 16
    bare ``template:<name>`` exemplars (#2712) are untouched by this pass,
    which only ever mints mission-qualified URNs.
    """
    nodes: list[DRGNode] = []
    edges: list[DRGEdge] = []
    seen_node_urns: set[str] = set()
    step_repo = MissionStepRepository(_missions_root(doctrine_root) / "mission-steps")
    for mission_type_id, _data, _path in _iter_mission_type_data(doctrine_root):
        steps = step_repo.resolve_all_for_mission_type(
            mission_type_id, pack_context=None
        ).values()
        for step, template_ref in iter_template_refs(steps):
            template_id = template_id_for(mission_type_id, template_ref.template_file)
            node_urn = template_urn(template_id)
            if node_urn not in seen_node_urns:
                seen_node_urns.add(node_urn)
                nodes.append(
                    DRGNode(urn=node_urn, kind=NodeKind.TEMPLATE, label=template_id)
                )
            action_urn = artifact_to_urn("action", f"{mission_type_id}/{step.id}")
            edges.append(
                DRGEdge(
                    source=action_urn,
                    target=node_urn,
                    relation=Relation.INSTANTIATES,
                )
            )
    edges.sort(key=lambda e: (e.source, e.target))
    return nodes, edges


def generate_graph(
    doctrine_root: Path,
    output_path: Path,
    *,
    generated_at: str | None = None,
) -> DRGGraph:
    """Compose extraction + calibration into a validated ``graph.yaml``.

    Args:
        doctrine_root: Path to ``src/charter/offering/``.
        output_path: Locates the output *directory* (``output_path.parent``).
            The graph is written there as per-kind ``<kind>.graph.yaml``
            fragments and any ``graph.yaml`` monolith in that directory is
            removed in the same write (DD-7/DD-8).
        generated_at: Optional fixed timestamp for deterministic output.
            If ``None``, ``"STATIC"`` is used so the output is always
            identical for the same input (idempotent).

    Returns:
        The validated ``DRGGraph`` instance.
    """
    # Step 1: Extract artifact nodes + edges
    artifact_nodes, artifact_edges = extract_artifact_edges(doctrine_root)

    # Step 2: Extract action nodes + edges
    action_nodes, action_edges = extract_action_edges(doctrine_root)

    # Step 3: Merge nodes (deduplicate by URN)
    nodes_by_urn: dict[str, DRGNode] = {}
    for node in artifact_nodes + action_nodes:
        _ensure_node(nodes_by_urn, node.urn, node.kind, node.label)

    # Step 4: Discover built-in artifacts not yet tracked
    _discover_built_in_artifact_nodes(doctrine_root, nodes_by_urn)

    # Step 4b: Discover mission-type nodes
    _discover_mission_type_nodes(doctrine_root, nodes_by_urn)

    # Step 4b': Discover mission_step_contract nodes (one per built-in step
    # contract) so the pre-review activation join resolves ACTIVE.
    _discover_mission_step_contract_nodes(doctrine_root, nodes_by_urn)

    # Step 4c: Graph-back the mission_type->step->template chain (FR-009):
    # mint mission-qualified template nodes + action->template instantiates
    # edges from the WP01 iter_template_refs projection.
    template_nodes, template_instantiation_edges = extract_template_instantiation_edges(
        doctrine_root
    )
    for node in template_nodes:
        _ensure_node(nodes_by_urn, node.urn, node.kind, node.label)

    # Step 5: Merge all edges (mission_type->action edges join before
    # calibration + the deterministic sort so they are treated uniformly)
    mission_type_edges = extract_mission_type_edges(doctrine_root)
    # Step 5b (#3604, T007): type-wide governance-profile.yaml selections as
    # direct mission_type --scope--> gov edges (distinct from the action-grain
    # scope edges action_edges already carries).
    governance_profile_scope_edges = extract_governance_profile_scope_edges(
        doctrine_root
    )
    # #3629: fail loud on any fictional ``selected_*`` entry (an id naming no
    # node minted by any pass above) instead of letting it reach the
    # calibration-target loop below, which would otherwise phantom-mint a
    # node for it — see ``assert_governance_scope_edges_resolve``'s docstring.
    assert_governance_scope_edges_resolve(governance_profile_scope_edges, nodes_by_urn)
    governance_scope_targets = {edge.target for edge in governance_profile_scope_edges}
    all_edges = (
        artifact_edges
        + action_edges
        + mission_type_edges
        + governance_profile_scope_edges
        + template_instantiation_edges
    )

    # Step 6: Calibrate surfaces
    all_nodes_list = list(nodes_by_urn.values())
    calibrated_edges = calibrate_surfaces(all_nodes_list, all_edges)

    # Ensure any new calibration-target nodes exist
    all_urns = {n.urn for n in all_nodes_list}
    for edge in calibrated_edges:
        for urn in (edge.source, edge.target):
            if urn not in all_urns:
                if urn in governance_scope_targets:
                    # assert_governance_scope_edges_resolve (above) already
                    # guarantees every governance scope-edge target is a
                    # pre-existing node; reaching here would mean that
                    # guarantee broke silently between the two checks. Fail
                    # loud rather than let this generic phantom-mint
                    # fallback fabricate a governance-selection node (#3629)
                    # -- narrowed so this loop can never re-swallow the
                    # defect the upfront check exists to catch.
                    raise ValueError(
                        f"governance scope-edge target {urn!r} unresolved "
                        "after upfront validation (fail-closed defense-in-depth)"
                    )
                # Infer kind from URN prefix
                prefix = urn.split(":", 1)[0]
                kind = _KIND_MAP.get(prefix)
                if kind is None:
                    continue  # unknown prefix -- should not happen
                _ensure_node(nodes_by_urn, urn, kind)
                all_urns.add(urn)

    # Step 7: Build graph with deterministic ordering
    ts = generated_at or "STATIC"
    sorted_nodes = sorted(nodes_by_urn.values(), key=lambda n: n.urn)
    sorted_edges = sorted(
        calibrated_edges,
        key=lambda e: (e.source, e.target, e.relation.value),
    )

    graph = DRGGraph(
        schema_version="1.0",
        generated_at=ts,
        generated_by="drg-migration-v1",
        nodes=sorted_nodes,
        edges=sorted_edges,
    )

    # Step 8: Validate
    assert_valid(graph)

    # Step 9: Write sharded YAML fragments (per populated node-kind) and
    # atomically retire the monolith in the same directory.
    _write_graph_yaml(graph, output_path)

    return graph


#: File name of the retired single-file DRG layout. ``load_graph_or_dir``
#: prefers it when present, so it must never coexist with fragments (DD-7).
_MONOLITH_NAME = "graph.yaml"
_FRAGMENT_SUFFIX = ".graph.yaml"


def _partition_by_kind(graph: DRGGraph) -> dict[NodeKind, DRGGraph]:
    """Partition *graph* into one sub-graph per **populated** node-kind (DD-8).

    Every node-kind that owns at least one node yields a fragment carrying that
    kind's node set plus the edges whose **source** node is of that kind. Each
    node lands in exactly one fragment (by its kind) and each edge in exactly
    one fragment (by its source-node kind), so concatenating the fragments
    reconstructs the whole graph with no node or edge lost or duplicated.

    Target-only kinds — kinds that own nodes but are never an edge source (e.g.
    ``template``) — still get a fragment (with an empty edge list); omitting
    them would silently drop their nodes on reload (not behaviour-preserving).

    Each fragment is emitted in canonical intra-fragment order (DD-11): nodes by
    URN, edges by ``(source, target, relation)``.
    """
    kind_by_urn: dict[str, NodeKind] = {n.urn: n.kind for n in graph.nodes}
    nodes_by_kind: dict[NodeKind, list[DRGNode]] = defaultdict(list)
    for node in graph.nodes:
        nodes_by_kind[node.kind].append(node)
    edges_by_kind: dict[NodeKind, list[DRGEdge]] = defaultdict(list)
    for edge in graph.edges:
        # ``assert_valid`` (run before writing) guarantees no dangling edge, so
        # every source URN maps to a known node kind.
        edges_by_kind[kind_by_urn[edge.source]].append(edge)

    fragments: dict[NodeKind, DRGGraph] = {}
    for kind, nodes in nodes_by_kind.items():
        fragments[kind] = DRGGraph(
            schema_version=graph.schema_version,
            generated_at=graph.generated_at,
            generated_by=graph.generated_by,
            nodes=sorted(nodes, key=lambda n: n.urn),
            edges=sorted(
                edges_by_kind.get(kind, []),
                key=lambda e: (e.source, e.target, e.relation.value),
            ),
        )
    return fragments


def _write_graph_yaml(graph: DRGGraph, output_path: Path) -> None:
    """Write *graph* as per-kind fragments beside *output_path*; retire monolith.

    DD-7/DD-8: the graph is stored as one ``<kind>.graph.yaml`` fragment per
    populated node-kind in ``output_path.parent`` (the loader glob root). Any
    ``graph.yaml`` monolith or stale fragment in that directory is removed in
    the same write so the directory never carries both layouts — otherwise
    ``load_graph_or_dir`` would prefer the monolith and silently mask the
    fragments.
    """
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    fragments = _partition_by_kind(graph)
    written: set[str] = set()
    for kind, fragment in fragments.items():
        fragment_path = output_dir / f"{kind.value}{_FRAGMENT_SUFFIX}"
        _dump_graph_document(fragment, fragment_path)
        written.add(fragment_path.name)

    # Remove stale fragments from a prior run whose kind is no longer populated.
    for existing in output_dir.glob(f"*{_FRAGMENT_SUFFIX}"):
        if existing.name not in written:
            existing.unlink()

    # Atomic monolith retirement (DD-7): never leave graph.yaml beside fragments.
    monolith = output_dir / _MONOLITH_NAME
    if monolith.is_file():
        monolith.unlink()


def _dump_graph_document(graph: DRGGraph, output_path: Path) -> None:
    """Serialise a single ``DRGGraph`` document to *output_path* as sorted YAML."""
    # T006: the five document-level keys are derived from ``DRGGraph.model_fields``
    # (via :func:`graph_document_to_dict`), not restated here, so a top-level
    # field added to the model is emitted without editing this writer. Nodes and
    # edges recurse through the same derived ``model_to_graph_dict`` helper.
    data: dict[str, Any] = graph_document_to_dict(graph)

    yaml_writer = YAML()
    yaml_writer.default_flow_style = False
    yaml_writer.allow_unicode = True
    yaml_writer.width = 4096
    # Sort keys at the top level for deterministic output
    with output_path.open("w") as fh:
        yaml_writer.dump(data, fh)


#: Model fields deliberately kept out of ``*.graph.yaml`` (FR-004, T016).
#:
#: ``provenance`` is the merge-time layer marker (FR-013). It is ``None`` for
#: every extractor-built node, so emitting it would add a dead key to all 14
#: shipped fragments. Withholding it is a *declaration*, not a silence: the set
#: is named, and ``test_the_withholding_set_names_only_real_model_fields``
#: asserts every member is a real field, so a typo here cannot rot into an
#: exclusion that excludes nothing.
#:
#: Everything a model declares and does not name here is emitted by
#: construction. That is the whole point -- the writers used to restate their
#: field names, so a field added to ``DRGNode``/``DRGEdge`` loaded fine and was
#: deleted on the next write.
FIELDS_WITHHELD_FROM_GRAPH_OUTPUT: frozenset[str] = frozenset({"provenance"})

#: Backwards-compatible private alias (T001 promotion). Existing call sites and
#: guard tests that read ``_FIELDS_WITHHELD_FROM_GRAPH_OUTPUT`` keep working; the
#: two names are one object.
_FIELDS_WITHHELD_FROM_GRAPH_OUTPUT = FIELDS_WITHHELD_FROM_GRAPH_OUTPUT

#: Fields whose *empty* value (``None`` or ``[]``) is intentionally omitted from
#: ``*.graph.yaml`` (contract W-1a, T002). This is the second half of totality.
#:
#: ``FIELDS_WITHHELD_FROM_GRAPH_OUTPUT`` makes the derivation total over field
#: *names*; this set makes it total over *values*. ``_render_for_yaml`` used to
#: collapse ``None`` **and** every empty list to ``None``, and the writer dropped
#: any key whose rendered value was ``None`` — so a novel ``impacts: list[str] =
#: []`` field vanished on an unpopulated instance while a completeness gate over a
#: populated fixture stayed green (vacuous for exactly the field B1 adds).
#:
#: The rule is now explicit and opt-in: a field is omitted-when-empty **only** if
#: it is named here. Every other declared field — including any B1/B2 adds — is
#: emitted even when empty (``null`` / ``[]``), so it can never be dropped in
#: silence. The members are exactly the pre-existing optionals whose empty form
#: was already absent from every shipped fragment, so the shipped graph stays
#: byte-identical. ``test_the_omit_when_empty_set_is_a_shrink_only_allowlist``
#: pins the content so padding it (the way to re-open the hole) costs a
#: deliberate, diff-visible edit.
_FIELDS_OMITTED_WHEN_EMPTY: frozenset[str] = frozenset(
    {"label", "tags", "when", "reason"}
)


def _is_empty(value: Any) -> bool:
    """Return whether *value* is an omissible empty: ``None`` or an empty list.

    Deliberately narrow: ``False`` and ``0`` are **not** empty, so a
    ``is_symmetric: bool = False`` field renders as ``false`` rather than being
    dropped. Only ``None`` and ``[]`` qualify — the two shapes the pre-T002
    writer silently collapsed.
    """
    return value is None or (isinstance(value, list) and not value)


def _render_for_yaml(value: Any) -> Any:
    """Render one model field value for YAML output.

    Enums are unwrapped before the ``str`` branch because ``NodeKind`` /
    ``Relation`` are ``StrEnum`` and would otherwise serialise as their repr;
    strings are whitespace-trimmed; lists recurse. Unlike the pre-T002 form this
    no longer collapses empty containers to ``None`` — omission is decided
    separately by :data:`_FIELDS_OMITTED_WHEN_EMPTY`, so a non-omitted empty
    value renders faithfully (``[]`` / ``None``) instead of vanishing.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_render_for_yaml(item) for item in value]
    return value


def model_to_graph_dict(model: BaseModel) -> dict[str, Any]:
    """Serialise every declared field of *model* except the withheld ones.

    Derived from ``type(model).model_fields`` rather than a hand-written key
    list, so a field added to the model is written without anyone remembering
    to update this function. This is the **public, canonical** DRG mapping
    writer (T001, mission ``doctrine-delivery-reachability``): every sibling
    write path — ``charter.synthesizer.project_drg`` and
    ``specify_cli.migration.rewrite_opposed_by`` — routes through it so no writer
    restates the field list by hand. It is registered as a ``MappingWriter`` in
    ``specify_cli.drg_writers.registry``; the registry's completeness gate
    iterates every member and fails naming the writer + the dropped field.

    Totality has **two** dimensions and this helper closes both: a field name is
    dropped only via :data:`FIELDS_WITHHELD_FROM_GRAPH_OUTPUT`, and an empty value
    is dropped only for a field named in :data:`_FIELDS_OMITTED_WHEN_EMPTY`
    (contract W-1a). Any other field — including a novel ``impacts: list[str] =
    []`` — is emitted even when empty.
    """
    rendered: dict[str, Any] = {}
    for field_name in type(model).model_fields:
        if field_name in FIELDS_WITHHELD_FROM_GRAPH_OUTPUT:
            continue
        raw = getattr(model, field_name)
        if field_name in _FIELDS_OMITTED_WHEN_EMPTY and _is_empty(raw):
            continue
        rendered[field_name] = _render_for_yaml(raw)
    return rendered


#: Backwards-compatible private alias. Internal call sites that predate the
#: T001 promotion keep working; the two names are one object.
_model_to_dict = model_to_graph_dict


def _node_to_dict(node: DRGNode) -> dict[str, Any]:
    """Field-derived ``DRGNode`` -> plain dict for YAML output."""
    return model_to_graph_dict(node)


def _edge_to_dict(edge: DRGEdge) -> dict[str, Any]:
    """Field-derived ``DRGEdge`` -> plain dict for YAML output."""
    return model_to_graph_dict(edge)


def graph_document_to_dict(graph: DRGGraph) -> dict[str, Any]:
    """Field-derived ``DRGGraph`` -> plain document dict for YAML output.

    Derives the document-level keys from ``DRGGraph.model_fields`` (T006) rather
    than restating ``schema_version`` / ``generated_at`` / ``generated_by`` /
    ``nodes`` / ``edges`` by hand, so a top-level field added to :class:`DRGGraph`
    is emitted without editing this function — the fourth writer named in the
    module note above. ``nodes`` / ``edges`` recurse through
    :func:`model_to_graph_dict`; every other declared field is copied verbatim.

    Registered as the sole ``DocumentWriter`` in
    ``specify_cli.drg_writers.registry`` and consumed by
    :func:`_dump_graph_document` so the production write path is derived too.
    """
    data: dict[str, Any] = {}
    for field_name in type(graph).model_fields:
        if field_name in FIELDS_WITHHELD_FROM_GRAPH_OUTPUT:
            continue
        value = getattr(graph, field_name)
        if field_name in {"nodes", "edges"}:
            data[field_name] = [model_to_graph_dict(item) for item in value]
        else:
            data[field_name] = value
    return data
