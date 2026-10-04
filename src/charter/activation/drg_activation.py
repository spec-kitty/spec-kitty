"""Activation-side DRG (Doctrine Reference Graph) logic.

Split out of ``charter/drg.py`` (mission ``charter-activation-split-01M16ZSE``,
DEC-1 in ``kitty-specs/charter-activation-split-01M16ZSE/contracts/
activation-topology-map.md``): the pure offering-type re-exports
(``ArtifactKind``, ``DRGNode``, ``NodeKind``, ``load_graph``, ...) stay on
the top-level ``charter.drg`` facade unchanged. The logic below reads
project-charter activation state (:class:`~charter.activation.pack_context.PackContext`)
to decide which doctrine artifacts are visible — an activation concern, not
an offering-type concern — so it lives inside ``charter.activation`` per the
runtime -> charter -> offering/activation boundary (ADR 2026-08-22-2 §5,
C-004).

Provides:

* :func:`load_org_drg` — loads all configured org packs from
  ``.kittify/config.yaml`` (FR-001, FR-004, NEW-1).
* :func:`filter_graph_by_activation` — the FR-006/FR-018 activation filter
  (WP11), plus its private helpers.
* :data:`merge_three_layers` — re-exported here (rather than from
  ``charter.drg``) because it rides alongside the activation-aware callers
  that also need :func:`filter_graph_by_activation` / :func:`load_org_drg`;
  its canonical implementation still lives in
  ``charter.offering.drg.merge`` (pure graph logic, no charter/specify_cli
  dependency) and is unchanged by this split.
"""

from __future__ import annotations

import logging
from pathlib import Path

from charter.offering.api import ArtifactKind
from charter.offering.artifact_kinds import CHARTER_ACTIVATABLE_KINDS, CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL
from charter.offering.drg.merge import merge_three_layers
from charter.offering.drg.models import DRGGraph
from charter.offering.drg.org_pack_config import load_pack_registry
from charter.offering.drg.org_pack_loader import (
    OrgDRGFragment,
    OrgPackParseError,
    OrgPackSchemaError,
    load_org_pack,
)

from .catalog import resolve_doctrine_root
from .kind_vocabulary import (
    MissionTypeNotAnArtifactKind,
    UnknownArtifactIdError,
    resolve_artifact_urn,
)
from .pack_context import PackContext

logger = logging.getLogger(__name__)

__all__ = [
    "filter_graph_by_activation",
    "load_org_drg",
    "merge_three_layers",
]

# ---------------------------------------------------------------------------
# Loader (FR-001, FR-004, NEW-1)
# ---------------------------------------------------------------------------


