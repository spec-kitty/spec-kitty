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

import ast
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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

    def key(self) -> RowKey:
        """Composite comparison identity (FR-004): ``(rel_path, qualname, token)``.

        Derived live from the current source line, so a line shift produces the
        SAME key (drift-immunity); ``sink_op`` is deliberately excluded -- it is
        diagnostic, not identity.
        """
        return composite_row_key(self.rel_path, self.line)

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


def main() -> int:
    errors: list[str] = []

    discovered = discover_rows()
    discovered_files = {r.rel_path for r in discovered}

    if not INVENTORY_PATH.exists():
        return _fail([f"inventory.md missing at {INVENTORY_PATH}"])

    inventory_rows = _parse_inventory_rows(INVENTORY_PATH.read_text(encoding="utf-8"))

    # ---- Check 1: valid dispositions + Named-untrusted rule (SC-003). ----
    errors.extend(_check_dispositions(inventory_rows))

    # ---- Build composite comparison maps (fail-closed on unparseable rows). ----
    parse_errors, inventory_keys = build_inventory_key_map(inventory_rows)
    errors.extend(parse_errors)
    discovered_keys = build_discovered_key_map(discovered)

    # ---- Check 2 (undercount) + Check 2b (overcount/ghost) via PURE seams. ----
    errors.extend(check_undercount(discovered_keys, inventory_keys))
    errors.extend(check_overcount(discovered_keys, inventory_keys))

    # ---- Check 3: known-candidate presence (path-level tripwire). ----
    errors.extend(_check_known_candidates(discovered_files, inventory_rows))

    # ---- Check 4: FR-009 meta.json source present + tagged. ----
    errors.extend(_check_fr009(inventory_rows))

    if errors:
        return _fail(errors)

    print(_summary(inventory_rows, len(discovered)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
