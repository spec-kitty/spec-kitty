"""Token budget enforcement and fetch substitution (WP05 T019, NFR-001).

The augmented WP prompt MUST stay under a configurable character budget
(default 32 000 chars, ~8 000 tokens at 4 chars/token).  When the rendered
governance payload exceeds the budget, the longest section bodies are
auto-substituted with the canonical fetch + when-doing stanza
(:func:`charter.activation.context_renderers.fetch_stanza.fetch_stanza`) until the
budget is met.

Substitution algorithm (deterministic, order-independent):

1. Render the join of all sections; if ``len <= budget``, return as-is.
2. Sort substitutable sections by body length (longest first), breaking
   ties on ``section_id`` ascending so the same input always produces the
   same output (no dict-iteration assumption).
3. Pop the longest; replace its body with the canonical fetch stanza
   derived from the ``selector`` + ``when_doing_clause`` carried by the
   section descriptor.
4. Re-render; if still over budget, repeat with the next-longest.
5. When all substitutable bodies have been replaced, emit a single
   trailing warning line so the executing agent knows which surface to
   fetch:

       ``# Governance payload: <N> sections substituted with fetch
       commands (budget=<B>).``

Sections marked ``substitutable=False`` (e.g. the small authority-paths
block, core-doctrine sections) stay inline regardless of body length.

The returned tuple is ``(joined_text, substitution_notes)`` where
``substitution_notes`` is a list of human-readable strings describing
the swaps; callers may log this so operators can audit which sections
got swapped.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from charter.activation.context_renderers.fetch_stanza import (
    DEFAULT_WHEN_CLAUSE,
    fetch_stanza,
    fetch_stanza_lines,
)
from charter.activation.context_renderers.section_bodies import (
    critical_section_selector,
    critical_section_when_clause,
)

__all__ = [
    "BUDGET_DEFAULT",
    "RenderedSection",
    "_PROFILE_INLINE_BODY_LIMIT_CHARS",
    "_budget_estimate",
    "_enforce_token_budget",
    "apply_token_budget",
    "budget_without_warning_line",
    "warning_line",
]


BUDGET_DEFAULT: int = 40_000
"""Default character budget — NFR-001 pin (~10000 tokens at 4 chars/token).

Raised 32_000 -> 40_000 (2026-08-12) after commit 3bcdda344 wired the
software-dev doctrine cascade (mutation-testing, disciplined-refactoring,
change-scope reconciliation) into action reachability. That legitimately grew
the essential Action Doctrine payload past the old 32k pin, tripping the
governance-contract guard (``tests/specify_cli/next/
test_wp_prompt_governance_contract.py``) by compacting away the anti-drift
anchors (DIRECTIVE_032, glossary path, ADR path). 40k gives the now-larger
essential cascade headroom without dropping either delivery contract.