def load_org_drg(
    repo_root: Path,
    *,
    strict: bool = True,
    degrade_malformed: bool = False,
) -> list[OrgDRGFragment]:
    """Load all configured org packs from ``.kittify/config.yaml``.

    Returns one :class:`OrgDRGFragment` per pack in declaration order.
    Layer indices are assigned ``1..N`` from the full-registry enumeration —
    a pack skipped under ``strict=False`` does **not** renumber its siblings.

    This function is project-config-aware (charter-domain): it reads the
    shared org-pack registry contract from
    :func:`charter.offering.drg.org_pack_config.load_pack_registry` and resolves each
    pack's local path relative to *repo_root*. Per-pack schema parsing and
    validation is delegated to :func:`charter.offering.drg.org_pack_loader.load_org_pack`.

    Parameters
    ----------
    repo_root:
        Repository root containing ``.kittify/config.yaml``. When the
        config is absent or has no ``doctrine.org`` pack entries, the
        function returns ``[]`` (NFR-001 backward compatibility — repos
        with no org packs behave identically to today).
    strict:
        When ``True`` (default), behaviour is identical to the original
        loader: every configured pack is loaded via
        :func:`charter.offering.drg.org_pack_loader.load_org_pack`, which raises
        :class:`OrgPackMissingError` when a pack ships no
        ``drg/fragment.yaml``. The diagnostic callers (``doctor doctrine`` /
        ``charter list`` / lint / status) keep this default so their
        error-reporting stays byte-identical (NFR-001).

        When ``False``, a pack whose ``drg/fragment.yaml`` does not exist is
        **skipped** (it contributes no fragment layer); any root-level
        ``*.graph.yaml`` it ships is still folded by
        :func:`charter.activation._drg_helpers.load_validated_graph`'s per-root loop, and
        a pack shipping neither is warned there. The cascade callers
        (``charter activate/deactivate``) pass ``strict=False`` so a mixed
        chain (one root-graph pack + one fragment pack) yields the real
        fragment edges instead of raising on the first fragment-less pack
        (DRG read-path bridge, mission ``drg-read-path-bridge-01M0CHVZ``, D3).
    degrade_malformed:
        Only meaningful when ``strict=False``. When ``True``, a pack whose
        ``drg/fragment.yaml`` is present but **unloadable** — malformed (a
        parse or schema fault — :class:`OrgPackParseError` /
        :class:`OrgPackSchemaError`) or unreadable (an ``OSError``:
        permission-denied, or the path is a directory) — is
        **skipped per-pack** with an operator-visible ``WARNING`` naming the
        offending pack, and the remaining healthy packs' fragments are still
        returned. The default ``False`` preserves the byte-identical fail-loud
        contract every non-degrading caller relies on (the diagnostic APIs, and
        the fail-loud composition path exercised by
        ``tests/integration/test_org_pack_chain_delivery.py``): a single
        malformed fragment still raises and aborts the whole load.

        This is deliberately narrow (mission ``doctrine-drg-silent-drop-
        boundary``, convergent LOW finding). ONLY the schema/parse fault of an
        *optional* fragment degrades — exactly the class the mission-step
        executor already tolerated, but per-pack instead of whole-chain, so a
        single bad optional pack no longer evicts its healthy siblings'
        fragments. The read-fault class (``OSError`` — an unreadable optional
        fragment) degrades identically (#4200 defect 2: the loader presents it
        as the I/O fault it is, never masked as a parse error, and this
        per-pack degrade keeps the mission-step composition path tolerant of
        exactly the condition it tolerated before that seam). Config faults
        (``NotImplementedError`` for an unsupported
        ``source:``, env-var / subdir-escape errors) are raised before the
        per-pack loop and still fail loud; endpoint / dangling-governance faults
        are surfaced downstream by ``load_validated_graph`` and are unaffected.
        ``strict=True`` NEVER degrades, whatever ``degrade_malformed`` is.

    Raises
    ------
    OrgPackMissingError:
        When ``strict=True`` and a configured pack ships no
        ``drg/fragment.yaml`` (FR-004).
    OrgPackParseError / OrgPackSchemaError:
        When a configured pack's ``drg/fragment.yaml`` is malformed — unless
        ``strict=False`` and ``degrade_malformed=True``, in which case only that
        pack is skipped (with a ``WARNING``) and its siblings still load.
    OSError:
        When a configured pack's ``drg/fragment.yaml`` exists but cannot be
        read (permissions, or the path is a directory) — unless
        ``strict=False`` and ``degrade_malformed=True``, in which case only
        that pack is skipped (with a ``WARNING``). Never masked as a parse
        error (#4200 defect 2).
    NotImplementedError:
        When a pack declares ``source: url`` or ``source: package`` —
        only ``local_path`` is shipped in this mission (NEW-1). Raised before
        the per-pack loop, so ``degrade_malformed`` never suppresses it.
    """
    registry = load_pack_registry(repo_root)
    fragments: list[OrgDRGFragment] = []
    for layer_index, pack in enumerate(registry.packs, start=1):
        pack_root = pack.effective_root(repo_root)
        if not strict and not (pack_root / "drg" / "fragment.yaml").exists():
            continue
        if strict or not degrade_malformed:
            fragments.append(load_org_pack(pack.name, pack_root, layer_index))
            continue
        try:
            fragments.append(load_org_pack(pack.name, pack_root, layer_index))
        except (OrgPackParseError, OrgPackSchemaError, OSError) as exc:
            logger.warning(
                "Org pack %r at %s ships a malformed or unreadable "
                "drg/fragment.yaml (%s: %s); dropping ONLY this pack's "
                "fragment and composing with the remaining org packs. "
                "Fix or remove this pack in .kittify/config.yaml.",
                pack.name,
                pack_root,
                type(exc).__name__,
                exc,
            )
    return fragments


# ---------------------------------------------------------------------------
# Merge (canonical implementation stays in ``charter.offering.drg.merge``)
# ---------------------------------------------------------------------------
# ``merge_three_layers`` (imported above) is pure graph logic with no
# charter/specify_cli dependency; it lives beside the activation filter here
# only because its callers are almost always also activation-filter callers.


