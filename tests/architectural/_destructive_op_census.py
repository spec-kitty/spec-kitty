"""Shared AST-census / allowlist-diff / self-mutation plumbing (DIRECTIVE_044).

Single authority for the three census architectural gates, so the
census machinery is written and audited once, not copy-pasted (charter
single-canonical-authority; DIRECTIVE_044):

* ``test_destructive_op_routing.py`` — scans **git argv literals**
  (``reset --hard`` / ``worktree remove --force`` / ``merge --abort``) under
  ``src/specify_cli`` (mission ``merge-destructive-op-safety-01M2XQF8``).
* ``test_mutation_ownership_routing.py`` — scans **Python filesystem
  ``ast.Call`` literals** (``shutil.rmtree`` / ``Path.unlink`` / …) in the
  ``init`` + upgrade-migration mutating-flow module set (mission
  ``ownership-boundary-preservation-01M32KEN``, WP09).
* ``test_overwrite_ownership_routing.py`` — scans the **overwrite /
  destination-clobber** ``ast.Call`` family (``os.replace`` /
  ``shutil.copy2`` / …) in a narrow module set (#4901).

All gates share the same shape: walk the AST of a fixed module set, classify
each literal, diff the live census against a frozen, individually-rationalized,
**shrink-only** allowlist (a NEW un-rationalized literal FAILS; a vanished one
only WARNS), and prove non-vacuity by (a) planting an un-routed op the same
scanner must detect and (b) dropping one real allowlist entry to reproduce the
exact gate failure. Everything below is the generic, classifier-agnostic core;
each gate keeps its own classifier, module set, and ``_ALLOWLIST``.

Identity and matching are NOT implemented here (C-004 / D-OP-9). A census site
is keyed by :class:`CensusKey`, built from
``tests.architectural._ratchet_keys.composite_key`` (the single identity
authority: enclosing qualname + normalized token line), plus the op label and
an ``op_ordinal`` among identical live sites; no line number is part of a key.
:func:`diff_against_allowlist` delegates to
``tests.architectural._content_identity.partition_findings`` (the single
matching authority). The census stale policy stays WARN (D-OP-8).
"""

from __future__ import annotations

import ast as _ast
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping
from pathlib import Path
from typing import NamedTuple, TypeVar

from tests.architectural._content_identity import partition_findings, with_blank_line_at_top, with_probe_above_statement
from tests.architectural._ratchet_keys import composite_key

# Re-export (C-004): ``_ratchet_keys.enclosing_qualname(source, lineno)`` is the ONE
# qualname algorithm; this module deliberately has none of its own.
from tests.architectural._ratchet_keys import enclosing_qualname as enclosing_qualname

from tests.architectural._ast_scan import parse_file, read_and_parse

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SPECIFY_CLI_ROOT = SRC_ROOT / "specify_cli"

_T = TypeVar("_T")

#: A census hit: ``(lineno, op)`` as every gate's finder reports it.
Hit = tuple[int, str]
_K = TypeVar("_K", bound=Hashable)


# ---------------------------------------------------------------------------
# AST plumbing
# ---------------------------------------------------------------------------


def iter_py_files(root: Path) -> list[Path]:
    """Every ``*.py`` file under *root*, ``__pycache__`` excluded, sorted."""
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def parse(path: Path) -> _ast.Module:
    """Parse *path*; fails closed (``UnparseableSourceError``) on a read/decode/syntax failure (#5139)."""
    return parse_file(path)


def parse_with_source(path: Path) -> tuple[str, _ast.Module]:
    """``(source, tree)`` for *path*; fails closed (``UnparseableSourceError``) on a read/decode/syntax failure (#5139)."""
    return read_and_parse(path)