NOTE: real charter payloads run ~65k pre-compaction, so this default is not a
production ceiling — the deeper work of keeping the anti-drift anchors
always-delivered under prod-scale compaction is tracked separately."""

_PROFILE_INLINE_BODY_LIMIT_CHARS = 2_400
"""Per-entry inline-body character ceiling (WP03/WP12): a profile-cited
artifact's verbatim body renders inline only when its estimated size (see
:func:`_budget_estimate`) is at or under this limit; otherwise the entry
renders as the canonical fetch + when-doing stanza instead."""


@dataclass(frozen=True)
class RenderedSection:
    """A single rendered section eligible for token-budget substitution.

    Attributes
    ----------
    section_id:
        Stable identifier used to break ties when sorting by body length
        and to surface in substitution notes.  Examples: ``"profile-cited-
        directives"``, ``"directive:DIRECTIVE_010"``, ``"section:
        terminology-canon"``.
    header:
        Optional leading line(s) emitted verbatim — the substitution
        algorithm never touches the header so anchors like ``Profile-Cited
        Directives (python-pedro):`` survive a swap.  Pass empty string
        for sections that have no separate header.
    body:
        The verbatim section body (potentially very long).  Substitution
        replaces this with the canonical fetch stanza when the section
        is selected.
    selector:
        Canonical ``<kind>:<identifier>`` selector for the fetch stanza
        (see :func:`charter.activation.context_renderers.fetch_stanza.format_selector`).
        Empty selector implies the section has no fetch path — in that
        case the section is treated as non-substitutable regardless of
        the ``substitutable`` flag.
    when_doing_clause:
        Verb-phrase completing the ``When you <clause>, ...`` sentence
        in the fetch stanza.  Empty falls back to
        :data:`charter.activation.context_renderers.fetch_stanza.DEFAULT_WHEN_CLAUSE`.
    substitutable:
        ``True`` when the section may be replaced with a fetch stanza
        under budget pressure.  Authority-paths and core-doctrine blocks
        carry ``False`` to keep them inline (they are small + critical).
    indent:
        Optional indentation applied to the fetch stanza lines when the
        section is substituted, so substituted output remains aligned
        with the surrounding list structure.
    replacement_body:
        Optional pre-rendered compact replacement. Used for global-selection
        groups, where retaining the selected IDs plus one parameterized fetch
        command is more useful than dropping the group to one selector.
    """

    section_id: str
    header: str
    body: str
    selector: str = ""
    when_doing_clause: str = ""
    substitutable: bool = True
    indent: str = ""
    replacement_body: str | None = None


def warning_line(count: int, budget: int) -> str:
    """Return the trailing warning line for *count* substitutions at *budget*."""

    return f"# Governance payload: {count} sections substituted with fetch commands (budget={budget})."


def budget_without_warning_line(count: int, budget: int) -> int:
    """Return pre-warning content budget after reserving warning-line space."""

    if count <= 0:
        return budget
    return budget - len(f"\n\n{warning_line(count, budget)}")


def _join_sections(sections: list[RenderedSection]) -> str:
    """Combine sections into a single text block.

    Sections are joined with a single blank line between them when both
    header and body are non-empty, mirroring the existing renderer
    behaviour in :mod:`charter.activation.context`.
    """

    blocks: list[str] = []
    for section in sections:
        pieces: list[str] = []
        if section.header:
            pieces.append(section.header)
        if section.body:
            pieces.append(section.body)
        if not pieces:
            continue
        blocks.append("\n".join(pieces))
    return "\n\n".join(blocks)


def _substituted_section(section: RenderedSection) -> RenderedSection:
    """Return a copy of *section* whose body is the canonical fetch stanza."""

    clause = section.when_doing_clause or DEFAULT_WHEN_CLAUSE
    if section.replacement_body is not None:
        replacement = section.replacement_body
    elif section.selector:
        replacement = fetch_stanza(section.selector, clause, indent=section.indent)
    else:
        # No fetch path available — keep the original body so we don't
        # silently drop content with no recovery rail.  This is also
        # guarded by the ``substitutable`` flag in :func:`apply_token_budget`.
        return section
    return RenderedSection(
        section_id=section.section_id,
        header=section.header,
        body=replacement,
        selector=section.selector,
        when_doing_clause=clause,
        substitutable=False,  # Already substituted; never re-swap.
        indent=section.indent,
        replacement_body=None,
    )


def apply_token_budget(
    sections: list[RenderedSection],
    *,
    budget: int = BUDGET_DEFAULT,
) -> tuple[str, list[str]]:
    """Combine *sections* into a single text under *budget* characters.

    See module docstring for the substitution algorithm.

    Parameters
    ----------
    sections:
        Ordered list of :class:`RenderedSection` descriptors.  Section
        order is preserved in the output; only the bodies of selected
        sections are swapped for fetch stanzas.
    budget:
        Character budget cap.  Defaults to :data:`BUDGET_DEFAULT`.

    Returns
    -------
    tuple[str, list[str]]
        ``(joined_text, substitution_notes)``.  When no substitution is
        needed, ``substitution_notes`` is the empty list and the joined
        text does not carry the trailing warning line.

    Notes
    -----
    The algorithm is deterministic: same input always produces the same
    output.  Ties on body length are broken by ascending ``section_id``,
    which protects against ``dict``-iteration order changes across
    Python versions.
    """

    if budget <= 0:
        # Defensive: a non-positive budget is treated as no-op so we
        # never silently drop content on a misconfigured caller.
        return _join_sections(sections), []

    current = list(sections)
    notes: list[str] = []

    joined = _join_sections(current)
    if len(joined) <= budget:
        return joined, notes

    while len(joined) > budget_without_warning_line(len(notes), budget):
        # Pick the longest substitutable section with a non-empty selector.
        candidates = [(idx, sec) for idx, sec in enumerate(current) if sec.substitutable and (sec.selector or sec.replacement_body is not None) and sec.body]
        if not candidates:
            # Nothing left to swap — break out and let the caller see the
            # over-budget text rather than looping forever.
            break

        # Sort longest body first, ties broken on section_id ascending so
        # the swap order is deterministic regardless of input ordering.
        candidates.sort(key=lambda pair: (-len(pair[1].body), pair[1].section_id))
        target_index, target_section = candidates[0]
        replaced = _substituted_section(target_section)
        current[target_index] = replaced
        notes.append(f"{target_section.section_id} (body {len(target_section.body)} chars -> fetch stanza)")
        joined = _join_sections(current)

    if notes:
        # Append the standardised warning line so operators see at a
        # glance which budget pressed and how many swaps happened.
        joined = f"{joined}\n\n{warning_line(len(notes), budget)}"

    return joined, notes


def _budget_estimate(lines: list[str]) -> int:
    """Total character cost of *lines* including newlines."""
    return sum(len(line) + 1 for line in lines)


def _split_leading_header(text: str) -> tuple[str, str]:
    """Split *text* into its leading anchor-header line and the remainder.

    ``section_block`` / each per-kind chunk of ``profile_block`` (see
    :func:`_split_profile_blocks`) are pre-rendered strings whose own first
    line is the anchor header (e.g. ``Action-Critical Charter Sections
    (implement):`` or ``Profile-Cited Tactics (reviewer-renata):``). Per the
    :class:`RenderedSection` contract, the header must never be swapped away
    with the body — so it is split off here rather than embedded in the
    substitutable ``body``.

    A text with no embedded newline has no separate header line by design
    (e.g. a bare fixture body in a unit test): it is returned unchanged as
    the body with an empty header, so a substitution still replaces the
    whole thing verbatim (existing behaviour for header-less bodies is
    preserved byte-for-byte).
    """
    if "\n" not in text:
        return "", text
    header, _, remainder = text.partition("\n")
    return header, remainder


def _split_profile_blocks(text: str) -> list[tuple[str, str]]:
    """Split the joined profile-cited block into per-kind ``(header, body)`` parts.

    ``_render_profile_sections`` renders up to six kind-blocks (directives,
    tactics, styleguides, toolguides, procedures, suggested-doctrine) and
    joins them with a blank line (``"\\n\\n".join(blocks)``); each block's own
    first line is its anchor header. None of the per-kind renderers ever
    emit an internal blank line (entries are single lines or fixed-shape
    inline bodies), so splitting on the blank-line separator recovers
    exactly the top-level kind boundaries without disturbing any kind's
    content — this is what lets every populated kind's header (not just the
    first) survive a substitution below.

    A ``profile_block`` with no blank-line-separated structure (e.g. a bare
    single-line unit-test fixture) degrades to a single ``(header, body)``
    pair via :func:`_split_leading_header`, matching prior single-candidate
    behaviour exactly.
    """
    if not text:
        return []
    return [_split_leading_header(chunk) for chunk in text.split("\n\n") if chunk]


def _heading_text(line: str) -> str | None:
    """Return the heading text of a ``### <heading>`` marker line, else ``None``.

    Plain string handling, linear in the line length. It returns what the former
    ``^###\\s+(\\S.*?)\\s*$`` match captured: ``###``, at least one whitespace
    character, then the heading with surrounding whitespace removed; a marker
    followed only by whitespace is not a heading. That regex backtracked
    quadratically on a heading with a long inner run of spaces, because the lazy
    ``.*?`` and the trailing ``\\s*`` both match a space (Sonar S8786, #4696).
    *line* is one line (no ``\\n``), as :func:`_split_critical_sections` passes it.
    """
    if not line.startswith("###") or not line[3:4].isspace():
        return None
    return line[3:].strip() or None


def _split_critical_sections(text: str) -> list[tuple[str, str, str]]:
    """Split the joined action-critical-sections body into per-heading parts.

    ``render_critical_section_bodies`` renders one ``### <heading>``
    sub-block per action-critical charter heading (Terminology Canon, Code
    Review Checklist, Regression Vigilance, ...), each already ending in
    its own selector-specific fetch stanza. Prior to this split, the WHOLE
    joined body (every heading concatenated) was handed to
    ``_enforce_token_budget`` as ONE opaque candidate — so whichever single
    heading pushed the combined body's length past whatever else was
    competing for a swap took every OTHER heading down with it. That is
    what regressed the WP-prompt governance contract (#3175 landing-pass
    fold): growing the profile-cited payload (language-scope admit-all fix)
    pushed the combined section body just over budget, and the ENTIRE
    block — Terminology Canon + Code Review Checklist [glossary/
    DIRECTIVE_032 anchor] + Regression Vigilance [ADR/glossary-path anchor]
    — was swapped for one generic stanza in a single shot, even though each
    heading individually is far smaller than most profile-cited kind-blocks
    and never needed to compete as a bloc.

    Splitting on the ``### `` sub-heading boundary — rather than on every
    blank line, as :func:`_split_profile_blocks` does for the profile block
    — is required here because a heading's verbatim charter.md body may
    legitimately contain internal blank lines (multi-paragraph prose); a
    blank-line split would fragment one heading into several bogus
    candidates. ``### `` boundaries are safe: :mod:`section_bodies` only
    ever emits that marker to open a new heading block.

    Returns ``(header, body, heading)`` triples in document order, where
    ``header`` is the literal ``### <heading>`` line (never swapped) and
    ``heading`` is the bare heading text (``Terminology Canon``) used to
    derive the heading-specific selector/when-clause on a swap. The block's
    own outer header line (``Action-Critical Charter Sections (<action>):``)
    precedes the first heading and carries no ``### `` prefix, so it never
    matches and is dropped here — the caller re-attaches it separately as
    the always-inline block header.
    """
    if not text:
        return []
    result: list[tuple[str, str, str]] = []
    for chunk in re.split(r"\n\n(?=### )", text):
        if not chunk:
            continue
        first_line, _, remainder = chunk.partition("\n")
        heading = _heading_text(first_line)
        if heading is None:
            # The block's own outer header (e.g. "Action-Critical Charter
            # Sections (implement):") precedes the first "### " heading and
            # carries no such prefix — not a headed sub-block to split.
            continue
        result.append((first_line, remainder, heading))
    return result


def _collect_section_block_candidates(section_block: str, action: str) -> list[RenderedSection]:
    """Build the per-heading swap candidates for *section_block*.

    ``section_block`` (the action-critical charter sections — Terminology
    Canon, Code Review Checklist, Regression Vigilance) is split into one
    candidate per heading, exactly as ``profile_block`` is split into one
    candidate per kind by :func:`_collect_profile_block_candidates` (see
    :func:`_split_critical_sections` / :func:`_split_profile_blocks`). Prior
    to that split, the WHOLE joined ``section_block`` competed as a single
    opaque candidate against individually-split, often much larger profile
    kind-blocks — so growing the profile payload (e.g. a language-scope fix
    admitting more profile-cited artifacts) could tip the combined section
    body just over the length that made it the single longest candidate,
    taking every heading's anchors (glossary path, ADR path, profile-cited
    ``DIRECTIVE_NNN`` citations) down in one swap even though each heading
    individually is far smaller than the profile content that should have
    been preferred. Splitting both sides the same way lets every candidate
    compete on its own real size, so the small, curated headings are
    naturally spared unless they are genuinely the largest thing left.
    """

    if not section_block:
        return []

    candidates: list[RenderedSection] = []
    headed = _split_critical_sections(section_block)
    if headed:
        for header, body, heading in headed:
            if not body:
                continue
            candidates.append(
                RenderedSection(
                    section_id=f"action-critical-sections:{heading}",
                    header=header,
                    body=body,
                    selector=critical_section_selector(heading),
                    when_doing_clause=critical_section_when_clause(heading),
                    substitutable=True,
                    indent="  ",
                )
            )
        return candidates

    # No "### <heading>" sub-structure detected at all (e.g. a bare
    # single-blob fixture) — fall back to the pre-split, single-
    # candidate behaviour covering the whole block. The header
    # (e.g. "Action-Critical Charter Sections (implement):") is
    # split off so a substitution below never removes it — see
    # _split_leading_header. A body-less section_block has nothing
    # left worth swapping, so it is left inline rather than added
    # as a candidate.
    header, body = _split_leading_header(section_block)
    if body:
        candidates.append(
            RenderedSection(
                section_id="action-critical-sections",
                header=header,
                body=body,
                selector=f"section:critical-{action}",
                when_doing_clause=("need to consult the action-critical charter sections"),
                substitutable=True,
                indent="  ",
            )
        )
    return candidates


def _collect_profile_block_candidates(profile_block: str) -> list[RenderedSection]:
    """Build one swap candidate per kind-block in *profile_block*.

    ``profile_block`` joins up to six kind-blocks (directives, tactics,
    styleguides, toolguides, procedures, suggested-doctrine), each with its
    own anchor header. Splitting it into one :class:`RenderedSection` per
    kind (rather than one opaque candidate for the whole block) means EVERY
    populated kind's header survives a swap, not just the first — see
    :func:`_split_profile_blocks`.
    """

    if not profile_block:
        return []

    candidates: list[RenderedSection] = []
    for index, (header, body) in enumerate(_split_profile_blocks(profile_block)):
        if not body:
            continue
        candidates.append(
            RenderedSection(
                section_id=f"profile-cited-sections-{index}",
                header=header,
                body=body,
                selector="section:profile-citations",
                when_doing_clause=("need to consult the profile-cited directives and tactics"),
                substitutable=True,
                indent="  ",
            )
        )
    return candidates


_SELECTION_GROUPS: dict[str, tuple[str, str]] = {
    "Selected paradigms:": ("paradigm", "are about to choose a reasoning frame"),
    "Selected directives:": ("directive", "are about to apply a code change"),
    "Selected tactics:": ("tactic", "are about to apply a code change"),
    "Selected styleguides:": ("styleguide", "are about to write styled output"),
    "Selected toolguides:": ("toolguide", "are about to invoke a project tool"),
    "Selected procedures:": ("procedure", "are about to follow a workflow"),
    "Selected agent profiles:": ("agent_profile", "are about to apply a code change"),
    "Selected mission step contracts:": (
        "mission_step_contract",
        "are about to step a mission action",
    ),
}


def _collect_selection_block_candidates(selection_block: str) -> list[RenderedSection]:
    """Build compactable per-kind candidates for global doctrine selections.

    A project can deliberately select hundreds of artifacts. Their individual
    bodies are useful while the aggregate fits, but must not bypass the 40k
    prompt cap. Under pressure, retain every selected ID and replace only the
    bodies with one parameterized, executable-shape fetch instruction per kind.
    """
    candidates: list[RenderedSection] = []
    for header, body in _split_profile_blocks(selection_block):
        group = _SELECTION_GROUPS.get(header)
        if group is None or not body:
            continue
        kind, clause = group
        id_lines = [line for line in body.splitlines() if line.startswith("  - ")]
        if not id_lines:
            continue
        compact = "\n".join(
            [
                *id_lines,
                f"  Run: spec-kitty charter context --include {kind}:SELECTED_ID",
                (f"  When you {clause}, replace SELECTED_ID with an ID above and apply the returned rule."),
            ]
        )
        candidates.append(
            RenderedSection(
                section_id=f"global-selection:{kind}",
                header=header,
                body=body,
                substitutable=True,
                replacement_body=compact,
            )
        )
    return candidates


def _swap_candidates_into_text(text: str, candidates: list[RenderedSection], budget: int) -> tuple[str, list[str]]:
    """Swap *candidates* (already sorted longest-first) into *text*.

    Iterates the sorted candidates, replacing each section's body with its
    canonical fetch stanza (see :func:`fetch_stanza_lines`) until *text*
    fits under *budget* (accounting for the trailing warning line) or the
    candidates are exhausted. A candidate whose body can no longer be found
    verbatim in the running text (renderer drift) is skipped defensively
    rather than aborting the whole substitution.

    Returns the possibly-substituted text and the ordered ``section_id``
    list of the swaps that were actually applied.
    """

    current_text = text
    swapped_ids: list[str] = []
    for section in candidates:
        if len(current_text) <= budget_without_warning_line(len(swapped_ids), budget):
            break
        stanza = section.replacement_body
        if stanza is None:
            stanza = "\n".join(
                fetch_stanza_lines(
                    section.selector,
                    section.when_doing_clause,
                    indent=section.indent,
                )
            )
        # Replace only the first occurrence — the block is rendered
        # exactly once in the bootstrap text.
        new_text = current_text.replace(section.body, stanza, 1)
        if new_text == current_text:
            # Defensive: block not found (renderer drift).  Skip it.
            continue
        current_text = new_text
        swapped_ids.append(section.section_id)
    return current_text, swapped_ids


def _enforce_token_budget(
    text: str,
    *,
    action: str,
    profile_block: str,
    section_block: str,
    selection_block: str = "",
    budget: int = BUDGET_DEFAULT,
) -> str:
    """Apply the NFR-001 token budget to *text* (WP05, consolidated WP04 T019).

    When ``len(text) <= budget`` the text is returned unchanged.  Over
    budget, the longest substitutable candidate is swapped for the
    canonical fetch + when-doing stanza, and the substitution loop iterates
    over the remaining candidates (longest first) until the budget holds
    or no swap candidates remain.

    Candidates are collected from ``section_block`` (one per heading, see
    :func:`_collect_section_block_candidates`) and ``profile_block`` (one
    per kind, see :func:`_collect_profile_block_candidates`), then swapped
    in by :func:`_swap_candidates_into_text`.  We do this by replacing whole
    blocks in the original ``text`` rather than re-joining, so the
    surrounding structure (Charter Context header, Policy Summary, Action
    Doctrine, References) stays byte-identical.

    Authority paths stay inline unconditionally (they are never added as
    a candidate at all — see the caller in ``bootstrap_text.py`` /
    ``compact_governance.py``).
    """

    if len(text) <= budget:
        return text

    candidates = _collect_section_block_candidates(section_block, action)
    candidates.extend(_collect_profile_block_candidates(profile_block))
    candidates.extend(_collect_selection_block_candidates(selection_block))

    if not candidates:
        # Nothing safe to substitute — return the original text so we
        # don't silently drop content.  The caller (the WP prompt
        # builder) sees over-budget text rather than missing content;
        # operators will spot the regression via the measurement script.
        return text

    # Sort longest first, ties broken on section_id for determinism. Every
    # heading/kind is now its own candidate (see _collect_section_block_
    # candidates / _collect_profile_block_candidates), so this competes on
    # each candidate's real size rather than on which side of the
    # section/profile divide it fell.
    candidates.sort(key=lambda sec: (-len(sec.body), sec.section_id))

    current_text, swapped_ids = _swap_candidates_into_text(text, candidates, budget)

    if swapped_ids:
        current_text = f"{current_text}\n\n{warning_line(len(swapped_ids), budget)}"

    return current_text
