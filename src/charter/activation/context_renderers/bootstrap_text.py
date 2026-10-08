"""Bootstrap-mode charter context text assembly (WP05, #2532).

Relocated verbatim from ``charter.activation.context``: the full bootstrap render
(:func:`_render_bootstrap_text`), the Action Doctrine emission helper
(:func:`_render_action_doctrine_lines`) plus its render-order table
(:class:`_ActionRenderRow` / ``_ACTION_RENDER_ROWS``), the action-guidelines
appender (:func:`_append_guidelines_lines` — co-located here since
``_render_bootstrap_text`` is its only caller), and the section headers/
constants exclusively consumed by this render.

Cycle note: three collaborators used here (``_render_profile_sections``,
``_select_reference_pointers``'s doctrine-root resolver
``charter.activation.catalog.resolve_offering_root``, and the ``_ActionDoctrineBundle``
type) stay in / are typed against ``charter.activation.context`` (profile-driven-
rendering / catalog / action-doctrine-bundle clusters, relocated by a later
WP). ``_render_profile_sections`` is imported function-locally to break the
load-time cycle a top-level import would create (``charter.activation.context`` imports
this module for its re-export shim); ``_ActionDoctrineBundle`` is imported
under ``TYPE_CHECKING`` only (a type-only reference never participates in the
runtime import graph), mirroring the existing lazy-import precedent already
used throughout ``charter.activation.context``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from charter.activation import progressive_disclosure as _pd
from charter.activation.context_renderers import render_authority_paths, render_critical_section_bodies
from charter.activation.context_renderers.activation_block import _render_activation_block
from charter.activation.context_renderers.artifact_bodies import _format_inline_glossary_body
from charter.activation.context_renderers.reference_pointers import _select_reference_pointers
from charter.activation.context_renderers.selection_block import (
    _build_action_org_source_map,
    _extend_named_artifact_lines,
    _render_selection_block,
)
from charter.activation.context_renderers.token_budget import _enforce_token_budget
from charter.activation.governance_references import render_governance_references
from charter.activation.language_advisory import CHARTER_EXTENSION_ADVISORY
from charter.activation.language_scope import infer_repo_languages, lacks_specialist_guidance
from charter.offering.spdd_reasons import append_spdd_reasons_guidance, is_spdd_reasons_active

if TYPE_CHECKING:
    from pathlib import Path

    from charter.activation.context import _ActionDoctrineBundle
    from charter.activation.schemas import DoctrineSelectionConfig
    from charter.offering.agent_profiles import AgentProfile

__all__ = [
    "_render_bootstrap_text",
]


BOOTSTRAP_HEADER = "Charter Context (Bootstrap):"
FIRST_LOAD_GUIDANCE = "  - This is the first load for this action. Use the summary and follow references as needed."
POLICY_SUMMARY_HEADER = "Policy Summary:"
NO_POLICY_SUMMARY_MESSAGE = "  - No explicit policy summary section found in charter.md."
REFERENCE_DOCS_HEADER = "Reference Docs:"
MISSING_REFERENCES_MESSAGE = "  - No references manifest found."
# WP01 (deliver-loaded-doctrine): the action-doctrine glossary block heading,
# matching the ``  <Heading>:`` shape ``_extend_named_artifact_lines`` uses.
_GLOSSARY_HEADING = "  Glossaries:"


def _append_guidelines_lines(lines: list[str], mission: str, action: str) -> None:
    """Append action guidelines to lines, silently skipping on any error."""
    from charter.offering.missions import MissionTemplateRepository

    try:
        repo = MissionTemplateRepository.default()
        result = repo.get_action_guidelines(mission, action)
        if result is not None:
            content = result.content.strip()
            if content:
                lines.append("  Guidelines:")
                for guideline_line in content.splitlines():
                    lines.append(f"    {guideline_line}")
    except Exception:  # noqa: BLE001, S110
        pass


class _ActionRenderRow(NamedTuple):
    """One Action Doctrine render row."""

    heading: str
    ids_attr: str  # attribute on _ActionDoctrineBundle
    service_attr: str  # repository/dict on the service (absent for assets here)
    title_attr: str
    summary_attr: str | None
    # D2c: the progressive-disclosure kind prefix (matches
    # ``progressive_disclosure``'s URN kind, e.g. "directive"/"tactic") for the
    # four kinds WP15's JSON payload already disclosure-cadences. ``None`` for
    # procedure/asset, which stay always-inline here (unchanged, pre-D2c
    # behaviour) — they are not part of the WP15 disclosure-cadenced kind set.
    progressive_kind: str | None = None


#: The Action Doctrine render order. Iterating it (not hand-written per-kind
#: calls) makes "the render emits every kind the bundle carries" one statement
#: (FR-009/B-2): a kind flipped into a slot renders as soon as it has a row.
#: WP11 (T059) retired the ``extended`` depth gate — every row renders on the
#: bootstrap load; the compact rail carries the same kinds as ids (T061).
_ACTION_RENDER_ROWS: tuple[_ActionRenderRow, ...] = (
    _ActionRenderRow("Directives", "directive_ids", "directives", "title", "intent", "directive"),
    _ActionRenderRow("Tactics", "tactic_ids", "tactics", "name", "purpose", "tactic"),
    _ActionRenderRow("Styleguides", "styleguide_ids", "styleguides", "title", None, "styleguide"),
    _ActionRenderRow("Toolguides", "toolguide_ids", "toolguides", "title", None, "toolguide"),
    _ActionRenderRow("Procedures", "procedure_ids", "procedures", "name", "purpose"),
    _ActionRenderRow("Assets", "asset_ids", "assets", "title", None),
)


def _render_action_doctrine_lines(
    lines: list[str],
    doctrine_bundle: _ActionDoctrineBundle,
    *,
    repo_root: Path | None,
) -> None:
    """Emit every kind the bundle resolves under the Action Doctrine heading.

    Assets have no repository on this lane, so ``getattr(service, "assets",
    None)`` is ``None`` and :func:`_extend_named_artifact_lines` emits bare ids.

    D2c: directive/tactic/styleguide/toolguide entries follow the same
    requires-eager / suggests-linked cadence WP15 already applies to the
    ``--json`` payload (:func:`progressive_disclosure.requires_closure`) —
    an entry outside the roots' requires-closure renders as a fetch +
    when-doing stanza instead of its full verbatim body. Before this, every
    resolved id always rendered its full body regardless of cadence, so a
    grain reached mostly through ``suggests`` (the norm — see WP15's own
    ADR) produced an Action Doctrine block large enough to blow the NFR-001
    token budget on its own; the (smaller, but budget-substitutable)
    profile-citation and charter-section blocks paid for it by being swapped
    away first, silently dropping profile-cited directives like DIRECTIVE_032
    even though swapping them never actually closed the budget gap.
    """
    service = doctrine_bundle.service
    all_action_ids: list[str] = [artifact_id for row in _ACTION_RENDER_ROWS for artifact_id in getattr(doctrine_bundle, row.ids_attr)]
    org_source_map = _build_action_org_source_map(repo_root, all_action_ids) if repo_root is not None and all_action_ids else {}
    inline_urns: frozenset[str] = (
        frozenset(_pd.requires_closure(doctrine_bundle.merged, doctrine_bundle.roots)) if doctrine_bundle.merged is not None else frozenset()
    )
    for row in _ACTION_RENDER_ROWS:
        _extend_named_artifact_lines(
            lines,
            row.heading,
            getattr(doctrine_bundle, row.ids_attr),
            getattr(service, row.service_attr, None),
            row.title_attr,
            row.summary_attr,
            org_source_map=org_source_map,
            progressive_kind=row.progressive_kind,
            inline_urns=inline_urns,
        )

    # WP01 (deliver-loaded-doctrine, FR-001/FR-002): glossary packs cannot ride
    # the generic ``_ActionRenderRow`` path -- that renderer emits a single
    # ``title``/``summary`` line and cannot express a term-surface list. The
    # dedicated glossary block emits surfaces-only + a fetch pointer (NFR-001).
    _render_glossary_lines(lines, doctrine_bundle)


def _render_glossary_lines(
    lines: list[str],
    doctrine_bundle: _ActionDoctrineBundle,
) -> None:
    """Emit the glossary block: term surfaces (names) + a ``--include`` pointer.

    Resolves each delivered ``glossary_pack_ids`` entry from
    ``service.glossary_packs``; a pack the repository cannot resolve degrades to
    its bare id (mirroring the bare-id fallback the named-artifact rows use).
    Emits nothing when the bundle carries no glossary ids, so a bundle without
    glossary delivery is byte-identical to the pre-WP01 render.
    """
    pack_ids = getattr(doctrine_bundle, "glossary_pack_ids", ()) or ()
    if not pack_ids:
        return
    repo = getattr(doctrine_bundle.service, "glossary_packs", None)
    rendered: list[str] = []
    for pack_id in pack_ids:
        pack = repo.get(pack_id) if repo is not None else None
        if pack is None:
            rendered.append(f"    - {pack_id}")
            continue
        rendered.extend(_format_inline_glossary_body(pack))
    if rendered:
        lines.append(_GLOSSARY_HEADING)
        lines.extend(rendered)


def _append_policy_summary_lines(lines: list[str], summary: list[str]) -> None:
    """Append up to 8 policy-summary bullet lines, or the "no summary" fallback."""
    if not summary:
        lines.append(NO_POLICY_SUMMARY_MESSAGE)
        return
    for item in summary[:8]:
        lines.append(f"  - {item}")


def _append_block(lines: list[str], block: str) -> None:
    """Append a blank separator followed by ``block``, when ``block`` is non-empty."""
    if block:
        lines.append("")
        lines.append(block)


def _resolve_authority_block(
    repo_root: Path | None,
    doctrine_selection: DoctrineSelectionConfig | None,
) -> str:
    """Render the authority-paths block, or "" when a prerequisite is absent.

    ``block`` keeps its ``str``-inferred type from the ``""`` literal across
    the reassignment below (mirrors the pre-refactor inline pattern) so the
    conditionally-``skip``-followed ``charter.activation.context_renderers`` import
    (see ``[[tool.mypy.overrides]]`` for ``charter.*`` in pyproject.toml)
    cannot make this function's return type look like ``Any`` to mypy.
    """
    block = ""
    if repo_root is not None and doctrine_selection is not None:
        block = render_authority_paths(repo_root, doctrine_selection)
    return block


def _resolve_reference_block(
    repo_root: Path | None,
    doctrine_selection: DoctrineSelectionConfig | None,
) -> str:
    """Render the governance-references block, or "" when a prerequisite is absent.

    See :func:`_resolve_authority_block` for why ``block`` starts as a
    ``str`` literal rather than being returned directly from the call.
    """
    block = ""
    if repo_root is not None and doctrine_selection is not None:
        block = render_governance_references(repo_root, doctrine_selection.governance_references)
    return block


def _append_reference_docs_lines(
    lines: list[str],
    selected_references: list[tuple[dict[str, str], Path]],
) -> None:
    """Append one line per selected reference pointer, or the "missing" fallback."""
    if not selected_references:
        lines.append(MISSING_REFERENCES_MESSAGE)
        return
    for reference, resolved_path in selected_references:
        ref_id = reference.get("id", "unknown")
        title = reference.get("title", "")
        lines.append(f"  - {ref_id}: {title} ({resolved_path})")


def _append_language_advisory(lines: list[str], repo_root: Path | None) -> None:
    """Append the single charter-extension advisory for a project without specialist guidance.

    The language authority decides (:func:`lacks_specialist_guidance`, operator
    decision D2); no repo root means no language signal and therefore no advisory.
    """
    if repo_root is None or not lacks_specialist_guidance(infer_repo_languages(repo_root), repo_root):
        return
    lines.append("")
    lines.append(f"  - Advisory: {CHARTER_EXTENSION_ADVISORY}")


def _render_bootstrap_text(
    *,
    charter_path: Path,
    action: str,
    summary: list[str],
    doctrine_bundle: _ActionDoctrineBundle,
    references: list[dict[str, str]],
    profile: AgentProfile | None = None,
    repo_root: Path | None = None,
    doctrine_selection: DoctrineSelectionConfig | None = None,
    charter_content: str = "",
) -> str:
    """Render the full bootstrap charter context text."""

    service = doctrine_bundle.service
    lines: list[str] = [
        BOOTSTRAP_HEADER,
        f"  - Source: {charter_path}",
        FIRST_LOAD_GUIDANCE,
        "",
        POLICY_SUMMARY_HEADER,
    ]
    _append_policy_summary_lines(lines, summary)

    # WP04 (FR-003) — authority paths block, between Policy Summary and the
    # action-critical bodies (resolved-context anchor order, data-model.md §3).
    _append_block(lines, _resolve_authority_block(repo_root, doctrine_selection))
    _append_block(lines, _resolve_reference_block(repo_root, doctrine_selection))

    # WP04 (FR-001) — action-critical charter section bodies; an absent heading
    # emits a fetch stanza so the agent still has a recovery path.
    section_block = render_critical_section_bodies(charter_content, action)
    _append_block(lines, section_block)

    # Cycle note: ``_render_profile_sections`` stays in ``charter.activation.context``
    # (profile-driven-rendering cluster, see module docstring); function-local
    # import avoids a load cycle.
    from charter.activation.context import _render_profile_sections  # noqa: PLC0415

    profile_block = _render_profile_sections(profile, service)
    _append_block(lines, profile_block)

    # WP04 (FR-005) — charter-level global selection rendering: the 5-kind block
    # surfaces every ``DoctrineSelectionConfig.selected_<kind>`` (with org provenance).
    selection_block = _render_selection_block(doctrine_selection, service, repo_root=repo_root)
    _append_block(lines, selection_block)

    # WP04 T023 — activation-registry hook (FR-007); renderer body is WP05's
    # surface (``charter.activation._activation_render``), this only ships the call site.
    activation_block = _render_activation_block(
        doctrine_selection,
        repo_root,
        service,
        mission_type=doctrine_bundle.mission,
        action=action,
    )
    _append_block(lines, activation_block)

    lines.append("")
    lines.append(f"Action Doctrine ({action}):")
    _render_action_doctrine_lines(lines, doctrine_bundle, repo_root=repo_root)

    _append_guidelines_lines(lines, doctrine_bundle.mission, action)

    if is_spdd_reasons_active(charter_path.parent.parent.parent):
        append_spdd_reasons_guidance(lines, doctrine_bundle.mission, action)

    lines.append("")
    lines.append(REFERENCE_DOCS_HEADER)
    # The reference-pointer resolver walks ``<root>/<kind>/`` for on-disk doctrine
    # docs. Mission relocate-builtin-doctrine-packs moved the built-in artefacts out
    # of ``src/charter/offering/<kind>/`` into ``packs/built-in/<kind>/``; ``resolve_offering_root()``
    # still points at the now-emptied ``src/doctrine`` tree (used for templates), so it
    # resolves nothing and every pointer dies. Resolve the built-in pack root instead,
    # mirroring how the ActiveCharterService repositories self-resolve ``packs/built-in/<kind>``.
    # Lazy import: avoids a load-time cycle (see module docstring).
    from charter.offering.pack_paths import built_in_root  # noqa: PLC0415

    selected_references = _select_reference_pointers(references, action, built_in_root())
    _append_reference_docs_lines(lines, selected_references)
    # FR-010 — appended BEFORE budgeting: the budget only swaps named candidate
    # blocks (never a tail line), so the advisory always survives it.
    _append_language_advisory(lines, repo_root)
    text = "\n".join(lines)

    # WP05 (NFR-001) — token budget enforcement.  When the bootstrap
    # render fits inside the budget the text passes through unchanged;
    # otherwise the longest substitutable section bodies are swapped
    # for fetch + when-doing stanzas until the budget holds.  Authority
    # paths and core doctrine stay inline (substitutable=False).
    #
    # ``budgeted`` is pinned to ``str`` (mirroring ``_resolve_authority_block``'s
    # ``block`` idiom above) so the conditionally-``skip``-followed
    # ``charter.activation.context_renderers`` import (see the ``charter.*``
    # ``[[tool.mypy.overrides]]`` in pyproject.toml) cannot make this return look
    # like ``Any`` to mypy.
    budgeted: str = _enforce_token_budget(
        text,
        action=action,
        profile_block=profile_block,
        section_block=section_block,
        selection_block=selection_block,
    )
    return budgeted