def module_string_constants(tree: _ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "literal"`` / ``NAME: str = "literal"`` bindings.

    Resolves indirections like ``coordination/workspace.py``'s
    ``_GIT_WORKTREE = "worktree"`` so an argv element referencing the constant
    by name is not invisible to a scan.
    """
    consts: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, _ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], _ast.Name)
            and isinstance(node.value, _ast.Constant)
            and isinstance(node.value.value, str)
        ):
            consts[node.targets[0].id] = node.value.value
        elif (
            isinstance(node, _ast.AnnAssign)
            and isinstance(node.target, _ast.Name)
            and node.value is not None
            and isinstance(node.value, _ast.Constant)
            and isinstance(node.value.value, str)
        ):
            consts[node.target.id] = node.value.value
    return consts


def import_alias_map(tree: _ast.Module) -> dict[str, str]:
    """Every ``import X`` / ``import X as Y`` binding in *tree*: bound local
    name -> canonical dotted module name (e.g. ``import shutil as sh`` ->
    ``{"sh": "shutil"}``; ``import shutil`` -> ``{"shutil": "shutil"}``).

    Walks the whole tree (not just module-level body) so a function-local
    ``import shutil as sh`` is resolved too — a receiver-name census that only
    recognised the literal ``shutil``/``os`` spelling would otherwise treat an
    aliased import as invisible.
    """
    aliases: dict[str, str] = {}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                aliases[bound] = alias.name
    return aliases


def from_import_map(tree: _ast.Module) -> dict[str, tuple[str, str]]:
    """Every ``from X import Y [as Z]`` binding in *tree*: bound local name ->
    ``(module, original_attr_name)`` (e.g. ``from shutil import rmtree`` ->
    ``{"rmtree": ("shutil", "rmtree")}``; ``from shutil import rmtree as rm``
    -> ``{"rm": ("shutil", "rmtree")}``).

    Resolves a bare-``Name`` call bound this way (``rmtree(x)``) to its
    canonical ``module.attr`` op label — a call-site classifier keyed only on
    ``ast.Attribute`` receivers never sees this call shape at all.
    """
    bindings: dict[str, tuple[str, str]] = {}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                bound = alias.asname or alias.name
                bindings[bound] = (node.module, alias.name)
    return bindings


def resolve_token(node: _ast.expr, consts: Mapping[str, str]) -> str | None:
    """A string constant, or a ``Name`` bound to a module-level string constant."""
    if isinstance(node, _ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, _ast.Name):
        return consts.get(node.id)
    return None


def argv_tokens(node: _ast.List | _ast.Tuple, consts: Mapping[str, str]) -> list[str | None]:
    """Resolve each element of a list/tuple literal to its string value or ``None``."""
    return [resolve_token(elt, consts) for elt in node.elts]


def ordered_subsequence(tokens: list[str | None], *needles: str) -> bool:
    """True when *needles* appear, in order (not necessarily contiguous), among
    the resolved (non-``None``) elements of *tokens*."""
    idx = 0
    for tok in tokens:
        if tok is not None and tok == needles[idx]:
            idx += 1
            if idx == len(needles):
                return True
    return False


# ---------------------------------------------------------------------------
# Allowlist diff (shrink-only ratchet) + self-mutation harness
# ---------------------------------------------------------------------------


class CensusKey(NamedTuple):
    """Content identity of one census site (plan D-OP-1).

    ``(qualname, token_line)`` is ``_ratchet_keys.composite_key(source, lineno)``;
    ``op`` is the gate's op label; ``op_ordinal`` is the 0-based ordinal among
    the live hits sharing ``(rel, qualname, token_line, op)``, ordered by line.
    No line number is part of the key -- an unrelated line shift cannot re-pin it.
    """

    rel: str
    qualname: str
    token_line: str
    op: str
    op_ordinal: int


def census_keys(rel: str, source: str, hits: Iterable[Hit]) -> dict[CensusKey, int]:
    """Key every ``(lineno, op)`` hit in *source* by content: ``{CensusKey: lineno}``.

    The line number in the values is diagnostic only (:func:`render_census_key`).
    """
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for lineno, op in hits:
        qualname, token_line = composite_key(source, lineno)
        groups[(qualname, token_line, op)].append(lineno)
    keys: dict[CensusKey, int] = {}
    for (qualname, token_line, op), linenos in groups.items():
        for ordinal, lineno in enumerate(sorted(linenos)):
            keys[CensusKey(rel, qualname, token_line, op, ordinal)] = lineno
    return keys


def render_census_key(key: CensusKey, lineno: int | None = None) -> str:
    """``rel::qualname::op#ordinal (line N) tokens=<token_line>`` for failure output.

    The line is a diagnostic locator only; paste a ``CensusKey(...)`` literal,
    never the line, into an allowlist.
    """
    where = f" (line {lineno})" if lineno is not None else ""
    return f"{key.rel}::{key.qualname}::{key.op}#{key.op_ordinal}{where} tokens={key.token_line}"


def diff_against_allowlist(live_flat: Iterable[_K], allowlist: Mapping[_K, str]) -> tuple[set[_K], set[_K]]:
    """Return ``(unexpected, stale)``.

    * ``unexpected`` — sites live in the tree but absent from *allowlist*:
      the gate FAILS on these (a new un-rationalized destructive literal).
    * ``stale`` — sites listed but no longer live: WARN only (shrink-only
      ratchet — legitimate cleanup must never be blocked). Content keys make
      warn-on-stale safe: a dead content key cannot re-bind to a new site.

    Delegates to :func:`tests.architectural._content_identity.partition_findings`
    (D-OP-9: one matcher). ``CensusKey.op_ordinal`` makes live keys unique, so
    its multiset match is exactly the set difference.
    """
    unexpected, unused = partition_findings(((key, key) for key in live_flat), Counter(allowlist.keys()))
    return set(unexpected), set(unused)


def census_partition(live: Mapping[_K, int], allowlist: Mapping[_K, str]) -> tuple[set[_K], set[_K]]:
    """A census gate's one detection + matching path: ``(unexpected, suppressed)``.

    *live* is the gate's keyed census (``{key: lineno}`` from the REAL finder,
    possibly over in-memory mutated sources); ``unexpected`` is what
    :func:`diff_against_allowlist` fails on and ``suppressed`` is every live key
    *allowlist* blesses. Each gate binds its own finder and ``_ALLOWLIST`` in a
    one-line ``_census_partition``; the gate, the line-drift tests and the
    non-widening tests all go through this seam.
    """
    unexpected, _stale = diff_against_allowlist(live, allowlist)
    return unexpected, live.keys() & allowlist.keys()


def scan_planted_source(tmp_path: Path, name: str, source: str, finder: Callable[[Path], _T]) -> _T:
    """Write *source* to ``tmp_path/name`` and run *finder* over it.

    The generic half of the planted-op non-vacuity proof: each gate passes its
    own literal finder so the SAME scanner the primary gate runs is proven to
    detect a planted, un-routed op.
    """
    planted = tmp_path / name
    planted.write_text(source, encoding="utf-8")
    return finder(planted)


def drop_one_entry(allowlist: Mapping[_K, str]) -> tuple[_K, dict[_K, str]]:
    """Return ``(victim, shrunk)`` where *victim* is one entry removed from
    *allowlist* — the generic half of the drop-one-entry non-vacuity proof:
    re-diffing *shrunk* against the live tree must reproduce the gate failure
    the primary gate would raise for a genuine regression."""
    victim = next(iter(allowlist))
    shrunk = {k: v for k, v in allowlist.items() if k != victim}
    return victim, shrunk


# ---------------------------------------------------------------------------
# Drift / non-widening harness: run a gate's REAL finder over in-memory sources
# ---------------------------------------------------------------------------

_PROBE_ARGUMENT = "_census_probe_arg"


def scan_sources(sources: Mapping[str, str], finder: Callable[[Path], list[Hit]]) -> dict[str, list[Hit]]:
    """Run *finder* over every ``rel -> source`` pair; key the hits by *rel*.

    The finders take a ``Path``, so each (possibly mutated) source is written to
    a temporary copy at the same repo-relative path and scanned there. The hits
    are keyed with the ORIGINAL repo-relative path, so the gate, the drift
    tests and the non-widening tests all share one detection path. Files with
    no hit are omitted, exactly as the on-disk scans do.
    """
    live: dict[str, list[Hit]] = {}
    with tempfile.TemporaryDirectory(prefix="census-scan-") as tmp:
        root = Path(tmp)
        for rel, source in sources.items():
            copy = root / rel
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(source, encoding="utf-8")
            hits = finder(copy)
            if hits:
                live[rel] = hits
    return live


def census_keys_for_sources(sources: Mapping[str, str], finder: Callable[[Path], list[Hit]]) -> dict[CensusKey, int]:
    """``{CensusKey: lineno}`` for every *finder* hit across *sources* (``rel -> source``)."""
    keys: dict[CensusKey, int] = {}
    for rel, hits in scan_sources(sources, finder).items():
        keys.update(census_keys(rel, sources[rel], hits))
    return keys


def describe_unexpected(unexpected: Iterable[CensusKey], sources: Mapping[str, str], finder: Callable[[Path], list[Hit]]) -> list[str]:
    """Render each unexpected key with its diagnostic line, for a gate's failure message."""
    keys = sorted(unexpected)
    rels = {key.rel for key in keys}
    linenos = census_keys_for_sources({rel: sources[rel] for rel in rels if rel in sources}, finder)
    return [render_census_key(key, linenos.get(key)) for key in keys]


