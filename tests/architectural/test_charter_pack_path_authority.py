"""Charter pack path authority gate (FR-016, NFR-002; mission charter-pack-cutover-01M491G6, WP03).

The project layer lives at ``.kittify/charter-packs/`` and every path inside a
charter pack (``drg/fragment.yaml``, ``org-charter.yaml``, ``presets/``) is
named once, in :mod:`kernel.charter_pack_paths`. This gate keeps it that way:

* **Clause (a)**: no ``"doctrine"`` path segment in a path-construction
  context under ``src/`` (the retired ``.kittify/doctrine/`` root, and any
  other ``doctrine`` directory a path is built through).
* **Clause (b)**: no re-spelling of the pack-path literals outside the
  authority: ``.kittify/charter-packs``, a ``"charter-packs"`` segment,
  ``"org-charter.yaml"``, ``"fragment.yaml"`` or a ``"presets"`` segment.
* **Clause (c)**: the non-Python surfaces follow the root: this repository's
  ``.gitignore`` names ``.kittify/charter-packs`` and no ``.kittify/doctrine``,
  and the state contract's project graph pattern is the kernel-built value.

Path-construction contexts (prose, docstrings and messages are excluded by
construction; the FR-018 vocabulary gate owns ``.kittify/doctrine`` in prose):

1. an operand of a ``/`` ``BinOp``;
2. an argument of ``Path(...)`` / ``PurePath(...)`` (and the pure variants) or
   of ``.joinpath(...)``, including a splatted tuple/list literal, or a splatted
   module-level tuple/list name (resolved in-module);
3. the right-hand side of an assignment when it is path-shaped (contains a
   ``/``, no whitespace) or a file name (``*.yaml``), including the elements of
   a tuple/list/set right-hand side;
4. an f-string whose literal text is path-shaped (the CR-07 split-literal
   shape ``f"{_X}/doctrine/{kind}"``), its constant parts split on ``/``;
5. any string constant that starts with ``.kittify/`` and has no whitespace;
6. loop-then-join: the elements of a tuple/list literal, or of a module-level
   tuple/list name, iterated by a ``for`` statement or a comprehension whose
   loop variable is a ``/`` operand or a ``Path()`` / ``joinpath()`` argument
   inside that loop (``repo_root / c for c in ("src", "doctrine")``).

Module-level ``str`` constant aliases are resolved, so ``X = ".kittify"`` /
``Y = "doctrine"`` ... ``root / X / Y`` and ``f"{X}/{Y}"`` cannot hide a site.
A tuple of bare words that is never splatted or loop-joined into a path
(``("doctrine", "glossary")``) is not a path and is not flagged.

Known limits (no live ``src`` site uses them; WP03 review cycle 1 probe): a
function-local alias (``seg = "doctrine"; root / seg``), ``os.path.join``,
string concatenation, a parameter default and a class attribute.

Authority and exemptions
------------------------
* :data:`AUTHORITY_REL_PATH` (``src/kernel/charter_pack_paths.py``) is the only
  file allowed to spell the clause (b) literals. It is scanned for clause (a)
  like every other module: WP14 deleted its temporary read fallback (FR-011),
  so it spells no retired segment (:func:`test_authority_spells_no_retired_segment`).
* :data:`RETIRED_LAYOUT_AUTHORITY_REL_PATH`
  (``src/specify_cli/migration/legacy_charter_layout.py``, the legacy-state
  predicate module of spec FR-018) is the only file allowed to spell the clause
  (a) segment: it names the retired layout so the cutover migration (which
  imports it and spells nothing itself) and the FR-011 CLI-root gate can detect
  it. It is scanned for clause (b) like every other module. WP25 replaced the
  former by-file exemption list with these two authorities: it deleted the
  frozen upgrade migrations' dead fallbacks into the deleted built-in tree, and
  the cutover migration no longer spells the segment.

Allowlist (``charter_pack_path_allowlist.yaml``)
-----------------------------------------------
Shrink-only, keyed on ``(file, qualname, literal, clause)``, every entry naming
the work package that drains it (WP04, WP05, WP14 or WP25) and a rationale.
NFR-002: it closes empty. Non-vacuity: a scanned-file floor, a live-census
ceiling with a margin, exact accounting, a staleness twin, per-literal (never
per-module) sanctioning, and a planted-literal self-test per clause and per
shape.
"""

