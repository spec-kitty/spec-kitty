"""Interview section → synthesis target mapping.

INVARIANT (R-9): The mappings in this module use **built-in-only DRG** for any
resolution during the interview phase. The project-layer DRG (if any) is NOT
merged in during interview-time target selection. This prevents stale or
circular project-layer entries from skewing interview defaults.

This invariant is enforced by ``resolve_sections()`` and locked by
``tests/charter/synthesizer/test_interview_mapping.py::test_r9_built_in_only_drg``.

---

The ``INTERVIEW_MAPPINGS`` table is the single source of truth for
interview-section → artifact-kind correspondence. WP04's
``test_context_reflects_synthesis`` reads this table to verify that the
synthesized artifact set matches the charter context output.

Mapping semantics
-----------------
Each ``InterviewSectionMapping`` entry describes one interview section and the
artifact kinds it drives. The ``requires_nonempty`` flag gates target emission
on a non-empty, non-whitespace answer for that section.

Producer key aliases
--------------------
The synthesis labels in ``INTERVIEW_MAPPINGS`` are legacy artifact-topic names.
The real ``CharterInterview.answers`` producer uses newer question keys. The
``_INTERVIEW_SECTION_ALIASES`` table is the explicit compatibility contract:
when a synthesis label is absent, resolver reads the producer alias before
deciding a required section is blank.

Special-case sections
---------------------
- ``selected_directives``: each selected directive URN drives a distinct tactic
  artifact (``how-we-apply-<directive-id>``) for each item in the selection
  list. Handled by ``resolve_sections()`` using a per-item expansion.
- ``language_scope``: each selected or declared language drives a distinct
  styleguide artifact (``<lang>-style-guide``). Handled by per-item expansion.

These expansions are intentionally kept inside ``resolve_sections()`` rather
than inside the table so the table remains declarative and inspectable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from charter.activation.language_scope import extract_declared_languages, is_placeholder_language_answer
from charter.offering.missions.mission_type_repository import builtin_mission_type_ids

__all__ = [
    "canonicalize_interview_section_label",
    "mission_type_urn_candidate",
    "normalize_interview_snapshot",
    "resolve_sections",
]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

ArtifactKind = Literal["directive", "tactic", "styleguide"]


@dataclass(frozen=True)
class InterviewSectionMapping:
    """Maps one interview section to a fixed set of artifact kinds.

    Parameters
    ----------
    section_label:
        The canonical interview section / question key (matches keys in
        ``CharterInterview.answers``, ``selected_directives``, etc.).
    kinds:
        Artifact kinds this section drives.
    requires_nonempty:
        When True, emit targets only when the section has a non-blank answer.
        When False, always emit (even for absent / blank answers).
    """

    section_label: str
    kinds: tuple[ArtifactKind, ...]
    requires_nonempty: bool = True


# ---------------------------------------------------------------------------
# The canonical mapping table (T009)
# ---------------------------------------------------------------------------

#: Public, explicitly-enumerated mapping table.
#: WP04's ``test_context_reflects_synthesis`` reads this to validate context.
INTERVIEW_MAPPINGS: tuple[InterviewSectionMapping, ...] = (
    # mission_type → directive describing the project's primary mission scope
    InterviewSectionMapping(
        "mission_type",
        ("directive",),
        requires_nonempty=False,  # always synthesize a mission-scope directive
    ),
    # testing_philosophy → tactic (how to test) + styleguide (testing conventions)
    InterviewSectionMapping(
        "testing_philosophy",
        ("tactic", "styleguide"),
        requires_nonempty=True,
    ),
    # neutrality_posture → directive constraining agent neutrality behaviour
    InterviewSectionMapping(
        "neutrality_posture",
        ("directive",),
        requires_nonempty=True,
    ),
    # risk_appetite → directive bounding acceptable risk
    InterviewSectionMapping(
        "risk_appetite",
        ("directive",),
        requires_nonempty=True,
    ),
    # quality_gates → styleguide for merge/review quality gates
    InterviewSectionMapping(
        "quality_gates",
        ("styleguide",),
        requires_nonempty=True,
    ),
    # review_policy → tactic for the review/approval workflow
    InterviewSectionMapping(
        "review_policy",
        ("tactic",),
        requires_nonempty=True,
    ),
    # documentation_policy → styleguide for docs standards
    InterviewSectionMapping(
        "documentation_policy",
        ("styleguide",),
        requires_nonempty=True,
    ),
)

# Real interview producer keys that feed legacy synthesis section labels.
_INTERVIEW_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "mission_type": ("project_intent",),
    "testing_philosophy": ("testing_requirements",),
    "risk_appetite": ("risk_boundaries",),
    "language_scope": ("languages_frameworks",),
}

# The sole consumer (``_section_answer_with_source``) tests membership via
# ``_normalize_section_selector(canonical) in _MISSION_IDENTIFIER_ANSWERS``,
# and ``_normalize_section_selector`` replaces ``-`` with ``_`` before the
# lookup — so the functionally reachable members are underscore-normalized
# ids. Derived from the canonical accessor (single source of truth, #2669
# IC-1a): a naive ``frozenset(builtin_mission_type_ids())`` would keep the
# shipped hyphen spellings (e.g. ``software-dev``) and silently drop the
# essential underscore alias ``software_dev``, breaking software-dev
# identifier matching. One cached ``mission_types/`` read at import of this
# module is the accepted NFR-001 carve-out for a module-level derived value
# (C-012) — this table is private with a single internal consumer, so a
# lazy form would be over-engineering.
_MISSION_IDENTIFIER_ANSWERS: frozenset[str] = frozenset(
    {
        mission_type_id.replace("-", "_")
        for mission_type_id in builtin_mission_type_ids()
    }
)

# #3052 edge wiring (FR-012/NFR-007): underscore-normalized mission-type
# identifier -> its ``mission_type:<id>`` DRG URN (built-in NodeKind.MISSION_TYPE,
# see doctrine/drg/models.py). Derived from the SAME canonical
# ``builtin_mission_type_ids()`` read as ``_MISSION_IDENTIFIER_ANSWERS`` above
# (single source of truth, #2669 IC-1a) so the two tables can never drift.
# This is the ONLY additional evidence source wired by WP07: when the
# ``mission_type`` answer IS (up to hyphen/underscore normalization) a shipped
# mission-type id, that identity *is* the declared upstream URN -- not an
# inferred relationship (NFR-007 no-fabrication).
_MISSION_TYPE_URN_BY_NORMALIZED_ID: dict[str, str] = {
    mission_type_id.replace("-", "_"): f"mission_type:{mission_type_id}"
    for mission_type_id in builtin_mission_type_ids()
}

# Gated sections without a direct producer key. These remain accepted for
# legacy/synthetic synthesis snapshots and are documented so contract tests do
# not silently bless missing real interview data.
_SYNTHETIC_SECTIONS: dict[str, str] = {
    "neutrality_posture": (
        "Legacy synthesis topic with no current CharterInterview producer key; "
        "accepted only when callers provide it explicitly."
    ),
}

_ALIAS_TO_SECTION: dict[str, str] = {
    alias: section
    for section, aliases in _INTERVIEW_SECTION_ALIASES.items()
    for alias in aliases
}

# Interview sections that receive special per-item expansion in resolve_sections().
# These are NOT rows in INTERVIEW_MAPPINGS because each item in the list drives
# a distinct artifact, not a single fixed artifact per section.
_EXPANDED_SECTIONS: frozenset[str] = frozenset(
    {
        "selected_directives",  # each directive → tactic:how-we-apply-<directive-id>
        "language_scope",  # each language → styleguide:<lang>-style-guide
    }
)


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _normalize_section_selector(label: str) -> str:
    return label.strip().replace("-", "_").replace(" ", "_")


def canonicalize_interview_section_label(label: str) -> str:
    """Return the legacy synthesis section label for a producer/alias key."""
    normalized = _normalize_section_selector(label)
    return _ALIAS_TO_SECTION.get(normalized, normalized)


def normalize_interview_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return a synthesis-canonical interview snapshot.

    Real ``CharterInterview.answers`` producer keys are copied into the legacy
    synthesis section labels before target resolution, adapter dispatch, and
    provenance hashing. Non-alias keys remain untouched.
    """
    normalized = dict(snapshot)

    for section_label, aliases in _INTERVIEW_SECTION_ALIASES.items():
        if section_label == "language_scope":
            continue
        _copy_alias_answer_into_canonical_section(normalized, section_label, aliases)

    _normalize_language_scope_section(normalized)

    return normalized