def read_sources(paths: Iterable[Path]) -> dict[str, str]:
    """``{repo-relative posix path: source text}`` for *paths* (unreadable files skipped)."""
    sources: dict[str, str] = {}
    for path in paths:
        try:
            sources[path.relative_to(REPO_ROOT).as_posix()] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return sources


def with_probes_above_sites(source: str, linenos: Iterable[int]) -> str:
    """Insert a drift probe above the statement of every site in *linenos*.

    Applied bottom-up so each earlier site's line number is still valid when
    its probe is inserted (WP02's :func:`with_probe_above_statement` inserts
    one probe per call).
    """
    for lineno in sorted(set(linenos), reverse=True):
        source = with_probe_above_statement(source, lineno)
    return source


def _smallest_stmt_spanning(tree: _ast.AST, lineno: int) -> _ast.stmt:
    best: _ast.stmt | None = None
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.stmt):
            continue
        end = node.end_lineno if node.end_lineno is not None else node.lineno
        if node.lineno <= lineno <= end and (best is None or end - node.lineno < (best.end_lineno or best.lineno) - best.lineno):
            best = node
    if best is None:
        raise ValueError(f"line {lineno} is not inside any statement")
    return best


def with_duplicated_statement(source: str, lineno: int) -> str:
    """Duplicate the innermost statement containing *lineno* directly below itself.

    Models "a second identical op in an exempted function": same enclosing
    function, same tokens, same op, one more occurrence.
    """
    stmt = _smallest_stmt_spanning(_ast.parse(source), lineno)
    lines = source.splitlines(keepends=True)
    end = stmt.end_lineno if stmt.end_lineno is not None else stmt.lineno
    block = lines[stmt.lineno - 1 : end]
    return "".join([*lines[:end], *block, *lines[end:]])


