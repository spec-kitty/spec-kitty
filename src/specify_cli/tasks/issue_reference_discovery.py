"""Multi-file issue-reference discovery (T028, FR-004, #1738).

Generalizes ``tasks.issue_matrix.detect_issue_references`` -- which reads
``spec.md`` **only** -- to every mission artifact that can legitimately carry
a load-bearing GH issue reference: ``spec.md``, ``plan.md``, ``research.md``,
``analysis-report.md``, plus every ``.md`` file directly under ``tasks/`` and
``contracts/``.

This module reuses the ONE canonical single-file detector
(:func:`specify_cli.tasks.issue_matrix.detect_issue_references`) per scanned
file -- same ``#NNNN`` regex, same canonicalization -- so there remains
exactly one issue-reference pattern definition in the codebase (WP08 risk:
"avoid a fourth definition"). This module owns only two concerns: *which*
files to scan, and how to merge/dedupe references discovered across them.

``detect_issue_references`` is NOT deleted or edited here (it is owned by
WP05): :func:`specify_cli.tasks.issue_matrix.scaffold_issue_matrix` still
calls it directly against ``spec.md`` alone for the initial-scaffold use case
(B3), so it remains a live building block. It IS superseded for
completeness/enforcement purposes -- the three enforcement sites
(``status.doctor.check_issue_matrix``,
``cli.commands.agent.tasks_parsing_validation._issue_matrix_evaluation`` /
``_issue_matrix_approval_blocker``) and the merge-time completeness gate
(``policy.merge_gates``) now call :func:`discover_issue_references` instead
(write-side-seam-matrix-tracer-01KYP3MH WP08, T029/T030).

move-task-approval-ergonomics-01M302R0 WP01 (#3469, FR-001/FR-011/FR-012/
FR-015)
------------------------------------------------------------------------
This module now also owns the **reference gating classification seam**: the
ONE pure, deterministic classifier (:func:`classify_occurrence` /
:func:`classify_occurrences`) that labels every discovered ``#NNNN``
reference as :class:`GatingClass.IMPLEMENTATION_TARGET` (gating),
``CONTEXT_ONLY``, or ``PR_OR_COMMIT_REF`` (both non-gating). Two invariants
hold everywhere in this module:

* **Default-gating fail-safe (FR-011)** -- a reference is
  ``implementation_target`` unless a positive, explicit signal demotes it.
  Ambiguity (including zero occurrences) stays gating.
* **Aggregate over all occurrences (FR-015)** -- classification is computed
  over EVERY occurrence of a number, not just the first; any
  implementation-target occurrence forces gating, even when an earlier
  occurrence looked non-gating.
* **Labels bind to ONE reference (#7011)** -- a *positional* citation label
  (``parent #``, ``epic #``, a leading ``see #``) demotes only the reference it
  leads into, decided from the occurrence's own ``ref_offset``; the
  line-scoped markers (``follow-up:``, ``baseline-red``) still speak about the
  whole statement. Before #7011 a label anywhere on the line demoted every
  number on it, which silently marked the Mission's own target issue
  ``not-applicable``.

:func:`gating_issue_numbers` and :func:`is_gating` are the ONE shared
gating predicate (FR-012, contract C2.1) -- the approval blocker,
``merge_gates``, and ``status/doctor`` must all derive "referenced-but-
missing" from this same authority rather than re-deriving it.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Sequence

    from specify_cli.tasks.issue_matrix import IssueReference


class GatingClass(StrEnum):
    """Gating classification for a discovered issue reference (FR-001).

    See ``contracts/classification-and-verdict-contract.md`` C1 and
    ``data-model.md`` (move-task-approval-ergonomics-01M302R0, #3469).
    """

    IMPLEMENTATION_TARGET = "implementation_target"
    CONTEXT_ONLY = "context_only"
    PR_OR_COMMIT_REF = "pr_or_commit_ref"


class Occurrence(NamedTuple):
    """One site where an issue number was found (FR-015 aggregate input).

    Attributes:
        source_file: Basename of the file the occurrence was found in.
        line_text: The stripped line text the number appeared on -- the
            classification signal surface (context markers / PR tokens /
            pull URLs are matched against this line).
        ref_offset: Index in ``line_text`` at which THIS citation begins --
            the ``#`` of a bare reference, the ``h`` of an issue URL -- or
            ``None`` when the caller cannot supply one (#7011). It is what
            lets a *positional* citation label demote only the number it
            actually leads into: on
            ``"**Input**: Issue #6926 (part of epic #6100)"`` the ``epic``
            label describes ``#6100``, never ``#6926``. ``None`` keeps the
            pre-#7011 whole-line semantics for backward-compatible
            positional construction (C-001).
        in_gating_scope: Whether the artefact this occurrence came from is in
            the gating scope -- ``spec.md`` or a ``tasks/`` file (#5516,
            operator ruling "Scope decides"). Set to ``False`` only by
            :func:`discover_issue_references` for ``plan.md``,
            ``research.md``, ``analysis-report.md`` and ``contracts/``; an
            out-of-scope occurrence is cited (non-gating) unless a closing
            keyword leads into it. Defaults to ``True`` so direct positional
            construction keeps its outcome.
    """

    source_file: str
    line_text: str
    ref_offset: int | None = None
    in_gating_scope: bool = True


# Explicit, positive non-gating signals (case-insensitive).
#
# PR/commit signal: a leading ``PR``/``PR#``/``pull`` token, OR a
# ``/pull/<n>`` URL anywhere on the line.
_PR_OR_COMMIT_PATTERN = re.compile(r"\bpr\s*#|\bpull\b|/pull/\d+", re.IGNORECASE)

# #5297: a commit citation -- a backticked 7-40 character hex SHA right next to
# the citation, as in ``(`ed6d34e75`, #4757)`` -- is evidence, not owed work.
# Positional, like the citation labels below: the SHA must sit within
# ``_COMMIT_SHA_WINDOW`` characters of THIS citation (before its ``#`` or after
# its number), so it never demotes an unrelated number further along the line.
# The token must carry at least one letter ``a-f`` AND one digit: an all-digit
# backticked token cannot be told from an ordinary number, and an all-letter one
# is usually an English word (``defaced``, ``deadbeef``), so both stay gating
# (fail-safe). A real 7-character SHA is all letters about 0.1% of the time.
_COMMIT_SHA_PATTERN = re.compile(r"`([0-9a-f]{7,40})`", re.IGNORECASE)
_COMMIT_SHA_WINDOW = 16
_HEX_LETTERS = frozenset("abcdefABCDEF")
_DECIMAL_DIGITS = frozenset("0123456789")
# The citation's own text, from its offset: ``#4757`` or a full issue URL.
_CITATION_TOKEN_PATTERN = re.compile(r"[^\s)\],;`]+")

# A closing keyword IS an implementation-target statement (#5516: it gates in
# every scanned artefact). Label-only: the number after it is the canonical
# detector's citation (FR-006, one number-recognition authority), and the label
# binds to the ONE citation it ends at, like the positional context labels. The
# keyword may be emphasised (``**Closes**``, ``**Fixes:**``) and the citation
# wrapped (```#12```, ``[#12](url)``, ``([#12](url))``, ``**#12**``); the label ends at the
# citation's first character, the ``#`` of a bare reference or the ``h`` of an
# issue URL (the only citation that starts with ``h``).
_CLOSING_KEYWORD_LABEL_PATTERN = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b(?:\*\*|__)?\s*:?(?:\*\*|__)?\s*[(\[`*_]*[#h]",
    re.IGNORECASE,
)

# A closing keyword directly preceded by a negation ("does not fix #N") is not a
# closing statement.
_NEGATION_SUFFIX_PATTERN = re.compile(
    r"\b(?:(?:does|did|is|was|will|has|had)\s+not|doesn't|didn't|isn't|wasn't|won't|hasn't|hadn't)\s*$",
    re.IGNORECASE,
)

# Context-only signals come in two kinds, because they mean different things.
#
# (1) LINE-scoped markers -- ``follow-up:`` / ``baseline-red`` are distinctive
# enough that their presence anywhere on the line marks the whole statement as
# context. Matched against the whole line, unchanged.
_LINE_CONTEXT_MARKER_PATTERN = re.compile(r"follow-up:|baseline-red", re.IGNORECASE)

# (2) POSITIONAL citation labels -- ``parent`` / ``epic`` / ``see`` are ordinary
# English words -- fail-open hole closed here (#3469): they only demote when
# used as a citation label, never when they merely occur somewhere on a
# genuine implementation-target line ("The parent widget must resolve #4521",
# "We see #4521 failures in prod"). A citation label is either (a)
# ``parent``/``epic`` sitting immediately (within 12 non-#/non-newline
# characters) before the ``#`` ref, e.g. "Tracked by the epic #200." /
# "Parent context: #200 ...", or (b) ``see`` leading the line (optionally after
# whitespace), e.g. "see #200 for ...".
#
# #7011: each of these arms ENDS at the ``#`` it describes, so the label binds
# to ONE number. Matching the pattern against the whole line (the pre-#7011
# behaviour) let a label for ``#6100`` demote an unrelated ``#6926`` earlier on
# the same line, which silently marked the Mission's own target issue
# ``not-applicable``. The pattern itself is unchanged -- only the window it is
# matched against, and the requirement that the match end at the citation
# (:func:`_positional_label_precedes_citation`).
#
# Extend these lists judiciously -- they are the single definition consumed by
# :func:`classify_occurrence`.
_POSITIONAL_CONTEXT_MARKER_PATTERN = re.compile(
    r"^\s*see\s*#|(?:parent|epic)\b[^#\n]{0,12}#",
    re.IGNORECASE,
)


def _positional_label_precedes_citation(occurrence: Occurrence) -> bool:
    """True iff a positional citation label leads into THIS occurrence's ``#``.

    ``ref_offset`` decides the window: for a known offset the label must END
    exactly where the citation begins (``line_text[:ref_offset + 1]``, the
    ``#`` included so the ``^``-anchored ``see`` arm still fits), which is the
    rule the pattern's own comment always stated. When the caller supplies no
    offset, the whole line is the window -- the pre-#7011 behaviour, kept so
    direct ``Occurrence(source_file=..., line_text=...)`` construction does not
    change outcome (C-001).
    """
    return bool(_labels_leading_into(_POSITIONAL_CONTEXT_MARKER_PATTERN, occurrence))


def _labels_leading_into(pattern: re.Pattern[str], occurrence: Occurrence) -> list[re.Match[str]]:
    """The ``pattern`` matches that lead into THIS occurrence's citation.

    With a known ``ref_offset`` a match must END exactly at the citation's ``#``
    (``line_text[:ref_offset + 1]``, the ``#`` included so the ``^``-anchored
    ``see`` arm still fits); with none, every match on the line counts (the
    pre-#7011 whole-line window, C-001).
    """
    offset = occurrence.ref_offset
    if offset is None:
        return list(pattern.finditer(occurrence.line_text))
    window = occurrence.line_text[: offset + 1]
    return [match for match in pattern.finditer(window) if match.end() == len(window)]


def _closing_keyword_leads_into(occurrence: Occurrence) -> bool:
    """True iff a non-negated closing keyword leads into this citation (#5516)."""
    line = occurrence.line_text
    return any(not _NEGATION_SUFFIX_PATTERN.search(line[: match.start()]) for match in _labels_leading_into(_CLOSING_KEYWORD_LABEL_PATTERN, occurrence))


def _commit_sha_beside_citation(occurrence: Occurrence) -> bool:
    """True iff a backticked commit SHA sits right beside this citation (#5297)."""
    line = occurrence.line_text
    shas = [match for match in _COMMIT_SHA_PATTERN.finditer(line) if _HEX_LETTERS.intersection(match.group(1)) and _DECIMAL_DIGITS.intersection(match.group(1))]
    offset = occurrence.ref_offset
    if offset is None:
        return bool(shas)
    token = _CITATION_TOKEN_PATTERN.match(line, offset)
    citation_end = token.end() if token else offset + 1
    return any(
        (sha.end() <= offset and offset - sha.end() <= _COMMIT_SHA_WINDOW) or (sha.start() >= citation_end and sha.start() - citation_end <= _COMMIT_SHA_WINDOW)
        for sha in shas
    )


def classify_occurrence(occurrence: Occurrence) -> GatingClass:
    """Classify a single occurrence line. Pure, deterministic (C1.5).

    Order matters:

    1. A non-negated closing keyword leading into the citation gates, in any
       artefact and ahead of every demoting rule (#5516) -- when the caller
       supplies the citation's offset. Without one, the keyword only lifts the
       out-of-scope demotion below, so direct ``Occurrence(file, line)``
       construction keeps its outcome (C-001).
    2. A PR/commit signal -- a PR token or pull URL on the line, or a commit SHA
       beside the citation (#5297) -- comes before the context markers, so a
       line like ``"PR #300 (see #300)"`` still resolves to the more specific
       ``PR_OR_COMMIT_REF`` rather than ``CONTEXT_ONLY``.
    3. An occurrence outside the gating scope is cited (``CONTEXT_ONLY``).
    4. The line-scoped and positional context markers, then the gating default.
    """
    closing = _closing_keyword_leads_into(occurrence)
    if closing and occurrence.ref_offset is not None:
        return GatingClass.IMPLEMENTATION_TARGET
    if _PR_OR_COMMIT_PATTERN.search(occurrence.line_text) or _commit_sha_beside_citation(occurrence):
        return GatingClass.PR_OR_COMMIT_REF
    if not occurrence.in_gating_scope and not closing:
        return GatingClass.CONTEXT_ONLY
    if _LINE_CONTEXT_MARKER_PATTERN.search(occurrence.line_text):
        return GatingClass.CONTEXT_ONLY
    if _positional_label_precedes_citation(occurrence):
        return GatingClass.CONTEXT_ONLY
    return GatingClass.IMPLEMENTATION_TARGET


def classify_occurrences(occurrences: Sequence[Occurrence]) -> GatingClass:
    """Aggregate classification over ALL occurrences of one number (FR-015).

    Default-gating fail-safe (FR-011): an empty/ambiguous occurrence set
    stays gating. Otherwise: any ``implementation_target`` occurrence forces
    gating (impl-target wins); else, when every occurrence is a PR/commit
    reference, the aggregate is ``pr_or_commit_ref``; otherwise (all
    ``context_only``, or a mix of the two non-gating classes) the aggregate
    is the more conservative ``context_only``.
    """
    if not occurrences:
        return GatingClass.IMPLEMENTATION_TARGET

    per_occurrence = [classify_occurrence(occurrence) for occurrence in occurrences]
    if any(cls is GatingClass.IMPLEMENTATION_TARGET for cls in per_occurrence):
        return GatingClass.IMPLEMENTATION_TARGET
    if all(cls is GatingClass.PR_OR_COMMIT_REF for cls in per_occurrence):
        return GatingClass.PR_OR_COMMIT_REF
    return GatingClass.CONTEXT_ONLY


def is_gating(ref: IssueReference) -> bool:
    """True iff ``ref``'s classification requires an issue-matrix row.

    FR-012/FR-013, contract C2.1/C4.1: the ONE shared predicate the approval
    blocker, ``merge_gates``, and ``status/doctor`` must all consume instead
    of re-deriving "referenced-but-missing" independently.
    """
    return ref.classification is GatingClass.IMPLEMENTATION_TARGET


def gating_issue_numbers(feature_dir: Path) -> set[str]:
    """The canonical set of gating ``#NNNN`` refs for a mission (FR-012).

    The SINGLE shared authority WP02/WP03 consume for "referenced-but-
    missing" (contract C2.1) -- do not reimplement this predicate elsewhere.
    Non-gating references (``context_only`` / ``pr_or_commit_ref``) are
    excluded even though :func:`discover_issue_references` still returns
    them (they remain visible for the audit trail, just non-blocking).
    """
    return {f"#{ref.number}" for ref in discover_issue_references(feature_dir) if is_gating(ref)}


# Single-file mission artifacts scanned in this fixed order (T028). Each is
# optional -- a mission without a ``research.md``/``analysis-report.md``
# simply contributes nothing from that slot. ``spec.md`` stays first so the
# existing single-file behavior (:func:`detect_issue_references` on
# ``spec.md`` alone) is a strict, order-preserving subset of this scan.
_SINGLE_FILE_ARTIFACTS: tuple[str, ...] = (
    "spec.md",
    "plan.md",
    "research.md",
    "analysis-report.md",
)

# Directories scanned non-recursively for ``.md`` files, in this fixed order,
# each sorted by filename for a deterministic scan.
_SCAN_DIRS: tuple[str, ...] = ("tasks", "contracts")

# #5516 (operator ruling "Scope decides"): only these artefacts carry gating
# references. Every other scanned artefact (``plan.md``, ``research.md``,
# ``analysis-report.md``, ``contracts/``) is background: a ``#N`` there is cited,
# not owed, unless a closing keyword leads into it.
_GATING_SCOPE_FILES: frozenset[str] = frozenset({"spec.md"})
_GATING_SCOPE_DIRS: frozenset[str] = frozenset({"tasks"})


def _in_gating_scope(path: Path, feature_dir: Path) -> bool:
    """True iff ``path`` is ``spec.md`` or a ``tasks/`` file of ``feature_dir`` (#5516)."""
    if path.parent == feature_dir:
        return path.name in _GATING_SCOPE_FILES
    return path.parent.parent == feature_dir and path.parent.name in _GATING_SCOPE_DIRS


def _iter_scan_paths(feature_dir: Path) -> list[Path]:
    """Return every artifact path to scan, in deterministic order.

    Missing single-file artifacts and missing/empty scan directories are
    silently skipped -- discovery must not fail a mission that simply has
    not authored a given optional artifact yet.
    """
    paths: list[Path] = []
    for name in _SINGLE_FILE_ARTIFACTS:
        candidate = feature_dir / name
        if candidate.is_file():
            paths.append(candidate)
    for dirname in _SCAN_DIRS:
        dir_path = feature_dir / dirname
        if not dir_path.is_dir():
            continue
        paths.extend(sorted(p for p in dir_path.glob("*.md") if p.is_file()))
    return paths


def discover_issue_references(feature_dir: Path) -> list[IssueReference]:
    """Return the deduplicated, ordered list of GH issue refs across a mission.

    Scans ``spec.md``, ``plan.md``, ``research.md``, ``analysis-report.md``
    (each optional) plus every ``.md`` file directly under ``tasks/`` and
    ``contracts/`` (also optional directories), reusing the canonical
    single-file detector (:func:`~specify_cli.tasks.issue_matrix.
    detect_issue_references`) per file so there is one #NNNN pattern
    definition.

    Ordering is deterministic: the single-file artifacts in the fixed order
    above, then ``tasks/*.md`` sorted by filename, then ``contracts/*.md``
    sorted by filename. Within that scan order, the FIRST file+line a given
    issue number appears in wins both the ``first_line_context`` AND the
    ``source_file`` (WP06 / T028, #1738) -- matching the single-file
    function's existing first-occurrence contract, extended to provenance.

    WP01 (#3469, FR-015): every occurrence across every scanned file --  not
    just the first -- is retained on the returned reference's
    ``occurrences`` field and folded into its aggregate ``classification``.
    A dual-cited number (context-only in the first file, an implementation
    target in a later one) still gates: aggregation happens BEFORE
    classification, never after a first-occurrence-only dedupe.

    Args:
        feature_dir: The mission's ``kitty-specs/<slug>/`` planning
            directory (or the caller's already topology-resolved read
            surface).

    Returns:
        Deduplicated :class:`~specify_cli.tasks.issue_matrix.IssueReference`
        list, ordered by first appearance across the scanned files. Empty
        list when no scanned file references a GH issue, or when
        ``feature_dir`` has none of the scanned artifacts.
    """
    # Deferred import (not a module-level ``from ... import``) so this stays
    # a live patch seam: callers/tests monkeypatch
    # ``specify_cli.tasks.issue_matrix.detect_issue_references`` and expect
    # every consumer -- this discovery module included -- to observe the
    # patched callable, the same contract the pre-WP08 single-file callers
    # relied on.
    from specify_cli.tasks.issue_matrix import IssueReference, detect_issue_references

    # T028 (#1738): keyed by number, valued by (first_line_context,
    # source_file) TOGETHER so the pair always travels from the same
    # first-occurrence file -- never independently re-derived, which could
    # otherwise mismatch context from one file against provenance from
    # another.
    first_seen: dict[int, tuple[str, str]] = {}
    # FR-015: every occurrence, across every file, aggregated BEFORE
    # classification -- never truncated to the first file's occurrences.
    occurrences_by_number: dict[int, list[Occurrence]] = {}
    for path in _iter_scan_paths(feature_dir):
        # #5516: scope travels on each occurrence so the ONE classifier decides.
        in_scope = _in_gating_scope(path, feature_dir)
        for ref in detect_issue_references(path):
            if ref.number not in first_seen:
                first_seen[ref.number] = (ref.first_line_context, ref.source_file)
            occurrences = ref.occurrences if in_scope else tuple(occ._replace(in_gating_scope=False) for occ in ref.occurrences)
            occurrences_by_number.setdefault(ref.number, []).extend(occurrences)
    references = [
        IssueReference(
            num,
            ctx,
            source_file,
            occurrences=tuple(occurrences_by_number[num]),
            classification=classify_occurrences(occurrences_by_number[num]),
        )
        for num, (ctx, source_file) in first_seen.items()
    ]
    # #7011: the issue this Mission exists to fix never reaches a gate as
    # non-gating, however its prose reads. Applied through the ONE promotion
    # helper so the scaffold (which detects on ``spec.md`` alone) cannot drift.
    return promote_source_issue_references(references, mission_source_issue_numbers(feature_dir))


# ---------------------------------------------------------------------------
# #7011 -- the Mission's own source issue is never auto-classified non-gating
# ---------------------------------------------------------------------------

# A ``source_description`` only names the source issue when it OPENS with one of
# these forms: ``Issue #N …``, ``GitHub issue N …``, ``Ticket #N …`` or a bare
# ``#N …``. Most values in this repository are free-form prose that happens to
# mention issue numbers ("Refactor mission system to address #6100 …"); promoting
# those would force verdicts the Mission does not owe. The explicit leading issue
# marker is what makes it a statement, so whatever follows the number (a colon, an
# em dash, a parenthetical such as the reported "(part of epic #6100)") does not
# matter.
#
# Label-only (FR-006): the number after the lead is read by the canonical
# detector (``issue_citations_in_line``), so a leading zero or any other filtered
# value is rejected here exactly as everywhere else (#7808).
_SOURCE_DESCRIPTION_LEAD_PATTERN = re.compile(r"^\s*(?:(?:github\s+)?(?:issue|ticket)\s*#?|#)\s*", re.IGNORECASE)

# The spec header convention (``**Input**: Issue #NNNN — …``).
_SPEC_INPUT_PREFIX = "**Input**"


def _read_json_object(path: Path) -> dict[str, object]:
    """Parse ``path`` as a JSON object, or ``{}`` on any read/parse/shape failure.

    NFR-002: discovery already runs inside the approval blocker, which must fail
    closed only on its own rule -- a missing, unreadable or malformed
    ``meta.json`` degrades to "no contribution", never an exception.
    """
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        # ValueError covers json.JSONDecodeError and UnicodeDecodeError.
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_text_or_empty(path: Path) -> str:
    """``path``'s text, or ``""`` when it is absent or unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, ValueError):
        return ""


def _source_issues_from_description(description: object) -> set[int]:
    """The leading ``Issue #N: …`` form of a free-form ``source_description``."""
    if not isinstance(description, str):
        return set()
    lead = _SOURCE_DESCRIPTION_LEAD_PATTERN.match(description)
    if lead is None:
        return set()
    from specify_cli.tasks.issue_matrix import issue_citations_in_line  # the ONE detector

    # Re-anchor the number right after the lead as a bare ``#N`` citation at
    # column 0, so the hashless ``GitHub issue N`` form goes through the same
    # detector and filter as every other number.
    rest = description[lead.end() :].partition("\n")[0]
    citations = issue_citations_in_line(f"#{rest}")
    return {citations[0][0]} if citations and citations[0][1] == 0 else set()


def _source_issues_from_spec(spec_text: str) -> set[int]:
    """The source issue(s) the spec itself declares.

    Two sources, both explicit statements rather than incidental prose: the
    ``**Input**:`` header line's FIRST same-repo reference (the mission-from-issue
    convention), and every ``Closes``/``Fixes``/``Resolves #N``. The ``#NNNN``
    recognition itself is delegated to
    :func:`~specify_cli.tasks.issue_matrix.issue_citations_in_line` so this module
    keeps its single-pattern invariant (FR-006: the closing keyword is a label,
    never a second number pattern).
    """

    from specify_cli.tasks.issue_matrix import issue_citations_in_line  # the ONE detector

    found: set[int] = set()
    input_line_seen = False
    for line in spec_text.splitlines():
        citations = issue_citations_in_line(line)
        if not input_line_seen and line.strip().startswith(_SPEC_INPUT_PREFIX):
            input_line_seen = True
            # Take the first reference of the ``**Input**:`` line that no
            # positional citation label (``epic``/``parent``/``see``) leads
            # into, so an ``Epic #6100`` lead cannot promote the umbrella ahead
            # of the target (#7011).
            for number, offset in citations:
                if not _positional_label_precedes_citation(Occurrence(source_file="spec.md", line_text=line, ref_offset=offset)):
                    found.add(number)
                    break
        # Every citation a non-negated closing keyword leads into: the same rule
        # and helper the classifier uses (#5516), so the two cannot drift.
        for number, offset in citations:
            if _closing_keyword_leads_into(Occurrence(source_file="spec.md", line_text=line, ref_offset=offset)):
                found.add(number)
    return found


def mission_source_issue_numbers(feature_dir: Path) -> frozenset[int]:
    """Issue numbers this Mission exists to fix (#7011, FR-002).

    Read from the Mission's own record -- ``meta.json`` ``source_description``
    and ``spec.md`` (its ``**Input**:`` line and any closing keyword line) -- so
    the guarantee does not depend on one authoring convention. Deliberately
    narrow: a passing mention of another number is never promoted (see
    ``_SOURCE_DESCRIPTION_LEAD_PATTERN``).

    Never raises: absent/unreadable/unparseable inputs contribute nothing
    (NFR-002), and at most one ``meta.json`` plus one ``spec.md`` are read
    (NFR-003).
    """
    meta = _read_json_object(feature_dir / "meta.json")
    spec_text = _read_text_or_empty(feature_dir / "spec.md")
    return frozenset(_source_issues_from_description(meta.get("source_description")) | _source_issues_from_spec(spec_text))


def promote_source_issue_references(
    references: Sequence[IssueReference],
    source_issues: frozenset[int] | set[int],
) -> list[IssueReference]:
    """Force the Mission's source issue(s) to ``implementation_target`` (FR-003).

    Promotion only rewrites the aggregate ``classification`` of a reference that
    was actually discovered: it never invents a row for an uncited number, and it
    never demotes. The reference is otherwise untouched (context, provenance and
    ``occurrences`` all survive for the audit trail).

    ``ref_offset=None`` handling and every other classification rule stay as they
    are -- this is the guarantee layered on top of the heuristic, not a
    replacement for it.
    """
    if not source_issues:
        return list(references)
    return [ref._replace(classification=GatingClass.IMPLEMENTATION_TARGET) if ref.number in source_issues else ref for ref in references]


__all__ = [
    "GatingClass",
    "Occurrence",
    "classify_occurrences",
    "discover_issue_references",
    "gating_issue_numbers",
    "is_gating",
    "mission_source_issue_numbers",
    "promote_source_issue_references",
]