def _copy_alias_answer_into_canonical_section(
    normalized: dict[str, Any],
    section_label: str,
    aliases: tuple[str, ...],
) -> None:
    """Copy an alias producer key's answer onto its canonical section label.

    Mutates ``normalized`` in place: when the canonical section is blank but
    an alias key carries a non-blank answer, the answer is copied onto the
    canonical key, then every alias key for this section is removed so the
    snapshot carries a single, canonical representation.
    """
    answer, source_key = _section_answer_with_source(normalized, section_label)
    if answer and source_key != section_label:
        normalized[section_label] = answer
    if answer:
        for alias in aliases:
            normalized.pop(alias, None)


def _normalize_language_scope_section(normalized: dict[str, Any]) -> None:
    """Populate ``language_scope`` from the ``languages_frameworks`` alias.

    Mutates ``normalized`` in place. ``language_scope`` is list-valued (each
    entry drives a distinct styleguide target), so it cannot reuse
    :func:`_copy_alias_answer_into_canonical_section`, which handles only
    scalar answers.
    """
    languages = _real_languages(_iter_clean_strings(normalized.get("language_scope", [])))
    if not languages and "languages_frameworks" in normalized:
        languages = _extract_languages_from_alias(normalized["languages_frameworks"])
        if languages:
            normalized["language_scope"] = list(languages)
    if languages:
        normalized.pop("languages_frameworks", None)


