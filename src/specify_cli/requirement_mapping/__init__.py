"""Structured requirement-to-WP mapping validation and frontmatter helpers.

The LLM registers mappings via ``spec-kitty agent tasks map-requirements``
which writes ``requirement_refs`` directly into each WP file's YAML
frontmatter.  ``finalize-tasks`` reads from frontmatter first (primary),
falling back to tasks.md text parsing for pre-API projects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, NamedTuple, TypedDict

from specify_cli.requirement_mapping import grammar as grammar
from specify_cli.requirement_mapping.grammar import (
    FAILING_REASONS as FAILING_REASONS,
)
from specify_cli.requirement_mapping.grammar import (
    FOREIGN_QUALIFIED as FOREIGN_QUALIFIED,
)
from specify_cli.requirement_mapping.grammar import (
    MALFORMED as MALFORMED,
)
from specify_cli.requirement_mapping.grammar import (
    MALFORMED_DECLARED_LEAD as MALFORMED_DECLARED_LEAD,
)
from specify_cli.requirement_mapping.grammar import (
    RULE_TEXT as RULE_TEXT,
)
from specify_cli.requirement_mapping.grammar import (
    UNKNOWN_SPEC_ID as UNKNOWN_SPEC_ID,
)
from specify_cli.requirement_mapping.grammar import (
    Accepted as Accepted,
)
from specify_cli.requirement_mapping.grammar import (
    RefVerdict as RefVerdict,
)
from specify_cli.requirement_mapping.grammar import (
    Rejected as Rejected,
)
from specify_cli.requirement_mapping.grammar import (
    RequirementId as RequirementId,
)
from specify_cli.requirement_mapping.grammar import (
    classify as classify,
)

# The package re-exports the grammar's public API (plan.md: "re-exports
# (import path unchanged)"), so ``specify_cli.requirement_mapping.classify``
# etc. resolve without reaching into the submodule. Several of these names
# (the verdict machinery: Accepted, Rejected, RefVerdict, classify, the three
# reason constants, FAILING_REASONS; the lint-only MALFORMED_DECLARED_LEAD
# and RULE_TEXT) have no consumer inside this WP -- finalize/map-requirements/
# the runtime wire them in WP02-WP05 (T003's Dead-symbol note). The re-export
# above is what keeps ``tests/architectural/test_no_dead_symbols.py`` green
# in the meantime; ``canonical``, ``find_all``, ``tokenize_refs``,
# ``DECLARED_SHAPE_PATTERNS``, ``blank_html_comments`` and ``parse`` already
# have real call sites below and need no such re-export.

# --- C-001: the grammar (src/specify_cli/requirement_mapping/grammar.py) is
# the ONE place that defines a requirement-ID pattern. Everything below reads
# ids through it; no pattern literal is re-declared here.
#
# Two names are kept importable for backward compatibility (T002's surveyed
# import surface: ``_DECLARED_ID_PATTERNS`` and ``_REF_FIND_PATTERN`` are
# imported directly by ``tests/specify_cli/test_bare_prose_false_negative_sample.py``):
#
# - ``_DECLARED_ID_PATTERNS`` is simply an alias of
#   :data:`grammar.DECLARED_SHAPE_PATTERNS` (now SC- and suffix-aware).
# - ``_REF_FIND_PATTERN`` is the grammar-generated LEGACY-COMPAT alias
#   (unqualified, unsuffixed, no compound check) -- kept ONLY so that frozen
#   test's own ``finditer``/``group(0)`` scan keeps its pinned figures.
#   Production code below never uses it; production uses
#   :func:`grammar.find_all`.
_DECLARED_ID_PATTERNS = grammar.DECLARED_SHAPE_PATTERNS
_REF_FIND_PATTERN = grammar._LEGACY_REF_FIND_PATTERN

# --- #3394: declared-requirement scoping -----------------------------------
#
# A spec.md may legitimately CITE a foreign requirement id in prose (e.g.
# "...easy to miss, see FR-021's default-pack materialization") without that
# citation being a requirement THIS spec declares. ``_REF_FIND_PATTERN``
# alone can't distinguish a citation from a declaration -- it matches both,
# which is #3394: a WP-coverage-eligible spec's own three requirements pass,
# but a mid-sentence citation of another mission's already-shipped FR gets
# treated as an FR this spec must also route to a work package.
#
# A requirement is "declared" (not merely cited) when it opens the line as
# one of four canonical shapes seen across the spec-template corpus
# (kitty-specs/) and the test-fixture corpus alike: the id column of a
# markdown table row (``| FR-001 | ... |``), a heading naming the id
# (``### FR-001`` / ``### FR-001: Title``), a bulleted/numbered list item
# (``- FR-001: ...``, ``- **FR-001**: ...``, ``1. FR-001 ...``), or a bold id
# leading a bare paragraph (``**FR-001 — Title.** body...``). A prose sentence
# that merely *mentions* an id in passing -- not at the start of a table
# cell, heading, bullet, or bold span -- matches none of the four and is
# correctly excluded.
# The id cell itself is sometimes bold (``| **FR-001** | ... |``, common
# across kitty-specs/) or struck through to mark a retired requirement
# (``| ~~FR-006~~ | ...``, e.g. mission retrospective-durable-home-01KVYM1W) --
# optional leading/trailing ``**``/``~~`` around the id, either or both.
#
# Corpus-validation note (#3394 review F2): the four shapes above and the
# decision NOT to hard-fail when a document matches none of them were
# validated against the 366-spec ``kitty-specs/`` corpus during the #3394 Op
# (``01KZYBXE5G1Y8J4C5FAYV1FKN1``). A stricter, hard-failing prototype (refuse
# whenever raw ``FR``/``NFR``/``C`` tokens are present but none match a
# declared shape) was measured at roughly a 6% false-positive rate against
# that corpus and rejected for that reason; the prototype and its measurement
# were not preserved outside the Op transcript, so this sentence is the
# durable record of the number and the rationale. See
# :func:`find_undeclared_requirement_citations` below for the soft,
# non-blocking warning shipped instead of that rejected hard-fail layer.
#
# WP01 (requirement-id-grammar): every shape now also recognises SC and a
# single lowercase letter suffix (FR-003), and the scan runs on
# ``grammar.blank_html_comments(text)`` first, so a declaration inside an
# HTML comment is not declared (data-model.md "Declared-ID set"). A candidate
# lead whose text is a compound (``C-007-mission``) is rejected rather than
# silently truncated to a shorter well-formed prefix.


def _declared_ids(spec_content: str) -> set[str]:
    """Ids written as a table row, an id-naming heading, or a bold-led definition.

    Doc-wide (not scoped to a ``Functional Requirements``-style heading):
    real specs also declare requirements with no enclosing section heading at
    all (e.g. a bare ``- **FR-001**: ...`` directly under the spec title), so
    scoping extraction to a heading boundary would silently drop those.

    Only the FIRST id on a line is captured (the ``break`` below stops at the
    first pattern match per line) -- this is load-bearing, not an oversight:
    it is what excludes a citation of another id inside a table row's own
    description cell from being counted as a second declaration. The trade-off
    is that a genuine multi-id declaration line (e.g.
    ``- **FR-001 / FR-002**: both must hold.``) silently loses every id after
    the first; a corpus scan (#3394 Op) found 16 such multi-id, non-table
    declaration lines across kitty-specs/*/spec.md, and every lost id in all 16
    was also declared via a table row elsewhere in the same spec, so measured
    loss is zero today. Do not "fix" the ``break`` without re-running that scan
    -- removing it would let a table row's description-cell citations leak back
    in as declarations, reintroducing #3394.
    """
    found: set[str] = set()
    blanked = grammar.blank_html_comments(spec_content)
    for line in blanked.splitlines():
        for pattern in _DECLARED_ID_PATTERNS:
            match = pattern.match(line)
            if match is None:
                continue
            if grammar.is_compound_tail(line, match.end(1)):
                continue
            canonical_id = grammar.canonical(match.group(1))
            if canonical_id is not None:
                found.add(canonical_id)
            break
    return found


_BARE_PROSE_KINDS: frozenset[str] = frozenset({"FR", "NFR", "C"})


def _unqualified_unsuffixed_ids(text: str) -> list[grammar.RequirementId]:
    """Bare-prose candidate ids: unqualified, unsuffixed FR/NFR/C only (C-009).

    A qualified citation (``slug#FR-001``) is never a candidate; SC and
    letter-suffixed ids stay out of the bare-prose candidate set, exactly as
    today -- only the compound-token exclusion (``FR-008-mandated``) can
    shrink it further (C-009).
    """
    return [
        requirement_id
        for requirement_id in grammar.find_all(text, spec_scan=True)
        if requirement_id.mission is None and requirement_id.suffix is None and requirement_id.kind in _BARE_PROSE_KINDS
    ]


def _raw_ref_tokens(text: str) -> set[str]:
    """Every unqualified, unsuffixed FR-/NFR-/C- id anywhere in ``text`` (pre-#3394 scan)."""
    return {requirement_id.canonical for requirement_id in _unqualified_unsuffixed_ids(text)}


def _is_requirement_heading(line: str) -> bool:
    """True for a markdown heading whose text mentions "requirement" (any case)."""
    stripped = line.lstrip()
    return stripped.startswith("#") and "requirement" in stripped.lower()


def _requirement_named_sections(spec_content: str) -> list[tuple[str, str]]:
    """``(heading_text, body)`` for every heading section naming "requirement".

    A section's body runs from immediately after its heading line to the next
    heading line (any level) or end of document -- mirrors how a human reader
    would scope "the Functional Requirements section".
    """
    lines = spec_content.splitlines()
    heading_idxs = [i for i, line in enumerate(lines) if line.lstrip().startswith("#")]
    sections: list[tuple[str, str]] = []
    for pos, idx in enumerate(heading_idxs):
        heading_line = lines[idx]
        if not _is_requirement_heading(heading_line):
            continue
        end = heading_idxs[pos + 1] if pos + 1 < len(heading_idxs) else len(lines)
        heading_text = heading_line.lstrip("#").strip()
        sections.append((heading_text, "\n".join(lines[idx + 1 : end])))
    return sections


def _undeclared_citation_warning(tokens: list[str], *, scope: str) -> str:
    joined = ", ".join(tokens)
    return (
        f"{scope} mentions requirement-shaped token(s) ({joined}) that matched none of the "
        "recognized declared shapes (table row / id-naming heading / bulleted item / bold-led "
        "paragraph) -- none of them count toward FR coverage. If these ARE this spec's own "
        "requirements, rewrite them in one of the recognized shapes; if they are citations of "
        "another mission's requirement, no action is needed."
    )


def find_undeclared_requirement_citations(spec_content: str) -> list[str]:
    """#3394 review F1: soft, non-blocking signal for the declared-shape-miss case.

    ``_declared_ids`` recognizes four declaration shapes (table row, heading,
    bullet, bold paragraph) and that scoping is deliberately NOT widened here
    (#3394 is settled). But a spec whose requirements are written in NONE of
    those shapes -- e.g. bare, unbulleted, unbolded sentences like "FR-001
    must hold. FR-002 too." -- now silently yields zero declared ids, and
    ``finalize-tasks``/``map-requirements`` then report full coverage with
    nothing to show for it (the same "reports success while measuring
    nothing" shape the project's ledger flags elsewhere).

    This detector does not change what counts as *declared*; it only flags,
    non-blockingly, when raw ref-shaped tokens (the pre-#3394
    ``_REF_FIND_PATTERN`` scan) are present but produced zero declared ids --
    either across the WHOLE document, or within a heading section whose title
    mentions "requirement" (e.g. "Functional Requirements", "Non-Functional
    Requirements").

    Returns:
        Human-readable warning message(s) -- empty when every raw token
        matched a declared shape, or when there were no raw tokens at all.
        Callers surface these as a non-blocking warning (console + a JSON
        field), never as a gate failure.
    """
    declared = _declared_ids(spec_content)
    doc_raw_tokens = _raw_ref_tokens(spec_content)
    if doc_raw_tokens and not declared:
        return [_undeclared_citation_warning(sorted(doc_raw_tokens), scope="spec.md")]

    warnings: list[str] = []
    for heading_text, section in _requirement_named_sections(spec_content):
        section_raw_tokens = _raw_ref_tokens(section)
        if section_raw_tokens and not _declared_ids(section):
            warnings.append(_undeclared_citation_warning(sorted(section_raw_tokens), scope=f"The {heading_text!r} section"))
    return warnings


class BareProseCandidate(NamedTuple):
    """One requirement-named section's undeclared, bare-prose id candidates."""

    section_heading: str
    ids: list[str]


BareProseResult = list[BareProseCandidate]


def find_bare_prose_requirement_ids(spec_content: str) -> BareProseResult:
    """#3396: a NEW per-token, per-line, document-scoped blocking predicate.

    ``find_undeclared_requirement_citations`` (#3395, above) fires only when a
    scope's *own* declared-id set is entirely empty (``section_raw_tokens and
    not _declared_ids(section)``) -- it is structurally blind to a section
    that declares SOME requirements correctly and writes OTHERS as bare,
    unbulleted, unbolded prose in that same section (#3396's exact repro: a
    declared ``NFR-001`` table row alongside bare-prose ``FR-001``/``FR-002``
    sentences under one "Functional Requirements" heading). Verified
    directly: ``find_undeclared_requirement_citations`` returns ``[]``
    against that repro, because the section's declared set is non-empty
    (``NFR-001`` is declared). This function is a distinct, NEW predicate --
    not a promotion of that one -- asking a finer-grained, per-line question
    instead: "does *this specific line* declare its own token, and if not, is
    that token declared *anywhere in the document*?"

    Algorithm (mirrors plan.md's "Architecture" section literally):

    1. ``document_declared = _declared_ids(spec_content)`` -- the existing,
       unmodified, whole-document declared-id set (C-001: the four
       ``_DECLARED_ID_PATTERNS`` shapes are not touched or widened here).
    2. For each ``(heading_text, body)`` in ``_requirement_named_sections`` --
       heading-scoping reused byte-identical (C-008: ``_is_requirement_heading``
       is NOT broadened in this mission; a bare-prose ``C-XXX`` item under a
       ``### Constraints`` heading remains a disclosed, out-of-scope blind
       spot -- see WP07).
    3. For each line in ``body``: if the line matches one of the four
       ``_DECLARED_ID_PATTERNS``, raw-token scanning of the REST of that line
       is skipped entirely -- the load-bearing rule that keeps a foreign or
       malformed id-shaped token in a properly-declared table row's own
       description column from being mistaken for a second, undeclared
       requirement (Story 2 AC3; the exact false-positive class that drove
       #3395's rejected doc-wide prototype's ~6% rate). Otherwise, the line is
       scanned for every ``_REF_FIND_PATTERN`` token; any token not present in
       ``document_declared`` is a bare-prose candidate, recorded against that
       section's heading.

    Scope is document-level, not section-level (C-006), by design: a token
    declared elsewhere in the document is already counted as a requirement,
    so a section merely citing it again is not a lost requirement.

    **Measured rate of this shipped function** -- re-verified independently
    twice with identical results, against the full ``kitty-specs/*/spec.md``
    corpus (N=368, measured 2026-08-14): **1/368 = 0.27%** of specs flag.
    The sole hit is ``kitty-specs/egress-refusal-consolidation-3110-
    01KYW895/spec.md``, section "Requirement-level falsifiers", ids
    ``C-1`` and ``C-3``. That hit is a **foreign-id citation**: the spec
    explicitly disambiguates its own constraint ids (``C-001``..``C-011``)
    from the orchestrator's self-correction ids (``C-1``..``C-4``, tracked
    in that mission's own ``ORCHESTRATOR-NOTES.md``) -- so this is a false
    positive, and the function's true-positive count over this corpus is
    **zero**.

    **Reconciliation -- do not mistake these for this function's rate.**
    The ``9/368 = 2.45%`` and ``139/368 = 37.77%`` figures below were
    measured during design against an *earlier, broader prototype* that did
    NOT apply this function's per-line declared-shape skip (step 3 below:
    "if the line matches ... raw-token scanning of the REST of that line is
    skipped entirely"). They describe that earlier, different predicate --
    not the per-line-skip-gated function shipped here -- and are retained
    only as the historical evidence for the document-scoped-vs-section-
    scoped design choice (C-006) immediately below; a future maintainer must
    not read them as this function's own false-positive rate.

    - **Document-scoped prototype** (matches this function's C-006 scoping
      choice, measured without the per-line skip rule): 9/368 = 2.45% of
      specs newly flagged.
    - **Section-scoped prototype** (rejected alternative -- "declared"
      meaning declared *within this section* rather than anywhere in the
      document, same pre-skip-rule scan): 139/368 = 37.77% of specs newly
      flagged -- 15x more than the document-scoped prototype figure, from
      the document-vs-section design choice alone.

    Document-scoped is the only correct reading (C-006) and is what this
    function implements; both prototype rates are recorded together here so
    a future maintainer cannot reasonably reintroduce the rejected
    section-scoped version without seeing the cost it was measured to
    carry.

    **WP07 -- false-negative sample + re-verified broadened-predicate FP figure
    (measured 2026-08-14, N=368, method: `tests/specify_cli/
    test_bare_prose_false_negative_sample.py`, a read-only corpus scan with the
    heading predicate locally broadened to also match "constraint" -- reusing
    this function's own per-line algorithm against the broadened section
    scoping, mirroring plan.md's PLAN-GOV-002 method; production
    `_is_requirement_heading` is untouched and byte-identical).** C-008's
    disposition (option (b), above) leaves `C-XXX` bare-prose items under a
    `### Constraints` heading structurally invisible to this function -- 325 of
    368 specs (88.32%) use that heading. This is the disclosure of that blind
    spot's two sides:

    - **Broadened-predicate FP rate (re-verified)**: 5/368 = 1.36% of specs are
      newly flagged when the heading predicate is broadened to also match
      "constraint" -- identical to PLAN-GOV-002's plan-time figure, same 5
      specs (`coord-read-residuals-merge-lanes-and-identity-routing-01KW2M8V`,
      `doctrine-public-api-surface-01KZPDSR`,
      `drg-relation-impacts-vocabulary-01KYFV87`,
      `foundational-values-creed-band-01KYFV8N`,
      `test-quality-doctrine-series-01KYFV8H`), independently re-run and
      re-verified rather than copied on trust.
    - **False-negative sample**: manual review of all 5 newly-flagged tokens
      found **zero genuine bare-prose requirements the shipped detector
      misses** -- zero true positives, matching PLAN-GOV-002's own
      classification. Two (`C-009` citing a sibling mission's own constraint
      id; `C-010` citing another mission's requirement from a narrative
      "Carried constraints" scratch heading) are foreign-id citations, the
      same class as this function's own 1/368 measured rate above. Two more
      (`C-009`, `C-005`) are likewise foreign/cross-mission citations under
      narrative "Carried constraints" scratch headings -- not the canonical
      `### Constraints` requirements table C-008 is about, so they are also
      instances of the broadened predicate's substring over-match risk (a
      plain `"constraint"` match also catching non-canonical prose headings),
      not the Constraints-heading blind spot itself. The remaining one
      (`C-007`, `doctrine-public-api-surface-01KZPDSR`) is this spec's own
      locally-declared `C-007-mission` id, mis-scanned as bare because its
      non-numeric-suffixed id text fails `_TABLE_ROW_ID_PATTERN`'s
      exact-digits capture (the same pre-existing, broadening-independent gap
      PLAN-GOV-002 already documented for `C-009-mirror`/`C-007-mission`
      shapes) -- not a requirement genuinely lost to bare prose either. This
      sample found no new evidence of a genuine missed requirement, but it
      does not retire the underlying structural blind spot (325/368 specs use
      a Constraints heading this function cannot see); a future spec with a
      genuine undeclared `C-XXX` under that heading would still go
      undetected. Informational only (Story 4 AC4) -- not a shipping gate,
      and does not change this function's behavior or measured rate above.

    Returns:
        One :class:`BareProseCandidate` per requirement-named section that
        contains at least one bare-prose candidate id -- sections with none
        are omitted. This pure function never catches an exception to return
        a quietly empty/clean result (NFR-002: silent-success prohibition);
        whatever the underlying section-scoping / declared-id computation
        raises propagates unchanged. The call-site wrapping that converts
        such an exception into an explicit, blocking failure message for
        callers is a separate concern, delivered per call site elsewhere in
        this mission.
    """
    document_declared = _declared_ids(spec_content)
    result: BareProseResult = []
    for heading_text, body in _requirement_named_sections(spec_content):
        section_ids: list[str] = []
        for line in body.splitlines():
            if any(pattern.match(line) for pattern in _DECLARED_ID_PATTERNS):
                continue
            for requirement_id in _unqualified_unsuffixed_ids(line):
                token = requirement_id.canonical
                if token not in document_declared and token not in section_ids:
                    section_ids.append(token)
        if section_ids:
            result.append(BareProseCandidate(section_heading=heading_text, ids=section_ids))
    return result


class CoverageSummary(TypedDict):
    """Coverage summary returned by :func:`compute_coverage`."""

    total_functional: int
    mapped_functional: int
    unmapped_functional: list[str]


def compute_coverage(mappings: dict[str, list[str]], functional_ids: set[str]) -> CoverageSummary:
    """Compute coverage summary: total, mapped, unmapped FRs.

    Matching is by canonical form (C-001); a malformed ref never maps
    anything.
    """
    mapped: set[str] = set()
    for refs in mappings.values():
        for ref in refs:
            canonical_form = grammar.canonical(ref)
            if canonical_form is not None:
                mapped.add(canonical_form)
    mapped_functional = sorted(mapped & functional_ids)
    unmapped_functional = sorted(functional_ids - mapped)
    return {
        "total_functional": len(functional_ids),
        "mapped_functional": len(mapped_functional),
        "unmapped_functional": unmapped_functional,
    }


_KIND_TO_BUCKET: dict[str, str] = {
    "FR": "functional",
    "NFR": "non_functional",
    "C": "constraint",
    "SC": "success_criteria",
}


def parse_requirement_ids_from_spec_md(spec_content: str) -> dict[str, list[str]]:
    """Parse DECLARED requirement IDs from spec.md content.

    Shared between map-requirements and finalize-tasks.

    Scoped to ids the spec genuinely *declares* -- a markdown table row
    (``| FR-001 | ... |``), a heading naming the id (``### FR-001``), a
    bulleted/numbered item, or a bold-led definition -- not every
    ``FR-NNN``/``NFR-NNN``/``C-NNN``/``SC-NNN`` token anywhere in the
    document (#3394). A spec's prose may cite another mission's
    already-shipped requirement as background context (e.g. "...easy to
    miss, see FR-021's default-pack materialization"); that citation is not
    a requirement THIS spec's work packages must cover, so it is excluded
    from every key below.

    ``all`` now includes success criteria and letter-suffixed ids (WP01,
    FR-003); ``functional`` includes suffixed FRs. ``non_functional``,
    ``constraint`` and ``success_criteria`` are new, each sorted.

    Returns:
        ``{"all": [...], "functional": [...], "non_functional": [...],
        "constraint": [...], "success_criteria": [...]}`` -- "all" is every
        declared id (used to check a WP-declared ref is *known*);
        "functional" is the FR subset (used for FR coverage gating).
    """
    declared = _declared_ids(spec_content)
    buckets: dict[str, list[str]] = {"functional": [], "non_functional": [], "constraint": [], "success_criteria": []}
    for req_id in declared:
        requirement_id = grammar.parse(req_id)
        if requirement_id is None:
            continue
        buckets[_KIND_TO_BUCKET[requirement_id.kind]].append(req_id)
    return {
        "all": sorted(declared),
        "functional": sorted(buckets["functional"]),
        "non_functional": sorted(buckets["non_functional"]),
        "constraint": sorted(buckets["constraint"]),
        "success_criteria": sorted(buckets["success_criteria"]),
    }


def _read_wp_frontmatter_values(
    tasks_dir: Path,
    load_value: Any,
) -> dict[str, list[str]]:
    """Shared WP*.md frontmatter-scan loop (T001 tidy-first).

    WP06 (requirement-id-grammar-01M3NRCA, C6/F13 disposal): this loop
    originally served two readers -- the typed-frontmatter
    ``read_all_wp_requirement_refs`` and the raw-dict
    ``read_all_wp_raw_requirement_refs``. WP02/WP03/WP04 re-pointed every
    product caller at the raw reader (classification needs the raw authored
    tokens, not a pre-normalized/respelled list), leaving the typed reader
    (and its sole caller, ``normalize_requirement_refs_value``) with zero
    product callers; both were deleted here (``tests/architectural/
    test_no_dead_symbols.py`` confirmed the zero-caller state). This shell
    now has exactly one caller, kept as a named helper because
    :func:`read_all_wp_raw_requirement_refs` may grow a sibling again.

    Args:
        tasks_dir: Directory containing WP*.md files.
        load_value: Callable(wp_file) -> list[str]; any exception it raises
            yields ``[]`` for that WP (matches the reader's own try/except
            behaviour).
    """
    result: dict[str, list[str]] = {}
    if not tasks_dir.exists():
        return result
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        match = re.match(r"(WP\d{2})", wp_file.name)
        if not match:
            continue
        wp_id = match.group(1)
        try:
            result[wp_id] = load_value(wp_file)
        except Exception:
            result[wp_id] = []
    return result


def read_all_wp_raw_requirement_refs(tasks_dir: Path) -> dict[str, list[str]]:
    """Read raw requirement_refs from all WP files' frontmatter.

    Uses the raw frontmatter dict (not the typed model) so that non-string
    items (e.g. integers) are preserved as ``<NON_STRING:...>`` tokens by
    :func:`_extract_raw_tokens`. This is the WP01 unified raw reader: WP02's
    finalize, WP03's map-requirements and WP04's runtime all classify its
    output, so its name and ``dict[wp_id, list[str]]`` raw-token shape are
    load-bearing.
    """
    from specify_cli.frontmatter import FrontmatterManager

    fm = FrontmatterManager()

    def _load(wp_file: Path) -> list[str]:
        raw_dict, _ = fm.read(wp_file)  # MIGRATION-ONLY: raw dict access is intentional here
        return _extract_raw_tokens(raw_dict.get("requirement_refs"))  # MIGRATION-ONLY: raw dict access is intentional here

    return _read_wp_frontmatter_values(tasks_dir, _load)


def _extract_raw_tokens(value: Any) -> list[str]:
    """Extract individual tokens from a frontmatter value, preserving case.

    Delegates to :func:`grammar.tokenize_refs` (T004 step 9; C-001: the one
    tokenisation of ``requirement_refs``). Case is preserved so that
    diagnostics can show exactly what was written (e.g. ``BOGUS`` vs
    ``bogus``). Callers that need uppercased tokens for comparison should
    uppercase themselves.
    """
    return grammar.tokenize_refs(value)