# ---------------------------------------------------------------------------
# Activation filter (FR-006, FR-018, WP11)
# ---------------------------------------------------------------------------
# Mission ``charter-doctrine-mission-type-configuration-01KSWJVX`` WP11.
#
# FR-018 specifies that DRG traversal is activation-filtered: only doctrine
# artifacts that are explicitly activated in the project charter are visible
# to charter-mediated resolution. "Activated" and "registered" are synonyms
# per the data-model. The filter is sourced from ``PackContext``:
#
# * ``PackContext.activated_kinds``           — plural artifact kinds the
#                                                charter has opted in to.
# * ``PackContext.activated_mission_types``   — mission type IDs the charter
#                                                has opted in to.
#
# FR-006's two-tier directive scope is honoured by this filter because
# mission-type-scoped directives only enter the resolved set when that
# mission type is activated. Project-scoped directives
# (``required_directives`` from the top-level charter) are never gated by
# the activation filter — they apply unconditionally to every mission.
#
# CRITICAL INVARIANT (WP11 T069): the activation filter applies ONLY to
# charter-mediated resolution paths. Direct doctrine-API callers
# (``MissionTemplateRepository.get(...)``, ``service.directives.get(...)``,
# etc.) bypass this filter and continue to return non-activated artifacts.
# This is by design: non-activated artifacts are non-canonical for charter
# resolution but remain reachable on operator request.


#: Inverse of :data:`_PLURAL_TO_SINGULAR`, used to map a URN's singular kind
#: prefix (e.g. ``"directive"``) back to its plural form (e.g.
#: ``"directives"``) so the activation filter can check membership in
#: :attr:`PackContext.activated_kinds`.
_SINGULAR_TO_PLURAL = CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL


#: Per-kind ``PackContext`` field names for per-artifact-ID gate (FR-038, WP08).
#: Maps a singular URN kind prefix to the corresponding ``PackContext`` attribute
#: that holds the three-state frozenset of activated artifact IDs.
_SINGULAR_TO_PER_KIND_FIELD: dict[str, str] = {kind.value: f"activated_{kind.plural}" for kind in ArtifactKind if kind in CHARTER_ACTIVATABLE_KINDS}


#: URN kind prefixes that represent mission steps. When the filter encounters
#: one of these kinds, it consults ``activated_mission_types`` (via the
#: ``_owning_mission_type`` heuristic below) instead of ``activated_kinds``.
_MISSION_STEP_SINGULAR_KINDS: frozenset[str] = frozenset({"mission_step_contract"})


#: Singular kinds excluded from stem->canonical-URN resolution (WP01).
#:
#: ``anti_pattern`` has no dedicated artifact file / config stem: it is a
#: re-kinded, tagged node living inside another kind's YAML fragment, never
#: a standalone ``*.anti_pattern.yaml`` file (see
#: ``charter.offering.artifact_kinds`` module docstring and its ``glob_pattern``
#: entry, which is declared for enum completeness but never matches a real
#: file). ``PackContext.activated_anti_patterns`` therefore already holds
#: the canonical/direct artifact id, not a config stem needing resolution —
#: routing it through :func:`charter.activation.kind_vocabulary.resolve_artifact_urn`
#: would always raise :class:`UnknownArtifactIdError` and silently drop
#: every anti-pattern node. This mirrors the reference tension-scan's
#: ``_CLI_KIND_TO_DRG_SINGULAR`` (``consistency_check.py:89-99``), which
#: likewise omits ``anti_pattern`` from stem-resolution treatment.
_NO_STEM_RESOLUTION_KINDS: frozenset[str] = frozenset({"anti_pattern"})


def _split_urn(urn: str) -> tuple[str, str]:
    """Split ``"<kind>:<id>"`` into ``(kind, id)``.

    Returns ``(urn, "")`` when the URN is malformed (no colon). Defensive
    against hand-constructed graphs that bypass DRGNode validation —
    ``str.partition(":")`` yields ``(whole, "", "")`` in that case so the
    identifier comes back empty and the activation filter routes the node
    through the default-allow branch.
    """
    head, _sep, tail = urn.partition(":")
    return (head, tail)


def _owning_mission_type(urn: str) -> str | None:
    """Best-effort recovery of the mission type ID that owns a mission-step URN.

    Mission-step contract URNs in the doctrine universe encode the owning
    mission type as the first path segment of the identifier portion. The
    runtime layout writes contracts under
    ``doctrine/missions/<mission-type>/mission_step_contracts/...`` and the
    canonical URN form is ``mission_step_contract:<mission-type>/<id>``.

    When the URN is not in that shape (e.g. an org-pack-authored step that
    has not been bound to a built-in mission type), this returns ``None``;
    the activation filter treats such steps as project-scoped and lets them
    through. WP08 / WP09 will tighten the convention once mission-type-owned
    org packs land.
    """
    _kind, identifier = _split_urn(urn)
    if not identifier:
        return None
    head, sep, _ = identifier.partition("/")
    if not sep:
        return None
    return head


