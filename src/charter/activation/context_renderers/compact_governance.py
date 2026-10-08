"""Compact-mode governance rendering (WP05, #2532).

Relocated verbatim from ``charter.activation.context``: the dispatch-facing compact
governance renderer (:func:`_render_compact_governance`), its companion
``charter.md`` section-block helper (:func:`_compact_section_block`), and the
resolved-bundle convenience wrapper (:func:`_render_compact_from_bundle`).

NOTE: this is the NEW render seam introduced by this WP — a different module
from the existing ``charter/compact.py`` (WP03's ``render_compact_view`` /
``_resolve_governance_summary`` home). The two are not to be conflated.

Cycle note: three collaborators used here (``_load_doctrine_selection``,
``_build_doctrine_service``, ``_render_profile_sections``) stay in
``charter.activation.context`` (org-pack-discovery / doctrine-service-builder /
profile-driven-rendering clusters, relocated by a later WP). Function-local
imports break the load-time cycle a top-level import would create
(``charter.activation.context`` imports this module for its re-export shim), mirroring
the existing lazy-import precedent already used throughout ``charter.activation.context``.

``suppress_project_resolver`` (WP03/#3064) is threaded through
``_render_compact_governance`` / ``_render_compact_from_bundle`` unchanged —
preserved exactly through this move (see each docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from charter.bundle import CHARTER_MD
from charter.activation.context_renderers import render_authority_paths, render_critical_section_bodies
from charter.activation.context_renderers.token_budget import _enforce_token_budget
from charter.activation.governance_references import render_governance_references

if TYPE_CHECKING:
    from pathlib import Path

    from charter.activation.context import _ActionDoctrineBundle
    from charter.offering.agent_profiles import AgentProfile

__all__ = [
    "_compact_section_block",
    "_render_compact_from_bundle",
    "_render_compact_governance",
]


def _compact_section_block(repo_root: Path, action: str | None) -> str:
    """Render the compact-mode action-critical section block (DISPLAY-only).

    Reads the companion ``charter.md`` for the given *action* and delegates
    to :func:`render_critical_section_bodies`. The companion file is an
    optional display surface (a project's governance authority lives in
    ``charter.yaml``), so a missing or unreadable ``charter.md`` degrades to
    the empty string rather than raising (NFR-005).
    """
    if not action:
        return ""
    charter_path = repo_root / CHARTER_MD
    if not charter_path.exists():
        return ""
    try:
        charter_content = charter_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return str(render_critical_section_bodies(charter_content, action))


def _render_compact_governance(
    repo_root: Path,
    *,
    directive_ids: list[str] | None = None,
    tactic_ids: list[str] | None = None,
    styleguide_ids: list[str] | None = None,
    toolguide_ids: list[str] | None = None,
    procedure_ids: list[str] | None = None,
    asset_ids: list[str] | None = None,
    profile: AgentProfile | None = None,
    action: str | None = None,
    suppress_project_resolver: bool = False,
) -> str:
    """Render the compact governance block (FR-034, WP11/T061).

    Compact mode preserves every directive ID, tactic ID, and section
    anchor that bootstrap mode would emit; only the long-form prose
    body is collapsed. ``directive_ids`` / ``tactic_ids`` are optional
    bootstrap-side lists that the caller has already resolved; when
    omitted the compact view falls back to the resolver's directive
    canon -- unless ``suppress_project_resolver`` is ``True`` (WP03/#3064:
    the empty-charter/generic-agent dispatch path passes this through from
    :func:`build_charter_context` so that fallback never merges the
    project catalog-fallback directive canon; see
    :func:`charter.activation.compact.render_compact_view` for the full rationale).

    WP11 (T061) widens this to the full delivered kind set (styleguide/
    toolguide/procedure/asset ids) — the render an agent receives on every load
    after the first (FR-010).

    When *profile* is provided (an :class:`AgentProfile` already resolved
    via :func:`_load_agent_profile`), the profile's
    ``directive_references`` and ``tactic_references`` are appended to
    the compact block as two additional sections (``Profile-Cited
    Directives`` / ``Profile-Cited Tactics``) so the WP06 wiring path
    can drive prompt-time governance even in compact mode.
    """
    from charter.activation.compact import render_compact_view

    view = render_compact_view(
        repo_root,
        directive_ids=directive_ids or (),
        tactic_ids=tactic_ids or (),
        styleguide_ids=styleguide_ids or (),
        toolguide_ids=toolguide_ids or (),
        procedure_ids=procedure_ids or (),
        asset_ids=asset_ids or (),
        suppress_project_resolver=suppress_project_resolver,
    )
    text: str = str(view.text)

    # WP04 — the compact render path must carry the same authority-paths
    # and action-critical-section blocks as the bootstrap path so the
    # prompt-governance contract holds in both modes (R-3 mitigation).
    augmented_blocks: list[str] = []
    # Cycle note: ``_load_doctrine_selection`` stays in ``charter.activation.context``
    # (see module docstring); function-local import avoids a load cycle.
    from charter.activation.context import _load_doctrine_selection  # noqa: PLC0415

    doctrine_selection = _load_doctrine_selection(repo_root)
    authority_block = render_authority_paths(repo_root, doctrine_selection)
    if authority_block:
        augmented_blocks.append(authority_block)
    reference_block = render_governance_references(
        repo_root,
        doctrine_selection.governance_references,
    )
    if reference_block:
        augmented_blocks.append(reference_block)

    # WP05 (IC-05) — the companion `charter.md` prose is DISPLAY-only and
    # optional: a project may have no `charter.md` on disk (e.g. governance
    # authority already lives in `charter.yaml`). ``_compact_section_block``
    # degrades gracefully to the empty string in that case (no crash, no
    # section block) rather than raising. The block is computed once and
    # reused for both the appended section and the NFR-001 budget input
    # below, instead of re-reading the companion file a second time.
    section_block_str = _compact_section_block(repo_root, action)
    if section_block_str:
        augmented_blocks.append(section_block_str)

    profile_block_str = ""
    if profile is not None:
        # Build a lightweight ActiveCharterService for the compact path. The
        # service constructor is cheap (catalog directories are mmaped
        # lazily) and the resulting sections compose with the compact
        # block without altering the existing ID/anchor surface.
        # Cycle note: ``_build_doctrine_service`` / ``_render_profile_sections``
        # stay in ``charter.activation.context`` (see module docstring); function-local
        # imports avoid a load cycle.
        from charter.activation.context import _build_doctrine_service, _render_profile_sections  # noqa: PLC0415

        service = _build_doctrine_service(repo_root)
        profile_block_str = _render_profile_sections(profile, service)
        if profile_block_str:
            augmented_blocks.append(profile_block_str)

    if not augmented_blocks:
        return text
    combined = text + "\n\n" + "\n\n".join(augmented_blocks)

    # WP05 (NFR-001) — compact view shares the budget cap with the
    # bootstrap path so prompts driven through the compact rail (e.g.
    # via the WP06 wiring) honour the same NFR-001 contract.
    return _enforce_token_budget(
        combined,
        action=action or "",
        profile_block=profile_block_str,
        section_block=section_block_str,
    )


def _render_compact_from_bundle(
    repo_root: Path,
    *,
    action: str,
    profile: AgentProfile | None,
    bundle: _ActionDoctrineBundle,
    suppress_project_resolver: bool = False,
) -> str:
    """Render the widened compact rail (T061): the steady-state render carries
    every delivered kind's ids (FR-010), collapsing only the long-form prose."""
    return _render_compact_governance(
        repo_root,
        directive_ids=list(bundle.directive_ids),
        tactic_ids=list(bundle.tactic_ids),
        styleguide_ids=list(bundle.styleguide_ids),
        toolguide_ids=list(bundle.toolguide_ids),
        procedure_ids=list(bundle.procedure_ids),
        asset_ids=list(bundle.asset_ids),
        profile=profile,
        action=action,
        suppress_project_resolver=suppress_project_resolver,
    )
