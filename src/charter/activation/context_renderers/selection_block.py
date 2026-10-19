"""Charter-level global selection rendering (WP05, #2532; originally WP04/FR-005).

Relocated verbatim from ``charter.activation.context`` (T025, single-owner extraction so
that shared, WP-contended file does not grow). This is the largest render-pure
seam: the 8 ``_render_selected_<kind>`` helpers (paradigm / directive / tactic /
styleguide / toolguide / procedure / agent_profile / mission_step_contract),
their shared implementation :func:`_render_selected_artifacts`, the composed
:func:`_render_selection_block`, provenance-suffix rendering
(:func:`_provenance_suffix`), the Action-Doctrine artifact-line helper
(:func:`_extend_named_artifact_lines`, consumed cross-module by
``bootstrap_text.py``), and the org-source-map builders
(:func:`_collect_org_source_map`, :func:`_build_action_org_source_map`).

Cycle note: :func:`_render_selection_block` needs
``charter.activation.context._read_org_required_selections`` — that helper is part of
the org-pack-discovery cluster, which stays in ``charter.activation.context`` until a
later WP relocates it (data-model.md's ``ch/org_pack_discovery.py`` row).
Since ``charter.activation.context`` re-exports symbols FROM this module, importing it
back at module level would create a load-time cycle; the call site below
does a function-local import instead (mirrors the existing
``charter.activation.pack_context`` / ``charter.activation.sync`` lazy-import precedent already
used throughout ``charter.activation.context``).

Only the names with a genuine external caller (``charter.activation.context``'s
re-export shim, ``bootstrap_text.py``'s cross-module import, or a direct test
import) are declared in ``__all__``; the three kind-specific renderers with
no such caller (``_render_selected_paradigms`` / ``_render_selected_directives``
/ ``_render_selected_tactics``) and the shared ``_render_selected_artifacts``
stay module-private, matching the ``reference_pointers.py`` precedent.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from charter.activation._catalog_miss import (
    emit_catalog_miss_warning,
    format_catalog_miss_stanza,
)
from charter.activation.context_renderers.artifact_bodies import (
    _format_inline_agent_profile_body,
    _format_inline_directive_body,
    _format_inline_paradigm_body,
    _format_inline_procedure_body,
    _format_inline_step_contract_body,
    _format_inline_styleguide_body,
    _format_inline_tactic_body,
    _format_inline_toolguide_body,
)
from charter.activation.identity_index import IdentityIndex
from charter.activation.context_renderers.catalog_diagnosis import _diagnose_catalog_miss
from charter.activation.context_renderers.fetch_stanza import (
    fetch_stanza_lines as _shared_fetch_stanza_lines,
    render_fetch_stanza as _render_fetch_stanza,
)
from charter.activation.context_renderers.token_budget import (
    _PROFILE_INLINE_BODY_LIMIT_CHARS,
    _budget_estimate,
)
from charter.offering.artifact_kinds import ArtifactKind

if TYPE_CHECKING:
    from pathlib import Path

    from charter.activation.progressive_disclosure import ArtifactRepository
    from charter.activation.schemas import GovernanceCharterConfig

# The 5 ``_SELECTED_*_HEADER`` constants, ``_collect_org_source_map``,
# ``_provenance_suffix``, and the 4 ``_render_selected_<kind>`` helpers listed
# below were de-exported after the context.py re-export shim retirement
# (doctrine-built-in-seam-consolidation WP06): no external ``src/`` importer
# remains for them. They stay module-internal, used by the functions in this
# module.
__all__ = [
    "_build_action_org_source_map",
    "_extend_named_artifact_lines",
    "_render_selection_block",
]


_SELECTED_PARADIGMS_HEADER = "Selected paradigms:"
_SELECTED_DIRECTIVES_HEADER = "Selected directives:"
_SELECTED_TACTICS_HEADER = "Selected tactics:"
_SELECTED_STYLEGUIDES_HEADER = "Selected styleguides:"
_SELECTED_TOOLGUIDES_HEADER = "Selected toolguides:"
_SELECTED_PROCEDURES_HEADER = "Selected procedures:"
_SELECTED_AGENT_PROFILES_HEADER = "Selected agent profiles:"
_SELECTED_MISSION_STEP_CONTRACTS_HEADER = "Selected mission step contracts:"

#: When-doing clause for a linked (suggests-reached) Action Doctrine entry —
#: mirrors the profile-citation renderers' own clause (D2c,
#: ``_render_profile_directives`` / ``_render_profile_tactics``) so the two
#: surfaces read consistently.
_ACTION_DOCTRINE_LINK_WHEN = "are about to apply a code change"


def _provenance_suffix(
    artifact_id: str,
    org_source_map: dict[str, str] | None,
) -> str:
    """Return ``" (source: org, pack: <name>)"`` for org-sourced artifacts.

    Per the WP04 contract (selection-schema.md §"Resolver-level"):

    * built-in / project artifacts → no suffix (matches today's convention).
    * org-distributed artifacts → ``(source: org, pack: <name>)`` so the
      operator can audit which pack contributed the rule.

    ``org_source_map`` maps ``artifact_id → pack_name``. When the pack name
    is not known (legacy callers pass an empty string), the suffix
    collapses to ``(source: org)`` so the provenance signal survives even
    without per-pack attribution.
    """
    if not org_source_map or artifact_id not in org_source_map:
        return ""
    pack = (org_source_map.get(artifact_id) or "").strip()
    if pack:
        return f" (source: org, pack: {pack})"
    return " (source: org)"


def _selection_id(identity: IdentityIndex | None, kind: ArtifactKind | None, token: str) -> str:
    """The repository key for a selected *token* (declared id or file stem).

    Repositories are keyed by declared id, so the identity index turns either
    spelling into that key with selection precedence (FR-017, #6406); a token no
    index knows falls back to :meth:`IdentityIndex.unindexed_key`.
    """
    if identity is None:
        return IdentityIndex.unindexed_key(kind, token)
    return identity.lookup_key(kind, token, selection=True)


def _render_selected_artifacts(
    selected_ids: list[str],
    repository: ArtifactRepository[Any] | None,
    *,
    header: str,
    selector_kind: str,
    when_clause: str,
    body_formatter: Callable[[object], list[str]],
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Shared implementation for the 8 ``_render_selected_<kind>`` helpers.

    Each helper is a thin wrapper that picks the right repository
    (``service.styleguides`` / ``service.toolguides`` / ...) and inline
    body formatter, then defers to this routine for the budget /
    fetch-stanza / provenance logic.

    Returns an empty list when ``selected_ids`` is empty so the caller
    can filter out the header — preserving the "no leading header,
    no trailing section" guarantee from the WP04 reviewer checklist.
    """
    if not selected_ids:
        return []

    lines: list[str] = [header]
    seen: set[str] = set()
    kind = ArtifactKind(selector_kind)
    for artifact_id in selected_ids:
        # Deduplicate while preserving authoring order (R-4 mitigation).
        if artifact_id in seen:
            continue
        seen.add(artifact_id)

        suffix = _provenance_suffix(artifact_id, org_source_map)
        header_line = f"  - {artifact_id}{suffix}"
        lines.append(header_line)

        artifact = None
        if repository is not None:
            try:
                lookup_id = _selection_id(identity, kind, artifact_id)
                artifact = repository.get(lookup_id)
            except Exception:  # noqa: BLE001 — best-effort catalog lookup
                artifact = None

        if artifact is None:
            # RISK-3 (Mission B post-merge): replace the generic
            # placeholder with a structured stanza that classifies the
            # miss (typo vs. missing vs. schema-validation drop) and
            # routes a warning through both ``warnings.warn`` and the
            # module logger so the failure is never silent.
            # FR-013: _diagnose_catalog_miss checks scope_filtered_ids
            # first so a scope-filtered artifact surfaces SCOPE_FILTERED
            # rather than MISSING_ARTIFACT.
            diagnosis = _diagnose_catalog_miss(artifact_id, repository, repo_root=repo_root)
            lines.extend(
                format_catalog_miss_stanza(
                    selector_kind=selector_kind,
                    artifact_id=artifact_id,
                    diagnosis=diagnosis,
                    indent="    ",
                )
            )
            emit_catalog_miss_warning(
                selector_kind=selector_kind,
                artifact_id=artifact_id,
                diagnosis=diagnosis,
            )
            lines.extend(
                _shared_fetch_stanza_lines(
                    f"{selector_kind}:{artifact_id}",
                    when_clause,
                    indent="    ",
                )
            )
            continue

        body_lines = body_formatter(artifact)
        if body_lines and _budget_estimate(body_lines) <= _PROFILE_INLINE_BODY_LIMIT_CHARS:
            lines.extend(body_lines)
        else:
            lines.extend(
                _shared_fetch_stanza_lines(
                    f"{selector_kind}:{artifact_id}",
                    when_clause,
                    indent="    ",
                )
            )

    return lines


def _render_selected_paradigms(
    selected_ids: list[str],
    service: object,
    *,
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Render globally-selected paradigms into prompt lines."""
    repo = getattr(service, "paradigms", None)
    return _render_selected_artifacts(
        selected_ids,
        repo,
        header=_SELECTED_PARADIGMS_HEADER,
        selector_kind="paradigm",
        when_clause="are about to choose a reasoning frame",
        body_formatter=_format_inline_paradigm_body,
        org_source_map=org_source_map,
        repo_root=repo_root,
        identity=identity,
    )


def _render_selected_directives(
    selected_ids: list[str],
    service: object,
    *,
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Render globally-selected directives into prompt lines."""
    repo = getattr(service, "directives", None)
    return _render_selected_artifacts(
        selected_ids,
        repo,
        header=_SELECTED_DIRECTIVES_HEADER,
        selector_kind="directive",
        when_clause=_ACTION_DOCTRINE_LINK_WHEN,
        body_formatter=_format_inline_directive_body,
        org_source_map=org_source_map,
        repo_root=repo_root,
        identity=identity,
    )


def _render_selected_tactics(
    selected_ids: list[str],
    service: object,
    *,
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Render globally-selected tactics into prompt lines."""
    repo = getattr(service, "tactics", None)
    return _render_selected_artifacts(
        selected_ids,
        repo,
        header=_SELECTED_TACTICS_HEADER,
        selector_kind="tactic",
        when_clause=_ACTION_DOCTRINE_LINK_WHEN,
        body_formatter=_format_inline_tactic_body,
        org_source_map=org_source_map,
        repo_root=repo_root,
        identity=identity,
    )


def _render_selected_styleguides(
    selected_ids: list[str],
    service: object,
    *,
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Render globally-selected styleguides into prompt lines (T017).

    Returns inline body lines when budget allows; fetch + when-doing
    stanzas when overflow triggers.  Provenance is appended as
    ``(source: org, pack: <name>)`` after each org-sourced artifact ID.
    """
    repo = getattr(service, "styleguides", None)
    return _render_selected_artifacts(
        selected_ids,
        repo,
        header=_SELECTED_STYLEGUIDES_HEADER,
        selector_kind="styleguide",
        when_clause="are about to write a code comment or styled output",
        body_formatter=_format_inline_styleguide_body,
        org_source_map=org_source_map,
        repo_root=repo_root,
        identity=identity,
    )


def _render_selected_toolguides(
    selected_ids: list[str],
    service: object,
    *,
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Render globally-selected toolguides into prompt lines (T018)."""
    repo = getattr(service, "toolguides", None)
    return _render_selected_artifacts(
        selected_ids,
        repo,
        header=_SELECTED_TOOLGUIDES_HEADER,
        selector_kind="toolguide",
        when_clause="are about to invoke a project tool",
        body_formatter=_format_inline_toolguide_body,
        org_source_map=org_source_map,
        repo_root=repo_root,
        identity=identity,
    )


def _render_selected_procedures(
    selected_ids: list[str],
    service: object,
    *,
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Render globally-selected procedures into prompt lines (T018)."""
    repo = getattr(service, "procedures", None)
    return _render_selected_artifacts(
        selected_ids,
        repo,
        header=_SELECTED_PROCEDURES_HEADER,
        selector_kind="procedure",
        when_clause="are about to follow a multi-step workflow",
        body_formatter=_format_inline_procedure_body,
        org_source_map=org_source_map,
        repo_root=repo_root,
        identity=identity,
    )


def _render_selected_agent_profiles(
    selected_ids: list[str],
    service: object,
    *,
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Render globally-selected agent profiles into prompt lines (T018)."""
    repo = getattr(service, "agent_profiles", None)
    return _render_selected_artifacts(
        selected_ids,
        repo,
        header=_SELECTED_AGENT_PROFILES_HEADER,
        selector_kind="agent_profile",
        when_clause=_ACTION_DOCTRINE_LINK_WHEN,
        body_formatter=_format_inline_agent_profile_body,
        org_source_map=org_source_map,
        repo_root=repo_root,
        identity=identity,
    )


def _render_selected_mission_step_contracts(
    selected_ids: list[str],
    service: object,
    *,
    org_source_map: dict[str, str] | None = None,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> list[str]:
    """Render globally-selected mission step contracts (T018)."""
    repo = getattr(service, "mission_step_contracts", None)
    return _render_selected_artifacts(
        selected_ids,
        repo,
        header=_SELECTED_MISSION_STEP_CONTRACTS_HEADER,
        selector_kind="mission_step_contract",
        when_clause="are about to step a mission action",
        body_formatter=_format_inline_step_contract_body,
        org_source_map=org_source_map,
        repo_root=repo_root,
        identity=identity,
    )


def _collect_org_source_map(
    repository: ArtifactRepository[Any] | None,
    artifact_ids: list[str],
    *,
    kind: ArtifactKind | None = None,
    identity: IdentityIndex | None = None,
) -> dict[str, str]:
    """Map ``artifact_id → "org"`` (placeholder pack name) for org-sourced IDs.

    Computed once per ``build_charter_context`` call so each renderer
    can call :func:`_provenance_suffix` without a repository walk
    (R-3 mitigation: ``Provenance source map computed N times per build``).

    The repository tracks provenance as one of ``"built-in"`` / ``"org"`` /
    ``"project"`` (see :meth:`charter.offering.base.BaseArtifactRepository.get_provenance`);
    today there is no per-pack attribution at the repository layer.  When
    that lands, the value here will gain pack-name semantics — for now
    we use an empty-string sentinel so the suffix collapses to
    ``(source: org)`` per :func:`_provenance_suffix`.

    Repositories are keyed by declared id, so with *kind* and *identity* a
    selected file stem is looked up by its declared id (FR-017, #6406); the
    returned map stays keyed by the spelling the charter selected.
    """
    if repository is None or not artifact_ids:
        return {}

    org_map: dict[str, str] = {}
    for artifact_id in artifact_ids:
        try:
            source = repository.get_provenance(_selection_id(identity, kind, artifact_id))
        except (AttributeError, KeyError):
            source = None
        if source == "org":
            org_map[artifact_id] = ""
    return org_map


#: (service attribute, ``selected_<plural>`` config field, kind) per selection section, in render order.
_SELECTION_SECTIONS: tuple[tuple[str, str, ArtifactKind], ...] = (
    ("paradigms", "selected_paradigms", ArtifactKind.PARADIGM),
    ("directives", "selected_directives", ArtifactKind.DIRECTIVE),
    ("tactics", "selected_tactics", ArtifactKind.TACTIC),
    ("styleguides", "selected_styleguides", ArtifactKind.STYLEGUIDE),
    ("toolguides", "selected_toolguides", ArtifactKind.TOOLGUIDE),
    ("procedures", "selected_procedures", ArtifactKind.PROCEDURE),
    ("agent_profiles", "selected_agent_profiles", ArtifactKind.AGENT_PROFILE),
    ("mission_step_contracts", "selected_mission_step_contracts", ArtifactKind.MISSION_STEP_CONTRACT),
)


def _merge_org_required(
    catalog_map: dict[str, str],
    selected_ids: list[str],
    required_ids: list[str],
    kind: ArtifactKind,
    identity: IdentityIndex | None,
) -> dict[str, str]:
    """Add org-pack-required ids to *catalog_map*, comparing declared ids.

    A selected token and a required token name one artifact when they resolve
    to the same declared id, whichever of stem or id each one spells (#6406).
    The catalog-derived map wins when both are present.
    """
    merged = dict(catalog_map)
    required = {_selection_id(identity, kind, rid) for rid in required_ids}
    for sid in selected_ids:
        if sid not in merged and _selection_id(identity, kind, sid) in required:
            # Sentinel value matches ``_collect_org_source_map``: empty
            # string collapses to a bare ``(source: org)`` suffix per
            # :func:`_provenance_suffix`.
            merged[sid] = ""
    return merged


def _render_selection_block(
    charter_config: GovernanceCharterConfig | None,
    service: object,
    *,
    repo_root: Path | None = None,
    identity: IdentityIndex | None = None,
) -> str:
    """Render the combined 8-kind selection section block.

    Concatenates the 8 ``_render_selected_<kind>`` outputs with blank
    lines between non-empty blocks so the prompt body remains readable.
    Returns ``""`` when no selections exist on the charter — the caller
    can then skip the leading blank line without emitting a stray
    section header.

    Mission B WP06: the provenance map now ALSO carries org-pack-required
    ids (read straight from each pack's ``org-charter.yaml``) so that
    artifacts declared by an org pack but absent from the catalog (e.g.
    a styleguide whose YAML failed schema validation) still surface their
    org provenance in the prompt.  The catalog-derived map wins when
    both are present — that path retains the per-artifact provenance the
    ActiveCharterService computed.

    *identity* (FR-017, #6406) resolves a selected file stem or declared id to
    the repository key; when omitted and *repo_root* is known, an index is built
    for this call.
    """
    if charter_config is None or service is None:
        return ""

    if identity is None and repo_root is not None:
        identity = IdentityIndex.build(repo_root)

    # WP04 T020: compute the provenance source map ONCE per build, then
    # pass it down to each renderer — avoids the N×repo-walk regression
    # called out in the WP04 risk table.
    #
    # Cycle note (WP05/#2532): ``_read_org_required_selections`` still lives
    # in ``charter.activation.context`` (org-pack-discovery cluster, not yet relocated).
    # A function-local import breaks the load-time cycle that a top-level
    # import would create (``charter.activation.context`` imports this module for its
    # re-export shim) — mirrors the existing lazy-import precedent already
    # used throughout ``charter.activation.context`` (e.g. ``charter.activation.pack_context``).
    from charter.activation.context import _read_org_required_selections  # noqa: PLC0415

    org_required: dict[str, list[str]] = _read_org_required_selections(repo_root) if repo_root is not None else {}

    org_maps: dict[str, dict[str, str]] = {}
    for attr, field_name, kind in _SELECTION_SECTIONS:
        selected: list[str] = getattr(charter_config, field_name)
        catalog_map = _collect_org_source_map(getattr(service, attr, None), selected, kind=kind, identity=identity)
        org_maps[attr] = _merge_org_required(catalog_map, selected, org_required.get(attr) or [], kind, identity)

    blocks: list[str] = []
    sections = (
        _render_selected_paradigms(charter_config.selected_paradigms, service, org_source_map=org_maps["paradigms"], repo_root=repo_root, identity=identity),
        _render_selected_directives(charter_config.selected_directives, service, org_source_map=org_maps["directives"], repo_root=repo_root, identity=identity),
        _render_selected_tactics(charter_config.selected_tactics, service, org_source_map=org_maps["tactics"], repo_root=repo_root, identity=identity),
        _render_selected_styleguides(charter_config.selected_styleguides, service, org_source_map=org_maps["styleguides"], repo_root=repo_root, identity=identity),
        _render_selected_toolguides(charter_config.selected_toolguides, service, org_source_map=org_maps["toolguides"], repo_root=repo_root, identity=identity),
        _render_selected_procedures(charter_config.selected_procedures, service, org_source_map=org_maps["procedures"], repo_root=repo_root, identity=identity),
        _render_selected_agent_profiles(
            charter_config.selected_agent_profiles,
            service,
            org_source_map=org_maps["agent_profiles"],
            repo_root=repo_root,
            identity=identity,
        ),
        _render_selected_mission_step_contracts(
            charter_config.selected_mission_step_contracts,
            service,
            org_source_map=org_maps["mission_step_contracts"],
            repo_root=repo_root,
            identity=identity,
        ),
    )
    for section_lines in sections:
        if section_lines:
            blocks.append("\n".join(section_lines))
    return "\n\n".join(blocks)


def _extend_named_artifact_lines(
    lines: list[str],
    heading: str,
    artifact_ids: list[str],
    repository: ArtifactRepository[Any] | None,
    title_attr: str,
    summary_attr: str | None,
    org_source_map: dict[str, str] | None = None,
    progressive_kind: str | None = None,
    inline_urns: frozenset[str] = frozenset(),
) -> None:
    """Append formatted artifact lines when the bucket is non-empty.

    When *org_source_map* is provided, each artifact contributed by an org
    pack receives a ``(source: org:<pack>)`` suffix (Option B — additive only
    when an org pack is present, preserving NFR-001 byte-stability when no
    org packs are configured).

    *repository* may be ``None`` when a delivered kind has no repository wired
    on this layer (e.g. assets on the WP10 base): every id then renders in the
    bare-id form, so the ids still reach the output (FR-009/B-2).

    D2c: when *progressive_kind* is set (directive/tactic/styleguide/
    toolguide), an entry outside *inline_urns* (WP15's requires-closure —
    the eager set) renders its id + title header line plus a fetch +
    when-doing stanza in place of the verbatim summary/body, matching the
    cadence WP15 already applies to the ``--json`` payload. *progressive_kind*
    ``None`` (procedure/asset) always renders the full verbatim line,
    unchanged from pre-D2c behaviour.
    """
    if not artifact_ids:
        return

    formatted: list[str] = []
    for artifact_id in artifact_ids:
        suffix = _provenance_suffix(artifact_id, org_source_map)
        artifact = repository.get(artifact_id) if repository is not None else None
        if artifact is None:
            formatted.append(f"    - {artifact_id}{suffix}")
            continue
        title = getattr(artifact, title_attr)
        is_linked = progressive_kind is not None and f"{progressive_kind}:{artifact_id}" not in inline_urns
        if is_linked:
            formatted.append(f"    - {artifact_id}: {title}{suffix}")
            formatted.extend(
                _render_fetch_stanza(
                    selector=f"{progressive_kind}:{artifact_id}",
                    when_clause=_ACTION_DOCTRINE_LINK_WHEN,
                )
            )
            continue
        summary = getattr(artifact, summary_attr) if summary_attr else None
        if isinstance(summary, str) and summary:
            formatted.append(f"    - {artifact_id}: {title} — {summary}{suffix}")
        else:
            formatted.append(f"    - {artifact_id}: {title}{suffix}")

    lines.append(f"  {heading}:")
    lines.extend(formatted)


def _build_action_org_source_map(
    repo_root: Path,
    artifact_ids: list[str],
) -> dict[str, str]:
    """Build an ``artifact_id → pack_name`` map for action-doctrine artifacts contributed by org packs.

    Uses :func:`charter.activation.drg_activation.load_org_drg` (WP06) to read the configured
    organisation-tier DRG fragments and maps each fragment node id to the
    pack name that contributed it.  The resulting map is consumed by
    :func:`_extend_named_artifact_lines` to append ``(source: org:<pack>)``
    suffixes.

    Returns ``{}`` when:
    * no org packs are configured (NFR-001 byte-stability — no diff to 23-fixture suite)
    * ``load_org_drg`` raises any exception (best-effort; action doctrine still renders)
    * no artifact IDs are provided

    Option B per T036: stanzas carry ``source:`` ONLY when an org pack
    contributes the artifact.  Shipped-only artifacts carry no suffix,
    preserving the existing plain-text rendering for all 23 governance-
    contract fixtures.

    Implementation note: we read provenance directly from the ``OrgDRGFragment``
    node list rather than calling ``merge_three_layers`` and inspecting the
    merged graph.  The merge monkey-patches a ``source`` sidecar attribute onto
    DRGEdge objects that already have a ``source`` field (the URN endpoint), which
    causes Pydantic validation failures when the returned DRGGraph is reconstructed
    with the real built-in graph (hundreds of edges).  Reading fragment nodes directly
    is simpler and sufficient for building the id → pack_name map.
    """
    if not artifact_ids:
        return {}

    try:
        from charter.activation.drg_activation import load_org_drg
    except ImportError:
        return {}

    try:
        org_fragments = load_org_drg(repo_root)
    except Exception:  # noqa: BLE001 — best-effort; never crash action doctrine rendering
        return {}

    if not org_fragments:
        # No org packs → NFR-001 preserved (byte-identical output for 23 fixtures).
        return {}

    # Build the map directly from fragment node ids.
    # Each fragment node has an ``id`` (e.g. ``"sox-controls"``) and the fragment
    # has a ``pack_name`` (e.g. ``"example-org"``).
    artifact_id_set = set(artifact_ids)
    source_map: dict[str, str] = {}
    for fragment in org_fragments:
        pack_name = fragment.pack_name
        for node in fragment.nodes:
            if node.id in artifact_id_set and node.id not in source_map:
                source_map[node.id] = pack_name

    return source_map