from __future__ import annotations

import ast
import importlib
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

from tests.architectural._ast_scan import read_and_parse

pytestmark = pytest.mark.architectural

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
SRC_ROOT = _REPO_ROOT / "src"
#: The allowlist ledger file (shrink-only; closed empty by WP25).
LEDGER_PATH = _THIS.parent / "charter_pack_path_allowlist.yaml"
GITIGNORE_PATH = _REPO_ROOT / ".gitignore"

#: The one module allowed to name the project pack root and the pack-relative paths.
AUTHORITY_REL_PATH = "src/kernel/charter_pack_paths.py"

#: Clause (a): the retired path segment.
LEGACY_SEGMENT = "doctrine"
#: Clause (b): the pack root literal and the pack-relative segments.
PACK_ROOT_LITERAL = ".kittify/charter-packs"
CLAUSE_B_SEGMENTS: frozenset[str] = frozenset({"charter-packs", "org-charter.yaml", "fragment.yaml", "presets"})

#: The work packages allowed to own (and drain) an allowlist entry.
DRAIN_OWNERS: frozenset[str] = frozenset({"WP04", "WP05", "WP14", "WP25"})

#: The one module allowed to spell the retired clause (a) segment: the legacy-state predicate.
RETIRED_LAYOUT_AUTHORITY_REL_PATH = "src/specify_cli/migration/legacy_charter_layout.py"
_CUTOVER_MIGRATION = "src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py"


#: Non-vacuity: the gate must have scanned at least this many ``src`` files.
#: Live count at landing (2026-10-07): 1,393; recorded with a margin so a
#: discovery regression (an empty or partial walk) reds instead of passing.
SCANNED_FILE_FLOOR = 1300

_PATH_CTORS = frozenset({"Path", "PurePath", "PurePosixPath", "PureWindowsPath"})
_PLACEHOLDER = "{}"
_WS = re.compile(r"\s")
_OWNER = re.compile(r"^WP\d{2}$")


class AllowlistEntryError(ValueError):
    """A malformed, glob-shaped, ownerless or unjustified allowlist entry."""


@dataclass(frozen=True)
class AllowKey:
    """The composite allowlist key: per literal, never per module."""

    rel_path: str
    qualname: str
    literal: str
    clause: str


@dataclass(frozen=True)
class Finding:
    """One pack-path literal in a path-construction context. ``lineno`` locates only."""

    rel_path: str
    qualname: str
    literal: str
    clause: str
    lineno: int

    @property
    def key(self) -> AllowKey:
        return AllowKey(self.rel_path, self.qualname, self.literal, self.clause)

    def describe(self) -> str:
        what = {
            "a": f"builds a path through the retired {LEGACY_SEGMENT!r} segment",
            "b": "re-spells a charter pack path literal outside kernel.charter_pack_paths",
        }[self.clause]
        return f"{self.rel_path}:{self.lineno} ({self.qualname}) literal={self.literal!r} {what} (FR-016 clause {self.clause}); use kernel.charter_pack_paths"


# --------------------------------------------------------------------------- #
# Literal classification.
# --------------------------------------------------------------------------- #
def _segments(text: str) -> list[str]:
    return [part for part in text.split("/") if part]


def clauses_for(text: str) -> list[str]:
    """Return the clauses (``"a"``, ``"b"``) a path string in a path context violates."""
    segments = _segments(text)
    hits: list[str] = []
    if LEGACY_SEGMENT in segments:
        hits.append("a")
    if PACK_ROOT_LITERAL in text or CLAUSE_B_SEGMENTS.intersection(segments):
        hits.append("b")
    return hits


def _is_path_shaped(text: str) -> bool:
    return "/" in text and not _WS.search(text)


def _is_assignable_path(text: str) -> bool:
    """An assignment right-hand side that declares a path or a file name."""
    if _WS.search(text):
        return False
    return "/" in text or text.endswith((".yaml", ".yml"))


# --------------------------------------------------------------------------- #
# Module-level alias resolution.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Aliases:
    strings: dict[str, str]
    sequences: dict[str, list[str]]


def _assign_pairs(tree: ast.Module) -> Iterator[tuple[str, ast.expr]]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
            yield node.target.id, node.value