def _insertion_offset(source_line: str, node: _ast.expr) -> int:
    """Column just inside the node's opening bracket / call parenthesis."""
    if isinstance(node, _ast.Call):
        func_end = node.func.end_col_offset or 0
        return source_line.index("(", func_end) + 1
    col = node.col_offset
    return col + 1 if source_line[col] in "[(" else col


def _callee_name(node: _ast.expr) -> str | None:
    if not isinstance(node, _ast.Call):
        return None
    func = node.func
    if isinstance(func, _ast.Attribute):
        return func.attr
    return func.id if isinstance(func, _ast.Name) else None


def with_leading_argument(
    source: str,
    lineno: int,
    node_types: tuple[type[_ast.expr], ...],
    *,
    callee: str | None = None,
) -> str:
    """Insert ``_census_probe_arg, `` as the first element/argument of the
    first *node_types* node starting on *lineno* (restricted to calls whose
    callee name is *callee*, when given).

    Models "a changed argument on an exempted op": the line count is unchanged
    (so a ``path:line:op`` key keeps blessing the site), but the op's token line
    gains a NAME token, so a content key for the edited op no longer matches.
    Changing only a string literal would NOT do: ``composite_key`` strips
    strings, so the token line would be identical.
    """
    tree = _ast.parse(source)
    candidates = [n for n in _ast.walk(tree) if isinstance(n, node_types) and n.lineno == lineno and (callee is None or _callee_name(n) == callee)]
    if not candidates:
        raise ValueError(f"no {node_types!r} node starts on line {lineno}")
    node = min(candidates, key=lambda n: n.col_offset)
    lines = source.splitlines(keepends=True)
    line = lines[lineno - 1]
    offset = _insertion_offset(line, node)
    lines[lineno - 1] = f"{line[:offset]}{_PROBE_ARGUMENT}, {line[offset:]}"
    return "".join(lines)