def _resolve_activated_urns_for_kind(
    node_kind: str,
    activated_ids: frozenset[str] | None,
    *,
    doctrine_root: Path,
    org_roots: list[Path],
    layer_roots: dict[str, Path] | None = None,
) -> frozenset[str] | None:
    """Resolve one kind's config-stem activation set to canonical URNs.

    Preserves the three-state semantics of :class:`PackContext`'s per-kind
    fields: ``None`` (key absent from config) stays ``None`` (default-allow);
    an explicit empty set resolves to an empty ``frozenset`` (block-all).

    Lifted (WP01, per ``contracts/activation-gate-contract.md``) from the
    soon-to-be-deleted tension-scan's ``_resolve_activated_urns_for_kind``
    (``consistency_check.py:874-905``): unknown/unresolvable stems are
    skipped, never raised (:class:`UnknownArtifactIdError`) -- they are
    already surfaced separately by ``_check_unknown_references``, and this
    gate must never raise (it is consumed by five callers, including the
    fail-closed-**report** ``_check_graph_kind_parity``).

    ``node_kind`` values in :data:`_NO_STEM_RESOLUTION_KINDS` (currently only
    ``anti_pattern``) bypass filesystem resolution entirely: their
    ``PackContext`` field already holds canonical/direct ids, not config
    stems, so each id is wrapped into a URN directly.
    """
    if activated_ids is None:
        return None
    if node_kind in _NO_STEM_RESOLUTION_KINDS:
        return frozenset(f"{node_kind}:{raw_id}" for raw_id in activated_ids)
    try:
        kind_enum = ArtifactKind.from_operator_token(node_kind)
    except MissionTypeNotAnArtifactKind:
        # Defensive parity with the reference pattern; unreachable via the
        # gate's fixed kind domain (_SINGULAR_TO_PER_KIND_FIELD never keys on
        # "mission-type"), kept for symmetry should that domain ever grow.
        return frozenset()

    urns: set[str] = set()
    for stem in activated_ids:
        try:
            urns.add(resolve_artifact_urn(kind_enum, stem, doctrine_root=doctrine_root, org_roots=org_roots, layer_roots=layer_roots))
        except UnknownArtifactIdError:
            continue  # Skip-with-report (contract): _check_unknown_references reports it.
    return frozenset(urns)


def _resolve_activated_urns_by_kind(
    pack_context: PackContext,
) -> dict[str, frozenset[str] | None]:
    """Batch-resolve every per-kind activation set to canonical URNs, once.

    Called once per :func:`filter_graph_by_activation` invocation -- never
    per node -- so resolution is O(kinds x stems), not O(nodes x stems x
    filesystem-walk). ``doctrine_root`` is sourced from
    :func:`charter.activation.catalog.resolve_doctrine_root` (the same source the
    surviving compiler ``references.yaml`` projection uses), never
    ``pack_context.pack_roots[0]`` (research.md D2 install-layout guard).
    """
    doctrine_root = resolve_doctrine_root()
    org_roots = list(pack_context.org_roots)
    return {
        node_kind: _resolve_activated_urns_for_kind(
            node_kind,
            getattr(pack_context, per_kind_field, None),
            doctrine_root=doctrine_root,
            org_roots=org_roots,
            layer_roots={"project": pack_context.repo_root / ".kittify"},
        )
        for node_kind, per_kind_field in _SINGULAR_TO_PER_KIND_FIELD.items()
    }