def _real_languages(values: tuple[str, ...]) -> tuple[str, ...]:
    """Drop placeholder/``unknown`` members so they never become a styleguide target."""
    return tuple(value for value in values if not is_placeholder_language_answer(value))


def _extract_languages_from_alias(raw_alias: object) -> tuple[str, ...]:
    """Extract declared languages from the ``languages_frameworks`` alias value."""
    if isinstance(raw_alias, str):
        return tuple(extract_declared_languages(raw_alias))
    return _real_languages(_iter_clean_strings(raw_alias))


def _section_answer_with_source(
    snapshot: dict[str, Any],
    section_label: str,
) -> tuple[str, str]:
    """Extract a scalar answer string and the key it came from.

    Returns ("", section_label) when the section and aliases are absent or not
    strings. The canonical section takes precedence over aliases.
    """
    keys = (section_label, *_INTERVIEW_SECTION_ALIASES.get(section_label, ()))
    if section_label == "mission_type":
        canonical = snapshot.get(section_label, "")
        if isinstance(canonical, str):
            normalized_canonical = _normalize_section_selector(canonical)
            if normalized_canonical in _MISSION_IDENTIFIER_ANSWERS:
                keys = (*_INTERVIEW_SECTION_ALIASES.get(section_label, ()), section_label)

    for key in keys:
        value = snapshot.get(key, "")
        if isinstance(value, str):
            answer = value.strip()
            if answer:
                return answer, key
    return "", section_label


def mission_type_urn_candidate(answer: str) -> str | None:
    """Return the ``mission_type:<id>`` URN *answer* would declare, or ``None``.

    #3052 edge wiring (FR-012/NFR-007): ``answer`` is genuine evidence exactly
    when it (up to hyphen/underscore normalization, mirroring
    ``_MISSION_IDENTIFIER_ANSWERS``) names a shipped mission-type id -- the
    built-in DRG carries a ``mission_type:<id>`` node for each one
    (``charter.offering.drg.models.NodeKind.MISSION_TYPE``). A free-text answer that
    does not name a shipped id carries no such evidence, so ``None`` is
    returned -- never inferred, never fabricated.

    This function only answers "does the answer name a shipped mission-type
    id" -- it does NOT confirm the URN is present in any particular run's DRG
    snapshot. Callers (``targets.build_targets``, R-9 forbids DRG access
    here) are responsible for that presence check before wiring the URN as a
    ``source_urns`` entry, so an incomplete DRG snapshot never turns into a
    dangling-URN validation failure.
    """
    normalized = _normalize_section_selector(answer)
    return _MISSION_TYPE_URN_BY_NORMALIZED_ID.get(normalized)


