"""Hidden git merge-driver entrypoints for Spec Kitty repositories.

Six custom drivers keep mission bookkeeping semantic under
``git merge --squash -X theirs`` (the squash mission→target integration in
``lanes/merge.py::_merge_branch_into``). A custom driver overrides ``-X theirs``
on the paths it is registered for, so target-newer canonical state is reconciled
rather than clobbered (#2709 / FR-003 / FR-004 / FR-008):

- ``merge-driver-event-log``         — ``status.events.jsonl`` union (append-only log).
- ``merge-driver-meta``              — ``meta.json`` field merge: acceptance/VCS keys
  target-authoritative (the accepted-newer ``ours`` side), ``acceptance_history``
  unioned, all other (planning) keys mission-authoritative (``theirs``; preserves
  the #1732 ``-X theirs`` planning-artifact authority).
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
  prose — see that driver's own docstring for the full history and why a
  divergent collision no longer aborts the squash).

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
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import typer

from specify_cli.acceptance import (
    ACCEPTANCE_HISTORY_FIELD,
    ACCEPTANCE_PROVENANCE_FIELDS,
)
from specify_cli.acceptance.matrix import AcceptanceMatrix, AcceptanceMatrixParseError
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
# mission-authoritative to preserve the #1732 ``-X theirs`` intent (C-002).
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


# ---------------------------------------------------------------------------
# #2970 (E1) — path-injection hardening shared by every driver entrypoint
# ---------------------------------------------------------------------------


class MergeDriverPathError(Exception):
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
    refused before any read/write happens.
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


def _resolve_merge_driver_paths_or_exit(base_path: str, ours_path: str, theirs_path: str) -> tuple[Path, Path, Path]:
    """:func:`_resolve_merge_driver_paths`, translating a refusal to ``Exit(1)``.

    Every driver entrypoint calls this FIRST, before any file is opened — the
    single choke point that closes all 5 S2083 findings in this module.
    """
    try:
        return _resolve_merge_driver_paths(base_path, ours_path, theirs_path)
    except MergeDriverPathError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def merge_driver_event_log(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Merge ``status.events.jsonl`` conflict inputs using event-log semantics."""
    base, ours, theirs = _resolve_merge_driver_paths_or_exit(base_path, ours_path, theirs_path)
    try:
        merge_event_log_files(
            base_path=base,
            ours_path=ours,
            theirs_path=theirs,
        )
    except EventLogMergeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


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
    arms become a single :class:`EventLogMergeError` so the ``merge_driver_meta``
    wrapper's existing ``except EventLogMergeError`` still translates them to
    ``typer.Exit(1)``. The non-object arm keeps the historical ``"is not a JSON
    object"`` wording; any other decode failure names the path and surfaces the
    underlying reason.
    """
    if str(exc).startswith(_L2_NON_OBJECT_PREFIX):
        return EventLogMergeError(f"{path}: meta.json is not a JSON object")
    return EventLogMergeError(f"{path}: malformed meta.json ({exc})")


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a ``meta.json`` object from *path*; empty/missing yields ``{}``.

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
    if not path.read_text(encoding="utf-8").strip():
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


def reconcile_meta_payloads(
    ours: dict[str, Any],
    theirs: dict[str, Any],
) -> dict[str, Any]:
    """Field-merge two ``meta.json`` payloads for the squash driver (FR-004).

    ``ours`` is the target checkout (accepted-newer authority for acceptance/VCS
    provenance); ``theirs`` is the mission branch (planning-key authority — the
    #1732 ``-X theirs`` intent). Acceptance/VCS scalar keys are taken from ``ours``
    when present; ``acceptance_history`` is unioned; every other key falls back to
    ``theirs`` so mission-authoritative planning state is preserved.
    """
    result = dict(theirs)  # mission-authoritative baseline (C-002 / #1732).
    for key in _TARGET_AUTHORITATIVE_META_FIELDS:
        if key in ours:
            result[key] = ours[key]
    unioned_history = _union_acceptance_history(
        theirs.get(ACCEPTANCE_HISTORY_FIELD),
        ours.get(ACCEPTANCE_HISTORY_FIELD),
    )
    if unioned_history:
        result[ACCEPTANCE_HISTORY_FIELD] = unioned_history
    return result


def merge_driver_meta(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Field-merge conflicting ``meta.json`` blobs; write result to ``ours``."""
    base, ours, theirs = _resolve_merge_driver_paths_or_exit(base_path, ours_path, theirs_path)
    _ = base  # %O ancestor: git always passes it, but the field merge is 2-way.
    try:
        merged = reconcile_meta_payloads(
            _load_json_object(ours),
            _load_json_object(theirs),
        )
    except (json.JSONDecodeError, EventLogMergeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    ours.write_text(json.dumps(merged, **_META_JSON_KWARGS) + "\n", encoding="utf-8")


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
# A fenced-code-block delimiter -- backtick (```` ``` ````) OR tilde
# (``~~~``); toggles the in-fence state ``_split_trace_blocks`` tracks (#4993:
# the backtick-only regex misread a heading-like line inside a ``~~~`` fence
# as a real section boundary).
_TRACE_FENCE_MARKER = re.compile(r"^(?:```|~~~)")
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
    """
    blocks: list[list[str]] = [[]]
    in_fence = False
    for line in text.splitlines():
        if not in_fence and _TRACE_SECTION_BOUNDARY.match(line):
            blocks.append([])
        if _TRACE_FENCE_MARKER.match(line):
            in_fence = not in_fence
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
# an explicit ``<!-- section:ID -->`` opening line (stable regardless of
# position or a heading text shared with another section), or, when no id is
# present, the block's first line paired with its per-document occurrence
# ordinal (the running count of prior blocks in the SAME document sharing
# that first line). Body-insensitive by construction (never a full-block
# hash): an edited section keeps its key, so an unchanged-vs-diverged
# comparison against base still fires -- see :func:`_trace_block_key`.
_TraceBlockKey = tuple[str, str] | tuple[str, str, int]


def _trace_block_key(block: tuple[str, ...], occurrence_ordinal: int) -> _TraceBlockKey:
    """A block's identity for 3-way base comparison (non-colliding, #4993).

    Prefers the explicit ``<!-- section:ID -->`` id parsed from the block's
    opening line when present. Otherwise falls back to
    ``("line", first_line, occurrence_ordinal)``, so two sections sharing an
    identical heading get distinct keys instead of colliding on a bare
    first-line return (the pre-#4993 bug: ``setdefault``-based indexing kept
    only the FIRST same-heading block, so every later same-heading block's
    base/ours comparison was silently mis-attributed to the first one's).

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
        return ("id", section_id.group(1))
    return ("line", first_line, occurrence_ordinal)


def _iter_trace_blocks_with_ordinal(
    text: str,
) -> Iterator[tuple[tuple[str, ...], int]]:
    """Yield each of *text*'s blocks paired with its per-document occurrence
    ordinal -- the running count of prior blocks in *this* document sharing
    the same first line, which :func:`_trace_block_key`'s fallback folds in
    so duplicate-heading blocks get distinct keys.
    """
    occurrence_counts: dict[str, int] = {}
    for block in _split_trace_blocks(text):
        first_line = block[0] if block else ""
        ordinal = occurrence_counts.get(first_line, 0)
        occurrence_counts[first_line] = ordinal + 1
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


def merge_driver_traces(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Union conflicting ``traces/*.md`` documents; write result to ``ours`` (#4894).

    3-way base-aware: reads ``%O`` so a section theirs left UNCHANGED from
    base, while ours edited the same section, is recognized as stale and
    dropped rather than resurrected alongside ours' edit (see
    :func:`_drop_stale_theirs_trace_blocks`). The remaining union is still
    section-granularity and append-only via :func:`union_trace_texts` --
    never a lossy line-level global dedup, never fail-closed on an ordinary
    repeat.
    """
    base, ours, theirs = _resolve_merge_driver_paths_or_exit(base_path, ours_path, theirs_path)
    base_text = base.read_text(encoding="utf-8") if base.exists() else ""
    ours_text = ours.read_text(encoding="utf-8") if ours.exists() else ""
    theirs_text = theirs.read_text(encoding="utf-8") if theirs.exists() else ""
    filtered_theirs_text = _drop_stale_theirs_trace_blocks(base_text, ours_text, theirs_text)
    ours.write_text(union_trace_texts(ours_text, filtered_theirs_text), encoding="utf-8")


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


class RowMatrixMergeError(Exception):
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
# prose driver (:func:`merge_driver_review_cycle`) to embed a two-verdict
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


def merge_driver_issue_matrix(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Row-aware, 3-way merge of ``issue-matrix.json``; write result to ``ours`` (FR-008)."""
    base, ours, theirs = _resolve_merge_driver_paths_or_exit(base_path, ours_path, theirs_path)
    try:
        merged = reconcile_issue_matrix_documents(
            _parse_json_document(base),
            _parse_json_document(ours),
            _parse_json_document(theirs),
        )
    except (RowMatrixMergeError, AcceptanceMatrixParseError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    ours.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def merge_driver_acceptance_matrix(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Row-aware, 3-way merge of ``acceptance-matrix.json``; write result to ``ours`` (FR-008)."""
    base, ours, theirs = _resolve_merge_driver_paths_or_exit(base_path, ours_path, theirs_path)
    try:
        merged = reconcile_acceptance_matrix_documents(
            _parse_json_document(base),
            _parse_json_document(ours),
            _parse_json_document(theirs),
        )
    except (RowMatrixMergeError, AcceptanceMatrixParseError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    ours.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


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
#       ``git merge --squash -X theirs`` reports the path as an unresolved
#       conflict (``_merge_branch_into`` then ``git merge --abort``s and
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
# module's row-matrix field-conflict markers use), but no longer raises
# ``typer.Exit(1)`` -- the squash proceeds with the conflict-marked prose as
# the resolved content. Retiring the driver entirely (falling through to
# plain ``-X theirs``) was considered and rejected only because embedding
# both sides costs nothing and preserves strictly more information than a
# bare ``-X theirs`` pick would.
#
# Identical content on both sides is NOT a collision at all -- it is the
# trivial, common case (the same verdict was independently recorded/copied
# onto both partitions) and resolves cleanly with no conflict markers.


def merge_driver_review_cycle(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Reconcile a ``review-cycle-N.md`` collision, best-effort, non-aborting.

    Two distinct verdict documents colliding under the same filename are
    NEVER unioned/field-merged/interleaved into one document -- see the
    module-level design-decision comment immediately above this function for
    the full reasoning (embed both verbatim, never fabricate a blended
    verdict). Unlike WP18's original T077 driver, a divergent collision no
    longer aborts the squash (FR-014/D-PLAN-6): the ``.md`` render is
    non-authoritative, unread prose now that ``status.events.jsonl``'s
    ``review_result`` event slot is the sole verdict authority, so refusing
    the merge over it is no longer justified.

    Identical content on both sides (byte-for-byte) is the trivial fast path:
    resolves cleanly, exit 0, never reported as a conflict. Otherwise, both
    raw documents are embedded verbatim inside standard git-style conflict
    markers (never blended field-by-field -- a review verdict has no safely
    mergeable sub-fields the way a JSON matrix row does) and the driver
    exits 0, so ``git merge --squash -X theirs`` treats the path as resolved
    and the squash proceeds.
    """
    base, ours, theirs = _resolve_merge_driver_paths_or_exit(base_path, ours_path, theirs_path)
    _ = base  # %O ancestor: unused -- an add/add collision has no common base,
    # and the fast-path decision is a pure 2-way (ours vs theirs) content
    # comparison regardless of whether a base exists.
    ours_text = ours.read_text(encoding="utf-8") if ours.exists() else ""
    theirs_text = theirs.read_text(encoding="utf-8") if theirs.exists() else ""

    if ours_text == theirs_text:
        # Trivial fast path (T077 validation checklist): the same verdict
        # landed on both partitions -- not a conflict, nothing to reconcile.
        ours.write_text(ours_text, encoding="utf-8")
        return

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
    typer.echo(
        f"review-cycle verdict collision at {ours.name}: two distinct "
        "best-effort renders collided under one filename (T017 create-window "
        "hazard); both embedded verbatim behind conflict markers -- "
        "non-aborting (FR-014/D-PLAN-6: the .md is non-authoritative, unread "
        "prose; the squash proceeds)",
        err=False,
    )