def _module_aliases(tree: ast.Module) -> _Aliases:
    """Resolve module-level ``NAME = "..."`` (one alias hop) and ``NAME = ("...", ...)``."""
    strings: dict[str, str] = {}
    sequences: dict[str, list[str]] = {}
    pairs = list(_assign_pairs(tree))
    for name, value in pairs:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            strings[name] = value.value
        elif isinstance(value, (ast.Tuple, ast.List)):
            items = [e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if items and len(items) == len(value.elts):
                sequences[name] = items
    for name, value in pairs:
        if isinstance(value, ast.Name) and value.id in strings and name not in strings:
            strings[name] = strings[value.id]
    return _Aliases(strings, sequences)


def _render(node: ast.expr, aliases: _Aliases) -> str | None:
    """Return the string a node stands for (constant, alias or f-string), else ``None``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in aliases.strings:
        return aliases.strings[node.id]
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                inner = _render(value.value, aliases) if isinstance(value.value, ast.Name) else None
                parts.append(inner if inner is not None else _PLACEHOLDER)
        return "".join(parts)
    return None


# --------------------------------------------------------------------------- #
# Path-construction contexts.
# --------------------------------------------------------------------------- #
def _is_path_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in _PATH_CTORS
    if isinstance(func, ast.Attribute):
        return func.attr in _PATH_CTORS or func.attr == "joinpath"
    return False


def _call_arg_nodes(call: ast.Call, aliases: _Aliases) -> Iterator[tuple[ast.AST, str]]:
    for arg in call.args:
        if isinstance(arg, ast.Starred):
            inner = arg.value
            if isinstance(inner, (ast.Tuple, ast.List)):
                for element in inner.elts:
                    text = _render(element, aliases)
                    if text is not None:
                        yield element, text
            elif isinstance(inner, ast.Name) and inner.id in aliases.sequences:
                for text in aliases.sequences[inner.id]:
                    yield inner, text
            continue
        text = _render(arg, aliases)
        if text is not None:
            yield arg, text


def _assigned_nodes(value: ast.expr, aliases: _Aliases) -> Iterator[tuple[ast.AST, str]]:
    elements = value.elts if isinstance(value, (ast.Tuple, ast.List, ast.Set)) else [value]
    for element in elements:
        if isinstance(element, (ast.Constant, ast.JoinedStr)):
            text = _render(element, aliases)
            if text is not None and _is_assignable_path(text):
                yield element, text


_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


def _iterable_strings(iterable: ast.expr, aliases: _Aliases) -> list[tuple[ast.AST, str]]:
    """The strings a loop iterates: a tuple/list literal's elements, or a module-level sequence alias."""
    if isinstance(iterable, (ast.Tuple, ast.List)):
        rendered = [(element, _render(element, aliases)) for element in iterable.elts]
        return [(element, text) for element, text in rendered if text is not None]
    if isinstance(iterable, ast.Name) and iterable.id in aliases.sequences:
        return [(iterable, text) for text in aliases.sequences[iterable.id]]
    return []


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _joins_name(scope: Iterable[ast.AST], name: str) -> bool:
    """Whether *name* is a ``/`` operand or a ``Path()`` / ``joinpath()`` argument anywhere in *scope*."""
    for root in scope:
        for node in ast.walk(root):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                if _is_name(node.left, name) or _is_name(node.right, name):
                    return True
            elif isinstance(node, ast.Call) and _is_path_call(node) and any(_is_name(arg, name) for arg in node.args):
                return True
    return False


def _loops(node: ast.AST) -> Iterator[tuple[ast.expr, ast.expr, list[ast.AST]]]:
    """Yield ``(target, iterable, scope)`` for a ``for`` statement or each generator of a comprehension."""
    if isinstance(node, (ast.For, ast.AsyncFor)):
        yield node.target, node.iter, list(node.body)
    elif isinstance(node, _COMPREHENSIONS):
        body: list[ast.AST] = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
        for generator in node.generators:
            yield generator.target, generator.iter, [*body, *generator.ifs]


def _loop_joined_strings(node: ast.AST, aliases: _Aliases) -> Iterator[tuple[ast.AST, str]]:
    """Loop-then-join: the strings a loop iterates are path parts when its variable is joined into a path."""
    for target, iterable, scope in _loops(node):
        if isinstance(target, ast.Name) and _joins_name(scope, target.id):
            yield from _iterable_strings(iterable, aliases)


def _path_context_strings(node: ast.AST, aliases: _Aliases) -> Iterator[tuple[ast.AST, str]]:
    """Yield ``(site node, rendered string)`` for each string *node* puts in a path context."""
    if isinstance(node, (ast.For, ast.AsyncFor, *_COMPREHENSIONS)):
        yield from _loop_joined_strings(node, aliases)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        for operand in (node.left, node.right):
            text = _render(operand, aliases)
            if text is not None:
                yield operand, text
    elif isinstance(node, ast.Call) and _is_path_call(node):
        yield from _call_arg_nodes(node, aliases)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
        yield from _assigned_nodes(node.value, aliases)
    elif isinstance(node, ast.JoinedStr):
        text = _render(node, aliases)
        if text is not None and _is_path_shaped(text):
            yield node, text
    elif _is_kittify_path_constant(node):
        assert isinstance(node, ast.Constant)
        yield node, str(node.value)


def _is_kittify_path_constant(node: ast.AST) -> bool:
    """A bare ``.kittify/...`` string anywhere is a repository path, whatever its context."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(".kittify/") and not _WS.search(node.value)


def _parent_map(tree: ast.Module) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _qualname(parents: dict[int, ast.AST], target: ast.AST) -> str:
    chain: list[str] = []
    cur: ast.AST | None = parents.get(id(target))
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chain.append(cur.name)
        cur = parents.get(id(cur))
    return ".".join(reversed(chain)) if chain else "<module>"


def _rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _scan_file(path: Path) -> list[Finding]:
    rel = _rel(path)
    _, tree = read_and_parse(path, display=rel)
    parents = _parent_map(tree)
    aliases = _module_aliases(tree)
    # The constant parts of an f-string are judged as part of the f-string, never alone.
    fstring_parts = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
    seen: set[tuple[int, str, str]] = set()
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if id(node) in fstring_parts:
            continue
        for site, text in _path_context_strings(node, aliases):
            for clause in clauses_for(text):
                marker = (id(site), text, clause)
                if marker in seen:
                    continue
                seen.add(marker)
                lineno = getattr(site, "lineno", getattr(node, "lineno", 0))
                findings.append(Finding(rel, _qualname(parents, site), text, clause, lineno))
    return findings


def scan(paths: Iterable[Path]) -> list[Finding]:
    """Scan the given Python files; no authority or exemption filtering (planted-test entry point)."""
    findings: list[Finding] = []
    for path in paths:
        findings.extend(_scan_file(path))
    return sorted(findings, key=lambda f: (f.rel_path, f.lineno, f.literal, f.clause))


def source_files(src_root: Path) -> list[Path]:
    """Every ``src`` Python file the gate covers: all of them.

    The two authorities are covered too; :func:`governed_findings` drops only
    the clause each one is allowed to spell.
    """
    return [p for p in sorted(src_root.rglob("*.py")) if "__pycache__" not in p.parts]


def governed_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Drop each authority's own clause findings; keep everything else."""
    own = {(AUTHORITY_REL_PATH, "b"), (RETIRED_LAYOUT_AUTHORITY_REL_PATH, "a")}
    return [f for f in findings if (f.rel_path, f.clause) not in own]


def check(findings: Iterable[Finding], allowlist: set[AllowKey]) -> list[str]:
    """Return a violation line for every finding the allowlist does not sanction."""
    return sorted(f.describe() for f in findings if f.key not in allowlist)


# --------------------------------------------------------------------------- #
# Allowlist.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AllowEntry:
    key: AllowKey
    owner: str
    rationale: str


def _require(entry: dict[str, object], field: str, context: str) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AllowlistEntryError(f"{context} lacks a non-empty {field!r} (got {value!r})")
    return value


def load_allowlist(path: Path = LEDGER_PATH) -> list[AllowEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries: list[AllowEntry] = []
    for idx, entry in enumerate(raw.get("charter_pack_path_literals") or []):
        context = f"charter_pack_path_literals[{idx}]"
        if not isinstance(entry, dict):
            raise AllowlistEntryError(f"{context} is not a mapping")
        rel_path = _require(entry, "file", context)
        if any(ch in rel_path for ch in "*?") or not rel_path.endswith(".py"):
            raise AllowlistEntryError(f"{context} file {rel_path!r} must name exactly one .py module (no globs)")
        clause = _require(entry, "clause", context)
        if clause not in ("a", "b"):
            raise AllowlistEntryError(f"{context} clause {clause!r} is not 'a' or 'b'")
        owner = _require(entry, "owner", context)
        if not _OWNER.match(owner) or owner not in DRAIN_OWNERS:
            raise AllowlistEntryError(f"{context} owner {owner!r} is not one of {sorted(DRAIN_OWNERS)}")
        key = AllowKey(rel_path, _require(entry, "qualname", context), _require(entry, "literal", context), clause)
        entries.append(AllowEntry(key, owner, _require(entry, "rationale", context)))
    return entries


def load_baseline(path: Path = LEDGER_PATH) -> int:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    value = raw.get("charter_pack_path_baseline")
    if not isinstance(value, int):
        raise AllowlistEntryError("charter_pack_path_baseline is missing or not an integer")
    return value


#: The allowlist as loaded from :data:`LEDGER_PATH` (NFR-002: closed empty by WP25).
ALLOWLIST: tuple[AllowEntry, ...] = tuple(load_allowlist())


def test_allowlist_is_empty() -> None:
    """NFR-002: every entry was drained; a new one needs a spec change, not an allowlist row."""
    assert ALLOWLIST == ()
    assert load_baseline() == 0


@lru_cache(maxsize=1)
def _live() -> tuple[tuple[Path, ...], tuple[Finding, ...]]:
    files = tuple(source_files(SRC_ROOT))
    return files, tuple(governed_findings(scan(files)))


def _live_findings() -> tuple[Finding, ...]:
    return _live()[1]


def _allow_keys() -> set[AllowKey]:
    return {entry.key for entry in load_allowlist()}


def _plant(tmp_path: Path, source: str, name: str = "planted.py") -> Path:
    target = tmp_path / name
    target.write_text(source, encoding="utf-8")
    return target


# =========================================================================== #
# Real-tree gate
# =========================================================================== #
def test_gate_green_on_the_tree() -> None:
    violations = check(_live_findings(), _allow_keys())
    assert violations == [], "\n".join(violations)


def test_scanned_file_floor() -> None:
    files, _ = _live()
    assert SCANNED_FILE_FLOOR >= 1000
    assert len(files) >= SCANNED_FILE_FLOOR, f"the gate scanned {len(files)} src files, below the floor {SCANNED_FILE_FLOOR}"


def test_allowlist_accounts_for_every_live_finding() -> None:
    """Exact accounting: one allowlist key per distinct live key, none speculative."""
    live = {f.key for f in _live_findings()}
    keys = _allow_keys()
    assert len(keys) == len(load_allowlist()), "duplicate allowlist entries"
    assert keys == live, f"unlisted: {sorted(live - keys, key=str)}; stale: {sorted(keys - live, key=str)}"


def test_allowlist_shrink_only() -> None:
    entries = load_allowlist()
    assert len(entries) <= load_baseline(), "the FR-016 allowlist grew past its baseline; route the site through kernel.charter_pack_paths instead"
    assert load_baseline() - len(entries) == 0, "lower charter_pack_path_baseline to the drained count"


def test_allowlist_entries_name_a_drain_owner() -> None:
    for entry in load_allowlist():
        assert entry.owner in DRAIN_OWNERS, entry


def test_authorities_exist() -> None:
    assert (_REPO_ROOT / AUTHORITY_REL_PATH).is_file()
    assert (_REPO_ROOT / RETIRED_LAYOUT_AUTHORITY_REL_PATH).is_file()


def test_retired_layout_authority_spells_only_the_retired_segment() -> None:
    """The predicate is in the tree walk, spells clause (a) (load-bearing control) and never clause (b)."""
    authority = scan([_REPO_ROOT / RETIRED_LAYOUT_AUTHORITY_REL_PATH])
    assert {f.clause for f in authority} == {"a"}
    assert _REPO_ROOT / RETIRED_LAYOUT_AUTHORITY_REL_PATH in _live()[0]


def test_cutover_migration_spells_no_retired_segment() -> None:
    """The cutover migration reads the retired layout through the predicate, never by spelling it."""
    assert scan([_REPO_ROOT / _CUTOVER_MIGRATION]) == []


def test_authority_spells_no_retired_segment() -> None:
    """The authority is scanned for clause (a) like every module, and spells none (FR-011)."""
    authority = scan([_REPO_ROOT / AUTHORITY_REL_PATH])
    assert {f.clause for f in authority} == {"b"}, "the authority may spell only the clause (b) literals"
    assert _REPO_ROOT / AUTHORITY_REL_PATH in _live()[0], "the authority must be in the tree walk"


def test_the_authoritys_clause_b_literals_are_its_own(tmp_path: Path) -> None:
    """Only the authority's clause (b) findings are dropped; a planted clause (a) one there is kept."""
    planted = Finding(AUTHORITY_REL_PATH, "<module>", "doctrine", "a", 1)
    own = Finding(AUTHORITY_REL_PATH, "<module>", "charter-packs", "b", 2)
    elsewhere = Finding("src/x.py", "<module>", "charter-packs", "b", 3)
    assert governed_findings([planted, own, elsewhere]) == [planted, elsewhere]


# --------------------------------------------------------------------------- #
# Clause (c): non-Python surfaces.
# --------------------------------------------------------------------------- #
def test_gitignore_follows_the_project_pack_root() -> None:
    rules = [line.strip() for line in GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()]
    active = [rule for rule in rules if rule and not rule.startswith("#")]
    assert not [rule for rule in active if ".kittify/doctrine" in rule]
    assert f"{PACK_ROOT_LITERAL}/**" in active
    assert f"!{PACK_ROOT_LITERAL}/graph.yaml" in active


def test_state_contract_pattern_is_kernel_built() -> None:
    paths = importlib.import_module("kernel.charter_pack_paths")
    contract = importlib.import_module("specify_cli.state.contract")
    surfaces = {s.name: s for s in contract.STATE_SURFACES}
    expected = f"{paths.PROJECT_PACK_ROOT_POSIX}/{paths.PROJECT_GRAPH_FILENAME}"
    assert surfaces["project_pack_graph"].path_pattern == expected


# =========================================================================== #
# Planted self-tests (non-vacuity): one per clause and per shape.
# =========================================================================== #
@pytest.mark.parametrize(
    ("source", "literal"),
    [
        pytest.param('from pathlib import Path\nROOT = Path(".kittify") / "doctrine"\n', "doctrine", id="binop"),
        pytest.param('from pathlib import Path\nROOT = Path(".kittify", "doctrine")\n', "doctrine", id="path-arg"),
        pytest.param('def f(root):\n    return root.joinpath(".kittify", "doctrine")\n', "doctrine", id="joinpath-arg"),
        pytest.param('def f(kind):\n    return f".kittify/doctrine/{kind}"\n', ".kittify/doctrine/{}", id="f-string"),
        pytest.param('from pathlib import Path\ndef f():\n    return Path(*(".kittify", "doctrine"))\n', "doctrine", id="tuple-splat"),
        pytest.param(
            'from pathlib import Path\nPARTS = (".kittify", "doctrine")\ndef f(r):\n    return r.joinpath(*PARTS)\n',
            "doctrine",
            id="tuple-alias-splat",
        ),
        pytest.param(
            'def f(root):\n    return tuple(root / c for c in ("src/charter/offering", "doctrine"))\n',
            "doctrine",
            id="loop-join-inline-iterable",
        ),
        pytest.param(
            'CANDIDATES = ("src/charter/offering", "doctrine")\n'
            "def f(root):\n    out = []\n    for c in CANDIDATES:\n        out.append(root.joinpath(c))\n    return out\n",
            "doctrine",
            id="loop-join-module-alias",
        ),
        pytest.param('SEG = "doctrine"\ndef f(root):\n    return root / ".kittify" / SEG\n', "doctrine", id="alias-constant"),
        pytest.param(
            'K = ".kittify"\nS = "doctrine"\ndef f(kind):\n    return f"{K}/{S}/{kind}"\n',
            ".kittify/doctrine/{}",
            id="alias-f-string",
        ),
        pytest.param('POLICY = ".kittify/doctrine/replaceable-builtins.yaml"\n', ".kittify/doctrine/replaceable-builtins.yaml", id="assign"),
        pytest.param('def f(p):\n    return p.startswith(".kittify/doctrine/")\n', ".kittify/doctrine/", id="kittify-string"),
    ],
)
def test_planted_clause_a_shapes_are_flagged(tmp_path: Path, source: str, literal: str) -> None:
    findings = scan([_plant(tmp_path, source)])
    assert [(f.clause, f.literal) for f in findings] == [("a", literal)]


@pytest.mark.parametrize(
    ("source", "literal"),
    [
        pytest.param('def f(r):\n    return r / ".kittify/charter-packs"\n', ".kittify/charter-packs", id="pack-root"),
        pytest.param('def f(r):\n    return r / ".kittify" / "charter-packs"\n', "charter-packs", id="pack-segment"),
        pytest.param('def f(p):\n    return p / "org-charter.yaml"\n', "org-charter.yaml", id="org-charter"),
        pytest.param('from pathlib import Path\nFRAG = Path("drg", "fragment.yaml")\n', "fragment.yaml", id="fragment"),
        pytest.param('def f(p):\n    return p / "presets"\n', "presets", id="presets"),
        pytest.param('ORG = "org-charter.yaml"\n', "org-charter.yaml", id="assign-filename"),
    ],
)
def test_planted_clause_b_literals_are_flagged(tmp_path: Path, source: str, literal: str) -> None:
    findings = scan([_plant(tmp_path, source)])
    assert [(f.clause, f.literal) for f in findings] == [("b", literal)]


@pytest.mark.parametrize(
    "source",
    [
        pytest.param('CATEGORIES = ("doctrine", "glossary")\nKIND = "doctrine"\n', id="non-path-tuple"),
        pytest.param('def f(x):\n    return x in ("doctrine", "presets")\n', id="membership-tuple"),
        pytest.param('def f(root):\n    return [k.upper() for k in ("doctrine", "glossary")]\n', id="loop-without-join"),
        pytest.param('def f():\n    """Writes .kittify/doctrine/ and org-charter.yaml."""\n', id="docstring"),
        pytest.param('def f(p):\n    raise ValueError(f"remove {p} from .kittify/doctrine/ and retry")\n', id="message"),
        pytest.param('from typing import Literal\nCategory = Literal["doctrine", "glossary"]\n', id="literal-type"),
        pytest.param('from pathlib import Path\nROOT = Path(".kittify") / "charter"\n', id="clean-path"),
    ],
)
def test_planted_non_path_shapes_are_not_flagged(tmp_path: Path, source: str) -> None:
    assert scan([_plant(tmp_path, source)]) == []


def test_allowlisting_one_literal_does_not_waive_the_module(tmp_path: Path) -> None:
    planted = _plant(
        tmp_path,
        'def f(root):\n    a = root / "doctrine" / "graph.yaml"\n    b = root / "presets"\n    return a, b\n',
    )
    findings = scan([planted])
    assert {(f.clause, f.literal) for f in findings} == {("a", "doctrine"), ("b", "presets")}
    sanctioned = next(f for f in findings if f.clause == "a")
    violations = check(findings, {sanctioned.key})
    assert len(violations) == 1 and "presets" in violations[0]


def test_stale_allowlist_entry_is_detected() -> None:
    speculative = AllowKey("src/specify_cli/future.py", "f", "doctrine", "a")
    assert speculative not in {f.key for f in _live_findings()}


def test_only_each_authoritys_own_clause_is_dropped() -> None:
    planted = [
        Finding(RETIRED_LAYOUT_AUTHORITY_REL_PATH, "<module>", "charter-packs", "b", 1),
        Finding(RETIRED_LAYOUT_AUTHORITY_REL_PATH, "<module>", "doctrine", "a", 2),
    ]
    assert governed_findings(planted) == planted[:1]
    # Control: the authority does spell the governed clause (b) literals, so dropping them is load-bearing.
    assert scan([_REPO_ROOT / AUTHORITY_REL_PATH])


def test_planted_glob_or_ownerless_allowlist_entry_is_refused(tmp_path: Path) -> None:
    base = {"qualname": "f", "literal": "doctrine", "clause": "a", "rationale": "r"}
    for bad in (
        {**base, "file": "src/specify_cli/**/x.py", "owner": "WP14"},
        {**base, "file": "src/x.py"},
        {**base, "file": "src/x.py", "owner": "WP99"},
    ):
        target = tmp_path / "allow.yaml"
        target.write_text(yaml.safe_dump({"charter_pack_path_literals": [bad]}), encoding="utf-8")
        with pytest.raises(AllowlistEntryError):
            load_allowlist(target)
