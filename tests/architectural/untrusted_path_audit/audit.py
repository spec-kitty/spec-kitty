#!/usr/bin/env python3
"""Reproducible untrusted-segment -> filesystem-sink audit (WP01 / FR-003, FR-004).

Run directly (from the repo root, so ``sys.path`` picks up the repo root the
way ``-m`` invocation always does -- a bare ``python audit.py`` would not)::

    python -m tests.architectural.untrusted_path_audit.audit

Exit code ``0`` means the live source tree still matches the committed
inventory; any non-zero exit is an audit failure a reviewer must read.

What this does
--------------
1. AST-walks every ``*.py`` under ``src/specify_cli``.
2. Flags a call site as an *untrusted -> FS sink* when an **untrusted path
   segment** (see ``UNTRUSTED_SEGMENT_NAMES`` / ``UNTRUSTED_SOURCE_CALLS``)
   reaches a **filesystem sink** -- either:
     * an inline ``<path-expr> / <untrusted-segment>`` ``BinOp`` join, or
     * a sink method/builtin (``open`` / ``read_text`` / ``write_text`` /
       ``mkdir`` / ``unlink`` / ``shutil.copy|move|rmtree`` / ...) invoked on a
       path that was built from an untrusted segment, including **one hop of
       local-variable aliasing** (``slug = meta.get("mission_slug"); root / slug``).
3. Cross-checks the machine-discovered sinks against the hand-curated
   dispositions in ``inventory.md`` using a **drift-proof composite row
   identity** (FR-004) and fails closed in BOTH directions.

Row identity (FR-004, IC-02)
----------------------------
The old raw ``rel_path:line`` comparand was a #2306 false-failure machine: a
blank line inserted above a documented sink shifted the line and reddened CI
even though nothing security-relevant changed. The comparison identity is now
the drift-proof composite::

    (rel_path, enclosing_qualname, token)

derived from ``tests.architectural._ratchet_keys.composite_key_from_file`` -- the
same primitive the write-side ratchets use. ``token`` is the space-joined code
tokens of the sink line (strings/comments stripped, f-string interior dropped
for 3.11/3.12 parity), truncated compactly at ``TOKEN_MAX_LEN`` chars with a
``…`` marker for inventory readability. A blank/comment insertion changes
neither the enclosing qualname nor the token, so the audit stays GREEN; a real
edit to the sink line (or a rename) changes the token/qualname and the audit
goes RED, forcing a review. The ``line`` column in ``inventory.md`` is now a
NON-authoritative jump-to locator -- it is never compared.

Both tripwire directions (FR-004, IC-02)
----------------------------------------
* **Undercount** (:func:`check_undercount`): every AST-discovered sink must map
  to an inventory row by composite identity, else RED (a new undocumented sink).
* **Overcount / ghost** (:func:`check_overcount`, NEW): every inventory row --
  minus rows explicitly tagged ``[inventory-only]`` -- must map to a live
  discovered sink, else RED (a deleted sink left silently documented). Both are
  PURE seams that :func:`main` itself calls, so the acceptance theater drives the
  real path.

Pure-move pairing and ``--fix`` (#6642)
---------------------------------------
A change that only MOVES a sink (module renamed / function relocated, joined
segment unchanged) used to redden BOTH tripwires -- one ghost overcount plus
one undercount -- forcing a hand re-pin of the inventory locator columns.
:func:`pair_relocations` (a PURE seam :func:`main` itself calls) now recognises
such a move and collapses it into ONE actionable ``sink moved:`` finding that
still exits non-zero until the inventory is re-pinned. A pair forms only when
**exactly one** ghost row and **exactly one** missing live sink share
``(token, untrusted source)`` and the token is not ``…``-truncated; anything
else (a genuine removal, a genuine new sink, a changed token, an ambiguous
group, a source-cell mismatch, a truncated token) stays RED for a human --
the ratchet keeps its teeth.

Re-running with ``--fix`` re-pins ONLY the machine locator columns
(``file:line`` and ``qualname``) of the paired rows; the token, untrusted
source, sink-op, disposition and rationale cells are never touched. ``--fix``
is fail-closed: it refuses to write while any non-relocation error exists,
and it re-audits the would-be result in memory (every check, from the rewritten
text) before touching the file.

Two supporting checks keep the pairing honest:

* **Source-cell canonicality**: a live row's ``untrusted source`` cell must be
  the exact canonical machine string the matcher prints -- a hand-tuned cell
  (``resolved.mission_slug`` where discovery says ``mission_slug``) would
  silently disable pairing for that row. Hand annotations belong in the
  rationale.
* **No line-shift chains**: rationale cells must not carry hand-kept
  ``1902→1933`` / ``shifted −11`` relocation-history chains -- git history
  already records them, and ``--fix`` re-pins the locators.

``[inventory-only]`` rows (freshen path)
----------------------------------------
A row carries the ``[inventory-only]`` tag in its rationale column when the
matcher intentionally cannot AST-discover it -- a RULESET known-false-negative
class (the FR-009 ``meta.json`` write-path; a cross-function diagnostic whose
join lives behind a boundary seam). Such a row is exempt from the overcount
guard and its notes name WHY. To freshen after a genuine sink change, run the
audit: :func:`check_undercount` prints the exact ``| file:line | qualname |
token | ... |`` row to paste. The disposition of each row (``routed-through-seam``
/ ``routed-through-seam (TODO)`` / ``trusted-source`` / ``unreachable``) is a
human judgement recorded in ``inventory.md``, NOT inferred by the matcher.

See ``RULESET.md`` for the seed-set, the sink predicate, and -- importantly --
the *known false-negative classes* (what this matcher does NOT trace).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

# --------------------------------------------------------------------------- #
# Locate the source tree relative to this file (repo-root independent).
# this file: <root>/tests/architectural/untrusted_path_audit/audit.py
# --------------------------------------------------------------------------- #
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[3]
SRC_ROOT = _REPO_ROOT / "src" / "specify_cli"
INVENTORY_PATH = _THIS.parent / "inventory.md"

# The composite-identity primitive lives in the sibling ``tests.architectural``
# package. No manual sys.path bootstrap is needed to resolve it: pytest already
# has the repo root on the path (rootdir-prepend via ``tests/__init__.py``),
# and ``python -m tests.architectural.untrusted_path_audit.audit`` (the
# supported direct-run form; a bare ``python audit.py`` puts the script's own
# directory, not the repo root, on ``sys.path`` and does not resolve this
# import) already has the invoking cwd -- the repo root -- there too.
from tests.architectural._ratchet_keys import composite_key_from_file

# --------------------------------------------------------------------------- #
# Composite row identity (FR-004, IC-02).
# --------------------------------------------------------------------------- #
#: Composite row identity: ``(rel_path, enclosing_qualname, truncated token)``.
RowKey = tuple[str, str, str]

#: Tokens longer than this are stored truncated (readability); the stored prefix
#: is verified unique per ``(rel_path, qualname)`` by the conversion tooling.
TOKEN_MAX_LEN = 60
#: Non-ASCII marker appended to a truncated token. It can never appear in a real
#: Python code token (source tokens are ASCII), so it is an unambiguous sentinel.
TOKEN_ELLIPSIS = "…"
#: Rationale-column tag exempting a row from the overcount guard (RULESET known-FN
#: / intentionally-removed sink). Each tagged row names WHY in its notes.
INVENTORY_ONLY_TAG = "[inventory-only]"

#: Prefix of a relocation finding (a pure move recognised by #6642's pairing).
#: ``--fix`` resolves exactly the errors carrying this prefix and nothing else.
RELOCATION_FINDING_PREFIX = "sink moved:"

#: Hand-kept line-shift chains are forbidden in rationale cells (#6642): git
#: history already records relocations, and ``--fix`` re-pins the locator
#: columns. Matches the arrow form (``1902→1933``) and the signed-shift prose
#: form (``shifted −11 by mission …``).
_LINE_SHIFT_CHAIN_RE = re.compile(r"\d+\s*→\s*\d+|\bshifted\s+[+−-]?\d+")


class RelocationPair(NamedTuple):
    """One recognised pure move: a ghost inventory row and its live sink.

    A pair forms when exactly one ghost key and exactly one missing discovered
    key share ``(token, untrusted source)`` — the columns a pure move (module
    rename / function relocation, joined segment unchanged) leaves intact.
    The human columns (disposition, rationale) carry over untouched.
    """

    ghost_key: RowKey
    ghost_locator: str
    missing_key: RowKey
    missing_locator: str


def truncate_token(token: str) -> str:
    """Return *token* compacted to ``TOKEN_MAX_LEN`` chars with a ``…`` marker."""
    if len(token) <= TOKEN_MAX_LEN:
        return token
    return token[:TOKEN_MAX_LEN] + TOKEN_ELLIPSIS


def composite_row_key(rel_path: str, line: int) -> RowKey:
    """Drift-proof identity for the sink at ``rel_path:line``.

    Returns ``(rel_path, enclosing_qualname, truncated token)`` -- stable across
    blank/comment-line insertions, changing only on a genuine edit/rename.
    """
    qualname, token = composite_key_from_file(SRC_ROOT / rel_path, line)
    return (rel_path, qualname, truncate_token(token))


# --------------------------------------------------------------------------- #
# Seed-set: untrusted source symbols (RULESET.md section "Seed-set").
# A *named* segment in this set may NEVER be classified ``trusted-source``
# (T003 Named-untrusted rule / SC-003).
# --------------------------------------------------------------------------- #
UNTRUSTED_SEGMENT_NAMES: frozenset[str] = frozenset(
    {
        "mission_slug",
        "feature_slug",
        "wp_id",
        "wp_slug",
        "slug",
        "run_id",
        "review_ref",
    }
)

# Untrusted source *calls* / attribute reads: ``meta.get("mission_slug")``,
# ``snapshot.mission_slug``, ``lifecycle.mission_slug`` etc. We match by the
# trailing attribute/argument name so the audit stays general.
UNTRUSTED_ATTR_NAMES: frozenset[str] = frozenset(
    {
        "mission_slug",
        "feature_slug",
        "wp_id",
        "wp_slug",
    }
)

# Sink method names invoked on a Path (``path.write_text(...)`` etc.).
SINK_METHODS: frozenset[str] = frozenset(
    {
        "open",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "mkdir",
        "unlink",
        "touch",
        "replace",
    }
)

# Sink free functions / qualified calls (``shutil.copy`` / ``atomic_write`` /
# builtin ``open``). Matched by trailing attribute name OR bare name.
SINK_FUNCTIONS: frozenset[str] = frozenset(
    {
        "open",
        "copy",
        "copy2",
        "copyfile",
        "move",
        "rmtree",
        "atomic_write",
        "write_text_within_directory",
    }
)


@dataclass(frozen=True)
class SinkRow:
    """One discovered untrusted-segment -> FS-sink call site."""

    rel_path: str
    line: int
    untrusted_source: str
    sink_op: str
    # Memoised composite key (composite_key_from_file re-reads and re-parses
    # the file; #6642's pairing seam consumes the key a second time). Deliberately
    # excluded from equality/hash/repr: two rows describing the same call site
    # must stay equal regardless of whether either has had key() called yet.
    _key_cache: RowKey | None = field(default=None, compare=False, repr=False)

    def key(self) -> RowKey:
        """Composite comparison identity (FR-004): ``(rel_path, qualname, token)``.

        Derived live from the current source line, so a line shift produces the
        SAME key (drift-immunity); ``sink_op`` is deliberately excluded -- it is
        diagnostic, not identity. Memoised (composite_key_from_file re-reads and
        re-parses the file; #6642's pairing seam consumes the key a second time).
        """
        if self._key_cache is None:
            key = composite_row_key(self.rel_path, self.line)
            object.__setattr__(self, "_key_cache", key)
            return key
        return self._key_cache

    def locator(self) -> str:
        """Non-authoritative jump-to locator ``rel_path:line`` (never compared)."""
        return f"{self.rel_path}:{self.line}"


def _segment_name(node: ast.expr) -> str | None:
    """Return the untrusted-segment name for *node*, else None.

    Recognises:
      * ``mission_slug`` (a seed Name),
      * ``snapshot.mission_slug`` (Attribute whose attr is untrusted),
      * ``meta.get("mission_slug")`` (Call to ``.get`` with an untrusted literal).
    """
    if isinstance(node, ast.Name) and node.id in UNTRUSTED_SEGMENT_NAMES:
        return node.id
    if isinstance(node, ast.Attribute) and node.attr in UNTRUSTED_ATTR_NAMES:
        return node.attr
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"get", "__getitem__"}
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and node.args[0].value in UNTRUSTED_ATTR_NAMES
    ):
        return f".get({node.args[0].value!r})"
    return None


def _collect_tainted_locals(tree: ast.AST) -> dict[str, str]:
    """One hop of aliasing: ``local = <untrusted-source>`` -> {local: source}.

    Also follows ``local = <untrusted-source> or fallback`` (BoolOp), the
    ``snapshot.mission_slug or feature_dir.name`` idiom used by the derived-view
    writers, because the tainted operand still flows into ``local``.
    """
    tainted: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        source = _segment_name(node.value)
        if source is None and isinstance(node.value, ast.BoolOp):
            for operand in node.value.values:
                source = _segment_name(operand)
                if source is not None:
                    break
        if source is not None:
            tainted[target.id] = source
    return tainted


def _names_in(node: ast.expr) -> set[str]:
    """All ``Name`` ids referenced anywhere inside *node*."""
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _join_taint(node: ast.expr, tainted: dict[str, str]) -> str | None:
    """Return the untrusted source if *node* is/contains a ``path / segment`` join.

    Matches ``<expr> / <untrusted>`` where ``<untrusted>`` is a direct seed
    segment OR a one-hop tainted local. Recurses into the left operand so
    ``root / a / mission_slug`` and ``root / slug / "meta.json"`` both match.
    """
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
        return None
    # Right operand directly untrusted?
    direct = _segment_name(node.right)
    if direct is not None:
        return direct
    if isinstance(node.right, ast.Name) and node.right.id in tainted:
        return f"{node.right.id}={tainted[node.right.id]}"
    # Recurse left so deeper joins are still caught.
    return _join_taint(node.left, tainted)


def _sink_func_name(call: ast.Call) -> str | None:
    """Return the sink-function name for a free/qualified call, else None."""
    func = call.func
    if isinstance(func, ast.Name) and func.id in SINK_FUNCTIONS:
        return func.id
    if isinstance(func, ast.Attribute) and func.attr in SINK_FUNCTIONS:
        return func.attr
    return None


def _audit_file(path: Path) -> list[SinkRow]:
    rel = path.relative_to(SRC_ROOT).as_posix()
    rows: list[SinkRow] = []
    # Local de-dup key: (line, sink_op) -- collapse identical repeated call
    # sites on one line. NOT the composite ``key()`` (which drops sink_op and is
    # the cross-inventory comparison identity).
    seen: set[tuple[int, str]] = set()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    tainted = _collect_tainted_locals(tree)
    tainted_locals = set(tainted)

    def _record(line: int, untrusted: str, sink_op: str) -> None:
        dedup = (line, sink_op)
        if dedup not in seen:
            seen.add(dedup)
            rows.append(SinkRow(rel, line, untrusted, sink_op))

    for node in ast.walk(tree):
        # (a) ``path / untrusted-segment`` join expressions (the path-build sink).
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            src = _join_taint(node, tainted)
            if src is not None:
                _record(node.lineno, src, "Path-join (/)")

        # (b) sink-method call on a receiver built from an untrusted segment.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in SINK_METHODS:
            recv = node.func.value
            recv_names = _names_in(recv)
            hit = _join_taint(recv, tainted)
            if hit is None and recv_names & tainted_locals:
                local = next(iter(recv_names & tainted_locals))
                hit = f"{local}={tainted[local]}"
            if hit is not None:
                _record(node.lineno, hit, f".{node.func.attr}()")

        # (c) sink free-function / qualified call with an untrusted-built arg.
        if isinstance(node, ast.Call):
            fname = _sink_func_name(node)
            if fname is not None:
                for arg in node.args:
                    src = _join_taint(arg, tainted)
                    if src is None and isinstance(arg, ast.Name) and arg.id in tainted:
                        src = f"{arg.id}={tainted[arg.id]}"
                    if src is not None:
                        _record(node.lineno, src, f"{fname}(...)")
                        break
    return rows


def discover_rows() -> list[SinkRow]:
    """AST-walk the source tree and return every discovered sink row, sorted."""
    rows: list[SinkRow] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        rows.extend(_audit_file(path))
    rows.sort(key=lambda r: (r.rel_path, r.line, r.sink_op))
    return rows


# --------------------------------------------------------------------------- #
# Known candidates (T004 anti-undercount tripwire). Each MUST surface at least
# one discovered row whose rel_path matches, OR carry an explicit
# disposition row in the inventory (the ``meta.json`` write-path is an FS sink
# keyed on ``feature_dir``, not a literal slug join, so it is asserted by
# inventory presence rather than by AST discovery -- see RULESET false-negatives).
# --------------------------------------------------------------------------- #
KNOWN_CANDIDATE_FILES: tuple[str, ...] = (
    # events/decision_log.py — removed from tripwire: WP03 added
    # assert_safe_path_segment before the slug join; no sinks remain.
    # dossier/drift_detector.py — removed from tripwire: WP03 added
    # assert_safe_path_segment in save_baseline/load_baseline; no sinks remain.
    # review/arbiter.py — removed from tripwire: mission
    # review-cycle-verdict-seam-rebuild-01KZ2W7W WP12 (FR-009,
    # arbiter-override-retirement) deleted `_find_review_cycle_artifact`
    # outright and reimplemented `get_arbiter_overrides_for_wp` over the
    # event-sourced `ReviewOverride` snapshot slot; no `tasks_dir / wp_id`
    # (or any other untrusted-segment) join remains in this module.
    # post_merge/review_artifact_consistency.py — removed from tripwire: the
    # SAME mission's WP13 (T059) rewrote `_artifact_dirs_for_wp` to resolve a
    # single directory through `review/cycle.py::_review_cycle_wp_dir` (T058's
    # owner function, already a KNOWN_CANDIDATE_FILES entry below) instead of
    # this module's own raw `tasks_dir / wp_id` fan-out join. The one
    # remaining local join in this file (`feature_dir / "tasks" / flat_slug`,
    # the no-workspace-root degrade) uses `flat_slug` -- a locally-derived
    # variable, not a name in `UNTRUSTED_SEGMENT_NAMES` -- so no
    # untrusted-segment join is AST-discoverable in this module any more.
    "coordination/surface_resolver.py",
    "missions/_read_path_resolver.py",
    "migration/mission_state.py",
    "review/cycle.py",
    "status/store.py",
    "status/views.py",
    "status/lifecycle.py",
    "status/aggregate.py",  # _find_meta_path composed-path reads
)

# The FR-009 meta.json slug source (top-level mission_metadata.py): asserted by
# inventory presence and required to carry the routed-through-seam (TODO) tag.
FR009_META_FILE = "mission_metadata.py"

# Number of markdown cells a well-formed inventory sink row carries after the
# FR-004 re-key (locator, qualname, token, source, sink_op, disposition, notes).
_INVENTORY_ROW_CELLS = 7


def _parse_inventory_rows(text: str) -> list[dict[str, str]]:
    """Parse the markdown sink table in inventory.md into row dicts.

    The table header is ``| file:line | qualname | token | untrusted source |
    sink op | disposition | rationale |`` (FR-004 re-key). ``qualname`` + ``token``
    are the composite comparison identity; ``file:line`` is a non-authoritative
    locator.
    """
    rows: list[dict[str, str]] = []
    in_table = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("| file:line "):
            in_table = True
            continue
        if in_table and line.replace(" ", "").startswith("|---"):
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < _INVENTORY_ROW_CELLS:
                continue
            rows.append(
                {
                    "locator": cells[0],
                    "qualname": cells[1],
                    "token": cells[2],
                    "source": cells[3],
                    "sink_op": cells[4],
                    "disposition": cells[5],
                    "rationale": cells[6],
                }
            )
    return rows


VALID_DISPOSITIONS = {
    "routed-through-seam",
    "routed-through-seam (TODO)",
    "trusted-source",
    "unreachable",
}

NAMED_UNTRUSTED = {"mission_slug", "feature_slug", "wp_id"}


def _inventory_row_key(row: dict[str, str]) -> RowKey | None:
    """Composite identity of an inventory row from its stored columns, or None.

    None signals a fail-closed parse error (missing rel_path/qualname/token) --
    :func:`build_inventory_key_map` turns that into a named audit error.
    """
    rel = row["locator"].rpartition(":")[0]
    qualname = row["qualname"].strip()
    token = row["token"].strip()
    if not rel or not qualname or not token:
        return None
    return (rel, qualname, token)


def build_discovered_key_map(discovered: list[SinkRow]) -> dict[RowKey, str]:
    """Map each discovered composite key to a live ``rel:line`` locator.

    Identical repeated sinks (e.g. the two ``done_bookkeeping`` branches that
    emit the byte-identical relative path) collapse to one key; the first live
    locator wins for the diagnostic message.
    """
    out: dict[RowKey, str] = {}
    for row in discovered:
        out.setdefault(row.key(), row.locator())
    return out


def build_inventory_key_map(
    rows: list[dict[str, str]],
) -> tuple[list[str], dict[RowKey, str]]:
    """Map non-``[inventory-only]`` inventory keys to their locator (fail-closed).

    Returns ``(errors, key_map)``. ``errors`` names any row whose stored identity
    cannot be parsed (T007 fail-closed). ``[inventory-only]``-tagged rows are
    excluded (exempt from both tripwires).
    """
    errors: list[str] = []
    out: dict[RowKey, str] = {}
    for row in rows:
        if INVENTORY_ONLY_TAG in row["rationale"]:
            continue
        key = _inventory_row_key(row)
        if key is None:
            errors.append(f"inventory row {row['locator']!r} has an unparseable stored identity (missing qualname/token column) -- fail-closed")
            continue
        out[key] = row["locator"]
    return errors, out


def check_undercount(
    discovered_keys: Mapping[RowKey, str],
    inventory_keys: Mapping[RowKey, str],
) -> list[str]:
    """Every discovered sink must be documented (PURE seam that ``main`` calls).

    Returns an error per discovered composite key absent from the inventory,
    naming the live ``rel:line`` locator (fresh from the scan) and printing the
    exact row to paste (the freshen path).
    """
    errors: list[str] = []
    for key in sorted(set(discovered_keys) - set(inventory_keys)):
        rel_path, qualname, token = key
        locator = discovered_keys[key]
        errors.append(
            f"discovered sink {locator} (qualname={qualname!r}, token={token!r}) "
            f"is MISSING from inventory.md (undercount tripwire); add a row: "
            f"| {locator} | {qualname} | {token} | <source> | <sink_op> | "
            f"<disposition> | <rationale> |"
        )
    return errors


def check_overcount(
    discovered_keys: Mapping[RowKey, str],
    inventory_keys: Mapping[RowKey, str],
) -> list[str]:
    """Every inventory row must map to a live sink (PURE seam, NEW FR-004 guard).

    Returns an error per inventory composite key with no live discovered sink --
    a ghost row whose sink was deleted or whose content changed. ``inventory_keys``
    already excludes ``[inventory-only]``-tagged rows.
    """
    errors: list[str] = []
    for key in sorted(set(inventory_keys) - set(discovered_keys)):
        rel_path, qualname, token = key
        locator = inventory_keys[key]
        errors.append(
            f"inventory row {locator} (qualname={qualname!r}, token={token!r}) "
            f"has NO live discovered sink (overcount/ghost tripwire): the sink "
            f"was removed or its content changed. Delete the stale row, or -- if "
            f"it documents an intentionally-removed / known-false-negative sink -- "
            f"tag it '{INVENTORY_ONLY_TAG}' in the rationale column, naming the "
            f"change that removed it."
        )
    return errors


def pair_relocations(
    discovered: Mapping[RowKey, tuple[str, str]],
    inventory: Mapping[RowKey, tuple[str, str]],
) -> tuple[list[RelocationPair], list[str]]:
    """Recognise pure moves: pair ghosts with missing sinks on (token, source).

    PURE seam that :func:`main` itself calls (#6642). *discovered* maps each
    live composite key to ``(locator, untrusted_source)``; *inventory* maps each
    non-``[inventory-only]`` inventory key to ``(locator, source cell)``. Both
    maps are KEY-deduped by their builders, so repeated rows collapse before
    grouping (counting keys, not rows).

    A pair forms for a ``(token, source)`` group holding **exactly one** ghost
    key and **exactly one** missing key, when the token is not ``…``-truncated.
    Everything else stays red for a human: a genuine removal (ghost without a
    missing twin), a genuine new sink (missing without a ghost twin), a changed
    token (the pair key breaks), an ambiguous group, a source-cell mismatch, or
    a truncated token (a shared 60-char prefix cannot distinguish a move from a
    removal-plus-addition — the row identity itself uses the truncated token).

    Returns ``(pairs, notes)``; *notes* are diagnostic strings for
    token-matches that did NOT pair (they never fire on a green tree, and every
    note coexists with the underlying ghost/undercount errors).
    """
    ghosts = {k: v for k, v in inventory.items() if k not in discovered}
    missing = {k: v for k, v in discovered.items() if k not in inventory}

    ghost_groups: dict[tuple[str, str], list[RowKey]] = {}
    for key, (_, source) in ghosts.items():
        ghost_groups.setdefault((key[2], source), []).append(key)
    missing_groups: dict[tuple[str, str], list[RowKey]] = {}
    for key, (_, source) in missing.items():
        missing_groups.setdefault((key[2], source), []).append(key)

    pairs: list[RelocationPair] = []
    notes: list[str] = []
    for (token, source), ghost_keys in sorted(ghost_groups.items()):
        missing_keys = missing_groups.get((token, source))
        if not missing_keys:
            # No same-(token, source) twin: explain every same-token /
            # different-source near-miss (the most common reason a real move
            # fails to pair), not an arbitrary first candidate.
            near_misses = sorted(m_loc for m_key, (m_loc, m_src) in missing.items() if m_key[2] == token and m_src != source)
            if near_misses:
                notes.append(
                    f"no automatic pairing for ghost row: its token matches live "
                    f"sink(s) {', '.join(near_misses)} but the untrusted source "
                    f"differs ({source!r} vs the discovered source there) — "
                    f"re-pin by hand or canonicalise the source cell"
                )
            continue
        if TOKEN_ELLIPSIS in token:
            notes.append(
                f"no automatic pairing for truncated token {token!r}: a shared "
                f"60-char prefix cannot distinguish a move from a removal plus "
                f"a new sink — re-pin by hand"
            )
            continue
        if len(ghost_keys) == 1 and len(missing_keys) == 1:
            ghost, moved = ghost_keys[0], missing_keys[0]
            pairs.append(RelocationPair(ghost, ghosts[ghost][0], moved, missing[moved][0]))
        else:
            notes.append(
                f"ambiguous relocation group (token={token!r}, source={source!r}): "
                f"{len(ghost_keys)} ghost row(s) vs {len(missing_keys)} missing "
                f"live sink(s) — automatic pairing requires exactly one of each; "
                f"re-pin by hand"
            )
    return pairs, notes


def _format_relocation_findings(pairs: Sequence[RelocationPair]) -> list[str]:
    """One actionable finding per recognised pure move (still RED until re-pin)."""
    return [
        f"{RELOCATION_FINDING_PREFIX} {p.ghost_locator} "
        f"(qualname={p.ghost_key[1]!r}, token={p.ghost_key[2]!r}) -> "
        f"{p.missing_locator}; the disposition and rationale carry over — "
        f"re-run with --fix to re-pin the locator columns (file:line, qualname)"
        for p in pairs
    ]


def _apply_relocation_fixes(text: str, pairs: Sequence[RelocationPair]) -> str:
    """Re-pin ONLY the locator columns (``file:line``, ``qualname``) of paired rows.

    The token, untrusted-source, sink-op, disposition and rationale cells are
    never touched (#3011 ``rekey_inventory.py`` precedent: never overwrite
    hand-adjudicated columns). Rows are matched by their STORED composite
    identity, exactly as the comparison seams see them.
    """
    rewrites = {p.ghost_key: p for p in pairs}
    out: list[str] = []
    in_table = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("| file:line "):
            in_table = True
            out.append(raw)
            continue
        if in_table and line.replace(" ", "").startswith("|---"):
            out.append(raw)
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
                out.append(raw)
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= _INVENTORY_ROW_CELLS:
                rel = cells[0].rpartition(":")[0]
                key = (rel, cells[1], cells[2]) if rel and cells[1] and cells[2] else None
                pair = rewrites.get(key) if key is not None else None
                if pair is not None:
                    cells[0] = pair.missing_locator
                    cells[1] = pair.missing_key[1]
                    out.append("| " + " | ".join(cells) + " |")
                    continue
        out.append(raw)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _fail(messages: list[str]) -> int:
    print("AUDIT FAILED", file=sys.stderr)
    for msg in messages:
        print(f"  - {msg}", file=sys.stderr)
    return 1


def _check_dispositions(inventory_rows: list[dict[str, str]]) -> list[str]:
    """Check 1: each row carries exactly one valid disposition (SC-003)."""
    errors: list[str] = []
    for row in inventory_rows:
        disp = row["disposition"]
        if disp not in VALID_DISPOSITIONS:
            errors.append(f"row {row['locator']!r} has invalid/missing disposition {disp!r}")
        # Named-untrusted rule: a named untrusted source may never be trusted-source.
        if disp == "trusted-source":
            src = row["source"]
            named = {n for n in NAMED_UNTRUSTED if n in src}
            # ``feature_dir.name`` / ``mission_dir.name`` are derived/trusted even
            # though the token ``mission`` appears; only a bare named segment trips.
            bare_named = {n for n in named if f"{n}.name" not in src and ".name" not in src}
            if bare_named:
                errors.append(f"row {row['locator']!r} classifies named-untrusted {sorted(bare_named)} as trusted-source (SC-003 violation)")
    return errors


def _check_known_candidates(discovered_files: set[str], inventory_rows: list[dict[str, str]]) -> list[str]:
    """Check 3: known-candidate presence (path-level anti-undercount tripwire)."""
    errors: list[str] = []
    for cand in KNOWN_CANDIDATE_FILES:
        in_discovered = cand in discovered_files
        in_inventory = any(r["locator"].startswith(cand) for r in inventory_rows)
        if not (in_discovered or in_inventory):
            errors.append(f"known candidate {cand!r} absent from BOTH discovered rows and inventory")
    return errors


def _check_fr009(inventory_rows: list[dict[str, str]]) -> list[str]:
    """Check 4: FR-009 meta.json source present + tagged routed-through-seam (TODO)."""
    errors: list[str] = []
    fr009_rows = [r for r in inventory_rows if r["locator"].startswith(FR009_META_FILE)]
    if not fr009_rows:
        errors.append(f"FR-009 candidate {FR009_META_FILE!r} (meta.json slug source) absent from inventory")
    elif not any(r["disposition"] == "routed-through-seam (TODO)" for r in fr009_rows):
        errors.append(f"FR-009 {FR009_META_FILE!r} row(s) must be tagged 'routed-through-seam (TODO)' (the write-path bypass WP02 fixes)")
    return errors


def _check_source_canonicality(
    discovered: Mapping[RowKey, tuple[str, str]],
    inventory_rows: list[dict[str, str]],
) -> list[str]:
    """Check 5: a live row's source cell is the canonical machine string (#6642).

    The relocation pairing compares the inventory ``untrusted source`` cell
    with the discovered row's machine ``untrusted_source`` by EXACT equality,
    so a hand-tuned cell (``resolved.mission_slug`` where discovery says
    ``mission_slug``) would silently disable pairing for that row. Ghost rows
    are exempt (the pairing rule governs them); ``[inventory-only]`` rows are
    exempt (never paired, never discovered).
    """
    errors: list[str] = []
    for row in inventory_rows:
        if INVENTORY_ONLY_TAG in row["rationale"]:
            continue
        key = _inventory_row_key(row)
        if key is None or key not in discovered:
            continue
        live_source = discovered[key][1]
        if row["source"] != live_source:
            errors.append(
                f"inventory row {row['locator']!r} source cell {row['source']!r} is not "
                f"the canonical machine string {live_source!r} — the relocation pairing "
                f"compares this cell by exact equality; re-pin it (move any hand "
                f"annotation into the rationale)"
            )
    return errors


def _check_no_line_shift_chains(inventory_rows: list[dict[str, str]]) -> list[str]:
    """Check 6: rationale cells carry no hand-kept line-shift chains (#6642).

    Git history already records relocations and ``--fix`` re-pins the locator
    columns, so a "line shifted 1902→1933 by mission …" chain is pure churn:
    every relocation PR would have to extend it by hand.
    """
    errors: list[str] = []
    for row in inventory_rows:
        match = _LINE_SHIFT_CHAIN_RE.search(row["rationale"])
        if match:
            errors.append(
                f"inventory row {row['locator']!r} rationale contains a hand-kept "
                f"line-shift chain ({match.group(0)!r}) — git history records "
                f"relocations; re-pin locators with --fix instead of logging shifts"
            )
    return errors


def _summary(inventory_rows: list[dict[str, str]], discovered_count: int) -> str:
    todo = sum(1 for r in inventory_rows if r["disposition"] == "routed-through-seam (TODO)")
    safe = sum(1 for r in inventory_rows if r["disposition"] == "routed-through-seam")
    trusted = sum(1 for r in inventory_rows if r["disposition"] == "trusted-source")
    unreachable = sum(1 for r in inventory_rows if r["disposition"] == "unreachable")
    inv_only = sum(1 for r in inventory_rows if INVENTORY_ONLY_TAG in r["rationale"])
    return (
        f"AUDIT OK: {len(inventory_rows)} inventory rows "
        f"({discovered_count} AST-discovered, {inv_only} inventory-only); "
        f"TODO(fix)={todo} safe={safe} trusted={trusted} unreachable={unreachable}"
    )


def _build_rich_discovered(discovered: list[SinkRow]) -> dict[RowKey, tuple[str, str]]:
    """Composite key -> ``(locator, untrusted_source)``, deduped (first wins)."""
    out: dict[RowKey, tuple[str, str]] = {}
    for row in discovered:
        out.setdefault(row.key(), (row.locator(), row.untrusted_source))
    return out


def _build_rich_inventory(rows: list[dict[str, str]]) -> dict[RowKey, tuple[str, str]]:
    """Composite key -> ``(locator, source cell)`` for pairable rows, deduped.

    Excludes ``[inventory-only]`` rows and rows with an unparseable identity
    (the latter are already fail-closed parse errors) — the ghost set the
    overcount guard sees, minus the exempt rows.
    """
    out: dict[RowKey, tuple[str, str]] = {}
    for row in rows:
        if INVENTORY_ONLY_TAG in row["rationale"]:
            continue
        key = _inventory_row_key(row)
        if key is not None:
            out.setdefault(key, (row["locator"], row["source"]))
    return out


def _collect_errors(
    discovered: list[SinkRow],
    inventory_rows: list[dict[str, str]],
) -> tuple[list[str], list[RelocationPair]]:
    """Run every check except file existence; return (errors, relocation pairs).

    The errors list includes one :data:`RELOCATION_FINDING_PREFIX` finding per
    recognised pure move (still RED — the inventory is out of sync until
    re-pinned); the two underlying ghost/undercount errors for a paired key are
    suppressed so a pure move reads as ONE actionable finding, not two
    misleading failures (#6642).
    """
    errors: list[str] = []

    # ---- Check 1: valid dispositions + Named-untrusted rule (SC-003). ----
    errors.extend(_check_dispositions(inventory_rows))

    # ---- Build composite comparison maps (fail-closed on unparseable rows). ----
    parse_errors, inventory_keys = build_inventory_key_map(inventory_rows)
    errors.extend(parse_errors)
    discovered_keys = build_discovered_key_map(discovered)

    # ---- Pure-move pairing (#6642) BEFORE the tripwires, so paired keys ----
    # ---- collapse into a single finding instead of two errors. ----
    rich_discovered = _build_rich_discovered(discovered)
    rich_inventory = _build_rich_inventory(inventory_rows)
    pairs, notes = pair_relocations(rich_discovered, rich_inventory)
    paired_ghosts = {p.ghost_key for p in pairs}
    paired_missing = {p.missing_key for p in pairs}

    # ---- Check 2 (undercount) + Check 2b (overcount/ghost) via PURE seams. ----
    errors.extend(
        check_undercount(
            {k: v for k, v in discovered_keys.items() if k not in paired_missing},
            inventory_keys,
        )
    )
    errors.extend(
        check_overcount(
            discovered_keys,
            {k: v for k, v in inventory_keys.items() if k not in paired_ghosts},
        )
    )
    errors.extend(_format_relocation_findings(pairs))
    errors.extend(notes)

    # ---- Check 3: known-candidate presence (path-level tripwire). ----
    errors.extend(_check_known_candidates({r.rel_path for r in discovered}, inventory_rows))

    # ---- Check 4: FR-009 meta.json source present + tagged. ----
    errors.extend(_check_fr009(inventory_rows))

    # ---- Check 5: source-cell canonicality (pair-key precondition). ----
    errors.extend(_check_source_canonicality(rich_discovered, inventory_rows))

    # ---- Check 6: no hand-kept line-shift chains in rationale cells. ----
    errors.extend(_check_no_line_shift_chains(inventory_rows))

    return errors, pairs


def _parse_args(argv: Sequence[str] | None) -> bool:
    """Parse the audit's CLI flags; return whether ``--fix`` was requested."""
    parser = argparse.ArgumentParser(
        prog="python -m tests.architectural.untrusted_path_audit.audit",
        description=("Reproducible untrusted-segment -> filesystem-sink audit. Exit 0 means the live source tree still matches the committed inventory."),
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help=(
            "re-pin the locator columns (file:line, qualname) of recognised pure "
            "sink relocations; dispositions and rationales are never touched, and "
            "the file is written only if the would-be result passes every check"
        ),
    )
    return bool(parser.parse_args(list(argv) if argv is not None else None).fix)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the audit; exit 0 only when the tree matches the inventory.

    *argv* defaults to no flags (the plain audit run the architectural test
    module drives); the ``python -m`` entry point passes ``sys.argv[1:]`` so
    ``--fix`` reaches it.
    """
    fix = _parse_args(argv or [])

    discovered = discover_rows()

    if not INVENTORY_PATH.exists():
        return _fail([f"inventory.md missing at {INVENTORY_PATH}"])

    original_text = INVENTORY_PATH.read_text(encoding="utf-8")
    inventory_rows = _parse_inventory_rows(original_text)
    errors, pairs = _collect_errors(discovered, inventory_rows)

    if fix:
        blocking = [e for e in errors if not e.startswith(RELOCATION_FINDING_PREFIX)]
        if blocking:
            # Fail-closed: never write while any non-relocation error exists.
            return _fail(["--fix refused to write: non-relocation errors are present:"] + blocking)
        if pairs:
            new_text = _apply_relocation_fixes(original_text, pairs)
            new_rows = _parse_inventory_rows(new_text)
            re_errors, _ = _collect_errors(discovered, new_rows)
            if re_errors:
                return _fail(["--fix refused to write: the re-pinned inventory would still fail:"] + re_errors)
            INVENTORY_PATH.write_text(new_text, encoding="utf-8")
            print(f"AUDIT FIXED: re-pinned {len(pairs)} relocated sink row(s) (locator columns only; disposition and rationale untouched)")
            print(_summary(new_rows, len(discovered)))
            return 0
        # Nothing to fix: behave exactly like a plain audit run (no write).

    if errors:
        return _fail(errors)

    print(_summary(inventory_rows, len(discovered)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
