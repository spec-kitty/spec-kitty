"""Structured-selector resolver for --topic (FR-011, FR-012, FR-013).

Resolves a user-facing topic string into a ``ResolvedTopic`` carrying the
bounded set of ``SynthesisTarget`` objects to regenerate.

Resolution order (contracts/topic-selector.md §1.4):
    1. ``<kind>:<slug>`` where kind ∈ synthesizable → project-local artifact set.
    2. ``<node-kind>:<identifier>`` → merged built-in+project DRG graph.
    3. ``<section-label>`` (no colon) → interview section labels.
    4. No hit → ``TopicSelectorUnresolvedError``.

Step 1 wins over step 2 when the LHS is synthesizable AND a project-local
artifact exists — the *local-first* rule (US-3, contracts/topic-selector.md §1.1).
No silent fallback between steps (FR-013, C-004).

Performance SLA: < 2 s on cold cache (SC-008) — all lookups are in-memory;
no filesystem I/O occurs inside resolve().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from collections.abc import Mapping, Sequence

from charter.offering.drg.models import NodeKind

from .errors import TopicSelectorUnresolvedError
from .interview_mapping import canonicalize_interview_section_label
from .request import SynthesisTarget

# ---------------------------------------------------------------------------
# Synthesizable kinds (tier-1 local-first rule)
# ---------------------------------------------------------------------------

SYNTHESIZABLE_KINDS: frozenset[str] = frozenset({"directive", "tactic", "styleguide"})

# DRG node kinds, derived from the canonical ``NodeKind`` enum so a new kind is
# addressable at the membership gate the moment it is declared — no hand copy to
# drift behind the enum (#3608). ``NodeKind`` value == URN prefix is guaranteed
# by ``DRGNode._validate_urn`` (charter/offering/drg/models.py). Mirrors the
# twin derivation ``_NODE_KIND_PREFIXES`` in ``charter/offering/drg/merge.py``.
_DRG_NODE_KINDS: frozenset[str] = frozenset(k.value for k in NodeKind)


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedTopic:
    """Successful resolution: bounded slice of targets to regenerate.

    Attributes
    ----------
    targets:
        The ``SynthesisTarget`` objects to regenerate.  May be empty for a
        DRG-URN hit where no project-local artifact references that URN
        (EC-4 zero-match — the caller renders the no-op diagnostic; no writes).
    matched_form:
        Which resolution tier succeeded.
    matched_value:
        Normalized form of the winning selector string.
    """

    targets: list[SynthesisTarget]
    matched_form: Literal["kind_slug", "drg_urn", "interview_section"]
    matched_value: str


# ---------------------------------------------------------------------------
# Candidate scoring for error messages
# ---------------------------------------------------------------------------


def _levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings (stdlib-only).

    Uses a compact O(min(len(a), len(b))) space implementation.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Ensure a is the shorter string for memory efficiency.
    if len(a) > len(b):
        a, b = b, a

    prev = list(range(len(a) + 1))
    for char_b in b:
        curr = [prev[0] + 1]
        for j, char_a in enumerate(a):
            cost = 0 if char_a == char_b else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _nearest_candidates(
    raw: str,
    project_artifacts: Sequence[SynthesisTarget],
    merged_drg: Mapping[str, Any],
    interview_sections: Sequence[str],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the top ``limit`` nearest candidates across all three forms.

    Parameters
    ----------
    raw:
        The unresolved topic string from the user.
    project_artifacts:
        List of all project-local SynthesisTarget objects.
    merged_drg:
        Merged DRG graph dict with a ``nodes`` list.
    interview_sections:
        Known interview section label strings.
    limit:
        Maximum number of candidates to return.

    Returns
    -------
    list[dict]
        Each dict has keys ``kind`` (form name), ``value`` (selector string),
        and ``distance`` (integer Levenshtein).
    """
    scored: list[dict[str, Any]] = []

    # Tier-1 candidates: kind:slug for project-local synthesizable artifacts
    for artifact in project_artifacts:
        value = f"{artifact.kind}:{artifact.artifact_id}"
        scored.append({
            "kind": "kind_slug",
            "value": value,
            "distance": _levenshtein(raw, value),
        })

    # Tier-2 candidates: DRG URN nodes
    nodes = merged_drg.get("nodes", []) if isinstance(merged_drg, dict) else []
    for node in nodes:
        urn = node.get("urn", "") if isinstance(node, dict) else getattr(node, "urn", "")
        if urn:
            scored.append({
                "kind": "drg_urn",
                "value": str(urn),
                "distance": _levenshtein(raw, str(urn)),
            })

    # Tier-3 candidates: interview section labels
    for section in interview_sections:
        scored.append({
            "kind": "interview_section",
            "value": section,
            "distance": _levenshtein(raw, section),
        })

    # Sort by distance, then by value for determinism
    scored.sort(key=lambda c: (c["distance"], c["value"]))
    return scored[:limit]