def _append_table_driven_results(
    results: list[tuple[str, dict[str, Any]]],
    interview_snapshot: dict[str, Any],
) -> None:
    """Append the standard fixed-cardinality section mappings."""
    for mapping in INTERVIEW_MAPPINGS:
        label = mapping.section_label
        answer, source_key = _section_answer_with_source(interview_snapshot, label)

        if mapping.requires_nonempty and not answer:
            continue

        results.append(
            (
                label,
                {
                    "answer": answer,
                    "kinds": list(mapping.kinds),
                    "source_section": label,
                    "answer_source": source_key,
                },
            )
        )


def _iter_clean_strings(raw_values: object) -> tuple[str, ...]:
    """Return stripped non-empty strings from a scalar or sequence input."""
    if isinstance(raw_values, str):
        cleaned = raw_values.strip()
        return (cleaned,) if cleaned else ()
    if isinstance(raw_values, (list, tuple)):
        return tuple(
            item.strip()
            for item in raw_values
            if isinstance(item, str) and item.strip()
        )
    return ()


def _append_selected_directives(
    results: list[tuple[str, dict[str, Any]]],
    interview_snapshot: dict[str, Any],
) -> None:
    """Append one tactic entry per selected directive."""
    for directive_id in _iter_clean_strings(
        interview_snapshot.get("selected_directives", [])
    ):
        results.append(
            (
                "selected_directives",
                {
                    "answer": directive_id,
                    "kinds": ["tactic"],
                    "source_section": "selected_directives",
                    "source_urns": (f"directive:{directive_id}",),
                    "directive_id": directive_id,
                },
            )
        )


def _append_language_scope_results(
    results: list[tuple[str, dict[str, Any]]],
    interview_snapshot: dict[str, Any],
) -> None:
    """Append one styleguide entry per declared language."""
    source_key = "language_scope"
    languages = _real_languages(_iter_clean_strings(interview_snapshot.get("language_scope", [])))
    if not languages:
        source_key = "languages_frameworks"
        languages = _extract_languages_from_alias(interview_snapshot.get("languages_frameworks", ""))

    for language in languages:
        normalized_language = language.lower()
        results.append(
            (
                "language_scope",
                {
                    "answer": normalized_language,
                    "kinds": ["styleguide"],
                    "source_section": "language_scope",
                    "answer_source": source_key,
                    "language": normalized_language,
                },
            )
        )


def resolve_sections(
    interview_snapshot: dict[str, Any],
    *,
    _use_built_in_only_drg: bool = True,  # R-9 invariant — always True at interview time
) -> list[tuple[str, dict[str, Any]]]:
    """Map interview answers to a list of (section_label, answer_context) pairs.

    Each pair represents one target-generation context. For most sections this
    is a 1-to-1 mapping. For expanded sections (``language_scope``,
    ``selected_directives``), one list item is emitted per selection.

    Parameters
    ----------
    interview_snapshot:
        The frozen interview answers dict from ``SynthesisRequest.interview_snapshot``.
    _use_built_in_only_drg:
        Internal sentinel documenting the R-9 invariant. Must never be set to
        ``False`` during interview-time resolution. Tests assert on this.

    Returns
    -------
    list[tuple[str, dict[str, Any]]]
        Each element is ``(section_label, answer_context)`` where
        ``answer_context`` carries the section's answer(s) and any
        DRG URN references relevant to the target.
    """
    # R-9: this function must never read from a merged (project + built-in) DRG.
    # The _use_built_in_only_drg sentinel documents and enforces this invariant.
    if not _use_built_in_only_drg:
        raise ValueError(
            "resolve_sections() requires _use_built_in_only_drg=True (R-9 invariant). "
            "Do not merge the project-layer DRG during interview-time resolution."
        )

    results: list[tuple[str, dict[str, Any]]] = []

    _append_table_driven_results(results, interview_snapshot)
    _append_selected_directives(results, interview_snapshot)
    _append_language_scope_results(results, interview_snapshot)

    return results
