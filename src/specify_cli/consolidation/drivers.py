"""Merge-driver bodies: the single owner of all seven registered drivers (#5119).

Seven custom drivers keep mission bookkeeping semantic under the mission→target
``git merge --squash`` in ``lanes/consolidation.py::_merge_branch_into`` (#4892 dropped
the old ``-X theirs``; ordinary source paths now fail closed on conflict). A
custom driver takes over conflict resolution on the paths it is registered for,
so target-newer canonical state is reconciled rather than clobbered or
hard-conflicting (#2709 / FR-003 / FR-004 / FR-008):

- ``merge-driver-event-log``         — ``status.events.jsonl`` union (append-only log).
- ``merge-driver-meta``              — ``meta.json`` field merge, base-aware for
  ordinary merges (a key changed or deleted on one side only survives from that
  side; on a genuine conflict acceptance/VCS/lifecycle keys are
  target-authoritative (the accepted-newer ``ours`` side) and planning keys are
  mission-authoritative (``theirs``; preserves the #1732 planning-artifact
  authority); coupled key groups move as one unit; ``acceptance_history`` is
  unioned). The consolidation pipeline's mission→target squash records no
  ancestry, so it opts into the two-way rule via :data:`META_DRIVER_TWO_WAY_ENV`
  (#5460).
- ``merge-driver-traces``            — ``traces/*.md`` markdown union: order-preserving
  line-level dedup so both sides' sections survive without duplication.
- ``merge-driver-acceptance-matrix`` — ``acceptance-matrix.json`` row-aware,
  base-aware (3-way) merge over ``criteria``/``negative_invariants``, keyed by
  ``criterion_id``/``invariant_id`` (FR-008 / see ``contracts/merge-driver-
  algorithm.md``).
- ``merge-driver-issue-matrix``      — ``issue-matrix.json`` row-aware,
  base-aware (3-way) merge over ``rows``, keyed by canonicalized ``issue_ref``.
- ``merge-driver-review-cycle``      — ``tasks/<wp>/review-cycle-*.md``
  best-effort, non-aborting reconciliation of a two-verdict collision
  (originally a refuse-fail-closed driver, review-cycle-verdict-seam-rebuild-
  01KZ2W7W WP18/T077; DOWNGRADED by verdict-seam-write-unification-01KZ9Q35
  WP09/FR-014/D-PLAN-6 now that the ``.md`` is non-authoritative, unread
  prose — see :func:`run_review_cycle_driver`'s own docstring for the full
  history and why a divergent collision no longer aborts the squash).
- ``merge-driver-decision-index``     — ``decisions/index.json`` union keyed
  by ``decision_id``, terminal-beats-open fold precedence (FR-009b / D13 /
  #5023 — see :func:`run_decision_index_driver`).

Git invokes a driver with ``%O %A %B`` = base / ours / theirs and expects the
merged result written to the ``ours`` (``%A``) path with exit 0. Under the squash
integration ``ours`` is the target checkout (e.g. ``main``) and ``theirs`` is the
mission branch.

**#2970 path-injection hardening (S2083).** Every driver's ``%O``/``%A``/``%B``
argv is externally-supplied (git-computed, but syntactically untrusted input to
this process). Per gitattributes(5) and confirmed empirically, git ALWAYS
materializes the three placeholders as sibling temp files in ONE directory (the
top of the working tree) for a real merge; every driver-unit test in this
codebase constructs them as siblings under one ``tmp_path`` for the same reason.
:func:`_resolve_merge_driver_paths` enforces exactly that invariant — the three
resolved paths must share a parent directory — before any read/write. An
absolute path or a ``..`` escape routing one placeholder outside that shared
directory (the concrete shape of the 5 S2083 BLOCKER findings) is refused
red-first, without narrowing any reconciliation rule below.

**Placement (#5119 / FR-002).** This module owns every driver's file-level
body AND its serialization — the exact reconcile-then-write bytes each driver
produces. Two callers execute the SAME body: the git-invoked subprocess shell
(``cli/commands/merge_driver.py``, a thin adapter translating a body's
:class:`MergeDriverError`/:class:`MergeDriverOutcome` to
``typer.echo``/``typer.Exit``) and the in-process driver replay
(``consolidation/git_probes.py::_resolve_registered_driver_callable``, via
:data:`MERGE_DRIVER_BODIES`). This module's own source must not import
``typer`` or any ``specify_cli.cli`` module other than the reviewed
``specify_cli.cli.console`` ledger entries (:class:`TestMergeCliBoundary`
enforces this as a direct-import scan over ``specify_cli/consolidation/**`` sources —
it does not follow this module's own imports transitively) — a body never
calls ``sys.exit``/raises ``typer.Exit``; it raises :class:`MergeDriverError`
(``str(exc)`` is the exact stderr text) and
returns a :class:`MergeDriverOutcome` (``notice``, when set, is the exact
stdout text) instead. See ``contracts/merge-driver-body.md`` for the binding
contract.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from pydantic import ValidationError

from kernel.vcs_lock import VCS_LOCK_META_FIELDS
from specify_cli.acceptance import (
    ACCEPTANCE_HISTORY_FIELD,
    ACCEPTANCE_PROVENANCE_FIELDS,
)
from specify_cli.acceptance.matrix import AcceptanceMatrix, AcceptanceMatrixParseError
from specify_cli.consolidation.mission_number import is_assigned_mission_number
from specify_cli.decisions.index_fold import is_allowed_terminal_reopen
from specify_cli.decisions.models import DecisionIndex, DecisionStatus
from specify_cli.mission_metadata import parse_meta_file
from specify_cli.status import EventLogMergeError, merge_event_log_files
from specify_cli.tasks.issue_matrix import _SCAFFOLD_VERDICT_PLACEHOLDER, ISSUE_MATRIX_SCHEMA_VERSION

# meta.json serialization identical to ``mission_metadata.write_meta`` so the
# reconciled blob is byte-consistent with the canonical writer (no diff churn).
_META_JSON_KWARGS: dict[str, Any] = {
    "indent": 2,
    "ensure_ascii": False,
    "sort_keys": True,
}

# Target-authoritative ``meta.json`` keys the squash driver takes from the
# accepted-newer target side. Acceptance/VCS provenance (the canonical
# ``ACCEPTANCE_PROVENANCE_FIELDS`` shapes) plus the target-assigned lifecycle /
# merge canonical fields (``mission_number``, ``status``, ``baseline_merge_commit``,
# the ``merged_*`` block): every one is minted on the target at accept/merge time,
# so a squash of the older mission branch must reconcile — not revert — them.
# Every OTHER key (mission planning identity: slug, mission_id, target_branch,
# purpose_*, friendly_name, created_at, coordination_branch, …) stays
# mission-authoritative to preserve the #1732 mission-authoritative planning intent (C-002).
_TARGET_AUTHORITATIVE_META_FIELDS: tuple[str, ...] = (
    *ACCEPTANCE_PROVENANCE_FIELDS,
    "mission_number",
    "status",
    "baseline_merge_commit",
    "merged_at",
    "merged_by",
    "merged_into",
    "merged_strategy",
    "merged_push",
    "merged_commit",
)
_TARGET_AUTHORITATIVE_META_SET: frozenset[str] = frozenset(_TARGET_AUTHORITATIVE_META_FIELDS)

#: Environment switch set to ``"1"`` by the consolidation pipeline's mission→target
#: squash subprocess. That ``git merge --squash`` records no ancestry, so ``%O`` is
#: the stale fork point after a reopen and a base-aware merge would resurrect
#: removed content; with the switch set ``merge-driver-meta`` ignores ``%O`` and
#: applies the two-way rule. Never set it for an ordinary merge, where ``%O`` is
#: the true merge base (#5460).
META_DRIVER_TWO_WAY_ENV: Final = "SPEC_KITTY_META_MERGE_TWO_WAY"

# Distinguishes "key absent on this side" from an explicit JSON ``null``.
_MISSING: Final = object()

# Keys written together by one writer, merged as ONE unit so a record is never
# half-flattened / half-recorded. ``vcs`` / ``vcs_locked_at`` stay individual keys
# (independent provenance, both target-authoritative).
_META_COUPLED_KEY_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"coordination_branch", "topology", "flattened"}),
    frozenset({"merged_at", "merged_by", "merged_into", "merged_strategy", "merged_push", "merged_commit"}),
    frozenset(ACCEPTANCE_PROVENANCE_FIELDS) - VCS_LOCK_META_FIELDS,
)


# ---------------------------------------------------------------------------
# Driver-body contract types (#5119 / FR-002 — contracts/merge-driver-body.md)
# ---------------------------------------------------------------------------


class MergeDriverError(Exception):
    """Unresolvable merge-driver conflict or invalid input.

    ``str(exc)`` is the EXACT stderr text a caller must echo unchanged — the
    CLI shell (``cli/commands/merge_driver.py``) never reformats it.
    """


@dataclass(frozen=True)
class MergeDriverOutcome:
    """A driver body's result. ``notice``, when set, is the exact stdout text
    a caller must echo (``merge-driver-review-cycle``'s collision notice
    today; every other body always returns ``notice=None``)."""

    notice: str | None = None


MergeDriverBody = Callable[[str, str, str], MergeDriverOutcome]


# ---------------------------------------------------------------------------
# #2970 (E1) — path-injection hardening shared by every driver entrypoint
# ---------------------------------------------------------------------------


class MergeDriverPathError(MergeDriverError):
    """Raised when a driver's ``%O``/``%A``/``%B`` argv escapes git's own
    same-directory temp-file contract (#2970 / Sonar S2083)."""


def _resolve_merge_driver_paths(base_path: str, ours_path: str, theirs_path: str) -> tuple[Path, Path, Path]:
    """Resolve the three driver placeholders, refusing a path-injection escape.

    Git materializes ``%O``/``%A``/``%B`` as three sibling temp files in ONE
    directory for every real invocation (verified empirically against git's
    merge-driver machinery); every driver-unit test in this codebase builds
    them the same way (three files under one ``tmp_path``). Requiring the
    three *resolved* paths to share a parent directory is therefore a
    zero-cost invariant for every legitimate caller, while an absolute path
    (e.g. ``/etc/...``) or a ``..`` traversal aimed at a DIFFERENT directory —
    the concrete shape of the 5 S2083 BLOCKER findings — fails it and is
    refused before any read/write happens. Every body calls this FIRST — the
    single choke point that closes all 5 S2083 findings in this module — and
    lets :class:`MergeDriverPathError` propagate to the caller (never catches
    it itself; the CLI shell translates it to ``typer.Exit(1)``, the replay
    caller lets it fail closed).
    """
    resolved = (
        Path(base_path).resolve(),
        Path(ours_path).resolve(),
        Path(theirs_path).resolve(),
    )
    if len({path.parent for path in resolved}) > 1:
        raise MergeDriverPathError(
            "refusing merge-driver invocation: %O/%A/%B do not share a parent "
            f"directory ({[str(path) for path in resolved]!r}) — refused as a "
            "possible path-injection attempt (#2970)"
        )
    return resolved


def run_event_log_driver(base_path: str, ours_path: str, theirs_path: str) -> MergeDriverOutcome:
    """Merge ``status.events.jsonl`` conflict inputs using event-log semantics."""
    base, ours, theirs = _resolve_merge_driver_paths(base_path, ours_path, theirs_path)
    try:
        merge_event_log_files(
            base_path=base,
            ours_path=ours,
            theirs_path=theirs,
        )
    except EventLogMergeError as exc:
        raise MergeDriverError(str(exc)) from exc
    return MergeDriverOutcome()


# ---------------------------------------------------------------------------
# meta.json field merge (FR-004)
# ---------------------------------------------------------------------------


# L2's non-object failure message begins with this prefix (regression-pinned in
# ``test_mission_metadata.py`` / ``test_feature_metadata.py``: ``"Expected JSON
# object in {path}, got {type}"``). The site-E wrapper keys on it to keep the
# driver's historical ``"is not a JSON object"`` wording for the non-object arm
# (pinned by ``test_merge_driver_wrappers_2709`` / this mission's site-E test)
# while surfacing every other decode failure as a named, path-carrying error.
_L2_NON_OBJECT_PREFIX = "Expected JSON object in "


def _blob_meta_error(path: Path, exc: ValueError) -> EventLogMergeError:
    """Translate a path-named L2 ``parse_meta_file`` failure into the driver's error.

    ``parse_meta_file(on_malformed="raise")`` raises a path-named
    :class:`ValueError` (:class:`kernel.meta_decode.MetaDecodeError` is a
    ``ValueError`` subclass; L2 re-expresses it as a plain path-named
    ``ValueError``) for both a non-object top level and a malformed body. Both
    arms become a single :class:`EventLogMergeError` so :func:`run_meta_driver`'s
    existing ``except EventLogMergeError`` still translates them to
    :class:`MergeDriverError`. The non-object arm keeps the historical ``"is not a
    JSON object"`` wording; any other decode failure names the path and surfaces
    the underlying reason.
    """
    if str(exc).startswith(_L2_NON_OBJECT_PREFIX):
        return EventLogMergeError(f"{path}: meta.json is not a JSON object")
    return EventLogMergeError(f"{path}: malformed meta.json ({exc})")


def _load_json_object(path: Path, *, empty_side: str | None = None) -> dict[str, Any]:
    """Load a ``meta.json`` object from *path*; empty/missing yields ``{}``.

    When *empty_side* names the side being read (``"ours"`` / ``"theirs"``) an
    empty or whitespace-only file raises instead: during a base-aware merge a
    real ``meta.json`` is never empty, and ``{}`` would read as "deleted every
    key" and silently drop the other side's keys (#5460).

    Decoding routes through the public L2 reader
    :func:`specify_cli.mission_metadata.parse_meta_file` (``on_malformed="raise"``)
    so a corrupt merge-blob ``meta.json`` fails LOUD and NAMED — an
    :class:`EventLogMergeError` carrying the path — rather than the pre-routing
    bare, unnamed :class:`json.JSONDecodeError` (mission
    ``meta-json-fail-closed-routing-01KZPJ1F`` / site E). The empty/whitespace-only
    short-circuit (C-010) is preserved *before* decoding.
    """
    if not path.exists():
        return {}
    try:
        is_blank = not path.read_text(encoding="utf-8").strip()
    except ValueError as exc:  # UnicodeDecodeError: a non-UTF-8 blob
        raise _blob_meta_error(path, exc) from exc
    if is_blank:
        if empty_side is not None:
            raise EventLogMergeError(f"{path}: {empty_side} meta.json is empty; refusing a base-aware merge that would treat it as deleting every key")
        return {}
    try:
        data = parse_meta_file(path, on_malformed="raise")
    except ValueError as exc:
        raise _blob_meta_error(path, exc) from exc
    # parse_meta_file("raise") returns a dict on success — a non-object top level
    # already raised above, and the empty case short-circuited to ``{}`` before
    # decoding, so ``data`` is never ``None`` here.
    return data or {}


def _union_acceptance_history(
    theirs_history: list[dict[str, Any]] | None,
    ours_history: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Union two ``acceptance_history`` lists, dedup by content, sort by time.

    Entries have no stable id, so dedup is by canonical-JSON equality. Order is
    deterministic (``accepted_at`` then ``accepted_by``) so the union is idempotent
    under repeat merges (NFR-001 spirit).
    """
    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for history in (theirs_history or [], ours_history or []):
        for entry in history:
            key = json.dumps(entry, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            combined.append(entry)
    combined.sort(
        key=lambda entry: (
            str(entry.get("accepted_at", "")),
            str(entry.get("accepted_by", "")),
        )
    )
    return combined


def _reconcile_meta_two_way(
    ours: dict[str, Any],
    theirs: dict[str, Any],
) -> dict[str, Any]:
    """Two-way field merge (no ancestor): the pre-#5460 rule, byte-for-byte."""
    result = dict(theirs)  # mission-authoritative baseline (C-002 / #1732).
    for key in _TARGET_AUTHORITATIVE_META_FIELDS:
        if key not in ours:
            continue
        if key == "mission_number" and not is_assigned_mission_number(ours[key]):
            continue
        result[key] = ours[key]
    unioned_history = _union_acceptance_history(
        theirs.get(ACCEPTANCE_HISTORY_FIELD),
        ours.get(ACCEPTANCE_HISTORY_FIELD),
    )
    if unioned_history:
        result[ACCEPTANCE_HISTORY_FIELD] = unioned_history
    return result


def _meta_merge_units(keys: set[str]) -> list[tuple[str, ...]]:
    """Group *keys* into merge units: one per touched coupled group, else one per key."""
    units: list[tuple[str, ...]] = []
    grouped: set[str] = {ACCEPTANCE_HISTORY_FIELD}  # unioned separately, never a unit
    for group in _META_COUPLED_KEY_GROUPS:
        if group & keys:
            units.append(tuple(sorted(group)))
            grouped |= group
    units.extend((key,) for key in sorted(keys - grouped))
    return units


def _resolve_meta_unit(
    unit: tuple[str, ...],
    base: dict[str, Any],
    ours: dict[str, Any],
    theirs: dict[str, Any],
) -> tuple[Any, ...]:
    """Three-way resolve one unit; returns the winning side's member values."""
    base_value = tuple(base.get(key, _MISSING) for key in unit)
    ours_value = tuple(ours.get(key, _MISSING) for key in unit)
    theirs_value = tuple(theirs.get(key, _MISSING) for key in unit)
    if ours_value == theirs_value or theirs_value == base_value:
        return ours_value
    if ours_value == base_value:
        return theirs_value
    # Genuine conflict: today's precedence (target-authoritative -> ours, else theirs).
    return ours_value if _TARGET_AUTHORITATIVE_META_SET.intersection(unit) else theirs_value


def _apply_mission_number_guard(
    result: dict[str, Any],
    ours: dict[str, Any],
    theirs: dict[str, Any],
) -> None:
    """An unassigned ``mission_number`` never replaces an assigned one (#4900)."""
    if is_assigned_mission_number(result.get("mission_number")):
        return
    for side in (ours, theirs):
        if is_assigned_mission_number(side.get("mission_number")):
            result["mission_number"] = side["mission_number"]
            return


def reconcile_meta_payloads(
    ours: dict[str, Any],
    theirs: dict[str, Any],
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Field-merge two ``meta.json`` payloads for the ``merge-driver-meta`` driver.

    Two rules, selected by *base* (git's ``%O`` ancestor):

    **Ordinary merge (non-empty *base*): per-unit three-way.** A merge unit is a
    single key, or a coupled key group that moves as one (the flatten triple
    ``coordination_branch``/``topology``/``flattened``; the ``merged_*`` block;
    the acceptance stamps). A unit changed, deleted or added on ONE side only
    survives from that side, so a teammate's unrelated edit can no longer revert
    ``mission close --discard`` (#5460); equal changes collapse. Only a genuine
    both-sides conflict falls back to the precedence below. ``None`` (JSON
    ``null``) is a value and an absent key is the private ``_MISSING`` sentinel,
    so "removed" and "changed to null" stay distinct.

    **Empty or absent *base*, or the consolidation pipeline's opt-out
    (:data:`META_DRIVER_TWO_WAY_ENV`): two-way.** ``ours`` is the target checkout
    (accepted-newer authority for acceptance/VCS provenance); ``theirs`` is the
    mission branch (planning-key authority, the #1732 mission-authoritative
    planning intent). Target-authoritative keys are taken from ``ours`` when
    present; every other key falls back to ``theirs``. The mission→target squash
    records no ancestry, so it must not trust ``%O``.

    In both rules ``acceptance_history`` is the deduplicated, time-ordered union
    of both sides, and ``mission_number`` is a deliberate exception to "present
    (even null) wins" (#4900): an UNASSIGNED value (``null``, missing,
    non-integer, 0 or negative; see
    :func:`specify_cli.consolidation.mission_number.is_assigned_mission_number`)
    never replaces a genuinely assigned one, whichever side it came from.
    """
    if not base:
        return _reconcile_meta_two_way(ours, theirs)
    result: dict[str, Any] = {}
    keys = set(base) | set(ours) | set(theirs)
    for unit in _meta_merge_units(keys):
        for key, value in zip(unit, _resolve_meta_unit(unit, base, ours, theirs), strict=True):
            if value is not _MISSING:
                result[key] = value
    _apply_mission_number_guard(result, ours, theirs)
    unioned_history = _union_acceptance_history(
        theirs.get(ACCEPTANCE_HISTORY_FIELD),
        ours.get(ACCEPTANCE_HISTORY_FIELD),
    )
    if unioned_history:
        result[ACCEPTANCE_HISTORY_FIELD] = unioned_history
    return result


def run_meta_driver(
    base_path: str,
    ours_path: str,
    theirs_path: str,
    *,
    two_way: bool = False,
) -> MergeDriverOutcome:
    """Field-merge conflicting ``meta.json`` blobs; write result to ``ours``.

    Reads the ``%O`` ancestor unless *two_way* (the consolidation pipeline's
    mission→target squash opt-out) is set. An empty/absent ancestor selects the
    two-way rule; a malformed one fails loud and named, like a malformed side.
    With a non-empty ancestor an empty or whitespace-only ``%A``/``%B`` is refused
    (named, nothing written) rather than read as "every key deleted".
    """
    base, ours, theirs = _resolve_merge_driver_paths(base_path, ours_path, theirs_path)
    try:
        base_payload = {} if two_way else _load_json_object(base)
        # Base-aware merge only: an empty side would read as "deleted every key".
        empty_ours, empty_theirs = ("ours", "theirs") if base_payload else (None, None)
        merged = reconcile_meta_payloads(
            _load_json_object(ours, empty_side=empty_ours),
            _load_json_object(theirs, empty_side=empty_theirs),
            base_payload,
        )
    except (json.JSONDecodeError, EventLogMergeError) as exc:
        raise MergeDriverError(str(exc)) from exc
    ours.write_text(json.dumps(merged, **_META_JSON_KWARGS) + "\n", encoding="utf-8")
    return MergeDriverOutcome()


# ---------------------------------------------------------------------------
# traces/*.md markdown union (FR-003 / #4894 section-granularity rewrite)
# ---------------------------------------------------------------------------

# An ATX markdown heading (``#`` through ``######``) OR the explicit
# ``<!-- section:... -->`` delimiter comment this module's docstring names --
# either one opens a new section/block for :func:`union_trace_texts`'s
# section-granularity dedup (#4894). Matched only OUTSIDE a fenced code block
# (see ``_TRACE_FENCE_MARKER``), so a heading-like line quoted inside a fence
# is never misread as a real section boundary.
_TRACE_SECTION_BOUNDARY = re.compile(r"^(?:#{1,6}\s+\S.*|<!--\s*section:.*-->)\s*$")
# A fenced-code-block delimiter opener/closer -- a run of 3+ backticks OR 3+
# tildes, per CommonMark fenced-code semantics. Captures the run so
# :func:`_match_trace_fence` can report both which character opened the
# fence and how long the run was (#4993: the backtick-only regex misread a
# heading-like line inside a ``~~~`` fence as a real section boundary; a
# landing-fold follow-up then found the naive "any fence marker toggles a
# shared boolean" toggler misread a DIFFERENT-character fence line, or a
# shorter same-character run, appearing INSIDE an already-open fence as a
# close -- see :func:`_split_trace_blocks`).
_TRACE_FENCE_MARKER = re.compile(r"^(`{3,}|~{3,})")


def _match_trace_fence(line: str) -> tuple[str, int] | None:
    """Return *line*'s fence character + run length if it opens/closes a
    fenced code block delimiter, else ``None``.

    CommonMark fenced-code semantics: a fence line is a run of 3+ backticks
    or 3+ tildes. A LATER fence line only closes an open fence when it uses
    the SAME character and its run is at least as long as the opener's --
    everything else (a different character, or a shorter same-character
    run) is ordinary content while a fence is open.
    """
    match = _TRACE_FENCE_MARKER.match(line)
    if match is None:
        return None
    run = match.group(1)
    return run[0], len(run)


# The id captured from a block's opening ``<!-- section:ID -->`` delimiter,
# when its first line is one -- see :func:`_trace_block_key`.
_TRACE_SECTION_ID = re.compile(r"^<!--\s*section:(.*?)\s*-->\s*$")


def _split_trace_blocks(text: str) -> list[tuple[str, ...]]:
    """Split *text* into ordered section/block-granularity chunks (#4894).

    A new block starts at each :data:`_TRACE_SECTION_BOUNDARY` line seen
    OUTSIDE a fenced code block; every other line (including a fence marker
    itself) belongs to the block already open. Content before the first
    boundary (a preamble) is its own block. Every line lands in exactly one
    block, in original order, so concatenating every returned block's lines
    reproduces *text* verbatim -- the property :func:`union_trace_texts`
    relies on for INV-3 (no non-empty line is ever dropped without an
    identical duplicate already present).

    Fence tracking is CHARACTER-aware (:func:`_match_trace_fence`): once a
    fence opens, only a later line with the SAME character and a run at
    least as long closes it. A landing-fold-only regression had a single
    shared ``in_fence`` boolean flip on ANY fence-marker line, so a literal
    ``~~~`` line inside a backtick-fenced block (or vice versa) spuriously
    closed the fence and over-split the block at the next heading-like line
    still really inside it.
    """
    blocks: list[list[str]] = [[]]
    open_fence: tuple[str, int] | None = None
    for line in text.splitlines():
        if open_fence is None and _TRACE_SECTION_BOUNDARY.match(line):
            blocks.append([])
        fence = _match_trace_fence(line)
        if fence is not None:
            if open_fence is None:
                open_fence = fence
            elif fence[0] == open_fence[0] and fence[1] >= open_fence[1]:
                open_fence = None
        blocks[-1].append(line)
    return [tuple(block) for block in blocks if block]


def union_trace_texts(ours_text: str, theirs_text: str) -> str:
    """Union two append-only trace documents at SECTION granularity (#4894 / FR-003).

    Concrete contract: split ``ours``/``theirs`` into blocks at
    :func:`_split_trace_blocks` boundaries (markdown headings and the
    ``<!-- section:... -->`` delimiter), then concatenate ours' blocks
    followed by theirs' blocks, in order, dropping a theirs block only when
    it is BYTE-IDENTICAL to a block already emitted -- a whole section
    repeated verbatim on both sides collapses to one copy. Repeated lines
    WITHIN one distinct section (fences, table separators, recurring prose)
    are never touched, so every non-empty line present in either input is
    present in the output (INV-3): a dropped theirs block's lines are, by
    construction, already present via the identical block that superseded it.

    This replaces the historical line-level GLOBAL dedup (#4894), which was
    unsound for markdown: a fence's opening/closing ``` line recurs across
    every distinct section and is not a duplicate to drop, so the old
    line-granularity ``seen`` set silently destroyed every section after the
    first.
    """
    ours_blocks = _split_trace_blocks(ours_text)
    seen: set[tuple[str, ...]] = set(ours_blocks)
    merged: list[str] = [line for block in ours_blocks for line in block]
    for block in _split_trace_blocks(theirs_text):
        if block in seen:
            continue
        seen.add(block)
        merged.extend(block)
    return "\n".join(merged) + "\n" if merged else ""


# A block's identity for 3-way base comparison: either the id captured from
# an explicit ``<!-- section:ID -->`` opening line, or, when no id is
# present, the block's first line -- EITHER WAY paired with its per-document
# occurrence ordinal (the running count of prior blocks in the SAME document
# sharing that same id, or that same first line when there is no id). Body-
# insensitive by construction (never a full-block hash): an edited section
# keeps its key, so an unchanged-vs-diverged comparison against base still
# fires -- see :func:`_trace_block_key`.
_TraceBlockKey = tuple[str, str, int]


def _trace_block_key(block: tuple[str, ...], occurrence_ordinal: int) -> _TraceBlockKey:
    """A block's identity for 3-way base comparison (non-colliding, #4993).

    Prefers the explicit ``<!-- section:ID -->`` id parsed from the block's
    opening line when present. Otherwise falls back to the block's first
    line. Either way the key is paired with *occurrence_ordinal* -- the
    running count of prior blocks in the SAME document sharing that same id
    (or first line) -- so two sections sharing an identical heading, OR two
    sections sharing an identical explicit id (itself an authoring mistake,
    but not one this driver should silently mis-attribute), get distinct
    keys instead of colliding on a bare id/first-line return (the pre-#4993
    bug: ``setdefault``-based indexing kept only the FIRST same-key block,
    so every later same-key block's base/ours comparison was silently
    mis-attributed to the first one's).

    Either way the key is body-insensitive (never a full-block hash): an
    in-place edit to a section's body keeps its key, which is what lets
    :func:`_drop_stale_theirs_trace_blocks` still detect "same section, body
    changed" (``theirs_unchanged`` vs ``ours_diverged``); only
    :func:`union_trace_texts`'s separate whole-block dedup compares full
    block content.
    """
    first_line = block[0] if block else ""
    section_id = _TRACE_SECTION_ID.match(first_line)
    if section_id:
        return ("id", section_id.group(1), occurrence_ordinal)
    return ("line", first_line, occurrence_ordinal)


def _trace_block_dedup_key(block: tuple[str, ...]) -> str:
    """The per-document occurrence-counting key for *block*: its explicit
    ``<!-- section:ID -->`` id when present, else its first line -- see
    :func:`_iter_trace_blocks_with_ordinal`.
    """
    first_line = block[0] if block else ""
    section_id = _TRACE_SECTION_ID.match(first_line)
    return f"id:{section_id.group(1)}" if section_id else f"line:{first_line}"


def _iter_trace_blocks_with_ordinal(
    text: str,
) -> Iterator[tuple[tuple[str, ...], int]]:
    """Yield each of *text*'s blocks paired with its per-document occurrence
    ordinal -- the running count of prior blocks in *this* document sharing
    the same :func:`_trace_block_dedup_key`, which :func:`_trace_block_key`
    folds in so duplicate-id and duplicate-heading blocks alike get distinct
    keys.
    """
    occurrence_counts: dict[str, int] = {}
    for block in _split_trace_blocks(text):
        dedup_key = _trace_block_dedup_key(block)
        ordinal = occurrence_counts.get(dedup_key, 0)
        occurrence_counts[dedup_key] = ordinal + 1
        yield block, ordinal


def _index_trace_blocks_by_key(text: str) -> dict[_TraceBlockKey, tuple[str, ...]]:
    """Index *text*'s blocks by :func:`_trace_block_key`, first-occurrence-wins.

    Occurrence ordinals are computed per this document alone, matching the
    identical per-document computation applied to ``theirs`` in
    :func:`_drop_stale_theirs_trace_blocks`, so the same section lines up
    across base/ours/theirs by key.
    """
    indexed: dict[_TraceBlockKey, tuple[str, ...]] = {}
    for block, ordinal in _iter_trace_blocks_with_ordinal(text):
        indexed.setdefault(_trace_block_key(block, ordinal), block)
    return indexed


def _drop_stale_theirs_trace_blocks(base_text: str, ours_text: str, theirs_text: str) -> str:
    """Filter *theirs_text* to drop sections stale relative to *base_text* (#4894).

    3-way base-awareness: a theirs block UNCHANGED from base under its
    section identity (:func:`_trace_block_key`), while ours' same-identity
    block DIVERGED from base, is theirs' now-superseded copy of content ours
    already edited -- keeping it would resurrect stale prose alongside ours'
    edit under a duplicate-looking heading. Every other theirs block (new, or
    itself changed from base, or a key ours never touched) is kept untouched
    and handed on to :func:`union_trace_texts`, which still performs the
    byte-identical whole-block dedup / append-union.

    A key both sides changed differently from base is deliberately NOT
    filtered here -- both versions are kept (never silently picked), so a
    genuine structural divergence never turns into a silent, lossy exit-0;
    it simply appends both authored copies, preserving INV-3 without
    aborting the merge (spec C-003: not fail-closed on an ordinary,
    non-verdict-bearing repeat/divergence -- unlike the keyed row-matrix
    drivers' verdict-field fail-closed rule, traces are keyless append-union
    prose).
    """
    base_by_key = _index_trace_blocks_by_key(base_text)
    ours_by_key = _index_trace_blocks_by_key(ours_text)

    kept: list[str] = []
    for block, ordinal in _iter_trace_blocks_with_ordinal(theirs_text):
        key = _trace_block_key(block, ordinal)
        base_block = base_by_key.get(key)
        ours_block = ours_by_key.get(key)
        theirs_unchanged = base_block is not None and block == base_block
        ours_diverged = ours_block is not None and ours_block != base_block
        if theirs_unchanged and ours_diverged:
            continue  # theirs' stale copy of a section ours already edited
        kept.extend(block)
    return "\n".join(kept) + "\n" if kept else ""


def run_traces_driver(base_path: str, ours_path: str, theirs_path: str) -> MergeDriverOutcome:
    """Union conflicting ``traces/*.md`` documents; write result to ``ours`` (#4894).

    3-way base-aware: reads ``%O`` so a section theirs left UNCHANGED from
    base, while ours edited the same section, is recognized as stale and
    dropped rather than resurrected alongside ours' edit (see
    :func:`_drop_stale_theirs_trace_blocks`). The remaining union is still
    section-granularity and append-only via :func:`union_trace_texts` --
    never a lossy line-level global dedup, never fail-closed on an ordinary
    repeat.

    A non-UTF-8 blob's ``UnicodeDecodeError`` propagates UNWRAPPED (never
    caught/translated here) -- this driver never caught it before the move
    and must not start now (research R2: "do not broaden catches").
    """
    base, ours, theirs = _resolve_merge_driver_paths(base_path, ours_path, theirs_path)
    base_text = base.read_text(encoding="utf-8") if base.exists() else ""
    ours_text = ours.read_text(encoding="utf-8") if ours.exists() else ""
    theirs_text = theirs.read_text(encoding="utf-8") if theirs.exists() else ""
    filtered_theirs_text = _drop_stale_theirs_trace_blocks(base_text, ours_text, theirs_text)
    ours.write_text(union_trace_texts(ours_text, filtered_theirs_text), encoding="utf-8")
    return MergeDriverOutcome()


# ---------------------------------------------------------------------------
# Row-aware, base-aware (3-way) matrix merge (FR-008)
# ---------------------------------------------------------------------------
#
# ``acceptance-matrix.json`` and ``issue-matrix.json`` are COORD-partition
# artifacts that both sides of a squash mission→target merge can genuinely
# diverge on (#2482 / #2804): the target fills evidence at accept time, a
# mission branch may independently gain its own rows. A whole-file
# "more-filled-side" pick (the retired #2804 heuristic) clobbers whichever
# side loses the fill-score comparison even when the two sides wrote
# DISJOINT rows — the exact #2482 loss this rewrite closes. These drivers
# instead reconcile PER ROW, 3-way (``%O``/``%A``/``%B``): see
# ``contracts/merge-driver-algorithm.md`` for the full contract this
# implements (row-key canonicalization, per-row reconciliation, delete-vs-
# stale disambiguation, byte-determinism, never re-authoring a computed
# field).


class RowMatrixMergeError(MergeDriverError):
    """Raised when a matrix document cannot be parsed/reconciled row-aware.

    Covers malformed JSON documents, the intra-side duplicate-key guard (two
    distinct raw rows on ONE side normalizing to the same canonical key), and
    a genuinely-diverged VERDICT-authority field (#4880: both sides authored
    a differing ``pass_fail`` / ``result`` / ``verdict``) — each is refused
    rather than silently resolved, per the algorithm contract's "never silent
    drop / never silent verdict flip" rule.
    """


def _parse_json_document(path: Path) -> dict[str, Any]:
    """Load a JSON *object* document from *path*; a missing file yields ``{}``."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RowMatrixMergeError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise RowMatrixMergeError(f"{path}: matrix document is not a JSON object")
    return data


# Git-style conflict markers used ONLY by the non-aborting review-cycle
# prose driver (:func:`run_review_cycle_driver`) to embed a two-verdict
# collision verbatim into an unread ``.md`` render (NFR-002). #4880 removed
# the row-matrix field-level embed path (:func:`_merge_field` now raises
# :class:`RowMatrixMergeError` instead) — these constants are no longer used
# for verdict-bearing JSON documents.
_CONFLICT_MARKER_OURS = "<<<<<<< ours"
_CONFLICT_MARKER_SEP = "======="
_CONFLICT_MARKER_THEIRS = ">>>>>>> theirs"


# Unset-sentinel placeholders per verdict-bearing field. During a 3-way merge an
# unset value yields to an authored value instead of failing closed (#4880): a
# lane that never recorded a verdict must not abort a merge with a lane that did.
# Imports issue_matrix._SCAFFOLD_VERDICT_PLACEHOLDER directly (rather than
# duplicating its "unknown" literal) so a retune of that canonical placeholder
# cannot silently desync this sentinel and reintroduce #2804. The acceptance
# side mirrors the CRITERION_VERDICTS / NEGATIVE_INVARIANT_RESULTS "pending"
# member (no importable named constant exists for it yet).
_ISSUE_MATRIX_SENTINELS: Mapping[str, str] = {"verdict": _SCAFFOLD_VERDICT_PLACEHOLDER}
_ACCEPTANCE_CRITERION_SENTINELS: Mapping[str, str] = {"pass_fail": "pending"}
_ACCEPTANCE_INVARIANT_SENTINELS: Mapping[str, str] = {"result": "pending"}


def _merge_field(
    field_name: str,
    base_v: Any,
    ours_v: Any,
    theirs_v: Any,
    *,
    sentinels: Mapping[str, str] | None = None,
    row_key: str | None = None,
) -> Any:
    """3-way merge of one field value (contract: per-row reconciliation).

    ``ours_v``/``theirs_v`` equal → take it (whether or not it changed from
    base). Changed on exactly one side (relative to *base_v*) → take the
    changed side (this also covers a field one side dropped entirely — a
    dict ``.get`` miss and ``base_v`` both read as ``None``, so "removed" and
    "changed to None" are treated identically, which is the correct 3-way
    reading). Changed on both sides to different values → a VERDICT-authority
    field (a key in *sentinels*) fails closed unless one side is the unset
    sentinel; any other field prefers the target (``ours``). Never embeds an
    in-band conflict marker into the verdict artifact (#4880 / #2804).
    """
    if ours_v == theirs_v:
        return ours_v
    if ours_v == base_v:
        return theirs_v
    if theirs_v == base_v:
        return ours_v
    # Both sides diverged from base to different values. Two rules reconcile
    # #4880 (a silently-corrupted VERDICT must fail closed) with #2804 (a
    # scaffold/placeholder row must yield to the filled side, never abort a
    # normal lane consolidation):
    #
    #   * VERDICT-AUTHORITY fields (pass_fail / result / verdict — the keys in
    #     *sentinels*) fail closed on a genuine disagreement, EXCEPT that an
    #     unset sentinel (``pending`` / ``unknown``) is not an authored value
    #     and yields to the authored side.
    #   * every OTHER field (evidence_ref, description, notes, proof_type, ...)
    #     is not verdict authority: it never aborts and never embeds a marker —
    #     it prefers the target side (``ours``), matching #2804 / #1732's
    #     target-authoritative tie convention (the accumulating target carries
    #     the filled value; the incoming lane's scaffold placeholder loses).
    verdict_sentinel = (sentinels or {}).get(field_name)
    if verdict_sentinel is None:
        return ours_v  # non-verdict field: target-authoritative, no abort, no marker
    if theirs_v == verdict_sentinel and ours_v != verdict_sentinel:
        return ours_v
    if ours_v == verdict_sentinel and theirs_v != verdict_sentinel:
        return theirs_v
    # #4880: two genuinely-authored, differing verdicts — fail closed. Name the
    # offending row so an operator can locate it in a many-row matrix, and label
    # the sides target/incoming (the ``ours``/``theirs`` primary/merge footgun).
    row_label = f"row {row_key!r}: " if row_key is not None else ""
    raise RowMatrixMergeError(
        f"{row_label}verdict field {field_name!r} diverged on both sides with no common base value (target/ours={ours_v!r}, incoming/theirs={theirs_v!r})"
    )


def _merge_row_fields(
    base_row: Mapping[str, Any] | None,
    ours_row: Mapping[str, Any],
    theirs_row: Mapping[str, Any],
    *,
    sentinels: Mapping[str, str] | None = None,
    row_key: str | None = None,
) -> dict[str, Any]:
    """Per-field 3-way merge of one row that exists (with differing content)
    on at least two of the three sides. ``base_row`` may be ``None`` (the row
    was added independently on both ``ours``/``theirs`` — every field then
    merges against an absent/``None`` base, which correctly always resolves
    to "changed on the side that has it")."""
    base = base_row or {}
    field_names = dict.fromkeys((*base, *ours_row, *theirs_row))
    return {name: _merge_field(name, base.get(name), ours_row.get(name), theirs_row.get(name), sentinels=sentinels, row_key=row_key) for name in field_names}


def _reconcile_added_row(
    ours_row: Mapping[str, Any] | None,
    theirs_row: Mapping[str, Any] | None,
    *,
    sentinels: Mapping[str, str] | None = None,
    row_key: str | None = None,
) -> dict[str, Any] | None:
    """A key absent from *base*: added on one side, or independently on both
    (contract rule 1/2 — never a delete, since there is no base entry to
    delete)."""
    if ours_row is None:
        return None if theirs_row is None else dict(theirs_row)  # added on B only
    if theirs_row is None:
        return dict(ours_row)  # added on A only
    if ours_row == theirs_row:
        return dict(ours_row)
    return _merge_row_fields(None, ours_row, theirs_row, sentinels=sentinels, row_key=row_key)


def _reconcile_existing_row(
    base_row: Mapping[str, Any],
    ours_row: Mapping[str, Any] | None,
    theirs_row: Mapping[str, Any] | None,
    *,
    sentinels: Mapping[str, str] | None = None,
    row_key: str | None = None,
) -> dict[str, Any] | None:
    """A key present in *base*: delete-vs-stale disambiguation (contract) +
    3-way field merge when both sides still carry (differing) content."""
    if ours_row is None:
        # ours deleted; theirs still carries the base entry (maybe changed).
        return None if theirs_row is None or theirs_row == base_row else dict(theirs_row)
    if theirs_row is None:
        # theirs deleted; ours still carries the base entry (maybe changed).
        return None if ours_row == base_row else dict(ours_row)
    if ours_row == theirs_row:
        return dict(ours_row)
    return _merge_row_fields(base_row, ours_row, theirs_row, sentinels=sentinels, row_key=row_key)


def _reconcile_row(
    *,
    base_row: Mapping[str, Any] | None,
    ours_row: Mapping[str, Any] | None,
    theirs_row: Mapping[str, Any] | None,
    sentinels: Mapping[str, str] | None = None,
    row_key: str | None = None,
) -> dict[str, Any] | None:
    """One row's 3-way reconciliation (contract: per-row reconciliation +
    delete-vs-stale disambiguation). Returns the merged row, or ``None`` when
    the row is dropped (both sides deleted it, or one side deleted it while
    the other left it genuinely unchanged from *base_row*)."""
    if base_row is None:
        return _reconcile_added_row(ours_row, theirs_row, sentinels=sentinels, row_key=row_key)
    return _reconcile_existing_row(base_row, ours_row, theirs_row, sentinels=sentinels, row_key=row_key)


def _canonicalize_keyed_rows(
    rows: Any,
    *,
    key_of: Callable[[Any, Mapping[str, Any]], str],
    is_row: Callable[[Any], bool] = lambda row: isinstance(row, Mapping),
) -> dict[str, dict[str, Any]]:
    """Canonicalize a side's raw row collection to ``{canonical_key: row}``.

    *rows* may be a ``list`` (acceptance-matrix ``criteria``/``negative_
    invariants``) or a ``dict`` keyed by raw issue-ref (issue-matrix
    ``rows``) — *key_of* extracts the canonical key from each. The intra-
    side collision guard (contract) fires here: two DISTINCT raw rows on
    this ONE side normalizing to the same canonical key raise
    :class:`RowMatrixMergeError` rather than silently collapsing (identical
    duplicates are harmlessly deduped).
    """
    items = rows.items() if isinstance(rows, Mapping) else enumerate(rows or [])
    canonical: dict[str, dict[str, Any]] = {}
    for raw_key, row in items:
        if not is_row(row):
            continue
        key = key_of(raw_key, row)
        row_dict = dict(row)
        if key in canonical and canonical[key] != row_dict:
            raise RowMatrixMergeError(
                f"intra-side duplicate row key {key!r}: two distinct rows on "
                "one side normalize to the same canonical key — refusing to "
                "silently collapse either (#2970-adjacent row-merge guard)"
            )
        canonical[key] = row_dict
    return canonical


def _reconcile_keyed_rows(
    base_rows: Any,
    ours_rows: Any,
    theirs_rows: Any,
    *,
    key_of: Callable[[Any, Mapping[str, Any]], str],
    sentinels: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """3-way reconcile one row collection, keyed by canonicalized identity.

    Returns ``{canonical_key: merged_row}`` in sorted-key order — the stable
    canonical order the contract requires for byte-determinism. *sentinels*
    maps a field name to its unset placeholder (e.g. ``{"verdict": "unknown"}``)
    so an unset side yields to an authored side instead of failing closed.
    """
    base = _canonicalize_keyed_rows(base_rows, key_of=key_of)
    ours = _canonicalize_keyed_rows(ours_rows, key_of=key_of)
    theirs = _canonicalize_keyed_rows(theirs_rows, key_of=key_of)

    merged: dict[str, dict[str, Any]] = {}
    for key in sorted({*base, *ours, *theirs}):
        row = _reconcile_row(base_row=base.get(key), ours_row=ours.get(key), theirs_row=theirs.get(key), sentinels=sentinels, row_key=key)
        if row is not None:
            merged[key] = row
    return merged  # already inserted in sorted-key order


# ---------------------------------------------------------------------------
# issue-matrix.json (FR-008): rows keyed by canonicalized issue_ref
# ---------------------------------------------------------------------------

# Matches a trailing run of 1+ digits, optionally preceded by ``#``/``GH-``/
# ``gh#`` — the shapes ``#1726`` / ``GH-1726`` / ``1726`` all normalize to.
_ISSUE_REF_DIGITS = re.compile(r"(\d+)\s*$")


def _canonicalize_issue_ref(raw_ref: str) -> str:
    """Normalize ``#1726`` / ``GH-1726`` / ``1726`` to the one canonical form.

    A ref with no trailing digits (a non-numeric key) is returned stripped,
    unchanged — it is already its own canonical form.
    """
    match = _ISSUE_REF_DIGITS.search(raw_ref.strip())
    return f"#{match.group(1)}" if match else raw_ref.strip()


def _issue_row_key(raw_ref: Any, _row: Mapping[str, Any]) -> str:
    return _canonicalize_issue_ref(str(raw_ref))


def reconcile_issue_matrix_documents(
    base_doc: Mapping[str, Any],
    ours_doc: Mapping[str, Any],
    theirs_doc: Mapping[str, Any],
) -> dict[str, Any]:
    """3-way, row-aware reconciliation of an ``issue-matrix.json`` document."""
    merged_rows = _reconcile_keyed_rows(
        base_doc.get("rows", {}),
        ours_doc.get("rows", {}),
        theirs_doc.get("rows", {}),
        key_of=_issue_row_key,
        sentinels=_ISSUE_MATRIX_SENTINELS,
    )
    return {"schema_version": ISSUE_MATRIX_SCHEMA_VERSION, "rows": merged_rows}


def run_issue_matrix_driver(base_path: str, ours_path: str, theirs_path: str) -> MergeDriverOutcome:
    """Row-aware, 3-way merge of ``issue-matrix.json``; write result to ``ours`` (FR-008)."""
    base, ours, theirs = _resolve_merge_driver_paths(base_path, ours_path, theirs_path)
    # reconcile_issue_matrix_documents never calls AcceptanceMatrix.from_dict, so the
    # only error it (or _parse_json_document) can raise is RowMatrixMergeError --
    # already a MergeDriverError subclass, so it propagates unhandled here, never
    # re-wrapped (contract invariant 3).
    merged = reconcile_issue_matrix_documents(
        _parse_json_document(base),
        _parse_json_document(ours),
        _parse_json_document(theirs),
    )
    ours.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return MergeDriverOutcome()


# ---------------------------------------------------------------------------
# acceptance-matrix.json (FR-008): criteria keyed by criterion_id,
# negative_invariants keyed by invariant_id
# ---------------------------------------------------------------------------

_ACCEPTANCE_IDENTITY_FIELDS: tuple[str, ...] = ("mission_slug", "mission_number", "mission_type")


def _row_key_field(field_name: str) -> Callable[[Any, Mapping[str, Any]], str]:
    """A ``key_of`` extractor reading a row's own id *field_name* (list-shaped
    collections have no meaningful raw key of their own — the id lives
    inside the row)."""

    def _key_of(_raw_key: Any, row: Mapping[str, Any]) -> str:
        return str(row.get(field_name, ""))

    return _key_of


def _reconcile_identity_fields(
    base_doc: Mapping[str, Any],
    ours_doc: Mapping[str, Any],
    theirs_doc: Mapping[str, Any],
) -> dict[str, Any]:
    """Prefer ``ours`` (target-authoritative, mirroring the #1732/#2804 tie
    convention) for the acceptance-matrix's scalar identity fields, falling
    back to ``theirs`` then *base_doc* so ``mission_slug`` — required by
    :meth:`AcceptanceMatrix.from_dict` — is never missing from a real
    document."""
    result: dict[str, Any] = {}
    for name in _ACCEPTANCE_IDENTITY_FIELDS:
        ours_value = ours_doc.get(name)
        result[name] = ours_value if ours_value not in (None, "") else theirs_doc.get(name)
    if result.get("mission_slug") in (None, ""):
        result["mission_slug"] = base_doc.get("mission_slug", "")
    return result


def reconcile_acceptance_matrix_documents(
    base_doc: Mapping[str, Any],
    ours_doc: Mapping[str, Any],
    theirs_doc: Mapping[str, Any],
) -> dict[str, Any]:
    """3-way, row-aware reconciliation of an ``acceptance-matrix.json`` document.

    ``overall_verdict`` is a COMPUTED property (never a stored/merged field,
    per the contract) — it is recomputed by :class:`AcceptanceMatrix` from the
    reconciled ``criteria``/``negative_invariants``, never taken from either
    side's stored (possibly stale) value.
    """
    merged_criteria = _reconcile_keyed_rows(
        base_doc.get("criteria", []),
        ours_doc.get("criteria", []),
        theirs_doc.get("criteria", []),
        key_of=_row_key_field("criterion_id"),
        sentinels=_ACCEPTANCE_CRITERION_SENTINELS,
    )
    merged_invariants = _reconcile_keyed_rows(
        base_doc.get("negative_invariants", []),
        ours_doc.get("negative_invariants", []),
        theirs_doc.get("negative_invariants", []),
        key_of=_row_key_field("invariant_id"),
        sentinels=_ACCEPTANCE_INVARIANT_SENTINELS,
    )
    merged_document = {
        **_reconcile_identity_fields(base_doc, ours_doc, theirs_doc),
        "criteria": list(merged_criteria.values()),
        "negative_invariants": list(merged_invariants.values()),
    }
    reconciled: dict[str, Any] = AcceptanceMatrix.from_dict(merged_document).to_dict()
    return reconciled


def run_acceptance_matrix_driver(base_path: str, ours_path: str, theirs_path: str) -> MergeDriverOutcome:
    """Row-aware, 3-way merge of ``acceptance-matrix.json``; write result to ``ours`` (FR-008)."""
    base, ours, theirs = _resolve_merge_driver_paths(base_path, ours_path, theirs_path)
    try:
        merged = reconcile_acceptance_matrix_documents(
            _parse_json_document(base),
            _parse_json_document(ours),
            _parse_json_document(theirs),
        )
    except AcceptanceMatrixParseError as exc:
        raise MergeDriverError(str(exc)) from exc
    # A RowMatrixMergeError from _parse_json_document is already a
    # MergeDriverError subclass and propagates unhandled here, never
    # re-wrapped (contract invariant 3).
    ours.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return MergeDriverOutcome()


# ---------------------------------------------------------------------------
# review-cycle-*.md (review-cycle-verdict-seam-rebuild-01KZ2W7W WP18/T077;
# DOWNGRADED by verdict-seam-write-unification-01KZ9Q35 WP09/FR-014/D-PLAN-6):
# a two-verdict collision is embedded, best-effort, and NEVER aborts the squash
# ---------------------------------------------------------------------------
#
# T017's discharge (see WP04's ruling and tests/architectural/test_merge_reconciliation_
# class_guard.py::test_review_cycle_tasks_hazard_is_ruled_and_tracked): the
# create-window split (ADR 2026-08-03-1) means a coord mission's review
# cycles land on TWO different physical surfaces during the migration window
# (cycle 1 on PRIMARY at ``tasks/<wp>/``, a later cycle mis-numbered "1" again
# on COORD because ``ReviewCycleArtifact.next_cycle_number`` globs only the
# worktree it is called from) -- so a genuine, DIFFERENT-content collision
# under the SAME ``review-cycle-N.md`` filename is reachable, not
# hypothetical.
#
# THE ORIGINAL DESIGN DECISION (T077, weighed against FR-006 / C-002(b)):
#
#   (a) REFUSE fail-closed -- embed both raw verdict documents, verbatim and
#       clearly demarcated (never interleaved/blended), and exit non-zero so
#       ``git merge --squash`` reports the path as an unresolved
#       conflict (``_merge_branch_into`` then tears down the squash and
#       raises -- the target ref is never advanced).
#
#   (b) RENUMBER -- silently reassign the incoming ("theirs") record the next
#       free cycle number in the reconciled directory and write it out as a
#       SECOND file, leaving ``ours`` untouched.
#
# WP18 implemented (a), not (b), because at the time a ``review-cycle-N.md``
# was the AUTHORITATIVE verdict record -- a reader could not tell a blended or
# silently-renumbered document from a genuine one, so any automatic
# reconciliation risked "inventing" a verdict decision (C-002(b)/FR-006).
#
# THE WP09/FR-014 DOWNGRADE (D-PLAN-6): the review-cycle-verdict-seam-rebuild
# mission's own WP05 (this mission's dependency) demoted the ``.md`` render to
# non-authoritative, unread best-effort prose -- ``status.events.jsonl``'s
# ``review_result`` event slot is now the sole verdict authority (see
# ``kitty-specs/verdict-seam-write-unification-01KZ9Q35/contracts/
# provenance-backfill.md``). With no reader left that trusts this document's
# ``cycle_number``/``verdict`` fields to decide "which record is latest", the
# fabrication risk (a) was refusing to accept no longer applies: two divergent
# best-effort renders colliding under one filename are ordinary prose drift,
# not a decision an automated driver would be wrong to reconcile. Aborting an
# otherwise-clean squash over unread prose is now pure friction with no
# safety benefit, so this driver is DOWNGRADED to non-aborting: it still
# embeds BOTH raw documents verbatim (never blending/interleaving/fabricating
# a merged verdict -- the same "never silently drop a side" discipline this
# module's row-matrix field-conflict markers use), but no longer raises an
# error -- the squash proceeds with the conflict-marked prose as the resolved
# content. Retiring the driver entirely (letting the collision fail closed
# like any other ordinary conflict) was considered and rejected only because
# embedding both sides costs nothing and preserves strictly more information
# than a hard conflict would.
#
# Identical content on both sides is NOT a collision at all -- it is the
# trivial, common case (the same verdict was independently recorded/copied
# onto both partitions) and resolves cleanly with no conflict markers.


def run_review_cycle_driver(base_path: str, ours_path: str, theirs_path: str) -> MergeDriverOutcome:
    """Reconcile a ``review-cycle-N.md`` collision, best-effort, non-aborting.

    Two distinct verdict documents colliding under the same filename are
    NEVER unioned/field-merged/interleaved into one document -- see the
    module-level design-decision comment immediately above this function for
    the full reasoning (embed both verbatim, never fabricate a blended
    verdict). Unlike WP18's original T077 driver, a divergent collision no
    longer aborts the squash (FR-014/D-PLAN-6): the ``.md`` render is
    non-authoritative, unread prose now that ``status.events.jsonl``'s
    ``review_result`` event slot is the sole verdict authority, so refusing
    the merge over it is no longer justified. The collision notice is
    returned via :attr:`MergeDriverOutcome.notice` for the CLI shell to echo
    to stdout -- the in-process replay caller (#5119) does not print it.

    Identical content on both sides (byte-for-byte) is the trivial fast path:
    resolves cleanly, exit 0, never reported as a conflict. Otherwise, both
    raw documents are embedded verbatim inside standard git-style conflict
    markers (never blended field-by-field -- a review verdict has no safely
    mergeable sub-fields the way a JSON matrix row does) and the driver
    resolves with exit 0, so ``git merge --squash`` treats the path as
    resolved and the squash proceeds.
    """
    base, ours, theirs = _resolve_merge_driver_paths(base_path, ours_path, theirs_path)
    _ = base  # %O ancestor: unused -- an add/add collision has no common base,
    # and the fast-path decision is a pure 2-way (ours vs theirs) content
    # comparison regardless of whether a base exists.
    ours_text = ours.read_text(encoding="utf-8") if ours.exists() else ""
    theirs_text = theirs.read_text(encoding="utf-8") if theirs.exists() else ""

    if ours_text == theirs_text:
        # Trivial fast path (T077 validation checklist): the same verdict
        # landed on both partitions -- not a conflict, nothing to reconcile.
        ours.write_text(ours_text, encoding="utf-8")
        return MergeDriverOutcome()

    conflict_document = "\n".join(
        (
            _CONFLICT_MARKER_OURS,
            ours_text,
            _CONFLICT_MARKER_SEP,
            theirs_text,
            _CONFLICT_MARKER_THEIRS,
        )
    )
    ours.write_text(conflict_document, encoding="utf-8")
    notice = (
        f"review-cycle verdict collision at {ours.name}: two distinct "
        "best-effort renders collided under one filename (T017 create-window "
        "hazard); both embedded verbatim behind conflict markers -- "
        "non-aborting (FR-014/D-PLAN-6: the .md is non-authoritative, unread "
        "prose; the squash proceeds)"
    )
    return MergeDriverOutcome(notice=notice)


# ---------------------------------------------------------------------------
# decisions/index.json (FR-009b / D13 / #5023): entries keyed by decision_id,
# terminal-beats-open fold precedence
# ---------------------------------------------------------------------------
#
# When the decision ledger becomes a PRIMARY-partition record (WP12),
# ``decisions/index.json`` starts travelling with lane and mission branches:
# two lanes that each add a decision then both rewrite the same file, and a
# plain ``git merge`` either conflicts or (under ``-X theirs``) silently
# drops one lane's entry. This driver unions ``entries`` keyed by
# ``decision_id`` so lane integration never loses an index entry.
#
# ``index_fold.apply_terminal``/``_select_terminal_event`` (the canonical
# event -> IndexEntry fold) only ever apply a terminal transition to ONE
# entry -- they never compare two independently-evolved ``IndexEntry``
# versions, so the terminal-beats-open precedence below has to be written
# here, reusing ``index_fold.is_allowed_terminal_reopen`` (the single
# transition-rule authority, #4919) rather than re-deriving which
# terminal-to-terminal transition is a legal reopen.


class DecisionIndexMergeError(MergeDriverError):
    """Raised when a ``decisions/index.json`` document cannot be parsed/reconciled.

    Covers malformed ``entries``, an entry missing (or non-string)
    ``decision_id``, an entry with an invalid ``status``, and a genuine
    collision this driver must never silently resolve -- a same-``decision_id``
    divergence that is neither "one side is OPEN, the other terminal" nor
    "the two terminal statuses form the one legal reopen pair" (see
    :func:`_resolve_decision_entry`). Mirrors the row-matrix drivers'
    ``RowMatrixMergeError``/the review-cycle driver's embedded-collision
    discipline: never silently drop a side, never silently pick one.
    """


def _decision_index_entries(doc: Mapping[str, Any], *, side: str) -> dict[str, dict[str, Any]]:
    """Canonicalize one side's ``entries`` to ``{decision_id: entry}``.

    Raises :class:`DecisionIndexMergeError` for a non-list ``entries``, a
    non-object entry, or an entry missing (or non-string) ``decision_id`` --
    never fabricates a merge over malformed input.
    """
    entries = doc.get("entries", [])
    if not isinstance(entries, list):
        raise DecisionIndexMergeError(f"{side}: 'entries' is not a list ({entries!r})")
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise DecisionIndexMergeError(f"{side}: entry is not a JSON object ({entry!r})")
        decision_id = entry.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id:
            raise DecisionIndexMergeError(f"{side}: entry missing 'decision_id' ({entry!r})")
        by_id[decision_id] = dict(entry)
    return by_id


_DECISION_TERMINAL_STATUSES = frozenset({DecisionStatus.RESOLVED, DecisionStatus.DEFERRED, DecisionStatus.CANCELED})


def _decision_entry_status(entry: Mapping[str, Any], *, side: str, decision_id: str) -> DecisionStatus:
    try:
        return DecisionStatus(entry.get("status"))
    except ValueError as exc:
        raise DecisionIndexMergeError(f"{side}: decision {decision_id!r} has an invalid 'status' ({entry.get('status')!r})") from exc


def _resolve_decision_entry(
    decision_id: str,
    ours_entry: dict[str, Any] | None,
    theirs_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve one ``decision_id``'s entry across ``ours``/``theirs``.

    - present on only one side -> taken as is;
    - identical content on both -> kept once;
    - one OPEN and the other terminal (resolved/deferred/canceled) -> the
      terminal entry wins (a terminal status always beats an open one);
    - both terminal, forming the one legal reopen pair
      (:func:`~specify_cli.decisions.index_fold.is_allowed_terminal_reopen`
      -- today only deferred -> resolved) -> the reopen TARGET wins, the
      same rule the forward write path (``decisions/service.py``) enforces;
    - any other divergence (two conflicting terminals, or a same-status
      content divergence) -- a genuine collision -- raises
      :class:`DecisionIndexMergeError`, exactly like the review-cycle
      driver's two-verdict collision, never silently picking a side.
    """
    if ours_entry is None:
        if theirs_entry is None:  # pragma: no cover - unreachable: caller only unions present ids
            raise DecisionIndexMergeError(f"decision {decision_id!r} resolved with no entry on either side")
        return theirs_entry
    if theirs_entry is None:
        return ours_entry
    if ours_entry == theirs_entry:
        return ours_entry

    ours_status = _decision_entry_status(ours_entry, side="ours", decision_id=decision_id)
    theirs_status = _decision_entry_status(theirs_entry, side="theirs", decision_id=decision_id)
    ours_terminal = ours_status in _DECISION_TERMINAL_STATUSES
    theirs_terminal = theirs_status in _DECISION_TERMINAL_STATUSES

    if ours_terminal and not theirs_terminal:
        return ours_entry
    if theirs_terminal and not ours_terminal:
        return theirs_entry
    if ours_terminal and theirs_terminal and ours_status != theirs_status:
        if is_allowed_terminal_reopen(ours_status, theirs_status):
            return theirs_entry
        if is_allowed_terminal_reopen(theirs_status, ours_status):
            return ours_entry

    raise DecisionIndexMergeError(
        f"decision {decision_id!r} diverged on both sides with no safe precedence "
        f"(ours status={ours_status.value!r}, theirs status={theirs_status.value!r}) "
        "-- refusing to silently pick a side"
    )


def union_decision_index(ours: Mapping[str, Any], theirs: Mapping[str, Any]) -> dict[str, Any]:
    """Pure union of two ``decisions/index.json`` documents (T060/P-M6).

    Shared by the git merge-driver body (:func:`run_decision_index_driver`)
    below and ``doctor decisions --repair``'s coordination-only-ledger merge,
    so there is exactly one union implementation (#5023) -- never a second,
    independently-maintained copy.

    ``entries`` is unioned keyed by ``decision_id`` with terminal-beats-open
    fold precedence (see :func:`_resolve_decision_entry`). Every OTHER
    top-level key (``version``, ``mission_id``) is target-authoritative --
    ``ours`` wins when present and non-empty, falling back to ``theirs`` --
    mirroring the row-matrix drivers' :func:`_reconcile_identity_fields` tie
    convention. The merged ``entries`` list is sorted deterministically by
    ``(created_at, decision_id)`` so a no-op union (``ours == theirs``) is
    byte-stable.

    Raises:
        DecisionIndexMergeError: malformed ``entries``, an entry missing
            ``decision_id``/with an invalid ``status``, or a genuine
            collision this function must never silently resolve (see
            :func:`_resolve_decision_entry`).
    """
    ours_entries = _decision_index_entries(ours, side="ours")
    theirs_entries = _decision_index_entries(theirs, side="theirs")

    merged_by_id = {
        decision_id: _resolve_decision_entry(decision_id, ours_entries.get(decision_id), theirs_entries.get(decision_id))
        for decision_id in dict.fromkeys((*ours_entries, *theirs_entries))
    }
    merged_entries = sorted(
        merged_by_id.values(),
        key=lambda entry: (str(entry.get("created_at", "")), str(entry.get("decision_id", ""))),
    )

    top_level_keys = (set(ours) | set(theirs)) - {"entries"}
    result: dict[str, Any] = {}
    for key in top_level_keys:
        ours_value = ours.get(key)
        result[key] = ours_value if ours_value not in (None, "") else theirs.get(key)
    result["entries"] = merged_entries
    return result


def run_decision_index_driver(base_path: str, ours_path: str, theirs_path: str) -> MergeDriverOutcome:
    """Union ``decisions/index.json`` entries keyed by ``decision_id`` (FR-009b/#5023).

    Like :func:`run_meta_driver`, this is a 2-way field union over
    ``ours``/``theirs`` -- ``%O`` (the common ancestor) is unused.
    ``decisions/index.json`` entries are append-only (a decision is opened
    once and only ever transitions forward), so no base-aware
    delete-vs-stale disambiguation like the row-matrix drivers' is needed.

    Collision semantics (see :func:`union_decision_index`/
    :func:`_resolve_decision_entry`): a terminal status (resolved / deferred
    / canceled) always beats ``open``; the one legal terminal-to-terminal
    reopen (deferred -> resolved) takes the reopen target; any other
    divergence -- two conflicting terminal statuses, or malformed input --
    raises :class:`MergeDriverError` (a git merge conflict) and never
    fabricates a merge.

    Output is byte-stable for ``ours == theirs``: the merged document is
    round-tripped through :class:`~specify_cli.decisions.models.DecisionIndex`
    and re-serialized with the exact ``decisions.store.save_index`` writer
    bytes (``sort_keys=True``, 2-space indent, trailing newline) -- never a
    raw-dict ``json.dumps``, whose output would NOT byte-match
    ``save_index``'s pydantic ``model_dump(mode="json")`` form (pydantic's
    datetime JSON form differs from plain ``isoformat()``).
    """
    base, ours, theirs = _resolve_merge_driver_paths(base_path, ours_path, theirs_path)
    _ = base  # %O ancestor unused -- see docstring (2-way union, append-only entries).
    merged = union_decision_index(_parse_json_document(ours), _parse_json_document(theirs))
    try:
        index = DecisionIndex.model_validate(merged)
    except ValidationError as exc:
        raise MergeDriverError(f"decisions/index.json: merged document failed schema validation ({exc})") from exc
    sorted_entries = tuple(sorted(index.entries, key=lambda e: (e.created_at.isoformat(), e.decision_id)))
    sorted_index = index.model_copy(update={"entries": sorted_entries})
    payload = json.dumps(sorted_index.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
    ours.write_text(payload, encoding="utf-8")
    return MergeDriverOutcome()


# ---------------------------------------------------------------------------
# Registry (#5119 / FR-002): the single table both callers resolve against
# ---------------------------------------------------------------------------

MERGE_DRIVER_BODIES: Mapping[str, MergeDriverBody] = MappingProxyType(
    {
        "merge-driver-event-log": run_event_log_driver,
        "merge-driver-meta": run_meta_driver,
        "merge-driver-traces": run_traces_driver,
        "merge-driver-issue-matrix": run_issue_matrix_driver,
        "merge-driver-acceptance-matrix": run_acceptance_matrix_driver,
        "merge-driver-review-cycle": run_review_cycle_driver,
        "merge-driver-decision-index": run_decision_index_driver,
    }
)

# Scoped to the symbols another src/ module actually imports by name
# (cli/commands/merge_driver.py, lanes/consolidation.py, consolidation/git_probes.py;
# ``run_meta_driver`` and ``META_DRIVER_TWO_WAY_ENV`` are consumed by the CLI shell
# and the consolidation pipeline respectively) -- everything else this
# module defines (MergeDriverOutcome, MergeDriverPathError,
# RowMatrixMergeError, the run_*_driver bodies, the reconcile_* / trace-union
# helpers) is intra-module-consumed-only from src's perspective (the
# MERGE_DRIVER_BODIES registry is the one cross-module surface for the
# bodies) and stays out of __all__ per tests/architectural/
# test_no_dead_symbols.py's #470 gate (fix option 2) -- tests still import
# them directly by qualified name; __all__ only governs `from module import *`.
__all__ = [
    "MergeDriverError",
    "MergeDriverBody",
    "MERGE_DRIVER_BODIES",
    "META_DRIVER_TWO_WAY_ENV",
    "run_meta_driver",
]