def _normalize_interview_section_label(label: str) -> str:
    """Normalize user-facing interview-section selectors.

    The stored section labels are underscore-delimited (`testing_philosophy`),
    but operators naturally type hyphenated forms (`testing-philosophy`).
    Normalize both to the canonical underscore form and map real interview
    producer keys (for example ``testing_requirements``) back to the legacy
    synthesis section labels stored in provenance.
    """
    return canonicalize_interview_section_label(label)


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _resolve_kind_slug(
    raw: str,
    project_artifacts: Sequence[SynthesisTarget],
) -> SynthesisTarget | None:
    """Tier-1: project-local artifact lookup by kind:slug.

    Matches on ``artifact.kind == lhs`` and (``artifact.artifact_id == rhs``
    OR ``artifact.slug == rhs``) to handle both directive IDs (PROJECT_001)
    and slug-based kinds (tactic, styleguide).

    Returns the matched SynthesisTarget, or None if no match.
    """
    colon_idx = raw.index(":")
    lhs = raw[:colon_idx].strip()
    rhs = raw[colon_idx + 1:].strip()

    if lhs not in SYNTHESIZABLE_KINDS:
        return None

    for artifact in project_artifacts:
        if artifact.kind != lhs:
            continue
        # Match by artifact_id (primary, used for directives like PROJECT_001)
        # or by slug (used for tactic/styleguide where artifact_id == slug)
        if artifact.artifact_id == rhs or artifact.slug == rhs:
            return artifact

    return None


def _resolve_drg_urn(
    raw: str,
    merged_drg: Mapping[str, Any],
    project_artifacts: Sequence[SynthesisTarget],
) -> list[SynthesisTarget] | None:
    """Tier-2: DRG URN lookup in the merged built-in+project graph.

    Returns the list of project-local artifacts whose provenance contains
    this URN in their source_urns.  Returns None if the URN is not found
    in the DRG at all (caller moves to next tier or raises).
    Returns an empty list if the URN exists in the DRG but no project-local
    artifact's provenance references it (EC-4 zero-match).
    """
    # Validate: the string must parse as <node-kind>:<identifier>
    colon_idx = raw.index(":")
    lhs = raw[:colon_idx].strip()

    # LHS must be a known DRG node kind
    if lhs not in _DRG_NODE_KINDS:
        return None

    # Check the merged DRG for the URN
    nodes = merged_drg.get("nodes", []) if isinstance(merged_drg, dict) else []
    drg_urns: set[str] = set()
    for node in nodes:
        urn = node.get("urn", "") if isinstance(node, dict) else getattr(node, "urn", "")
        if urn:
            drg_urns.add(str(urn))

    if raw not in drg_urns:
        return None

    # URN exists in DRG — find all project-local artifacts whose provenance
    # source_urns includes this URN.
    matched: list[SynthesisTarget] = []
    for artifact in project_artifacts:
        if raw in artifact.source_urns:
            matched.append(artifact)

    return matched