def _node_is_activated(
    node_kind: str,
    artifact_id: str,
    pack_context: PackContext,
    resolved_urns_by_kind: dict[str, frozenset[str] | None],
) -> bool:
    """Return ``True`` when the artifact is visible under the activation filter.

    Parameters
    ----------
    node_kind:
        Singular URN kind prefix (e.g. ``"directive"``, ``"tactic"``).
    artifact_id:
        Identifier portion of the URN (the part after the first ``":"``).
        An empty string (malformed URN) bypasses the per-artifact-ID gate.
    pack_context:
        Activation state from the project charter.
    resolved_urns_by_kind:
        Pre-resolved (WP01) canonical-URN sets per singular kind, built once
        by :func:`_resolve_activated_urns_by_kind` in
        :func:`filter_graph_by_activation`. This keeps ``_node_is_activated``
        a pure membership check with no filesystem I/O.

    Decision tree:

    1. Mission-step contract nodes (``mission_step_contract:<owner>/<id>``):
       activated iff the recovered owner mission type is in
       ``activated_mission_types``. Steps that cannot be owner-attributed
       fall through to the kind filter (defensive default-allow).
    2. All other kinds: the singular URN prefix is mapped to its plural form
       and checked against ``activated_kinds``. An unknown kind (e.g. an
       extension kind not yet in :data:`_SINGULAR_TO_PLURAL`) is allowed
       through so the filter never silently swallows new artifact kinds —
       the DRG schema validator is the gatekeeper for kind legality.
    3. Per-artifact-ID gate (FR-038, WP08; canonical-URN corrected, WP01):
       after the kind-level check, the pre-resolved canonical-URN set for
       this kind is consulted. ``None`` (key absent from config) means all
       IDs are allowed. An empty frozenset (explicit empty list) blocks all
       IDs. A non-empty frozenset gates by full URN membership (not the bare
       artifact id). An empty *artifact_id* (malformed URN) bypasses this
       gate (default-allow).
    """
    # Step 1: mission-step contract kind check.
    if node_kind in _MISSION_STEP_SINGULAR_KINDS:
        # Reconstruct the URN to reuse _owning_mission_type which expects a full URN.
        pseudo_urn = f"{node_kind}:{artifact_id}"
        owner = _owning_mission_type(pseudo_urn)
        if owner is not None:
            return owner in pack_context.activated_mission_types
        # Fall through: ownerless step relies on kind filter.

    # Step 2: kind-level gate.
    plural = _SINGULAR_TO_PLURAL.get(node_kind)
    if plural is None:
        return True
    if plural not in pack_context.activated_kinds:
        return False

    # Step 3: per-artifact-ID gate (FR-038, WP08), full-URN comparison (WP01).
    resolved_urns = resolved_urns_by_kind.get(node_kind)
    # artifact_id="" (malformed URN) → bypass (default-allow)
    if resolved_urns is not None and artifact_id:
        node_urn = f"{node_kind}:{artifact_id}"
        if node_urn not in resolved_urns:
            return False

    return True


def filter_graph_by_activation(
    graph: DRGGraph,
    pack_context: PackContext,
) -> DRGGraph:
    """Return a copy of *graph* limited to artifacts activated in *pack_context*.

    Applies the FR-018 activation filter:

    * Mission-step contract nodes are kept only when their owning mission
      type is in :attr:`PackContext.activated_mission_types`.
    * All other artifact kinds are kept only when their plural kind is in
      :attr:`PackContext.activated_kinds`.
    * Per-kind activated-ID sets (e.g. :attr:`PackContext.activated_directives`)
      hold config **stems**; WP01 resolves them to canonical URNs once per
      call (:func:`_resolve_activated_urns_by_kind`) via
      :func:`charter.activation.kind_vocabulary.resolve_artifact_urn` and compares on
      the node's full URN -- see ``contracts/activation-gate-contract.md``.
    * Edges are kept only when both endpoints survive node filtering. This
      preserves the graph invariant that an edge always points to a node in
      the same graph; downstream traversal code does not need to special-
      case dangling edges.

    The function never mutates *graph*; it builds a fresh :class:`DRGGraph`.

    See module docstring for the FR-006 / FR-018 binding and the WP11 T069
    invariant: this filter applies only to charter-mediated resolution.
    Direct doctrine-API callers (``DoctrineService.<repo>.get(...)``,
    ``MissionTemplateRepository.get(...)``) are exempt.
    """
    resolved_urns_by_kind = _resolve_activated_urns_by_kind(pack_context)
    surviving_nodes = [n for n in graph.nodes if _node_is_activated(*_split_urn(n.urn), pack_context, resolved_urns_by_kind)]
    surviving_urns = {n.urn for n in surviving_nodes}
    surviving_edges = [e for e in graph.edges if e.source in surviving_urns and e.target in surviving_urns]
    # ``model_construct`` skips the URN-prefix validators on each node/edge.
    # The input *graph* was already validated upstream, and we are returning
    # a strict subset of its nodes and edges, so the output is invariant-
    # preserving by construction. Skipping revalidation also keeps the
    # filter agnostic to extension kinds (e.g. mission-step URNs whose
    # singular form may not yet be enumerated in :class:`NodeKind`).
    return DRGGraph.model_construct(
        schema_version=graph.schema_version,
        generated_at=graph.generated_at,
        generated_by=graph.generated_by,
        nodes=surviving_nodes,
        edges=surviving_edges,
    )
