"""Substantive-content gate for spec/plan auto-commit (issue #846).

Section-presence-only signal — there is no byte-length OR fallback.
A scaffold + arbitrary prose without the required structural rows
remains NON-substantive.

Used by ``mission create`` and ``setup-plan`` in
``specify_cli.cli.commands.agent.mission`` to decide whether
``spec.md`` / ``plan.md`` should be auto-committed.

See:
- ``kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/specify-plan-commit-boundary.md``
- ``research.md`` R7 (revised) and R8.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, Literal

from kernel.git import GitCommandError, is_tracked
from kernel.paths import repo_tree_path
from specify_cli.requirement_mapping import grammar

Kind = Literal["spec", "plan"]

# Template placeholder patterns — content composed entirely of these is NOT
# substantive. Conservative on purpose: matches the scaffolds shipped by the
# spec/plan templates without snagging real prose that incidentally includes
# square-bracket text.
_PLACEHOLDER_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\[NEEDS CLARIFICATION[^\]]*\]"),
    re.compile(r"\[e\.g\.,[^\]]*\]"),
    re.compile(r"\[FEATURE\]"),
    re.compile(r"\[###-feature[^\]]*\]"),
    re.compile(r"\[Short title\]"),
    re.compile(r"\[Measurable threshold[^\]]*\]"),
    re.compile(r"\[role\]"),
    re.compile(r"\[goal\]"),
    re.compile(r"\[benefit\]"),
    re.compile(r"\[specific capability[^\]]*\]"),
    re.compile(r"\[key interaction[^\]]*\]"),
    re.compile(r"\[data requirement[^\]]*\]"),
    re.compile(r"\[behavior[^\]]*\]"),
    re.compile(r"\[domain-specific[^\]]*\]"),
    re.compile(r"\[if applicable[^\]]*\]"),
    re.compile(r"\[Project-specific[^\]]*\]"),
    re.compile(r"\[single/web/mobile[^\]]*\]"),
    # --- #3832 / WP03 Decision 4 (T008 non-vacuity finding): documentation
    # 's own checked fields (Documentation Framework, Languages Detected,
    # Output Format, Hosting Platform) use an enumerated-choice bracket style
    # that does NOT start with "e.g.," or "NEEDS CLARIFICATION", so none of
    # the pre-existing patterns above matched it — verified empirically while
    # building T008's documentation negative fixture: without these, the
    # unedited scaffold's own primary field read as "real" content, which
    # would have made the whole-scaffold negative fixture vacuously pass
    # (NFR-005). Whole-bracket literals (``re.escape``) since the enumerated
    # choice lists are template-fixed text, not a variable "e.g." example.
    re.compile(re.escape("[Sphinx | MkDocs | Docusaurus | Jekyll | Hugo | None (starting fresh) or NEEDS CLARIFICATION]")),
    re.compile(re.escape("[Python, JavaScript, Rust, etc. - from codebase analysis]")),
    re.compile(re.escape("[HTML | Markdown | PDF or NEEDS CLARIFICATION]")),
    re.compile(re.escape("[Read the Docs | GitHub Pages | GitBook | Custom or NEEDS CLARIFICATION]")),
    # --- #3832 / WP03 Decision 4: research-plan-template.md's own checked
    # fields (Research Question, Data Sources). One literal per actual
    # bracket phrase, same conservative style as the entries above — never a
    # generic "any bracketed span" rule (NFR-005 false-negative risk).
    re.compile(r"\[Primary question\]"),
    re.compile(r"\[List search terms\]"),
    re.compile(r"\[What qualifies for review\]"),
    re.compile(r"\[What will be filtered out\]"),
    # --- #3832 / WP03 Decision 4: plan-plan-skeleton.md's own checked fields
    # (Problem Decomposition, Scope — MoSCoW, Sequencing & Prioritisation,
    # Decisions).
    re.compile(r"\[Sub-problem statement\]"),
    re.compile(r"\[Cluster name\]"),
    re.compile(r"\[SP-# or none\]"),
    re.compile(r"\[SP-#\]"),
    re.compile(r"\[High/Low\]"),
    re.compile(r"\[Why it goes first\]"),
    re.compile(r"\[Why it goes next\]"),
    re.compile(r"\[Without this, the plan fails its purpose\]"),
    re.compile(r"\[Important, painful to omit, but not fatal if deferred\]"),
    re.compile(r"\[Desirable, included only if Must/Should leave room\]"),
    re.compile(r"\[Explicitly deferred — may return in a later cut\]"),
    re.compile(r"\[Problem, drivers, constraints forcing this decision now\]"),
    re.compile(r"\[Chosen option, stated plainly\]"),
    re.compile(r"\[Why this option wins\]"),
    re.compile(r"\[Accepted trade-offs, positive and negative\]"),
)


def _strip_placeholders(s: str) -> str:
    """Remove template placeholders so their text does not count as content."""
    for pattern in _PLACEHOLDER_PATTERNS:
        s = pattern.sub("", s)
    return s


# Functional Requirements rows can show up in two source-template shapes:
# - Markdown table:  | FR-001 | <title> | <description> | <priority> | <status> |
# - Bulleted list:   - **FR-001**: <description>
# Either qualifies as long as the description is non-empty after placeholder
# stripping AND is not the literal "As a [role], I want [goal]..." scaffold.
#
# #5387: which lines count as FR rows is the requirement-ID grammar's call
# (ADR 2026-09-29-1), not a pattern of this module's own. A row qualifies
# when its lead is a local functional id the grammar declares in that shape
# (``grammar.DECLARED_TABLE_ROW`` / ``grammar.DECLARED_LIST_ITEM``), so a
# letter-suffixed (``FR-006a``) or wider (``FR-1001``) id counts, while a
# commented-out row, a dotted or compound tail, or a non-FR kind does not.


def _row_cells_have_substantive_content(
    rest: str,
    *,
    skip_leading_columns: int = 0,
    take_columns: int | None = None,
) -> bool:
    """Return True iff the pipe-delimited cells in ``rest`` carry real content."""
    columns = [c.strip() for c in rest.rstrip("|").split("|")]
    columns = columns[skip_leading_columns:]
    descriptive_cols = columns if take_columns is None else columns[:take_columns]
    return any(_is_substantive_text(c) for c in descriptive_cols)


def _table_rows_have_substantive_content(
    body: str,
    row_pattern: re.Pattern[str],
    *,
    skip_leading_columns: int = 0,
    take_columns: int | None = None,
) -> bool:
    """Return True iff any row matched by ``row_pattern`` has real content.

    Table-row-scanning core for the #3832 template-derived plan-table
    detector (Decision 3(b)); the spec check's FR rows go through
    :func:`_fr_table_row_cells` instead, with the same per-row cell check
    (:func:`_row_cells_have_substantive_content`).

    ``row_pattern`` must expose a named group ``rest`` capturing the
    pipe-delimited remainder of a row after whatever anchor prefix the
    pattern itself consumes. ``skip_leading_columns`` additionally
    drops that many leading cells from ``rest`` before descriptiveness is
    checked (used to drop a table's own id/order column when the pattern
    could not exclude it up front); ``take_columns`` then caps how many of
    the remaining cells are checked (``None`` means "all of them").
    """
    return any(
        _row_cells_have_substantive_content(
            m.group("rest"),
            skip_leading_columns=skip_leading_columns,
            take_columns=take_columns,
        )
        for m in row_pattern.finditer(body)
    )


def _is_local_fr(token: str) -> bool:
    """True when the grammar reads ``token`` as a local functional requirement id."""
    requirement_id = grammar.parse(token)
    return requirement_id is not None and requirement_id.is_functional and not requirement_id.is_foreign


def _fr_table_row_cells(line: str) -> str | None:
    """The cells after the id cell when ``line`` is a declared FR table row."""
    match = grammar.DECLARED_TABLE_ROW.match(line)
    if match is None or not _is_local_fr(match.group(1)):
        return None
    return line[match.end() :]


def _has_substantive_fr_row(body: str) -> bool:
    """Return True iff the body contains at least one populated FR row.

    Substantive means: one of the descriptive columns (Title or Description in
    a Markdown table; the single description segment in a bullet) has
    non-placeholder content. Priority / Status columns (`High`, `Open`, etc.)
    do **not** qualify a row on their own — those values are present in the
    raw scaffold rows. HTML comments are blanked first, as the grammar's own
    declared-id scan does, so a commented-out example row never counts.

    Decision 5 (#3832): this remains the SOLE ``kind="spec"`` detector —
    ``mission_check_prerequisites.py``'s guard keeps calling this function
    exactly as before.
    """
    lines = grammar.blank_html_comments(body).splitlines()
    for line in lines:
        # Table-form rows: FR-### | <title> | <description> | <priority> | <status> |
        cells = _fr_table_row_cells(line)
        if cells is not None and _row_cells_have_substantive_content(cells, take_columns=2):
            return True
        # Bullet-form rows: - **FR-###**: <description>
        desc = _extract_fr_bullet_description(line)
        if desc is not None and _is_substantive_text(desc):
            return True
    return False


def _has_substantive_research_spec(body: str) -> bool:
    """Require a populated research question and scope with native requirements."""
    from charter.missions import MissionTemplateRepository

    template = (MissionTemplateRepository.default_missions_root() / "research/templates/research-spec-template.md").read_text(encoding="utf-8")
    template_lines: dict[str, str] = {}
    for template_line in template.splitlines():
        template_match = grammar.declared_shape_patterns("research")[2].match(template_line)
        if template_match is not None:
            template_lines[template_match.group(1)] = template_line.strip()
    section = _extract_section_body(body, "Research Question & Scope")
    if section is None:
        return False
    if re.search(r"(?m)^\s*\*\*Scope\*\*:\s*$", section) is None:
        return False
    for label in ("Primary Research Question", "In Scope"):
        match = re.search(rf"(?m)^\s*(?:-\s*)?\*\*{re.escape(label)}\*\*:\s*(.+)$", section)
        if match is None or "[" in match.group(1) or not _is_substantive_text(match.group(1)):
            return False

    requirements = _extract_section_body(body, "Research Requirements")
    if requirements is None:
        return False
    found: set[str] = set()
    for line in grammar.blank_html_comments(requirements).splitlines():
        match = grammar.declared_shape_patterns("research")[2].match(line)
        if match is None or grammar.is_compound_tail(line, match.end(1)):
            continue
        requirement_id = grammar.parse(match.group(1), mission_type="research")
        if requirement_id is None or requirement_id.kind not in {"DR", "AR", "QR"}:
            continue
        description = line[match.end(1) :].lstrip("* :\t-")
        if description and "[" not in description and _is_substantive_text(description) and line.strip() != template_lines.get(requirement_id.canonical):
            found.add(requirement_id.kind)
    return found == {"DR", "AR", "QR"}


def _extract_fr_bullet_description(line: str) -> str | None:
    """Return a bullet FR description when ``line`` is a declared FR list item."""
    match = grammar.DECLARED_LIST_ITEM.match(line)
    if match is None or not _is_local_fr(match.group(1)):
        return None
    if grammar.is_compound_tail(line, match.end(1)):
        return None
    suffix = line[match.end(1) :]
    if line[: match.start(1)].endswith("**"):
        if not suffix.startswith("**"):
            return None
        suffix = suffix[2:]
    suffix = suffix.lstrip()
    if not suffix or suffix[0] not in ":-":
        return None
    desc = suffix[1:].strip()
    return desc or None


# Recognises the empty user-story scaffold ("As a , I want  so that .") that
# remains after placeholder stripping. Permits the single-letter article and
# tolerates trailing punctuation/whitespace.
_EMPTY_USER_STORY_SCAFFOLDS: Final[frozenset[str]] = frozenset(
    {
        "as a i want so that",
        "as an i want so that",
    }
)


def _is_substantive_text(raw: str) -> bool:
    """Return True iff ``raw`` has real content after placeholder stripping."""
    cleaned = _strip_placeholders(raw).strip()
    if not cleaned:
        return False
    normalized = " ".join(cleaned.rstrip(".").replace(",", " ").split()).lower()
    return normalized not in _EMPTY_USER_STORY_SCAFFOLDS


def _is_real_technical_context_value(raw: str) -> bool:
    """Return True iff a Technical Context field value is non-placeholder."""
    value = _strip_placeholders(raw).strip()
    if not value:
        return False
    # Reject pure "NEEDS CLARIFICATION" residue and other obvious placeholders
    # that survived the strip pass (e.g. a bare "NEEDS CLARIFICATION").
    return not re.fullmatch(r"NEEDS CLARIFICATION\.?", value)


def _extract_section_body(body: str, heading: str) -> str | None:
    """Return the body text under ``## {heading}`` up to the next TRUE ``##``, or None.

    ``(?!##(?!#))`` stops only at a genuine level-2 heading (``## X``, not
    followed by a third ``#``) — a naive ``(?!##)`` also matches at the start
    of a nested ``### X`` sub-heading (since ``###`` itself starts with
    ``##``), which would truncate a container's body before any nested
    ``###`` content it holds (e.g. ``research``'s ``## Methodology`` container
    holding ``### Data Sources`` — found while building T008's fixture
    matrix).
    """
    section = re.search(
        rf"##\s+{re.escape(heading)}\s*\n(?P<body>(?:[^\n]|\n(?!##(?!#)))*)",
        body,
        flags=re.DOTALL,
    )
    return section.group("body") if section is not None else None


_BOLD_FIELD_LINE: Final[re.Pattern[str]] = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?\*\*(?P<label>[^*\n]+)\*\*[ \t]*:[ \t]*(?P<val>[^\n]*)",
    flags=re.MULTILINE,
)


def _has_substantive_bulleted_sublist(remainder: str) -> bool:
    """Return True iff a bulleted sub-list beneath a bold field has real content.

    Decision 3(a) value-capture extension: some fields (``documentation``'s
    ``Build Commands``) write their value as a bulleted sub-list on the lines
    *below* the label, not inline after the colon. Scans lines immediately
    following the label until the next bold-field line or the first
    non-bullet, non-blank line (heading, prose, etc.).
    """
    for line in remainder.splitlines():
        if re.match(r"^[ \t]*\*\*[^*\n]+\*\*[ \t]*:", line):
            break
        stripped_line = line.strip()
        if not stripped_line:
            continue
        if stripped_line[0] not in "-*":
            break
        content = stripped_line[1:].strip()
        if _is_substantive_text(content):
            return True
    return False


def _is_bold_field_substantive(section_body: str, label: str, *, sub_list_valued: bool = False) -> bool:
    """Return True iff ``label``'s own bold-field value (in ``section_body``) is real.

    FR-013 (#1896): tolerates an optional leading ``-``/``*`` bullet marker
    before the bolded label.
    """
    stripped = _strip_placeholders(section_body)
    match = re.search(
        rf"^[ \t]*(?:[-*][ \t]+)?\*\*{re.escape(label)}\*\*[ \t]*:[ \t]*(?P<val>[^\n]*)",
        stripped,
        flags=re.MULTILINE,
    )
    if match is None:
        return False
    if _is_real_technical_context_value(match.group("val")):
        return True
    if not sub_list_valued:
        return False
    return _has_substantive_bulleted_sublist(stripped[match.end() :])


def _any_other_bold_field_substantive(section_body: str, *, exclude_label: str | None = None) -> bool:
    """Return True iff any bold field other than ``exclude_label`` has a real value.

    Generalizes the pre-#3832 peer-field scan (any bold field in a bold-field
    container, e.g. ``software-dev``'s Technical Context) by parameter.
    """
    stripped = _strip_placeholders(section_body)
    for field in _BOLD_FIELD_LINE.finditer(stripped):
        if exclude_label is not None and field.group("label").strip() == exclude_label:
            continue
        if _is_real_technical_context_value(field.group("val")):
            return True
    return False


_GENERIC_TABLE_ROW: Final[re.Pattern[str]] = re.compile(r"^[ \t]*\|(?P<rest>.+)\|[ \t]*$", re.MULTILINE)
_TABLE_SEPARATOR_ROW: Final[re.Pattern[str]] = re.compile(r"^[ \t]*\|(?:[ \t]*:?-{2,}:?[ \t]*\|)+[ \t]*$")


def _table_data_rows(section_body: str) -> list[str]:
    """Return the pipe-table rows in ``section_body`` that follow the header separator."""
    lines = section_body.splitlines()
    pipe_lines = [(i, ln) for i, ln in enumerate(lines) if ln.strip().startswith("|")]
    sep_idx = next((i for i, ln in pipe_lines if _TABLE_SEPARATOR_ROW.match(ln)), None)
    if sep_idx is None:
        return []
    return [ln for i, ln in pipe_lines if i > sep_idx]


def _is_table_field_substantive(body: str, heading: str) -> bool:
    """Return True iff any data row of the ``## {heading}`` table has real content.

    Decision 3(b): generalizes ``_has_substantive_fr_row``'s table half — the
    row-selection predicate is "a data row of this table" (anything after the
    header separator) instead of "starts with FR-###"; the leading column
    (an id/order value, e.g. ``SP-1``) is excluded from the descriptive scan,
    mirroring how the FR-### id column is already excluded today.
    """
    section_body = _extract_section_body(body, heading)
    if section_body is None:
        return False
    data_rows_text = "\n".join(_table_data_rows(section_body))
    if not data_rows_text:
        return False
    return _table_rows_have_substantive_content(data_rows_text, _GENERIC_TABLE_ROW, skip_leading_columns=1)


def _nested_repeatable_bodies(container_body: str, child_label_prefix: str) -> list[str]:
    """Return the bodies of every ``### {child_label_prefix}...`` heading."""
    pattern = re.compile(
        rf"^###[ \t]+{re.escape(child_label_prefix)}\S*[^\n]*\n(?P<body>(?:[^\n]|\n(?!#{{1,6}}[ \t]))*)",
        flags=re.MULTILINE | re.DOTALL,
    )
    return [m.group("body") for m in pattern.finditer(container_body)]


def _nested_named_sibling_body(container_body: str, child_label: str) -> str | None:
    """Return the body of the ONE ``### {child_label}`` heading, located by name."""
    pattern = re.compile(
        rf"^###[ \t]+{re.escape(child_label)}[ \t]*\n(?P<body>(?:[^\n]|\n(?!#{{1,6}}[ \t]))*)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(container_body)
    return match.group("body") if match is not None else None


def _is_nested_heading_field_substantive(
    body: str,
    container_heading: str,
    *,
    sub_shape: Literal["repeatable", "named_sibling"],
    child_label: str,
) -> bool:
    """Return True per Decision 3(c)'s two nested-``###``-heading sub-shapes.

    (c-i) ``repeatable``: substantive iff at least one ``### {child_label}...``
    instance nested under ``## {container_heading}`` has real content
    (``plan``'s ``Decisions`` / ``### Decision D-N``).
    (c-ii) ``named_sibling``: substantive iff the ONE nested ``###
    {child_label}`` heading — located by name, not merely nesting depth —
    has real content (``research``'s ``Data Sources`` under ``##
    Methodology``).
    """
    container_body = _extract_section_body(body, container_heading)
    if container_body is None:
        return False
    if sub_shape == "repeatable":
        return any(_any_other_bold_field_substantive(b) for b in _nested_repeatable_bodies(container_body, child_label))
    sibling_body = _nested_named_sibling_body(container_body, child_label)
    if sibling_body is None:
        return False
    return _any_other_bold_field_substantive(sibling_body)


@dataclass(frozen=True)
class _BoldField:
    """Shape (a): a specific, named bold-field label inside ``## heading``."""

    heading: str
    label: str
    sub_list_valued: bool = False


@dataclass(frozen=True)
class _AnyBoldField:
    """Shape (a): "any bold field in ``## heading``" (optionally excluding one label).

    Used where a whole heading is itself the checked field (``plan``'s
    ``Scope — MoSCoW``) or where the pre-#3832 behaviour was already "any
    other field" (``software-dev``'s Technical Context peers, NFR-003).

    ``example_label`` names a concrete, real field for operator-facing
    messages ONLY (:func:`_field_display_name`) — detection itself never
    narrows to one label. ``software-dev`` sets this to "Primary
    Dependencies" to preserve the pre-#3832 blocked-reason wording exactly
    (NFR-003); other declarations may leave it unset and fall back to a
    generic "a peer field in {heading}" description.
    """

    heading: str
    exclude_label: str | None = None
    example_label: str | None = None


@dataclass(frozen=True)
class _TableField:
    """Shape (b): a Markdown table directly under ``## heading``."""

    heading: str


@dataclass(frozen=True)
class _NestedHeadingField:
    """Shape (c): a nested ``###`` heading under ``## heading`` (see Decision 3(c))."""

    heading: str
    sub_shape: Literal["repeatable", "named_sibling"]
    child_label: str


_FieldSpec = _BoldField | _AnyBoldField | _TableField | _NestedHeadingField


@dataclass(frozen=True)
class _PlanFieldDeclaration:
    """One mission type's checked plan.md fields (Decision 1 & 2)."""

    primary: _FieldSpec
    peers: tuple[_FieldSpec, ...]


# --- Decision 1/2: per-type field declaration, template-derived metadata
# resolved once per mission type and checked in alongside the template it
# describes. NOT re-parsed from template prose at runtime (ruling #2). If a
# declaration and its template ever disagree, that is a defect caught by the
# non-vacuity fixture matrix (plan.md §Architectural Gate Non-Vacuity), not a
# silent pass.
#
# NFR-004 reconciliation for ``research``: spec.md names three fields
# ("Research Context, Methodology, Data Sources") but ``## Methodology`` is a
# pure grouping container with no bold-field/table content of its own — the
# checked set is the two fields that actually carry checkable content:
# "Research Question" (Research Context's own primary field) and
# "Data Sources" (the one nested Methodology child this design targets by
# name). See plan.md Decision 1's reconciliation note.
#
# #3830 fix round (severity 3, operator-ruled FIX-2): this table carries
# declarations ONLY for the four mission types core itself ships templates
# for. It previously also carried a "qa" entry as a proof-of-mechanism
# fixture — that has been REMOVED. Core must not carry a field declaration
# for an org-tier pack it has never seen: a real third-party ``qa`` pack's
# shipped template uses numbered headings (``## 1. Test Items``) and has no
# bold ``**Primary Item**`` field at all, so the old synthetic entry matched
# on NAME and then failed permanently on CONTENT — actively misleading
# guidance (a "missing peer field" diagnosis) for the one real custom
# mission type this whole mission was built from, instead of the honest
# "unregistered type" diagnosis an org-tier pack with no declaration at all
# gets. A mission type NOT in this table is not unsupported: see
# :func:`_resolve_declaration` below, which also checks a PACK-PROVIDED
# declaration resolved through the same template-resolution seam that
# resolves the mission type's own plan template — the #3830 FIX-1 seam. The
# proof-of-mechanism fixture that used to squat "qa" here now lives entirely
# test-side as "example-custom" (see
# ``tests/specify_cli/missions/test_substantive_gate_formats.py``), wired
# through that pack-provided seam instead of a core dict entry.
_PLAN_FIELD_DECLARATIONS: Final[dict[str, _PlanFieldDeclaration]] = {
    "software-dev": _PlanFieldDeclaration(
        primary=_BoldField(heading="Technical Context", label="Language/Version"),
        peers=(
            _AnyBoldField(
                heading="Technical Context",
                exclude_label="Language/Version",
                example_label="Primary Dependencies",
            ),
        ),
    ),
    "documentation": _PlanFieldDeclaration(
        primary=_BoldField(heading="Technical Context", label="Documentation Framework"),
        peers=(
            _BoldField(heading="Technical Context", label="Languages Detected"),
            _BoldField(heading="Technical Context", label="Output Format"),
            _BoldField(heading="Technical Context", label="Hosting Platform"),
            _BoldField(heading="Technical Context", label="Build Commands", sub_list_valued=True),
        ),
    ),
    "research": _PlanFieldDeclaration(
        primary=_BoldField(heading="Research Context", label="Research Question"),
        peers=(_NestedHeadingField(heading="Methodology", sub_shape="named_sibling", child_label="Data Sources"),),
    ),
    "plan": _PlanFieldDeclaration(
        primary=_TableField(heading="Problem Decomposition"),
        peers=(
            _AnyBoldField(heading="Scope — MoSCoW"),
            _TableField(heading="Sequencing & Prioritisation"),
            _NestedHeadingField(heading="Decisions", sub_shape="repeatable", child_label="Decision D-"),
        ),
    ),
}


# ---------------------------------------------------------------------------
# #3830 FIX-1 (severity-4 blocker): pack-provided field-declaration seam.
#
# A mission type shipped by an org pack has no way to make its own name
# appear in ``_PLAN_FIELD_DECLARATIONS`` above without a PR against spec-kitty
# core — that reproduces the exact "custom mission types are second-class
# citizens" defect this mission is named for, via a hardcoded allowlist
# instead of the single ``mission_type != "software-dev"`` guard the
# operator rejected in this mission's own Decision 1.
#
# The fix: an org pack ships a ``plan-field-declaration.yaml`` file
# alongside its ``plan-template.md`` (same ``missions/{mission}/templates/``
# directory) and it is discovered through :func:`specify_cli.runtime.resolver
# .resolve_template` — the SAME 6-tier precedence chain (override > legacy >
# org > global-mission > global > package-default) that resolves the plan
# template itself (:func:`_resolve_plan_template` in
# ``mission_setup_plan.py``). This genuinely honours FR-006's "derive fields
# from the mission type's own resolved plan template": the declaration is
# resolved through the identical seam, scoped to the identical mission/tier,
# as the template it describes.
#
# Org precedence for this asset is deliberately first-declared-root-wins
# (``resolve_template``'s org loop returns on the first configured org root
# that has the file) -- consistent with the ``plan-template.md`` it rides
# alongside, and deliberately UNLIKE ``expected-artifacts.yaml``, which
# resolves last-match across configured org roots.
#
# Core-shipped types (the four keys above) are checked FIRST and never touch
# this seam in the common path — they keep their declarations exactly where
# they live today (NFR-003: no behaviour change for existing types).
# ---------------------------------------------------------------------------

_PACK_DECLARATION_ASSET_NAME: Final[str] = "plan-field-declaration.yaml"


class _PackDeclarationError(ValueError):
    """A pack-provided ``plan-field-declaration.yaml`` is present but malformed.

    Raised (not silently swallowed) so a declared-but-broken pack fails
    loudly with a diagnosable reason — mirroring the resolver's own
    "declared but broken org pack still warns" posture — rather than
    masquerading as an ordinary undeclared-type fail-closed result.
    """


# #3832 fold: per-kind allow-sets for unknown-key rejection, parity with
# expected-artifacts.yaml's ``extra="forbid"`` posture -- a typo'd optional
# key (e.g. ``labell``) must fail loud, not be silently ignored via
# ``dict.get``.
_COMMON_FIELD_KEYS: Final[frozenset[str]] = frozenset({"kind", "heading"})
_FIELD_KIND_ALLOWED_KEYS: Final[dict[str, frozenset[str]]] = {
    "bold_field": frozenset({"label", "sub_list_valued"}),
    "any_bold_field": frozenset({"exclude_label", "example_label"}),
    "table_field": frozenset(),
    "nested_heading_field": frozenset({"sub_shape", "child_label"}),
}


def _reject_unknown_field_keys(entry: dict[str, object], kind: str) -> None:
    """Raise :class:`_PackDeclarationError` if ``entry`` has keys outside ``kind``'s allow-set."""
    allowed = _COMMON_FIELD_KEYS | _FIELD_KIND_ALLOWED_KEYS[kind]
    unknown = sorted(set(entry) - allowed)
    if unknown:
        raise _PackDeclarationError(f"field entry {entry!r} has unknown key(s) {unknown!r} for kind {kind!r}")


def _field_spec_from_mapping(entry: object) -> _FieldSpec:
    """Parse one YAML mapping into a :data:`_FieldSpec` (T-shape dispatch)."""
    if not isinstance(entry, dict):
        raise _PackDeclarationError(f"field entry must be a mapping, got {entry!r}")
    kind = entry.get("kind")
    heading = entry.get("heading")
    if not isinstance(heading, str) or not heading.strip():
        raise _PackDeclarationError(f"field entry {entry!r} is missing a non-blank 'heading'")
    if kind == "bold_field":
        _reject_unknown_field_keys(entry, kind)
        label = entry.get("label")
        if not isinstance(label, str) or not label.strip():
            raise _PackDeclarationError(f"bold_field entry {entry!r} is missing a non-blank 'label'")
        return _BoldField(heading=heading, label=label, sub_list_valued=bool(entry.get("sub_list_valued", False)))
    if kind == "any_bold_field":
        _reject_unknown_field_keys(entry, kind)
        exclude_label = entry.get("exclude_label")
        example_label = entry.get("example_label")
        return _AnyBoldField(
            heading=heading,
            exclude_label=exclude_label if isinstance(exclude_label, str) else None,
            example_label=example_label if isinstance(example_label, str) else None,
        )
    if kind == "table_field":
        _reject_unknown_field_keys(entry, kind)
        return _TableField(heading=heading)
    if kind == "nested_heading_field":
        _reject_unknown_field_keys(entry, kind)
        sub_shape = entry.get("sub_shape")
        if sub_shape not in ("repeatable", "named_sibling"):
            raise _PackDeclarationError(f"nested_heading_field entry {entry!r} has invalid 'sub_shape' {sub_shape!r}")
        child_label = entry.get("child_label")
        if not isinstance(child_label, str) or not child_label.strip():
            raise _PackDeclarationError(f"nested_heading_field entry {entry!r} is missing a non-blank 'child_label'")
        return _NestedHeadingField(heading=heading, sub_shape=sub_shape, child_label=child_label)
    raise _PackDeclarationError(f"field entry {entry!r} has unknown or missing 'kind' {kind!r}")


_TOP_LEVEL_DECLARATION_KEYS: Final[frozenset[str]] = frozenset({"primary", "peers"})


def _plan_field_declaration_from_yaml(path: Path) -> _PlanFieldDeclaration:
    """Parse a pack-provided ``plan-field-declaration.yaml`` file."""
    import yaml  # noqa: PLC0415 — lazy: keeps a YAML dependency off this module's plain import path

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _PackDeclarationError(f"{path} could not be read as YAML: {exc}") from exc
    if not isinstance(raw, dict) or "primary" not in raw:
        raise _PackDeclarationError(f"{path} must be a mapping with a 'primary' field entry")
    unknown_top_level = sorted(set(raw) - _TOP_LEVEL_DECLARATION_KEYS)
    if unknown_top_level:
        raise _PackDeclarationError(f"{path} has unknown top-level key(s) {unknown_top_level!r}")
    primary = _field_spec_from_mapping(raw["primary"])
    raw_peers = raw.get("peers", [])
    if not isinstance(raw_peers, list) or not raw_peers:
        raise _PackDeclarationError(f"{path} 'peers' must be a non-empty list")
    peers = tuple(_field_spec_from_mapping(peer) for peer in raw_peers)
    return _PlanFieldDeclaration(primary=primary, peers=peers)


def _pack_provided_declaration(mission_type: str, project_dir: Path) -> _PlanFieldDeclaration | None:
    """Discover ``mission_type``'s pack-provided plan field declaration, if any.

    Resolved through :func:`specify_cli.runtime.resolver.resolve_template` —
    the exact seam that resolves ``mission_type``'s own plan template.
    Returns ``None`` when no tier has the asset (the ordinary case for every
    mission type that isn't shipping its own declaration).
    """
    from specify_cli.runtime.resolver import resolve_template  # noqa: PLC0415 — lazy: keeps runtime off this module's load

    try:
        resolution = resolve_template(_PACK_DECLARATION_ASSET_NAME, project_dir, mission=mission_type)
    except FileNotFoundError:
        return None
    # resolve_template's tiers 1b/2/5 (global override, legacy, global
    # non-mission) are mission-agnostic -- a single global
    # plan-field-declaration.yaml at one of those tiers would otherwise gate
    # EVERY undeclared mission type's plan against one type's fields. Only a
    # mission-scoped hit (tiers 1a/3/4/6, all of which include
    # "/missions/{mission_type}/" in the resolved path) is a genuine
    # declaration for this mission type.
    if f"/missions/{mission_type}/" not in resolution.path.as_posix():
        return None
    return _plan_field_declaration_from_yaml(resolution.path)


def _resolve_declaration(mission_type: str, project_dir: Path | None) -> _PlanFieldDeclaration | None:
    """Return ``mission_type``'s field declaration: built-in first, then pack-provided.

    ``project_dir`` is optional so every pre-#3830 caller that does not pass
    it keeps its exact prior behaviour (built-in lookup only, fails closed
    for anything else) — the pack-provided seam is additive.
    """
    declaration = _PLAN_FIELD_DECLARATIONS.get(mission_type)
    if declaration is not None:
        return declaration
    if project_dir is None:
        return None
    return _pack_provided_declaration(mission_type, project_dir)


def _field_container_heading(spec: _FieldSpec) -> str:
    """Return the top-level ``##`` heading a field's presence check reads."""
    return spec.heading


def _field_display_name(spec: _FieldSpec) -> str:
    """Return the human-readable name for ``spec``, used in diagnostic messages."""
    if isinstance(spec, _BoldField):
        return spec.label
    if isinstance(spec, _AnyBoldField):
        return spec.example_label if spec.example_label is not None else f"a peer field in {spec.heading}"
    if isinstance(spec, _TableField):
        return spec.heading
    return spec.child_label if spec.sub_shape == "named_sibling" else spec.heading


def _is_field_substantive(body: str, spec: _FieldSpec) -> bool:
    """Dispatch a single declared field to its shape-(a)/(b)/(c) detector (T009)."""
    if isinstance(spec, _BoldField):
        section_body = _extract_section_body(body, spec.heading)
        if section_body is None:
            return False
        return _is_bold_field_substantive(section_body, spec.label, sub_list_valued=spec.sub_list_valued)
    if isinstance(spec, _AnyBoldField):
        section_body = _extract_section_body(body, spec.heading)
        if section_body is None:
            return False
        return _any_other_bold_field_substantive(section_body, exclude_label=spec.exclude_label)
    if isinstance(spec, _TableField):
        return _is_table_field_substantive(body, spec.heading)
    return _is_nested_heading_field_substantive(
        body,
        spec.heading,
        sub_shape=spec.sub_shape,
        child_label=spec.child_label,
    )


def _is_plan_substantive_for_type(body: str, mission_type: str, *, project_dir: Path | None = None) -> bool:
    """Return True iff ``body`` satisfies ``mission_type``'s primary+peer combination rule.

    Combination rule (unchanged from the pre-#3832 Language/Version-plus-a-peer
    semantics): the template's FIRST scaffolded field is primary and must be
    substantive, PLUS at least one peer field must also be substantive.

    A mission type with NO declaration at all — neither built-in nor
    pack-provided (:func:`_resolve_declaration`, ``project_dir``'s seam) —
    fails closed (T002(b)) — this is a deliberate design choice, not an
    omission: NFR-005 forbids a "neutral pass that always returns True", so
    an undeclared type cannot silently pass. ``project_dir`` is optional so
    callers that never pass it keep pre-#3830 built-in-only behaviour.
    """
    declaration = _resolve_declaration(mission_type, project_dir)
    if declaration is None:
        return False
    if not _is_field_substantive(body, declaration.primary):
        return False
    return any(_is_field_substantive(body, peer) for peer in declaration.peers)


class _FieldStatus(Enum):
    SUBSTANTIVE = "substantive"
    SECTION_ABSENT = "section_absent"
    PLACEHOLDER_ONLY = "placeholder_only"


def _field_status(body: str, spec: _FieldSpec) -> _FieldStatus:
    """Return the tri-state diagnosis for ``spec`` used to build a gap message."""
    if _extract_section_body(body, _field_container_heading(spec)) is None:
        return _FieldStatus.SECTION_ABSENT
    return _FieldStatus.SUBSTANTIVE if _is_field_substantive(body, spec) else _FieldStatus.PLACEHOLDER_ONLY


def _undeclared_mission_type_gap(mission_type: str) -> str:
    """T002(b): the distinct diagnostic for a resolvable template with no declaration."""
    return (
        f"No field declaration is registered for mission type {mission_type!r}; "
        "plan.md's substantive-content gate cannot evaluate this mission type "
        "until a declaration entry is added for it."
    )


def _no_peer_gap_message(container: str, primary_name: str, peers: tuple[_FieldSpec, ...]) -> str:
    peer_names = ", ".join(_field_display_name(p) for p in peers)
    hint = (
        " (bulleted '- **Field**: value' fields are accepted — populate at least one peer field)"
        if any(isinstance(p, (_BoldField, _AnyBoldField)) for p in peers)
        else ""
    )
    return f"{container} has **{primary_name}** but no peer field with non-placeholder content{hint}. Checked peer(s): {peer_names}."


def describe_technical_context_gap(
    body: str, mission_type: str = "software-dev", *, project_dir: Path | None = None
) -> str | None:
    """Return a human reason when ``mission_type``'s primary+peer plan fields fail the gate.

    Decision 1/2 (#3832): generalized off the SAME per-type field declaration
    ``is_substantive`` now uses (T002/T007) — no longer hardcoded to
    ``software-dev``'s "Technical Context"/"Language/Version" (the default
    argument preserves that exact behaviour for existing single-argument
    callers). The SELECTION of which diagnostic to emit tracks the real
    shape-(a)/(b)/(c) failure via :func:`_field_status` — not a
    bold-field-only regex re-run against every type's fields regardless of
    their declared shape (a naive label-only substitution would always
    misdiagnose a shape-(b)/(c) peer failure as "primary missing").

    Returns ``None`` when the gate is substantive (no gap), or one of three
    diagnostic strings otherwise: the container section is absent; the
    primary field is missing or placeholder-only; or peer fields exist but
    none carries non-placeholder content. A mission type with NO declaration
    anywhere (built-in or, when ``project_dir`` is given, pack-provided —
    #3830 FIX-1) gets its own distinct diagnostic (T002(b)) rather than
    either of the above.
    """
    declaration = _resolve_declaration(mission_type, project_dir)
    if declaration is None:
        return _undeclared_mission_type_gap(mission_type)

    primary_status = _field_status(body, declaration.primary)
    primary_name = _field_display_name(declaration.primary)
    container = _field_container_heading(declaration.primary)

    if primary_status is _FieldStatus.SECTION_ABSENT:
        return f"{container} section is missing from plan.md."
    if primary_status is _FieldStatus.PLACEHOLDER_ONLY:
        return f"{container} **{primary_name}** is missing or carries only placeholder content."
    if any(_field_status(body, peer) is _FieldStatus.SUBSTANTIVE for peer in declaration.peers):
        return None
    return _no_peer_gap_message(container, primary_name, declaration.peers)


def describe_plan_field_requirements(
    mission_type: str, *, project_dir: Path | None = None
) -> tuple[str, str, str] | None:
    """Return ``(container_heading, primary_field_name, example_peer_name)``.

    T007: the single source ``mission_setup_plan.py``'s operator-facing
    scaffold/blocked-reason messages read from — so those message sites never
    carry their own independently-maintained heading/label literal alongside
    the Decision 1/2 declaration. Returns ``None`` when ``mission_type`` has
    no declaration anywhere — built-in or, when ``project_dir`` is given,
    pack-provided (#3830 FIX-1) — a fail-closed case callers must NOT paper
    over with a generic field-name message (see the compounding-diagnostic
    fix in ``mission_setup_plan.py``).
    """
    declaration = _resolve_declaration(mission_type, project_dir)
    if declaration is None:
        return None
    primary_name = _field_display_name(declaration.primary)
    example_peer = _field_display_name(declaration.peers[0]) if declaration.peers else primary_name
    return _field_container_heading(declaration.primary), primary_name, example_peer


def is_pristine_scaffold(content: str, template_content: str) -> bool:
    """Return True iff ``content`` is byte-identical to a freshly-copied scaffold.

    FR-009 / #2566: distinguishes the FIRST happy-path scaffold write (an
    artifact that has never been touched since the template was copied) from
    populated-but-insufficient content (someone started editing but has not
    yet filled in the required substantive fields). The comparison is
    intentionally strict byte-equality: any edit — even whitespace-only — moves
    the file out of "pristine" and into the (still exercised)
    populated-but-insufficient path, which stays ``blocked`` (K-1 / NFR-005).

    Args:
        content: The current on-disk content of the artifact being checked.
        template_content: The content of the template that was copied to
            scaffold the artifact.

    Returns:
        True iff ``content == template_content``.
    """
    return content == template_content


def is_substantive(
    file_path: Path, kind: Kind, *, mission_type: str = "software-dev", project_dir: Path | None = None
) -> bool:
    """Section-presence-only substantive-content gate.

    Args:
        file_path: Path to the artifact file (spec.md or plan.md).
        kind: ``"spec"`` or ``"plan"``.
        mission_type: Selects the research question/scope and DR/AR/QR gate
            for research specs, or the per-type field declaration for plans.
            Defaults to ``"software-dev"`` for existing callers.
        project_dir: Repository/project root used to discover a
            PACK-PROVIDED field declaration (#3830 FIX-1) for a
            ``mission_type`` with no built-in entry, resolved through the
            SAME template-resolution seam that resolves ``mission_type``'s
            plan template. Optional — omitted, this keeps pre-#3830
            built-in-only behaviour.

    Returns:
        True iff the file contains at least one structurally-required,
        non-placeholder content row for the given artifact kind. A
        ``mission_type`` with no registered field declaration anywhere
        (built-in or pack-provided) fails closed (returns ``False`` — see
        :func:`_is_plan_substantive_for_type`).

    Raises:
        ValueError: If ``kind`` is not one of ``{"spec", "plan"}``.
        OSError: If the file cannot be read.
    """
    body = file_path.read_text(encoding="utf-8")
    if kind == "spec":
        if mission_type == "research":
            return _has_substantive_research_spec(body)
        return _has_substantive_fr_row(body)
    if kind == "plan":
        return _is_plan_substantive_for_type(body, mission_type, project_dir=project_dir)
    raise ValueError(f"Unknown kind: {kind!r}")


def _git_commit_check_context(file_path: Path, repo_root: Path) -> tuple[Path, str] | None:
    """Return ``(git_cwd, tree_path)`` for committedness checks, or ``None``.

    Thin wrapper over the shared kernel seam :func:`kernel.paths.repo_tree_path`
    that maps the "file outside the repo" case (``ValueError``) to ``None`` — the
    sentinel ``is_committed`` reads as "cannot check, treat as uncommitted". The
    worktree-strip and forward-slash normalization (#2836) live in the kernel so
    this module and ``mission_finalize`` cannot drift.
    """
    try:
        return repo_tree_path(file_path, repo_root)
    except ValueError:
        return None


def _head_carries_path(git_cwd: Path, tree_path: str) -> bool:
    """Return True iff ``tree_path`` is tracked AND present at ``HEAD``."""
    try:
        if not is_tracked(git_cwd, tree_path):
            return False
        subprocess.run(
            ["git", "-C", str(git_cwd), "cat-file", "-e", f"HEAD:{tree_path}"],
            check=True,
            capture_output=True,
        )
        return True
    except (GitCommandError, subprocess.CalledProcessError, FileNotFoundError):
        # Committedness probe: any git failure reads as "not committed" (the
        # caller's documented "cannot check, treat as uncommitted").
        return False


def is_committed(
    file_path: Path,
    repo_root: Path,
    *,
    diagnostics: list[str] | None = None,
) -> bool:
    """Return True iff ``file_path`` is committed on the git surface it lives on.

    Single-surface check (FR-011): a file is "committed" iff it is tracked AND
    present at the ``HEAD`` of the git surface it physically resides on. The
    surface is derived from ``file_path`` itself via
    :func:`_git_commit_check_context` — a linked worktree (``.worktrees/<name>/``)
    is checked against that worktree's branch tree, the primary checkout against
    primary ``HEAD``.

    This collapses the former 3-leg OR (coordination-ref / HEAD /
    primary-target-branch). The OR was load-bearing only when a caller fed the
    PRIMARY-checkout path while the spec lived solely on the coordination
    branch — but the sole non-test caller (setup-plan) already feeds the
    READ-resolved ``spec_file``: since #2106 (gate-read-surface-completion)
    re-partitioned SPEC as a primary-kind, the caller now resolves SPEC to the
    PRIMARY dir for ALL topologies — both the coord-topology case (the coord
    worktree carries status events only, no planning artifacts) and the #1718
    create-window. The #1848 coord-deleted case never
    reaches this function — the read-path resolution upstream raises
    ``CoordinationBranchDeleted`` (a ``StatusReadPathNotFound``) and the caller
    exits before the commit check. So the read-resolved surface converges with
    the retired OR on every reachable cell (proven via the parametrized
    envelope + a live repro, NFR-003 behaviour-preserving).

    Args:
        file_path: The file to check for commit presence.
        repo_root: The repository root used to derive ``file_path``'s git
            surface (worktree-vs-primary) for the ``HEAD`` check.
        diagnostics: Optional sink — when provided, one human-readable line
            describing the surface checked is appended, annotated with
            hit/miss.

    Returns:
        ``True`` iff ``file_path`` is tracked and present at ``HEAD`` of its own
        git surface.
    """
    check_context = _git_commit_check_context(file_path, repo_root)
    if check_context is None:
        if diagnostics is not None:
            diagnostics.append(f"file outside repo_root {repo_root}: not committed")
        return False
    git_cwd, tree_path = check_context

    head_hit = _head_carries_path(git_cwd, tree_path)
    if diagnostics is not None:
        diagnostics.append(f"HEAD:{tree_path} (cwd={git_cwd}): {'hit' if head_hit else 'miss'}")
    return head_hit


# Kind: demoted — used only within this module; no cross-module src/
# from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
__all__ = [
    "describe_plan_field_requirements",
    "describe_technical_context_gap",
    "is_committed",
    "is_pristine_scaffold",
    "is_substantive",
]