def _resolve_interview_section(
    raw: str,
    project_artifacts: Sequence[SynthesisTarget],
    interview_sections: Sequence[str],
) -> list[SynthesisTarget] | None:
    """Tier-3: interview section label lookup.

    Returns the list of project-local artifacts whose source_section equals
    raw (exact, case-sensitive match).  Returns None if raw is not in the
    known interview section set.
    """
    normalized_sections = {
        _normalize_interview_section_label(section): _normalize_interview_section_label(section)
        for section in interview_sections
    }
    normalized_raw = _normalize_interview_section_label(raw)
    canonical_section = normalized_sections.get(normalized_raw)
    if canonical_section is None:
        return None

    matched: list[SynthesisTarget] = [
        artifact
        for artifact in project_artifacts
        if artifact.source_section == canonical_section
    ]
    return matched


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def resolve(
    raw: str,
    project_artifacts: Sequence[SynthesisTarget],
    merged_drg: Mapping[str, Any],
    interview_sections: Sequence[str],
) -> ResolvedTopic:
    """Resolve a user-supplied topic selector into a bounded set of targets.

    Resolution order (contracts/topic-selector.md §1.4):
        1. ``<kind>:<slug>`` where kind ∈ {directive, tactic, styleguide}
           → project-local artifact set (local-first rule).
        2. ``<node-kind>:<identifier>`` → merged DRG graph.
        3. ``<section-label>`` (no colon) → interview section labels.
        4. No hit → ``TopicSelectorUnresolvedError``.

    Parameters
    ----------
    raw:
        The raw ``--topic`` argument from the user (no pre-processing applied).
    project_artifacts:
        Sequence of all project-local SynthesisTarget objects (from provenance
        sidecars or a live tree scan).
    merged_drg:
        The merged built-in+project DRG graph as a dict with a ``nodes`` list.
        Each node should have a ``urn`` key/attribute.
    interview_sections:
        Ordered sequence of known interview section label strings.

    Returns
    -------
    ResolvedTopic
        Successful resolution.  ``.targets`` may be empty for a DRG-URN
        zero-match (EC-4 — caller renders the no-op diagnostic).

    Raises
    ------
    TopicSelectorUnresolvedError
        When all three tiers fail.  Carries ``candidates`` for the CLI panel.
    ValueError
        When ``raw`` is empty or consists only of whitespace (C-004).
    """
    if not raw or not raw.strip():
        raise ValueError(
            "Topic selector must be a non-empty string. "
            "Free-text selectors are rejected (C-004). "
            "Use one of: <kind>:<slug>, <drg-urn>, or <interview-section-label>."
        )

    raw = raw.strip()
    has_colon = ":" in raw

    attempted_forms: list[str] = []

    if has_colon:
        colon_idx = raw.index(":")
        lhs = raw[:colon_idx].strip()

        # Tier 1: project-local kind:slug (synthesizable kinds only)
        if lhs in SYNTHESIZABLE_KINDS:
            attempted_forms.append("kind_slug")
            artifact = _resolve_kind_slug(raw, project_artifacts)
            if artifact is not None:
                return ResolvedTopic(
                    targets=[artifact],
                    matched_form="kind_slug",
                    matched_value=raw,
                )

        # Tier 2: DRG URN
        attempted_forms.append("drg_urn")
        drg_results = _resolve_drg_urn(raw, merged_drg, project_artifacts)
        if drg_results is not None:
            # URN found in DRG (even if no project artifacts reference it — EC-4)
            return ResolvedTopic(
                targets=drg_results,
                matched_form="drg_urn",
                matched_value=raw,
            )

    else:
        # Tier 3: interview section label
        attempted_forms.append("interview_section")
        section_results = _resolve_interview_section(raw, project_artifacts, interview_sections)
        if section_results is not None:
            normalized_sections = {
                _normalize_interview_section_label(section): _normalize_interview_section_label(section)
                for section in interview_sections
            }
            matched_value = normalized_sections[_normalize_interview_section_label(raw)]
            return ResolvedTopic(
                targets=section_results,
                matched_form="interview_section",
                matched_value=matched_value,
            )

    # No hit — collect candidates and raise structured error
    candidates = _nearest_candidates(raw, project_artifacts, merged_drg, interview_sections)
    candidate_tuples = tuple(
        f"{c['kind']}:{c['value']} (distance={c['distance']})"
        for c in candidates
    )
    raise TopicSelectorUnresolvedError(
        raw=raw,
        attempted_forms=tuple(attempted_forms),
        candidates=candidate_tuples,
    )


__all__ = [
    "SYNTHESIZABLE_KINDS",
    "ResolvedTopic",
    "resolve",
]