def _describe(keys: Iterable[object]) -> list[str]:
    return sorted(str(key) for key in keys)


def assert_partition_survives_drift(
    rel: str,
    source: str,
    partition: Callable[[Mapping[str, str]], tuple[set[_K], set[_K]]],
    site_linenos: Iterable[int],
    file_keys: Iterable[_K],
) -> None:
    """NFR-001 / NFR-002: the gate's ``(unexpected, suppressed)`` partition of
    *rel* is identical after (i) a blank line at the top and (ii) a probe
    statement above every census site; the per-file suppressed count is
    unchanged and, unless one of *file_keys* is already stale, non-zero."""
    base_unexpected, base_suppressed = partition({rel: source})
    stale = set(file_keys) - base_suppressed
    assert stale or base_suppressed, f"{rel}: vacuous drift case -- no allowlisted site is suppressed on the unmutated source"
    mutations = {
        "blank line at top": with_blank_line_at_top(source),
        "probe above every census site": with_probes_above_sites(source, site_linenos),
    }
    for label, mutated in mutations.items():
        unexpected, suppressed = partition({rel: mutated})
        assert (unexpected, suppressed) == (base_unexpected, base_suppressed), (
            f"{rel}: census partition changed under line drift ({label}). "
            f"newly unexpected={_describe(unexpected - base_unexpected)} "
            f"no longer suppressed={_describe(base_suppressed - suppressed)}"
        )
        assert len(suppressed) == len(base_suppressed), f"{rel}: suppressed count changed under {label}"


def assert_second_identical_op_is_unexpected(
    rel: str,
    source: str,
    partition: Callable[[Mapping[str, str]], tuple[set[_K], set[_K]]],
    lineno: int,
) -> None:
    """Non-widening: duplicating an exempted op statement inside its function
    yields at least one NEW unexpected key -- an allowlist entry blesses one
    occurrence, never "every identical op in that function"."""
    base_unexpected, _ = partition({rel: source})
    unexpected, _ = partition({rel: with_duplicated_statement(source, lineno)})
    assert unexpected - base_unexpected, f"{rel}: a second identical op (duplicate of line {lineno}) was silently blessed by the allowlist"


def assert_changed_argument_is_unexpected(
    rel: str,
    source: str,
    partition: Callable[[Mapping[str, str]], tuple[set[_K], set[_K]]],
    mutated: str,
) -> None:
    """Non-widening: a token-changing argument edit on an exempted op makes the
    edited site unexpected (FAIL) and its old entry stale (WARN)."""
    base_unexpected, base_suppressed = partition({rel: source})
    unexpected, suppressed = partition({rel: mutated})
    new_unexpected = unexpected - base_unexpected
    newly_stale = base_suppressed - suppressed
    assert len(new_unexpected) == 1, (
        f"{rel}: an exempted op whose arguments changed is still blessed by its allowlist entry "
        f"(new unexpected={_describe(new_unexpected)}, still suppressed={_describe(suppressed)})"
    )
    assert len(newly_stale) == 1, f"{rel}: the edited op's old entry should turn stale, got {_describe(newly_stale)}"
