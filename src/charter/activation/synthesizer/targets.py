"""Synthesis target construction, ordering, and duplicate detection.

This module converts ``(section_label, answer_context)`` pairs produced by
``interview_mapping.resolve_sections()`` into ordered ``SynthesisTarget``
instances ready for adapter dispatch.

Key responsibilities
--------------------
- ``build_targets()``: resolves answer context to ``SynthesisTarget`` objects;
  assigns ``artifact_id`` per kind; validates source URNs against the DRG
  snapshot (EC-2 / FR-008 early gate).
- ``order_targets()``: deterministic ordering — kind priority (directive →
  tactic → styleguide), then lexicographic slug within kind (FR-014).
- ``detect_duplicates()``: raises ``DuplicateTargetError`` if any (kind, slug)
  appears more than once in a single run (EC-7).

These three functions are the only callers of DRG-snapshot URN resolution in
WP02 — the rest of the pipeline does not touch the DRG.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import DuplicateTargetError, ProjectDRGValidationError
from .request import SynthesisTarget

__all__ = [
    "build_targets",
    "detect_duplicates",
    "order_targets",
]



# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Kind-ordering for deterministic output. Lower index = higher priority.
_KIND_ORDER: dict[str, int] = {
    "directive": 0,
    "tactic": 1,
    "styleguide": 2,
}

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------


def _kebab(s: str) -> str:
    """Convert an arbitrary string to a kebab-case slug.

    - Lowercases everything.
    - Replaces non-alphanumeric runs with hyphens.
    - Strips leading/trailing hyphens.
    - Collapses consecutive hyphens.
    """
    lowered = s.lower()
    slashed = re.sub(r"[^a-z0-9]+", "-", lowered)
    stripped = slashed.strip("-")
    return re.sub(r"-{2,}", "-", stripped) or "unknown"


def _make_directive_artifact_id(index: int) -> str:
    """Generate a ``PROJECT_NNN`` artifact ID for the Nth directive (1-based)."""
    return f"PROJECT_{index:03d}"


def _make_slug_for_section(section_label: str, kind: str, answer_context: dict[str, Any]) -> str:
    """Derive a slug from the section label and kind.

    Special cases:
    - ``selected_directives``: slug is ``how-we-apply-<directive-id-kebab>``.
    - ``language_scope``: slug is ``<lang>-style-guide``.
    - ``testing_philosophy`` + tactic: ``testing-philosophy-tactic``.
    - ``testing_philosophy`` + styleguide: ``testing-style-guide``.
    - Default: ``<section-kebab>-<kind>``.
    """
    if section_label == "selected_directives":
        directive_id = answer_context.get("directive_id", "")
        return f"how-we-apply-{_kebab(directive_id)}"

    if section_label == "language_scope":
        lang = answer_context.get("language", "")
        return f"{_kebab(lang)}-style-guide"

    if section_label == "testing_philosophy":
        if kind == "tactic":
            return "testing-philosophy-tactic"
        if kind == "styleguide":
            return "testing-style-guide"

    if section_label == "mission_type":
        return "project-intent-directive"

    if section_label == "neutrality_posture":
        return "neutrality-posture-directive"

    if section_label == "risk_appetite":
        return "risk-appetite-directive"

    if section_label == "quality_gates":
        return "quality-gates-style-guide"

    if section_label == "review_policy":
        return "review-policy-tactic"

    if section_label == "documentation_policy":
        return "documentation-policy-style-guide"

    # Fallback: kebab of section + kind
    return f"{_kebab(section_label)}-{kind}"


def _make_title_for_section(section_label: str, kind: str, answer_context: dict[str, Any]) -> str:
    """Derive a human-readable title from the section label and kind."""
    if section_label == "selected_directives":
        directive_id = answer_context.get("directive_id", "")
        return f"How We Apply {directive_id}"

    if section_label == "language_scope":
        lang = answer_context.get("language", "")
        return f"{lang.capitalize()} Style Guide"

    if section_label == "mission_type":
        return "Project Intent Directive"

    kind_display = kind.capitalize()
    section_display = section_label.replace("_", " ").title()
    return f"{section_display} {kind_display}"


# ---------------------------------------------------------------------------
# URN validation
# ---------------------------------------------------------------------------


def _known_drg_urns(drg_snapshot: dict[str, Any]) -> frozenset[str]:
    """Return the set of node URNs present in *drg_snapshot*."""
    nodes = drg_snapshot.get("nodes", [])
    return frozenset(
        str(node["urn"])
        for node in nodes
        if isinstance(node, dict) and node.get("urn")
    )


def _validate_source_urns(
    source_urns: tuple[str, ...],
    drg_snapshot: dict[str, Any],
    target_label: str,
) -> None:
    """Raise ProjectDRGValidationError if any URN in source_urns is not in drg_snapshot.

    This is the EC-2 / FR-008 early-gate check: synthesis fails closed before
    any adapter call or write if the interview answers reference a URN that
    does not exist in the (built-in-only) DRG snapshot.

    Parameters
    ----------
    source_urns:
        URNs from the answer context or derived from interview selections.
    drg_snapshot:
        The frozen built-in-only DRG snapshot from ``SynthesisRequest.drg_snapshot``.
    target_label:
        Human-readable label for the target being built (for error messages).
    """
    known_urns = _known_drg_urns(drg_snapshot)
    dangling = [u for u in source_urns if u not in known_urns]
    if dangling:
        raise ProjectDRGValidationError(
            errors=tuple(
                f"Source URN '{u}' referenced by target '{target_label}' "
                f"does not exist in the built-in DRG snapshot."
                for u in dangling
            ),
            merged_graph_summary=(
                f"{len(known_urns)} known URNs; "
                f"{len(dangling)} dangling reference(s): {', '.join(dangling)}"
            ),
        )


def _present_source_urns(
    source_urns: tuple[str, ...],
    drg_snapshot: dict[str, Any],
) -> tuple[str, ...]:
    """Keep the table-declared *source_urns* the run's own DRG snapshot holds (#6442).

    A presence check, not validation: a snapshot without the directive omits the
    edge instead of raising ``ProjectDRGValidationError``, so no URN ever dangles.
    """
    known = _known_drg_urns(drg_snapshot)
    return tuple(urn for urn in source_urns if urn in known)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_targets(
    interview_snapshot: dict[str, Any],
    mappings: list[tuple[str, dict[str, Any]]],
    drg_snapshot: dict[str, Any],
) -> list[SynthesisTarget]:
    """Build ``SynthesisTarget`` objects from resolved interview sections.

    Parameters
    ----------
    interview_snapshot:
        Frozen interview answers, kept for call-site symmetry with the
        synthesis pipeline. Resolution has already occurred in
        ``interview_mapping.resolve_sections()``.
    mappings:
        Output of ``interview_mapping.resolve_sections(interview_snapshot)``.
        Each element is ``(section_label, answer_context)``.
    drg_snapshot:
        Frozen built-in-only DRG snapshot for source-URN validation (EC-2).

    Returns
    -------
    list[SynthesisTarget]
        One ``SynthesisTarget`` per (section, kind) combination in ``mappings``.

    Raises
    ------
    ProjectDRGValidationError
        If any source URN referenced by the answer context does not exist in
        ``drg_snapshot``. Synthesis fails closed before any adapter call (EC-2).
    """
    _ = interview_snapshot
    targets: list[SynthesisTarget] = []
    # Track directive count to assign PROJECT_NNN IDs (1-based, globally across run).
    directive_index = 0

    for section_label, answer_context in mappings:
        kinds: list[str] = answer_context.get("kinds", [])
        source_section: str | None = answer_context.get("source_section") or None
        explicit_source_urns: tuple[str, ...] = tuple(
            answer_context.get("source_urns", ())
        )

        # Validate any explicitly declared source URNs against the DRG.
        if explicit_source_urns:
            _validate_source_urns(
                explicit_source_urns,
                drg_snapshot,
                target_label=f"{section_label}:{kinds}",
            )

        for kind in kinds:
            slug = _make_slug_for_section(section_label, kind, answer_context)
            title = _make_title_for_section(section_label, kind, answer_context)

            # Assign artifact_id per kind.
            if kind == "directive":
                directive_index += 1
                artifact_id = _make_directive_artifact_id(directive_index)
            else:
                # For tactic / styleguide: artifact_id == slug
                artifact_id = slug

            # A per-kind source (#6442) is added for that kind only, after a
            # presence check against this run's DRG snapshot. The project-intent
            # directive carries no mission-type source (#6443).
            kind_urns = _present_source_urns(
                tuple(answer_context.get("source_urns_by_kind", {}).get(kind, ())),
                drg_snapshot,
            )
            all_source_urns = tuple(dict.fromkeys((*explicit_source_urns, *kind_urns)))

            target = SynthesisTarget(
                kind=kind,
                slug=slug,
                title=title,
                artifact_id=artifact_id,
                source_section=source_section,
                source_urns=all_source_urns,
            )
            targets.append(target)

    return targets


def order_targets(targets: list[SynthesisTarget]) -> list[SynthesisTarget]:
    """Return a new list with deterministic ordering.

    Ordering rule (FR-014):
    1. Kind priority: directive → tactic → styleguide.
    2. Within a kind: lexicographic ascending slug.

    This ordering is idempotent — applying it twice produces an identical result.

    Parameters
    ----------
    targets:
        Unordered list of synthesis targets.

    Returns
    -------
    list[SynthesisTarget]
        Deterministically ordered copy.
    """
    return sorted(
        targets,
        key=lambda t: (_KIND_ORDER.get(t.kind, 99), t.slug),
    )


def detect_duplicates(targets: list[SynthesisTarget]) -> None:
    """Raise DuplicateTargetError if any (kind, slug) appears more than once.

    EC-7: orchestration rejects the run before any adapter call if two targets
    share the same (kind, slug) pair.

    Parameters
    ----------
    targets:
        List of synthesis targets (before or after ordering).

    Raises
    ------
    DuplicateTargetError
        On the first duplicate (kind, slug) found.
    """
    seen: dict[tuple[str, str], int] = {}
    for target in targets:
        key = (target.kind, target.slug)
        seen[key] = seen.get(key, 0) + 1

    for (kind, slug), count in seen.items():
        if count > 1:
            raise DuplicateTargetError(kind=kind, slug=slug, occurrences=count)
