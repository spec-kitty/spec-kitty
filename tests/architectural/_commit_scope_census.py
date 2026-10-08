"""Census of sweeping, pathspec-less and hook-bypassing commit routes in ``src/`` (#5443, FR-013).

Mission ``upgrade-migration-commit-scope-01M4AKVE``. The rule: an automatic
commit records exactly the paths the operation wrote. Every automatic commit
goes through ``safe_commit`` with an explicit path list; a merge, revert or
squash conclusion, where git refuses a pathspec, goes through the one
merge-conclusion owner (``specify_cli.git.merge_conclusion``). This module is
the single authority for that rule; ``test_commit_scope_owner.py`` runs it over
``src/`` and requires zero hits, with no allowlist.

**Forms** (``classify_argv``; the ``kind`` of a :class:`Hit`):

* ``add-sweep`` -- ``add`` with ``-A``/``--all``/``.``/``-u``/``--update``/``:/``/``:/*``;
* ``commit-no-pathspec`` -- ``commit`` without ``-- <path...>``;
* ``amend-no-pathspec`` -- ``commit --amend`` without ``-- <path...>``;
* ``commit-all`` -- ``commit -a``/``--all``;
* ``hook-bypass`` -- ``--no-verify`` on any subcommand, ``commit -n``, or a
  ``-c core.hooksPath=...`` global override;
* ``committing-merge`` -- ``merge`` without ``--no-commit``/``--squash``/
  ``--ff-only``/``--abort``/``--quit`` (``--continue`` commits);
* ``committing-revert`` / ``committing-cherry-pick`` -- without ``--no-commit``/
  ``-n``/``--abort``/``--quit``/``--skip``.

A candidate argv is every list/tuple literal whose first resolved token is
``"git"``, plus the argv of a call to a known git runner (:data:`GIT_RUNNER_NAMES`):
its first list/tuple argument, or, for a varargs runner such as
``run_git(cwd, *args)``, its positional arguments after ``cwd``. Module-level
string constants resolve (``_ADD = "add"``); a ``*starred`` element and any other
expression is an unresolved token, which never satisfies a flag test and never
counts as ``"--"`` (an unresolved token *after* ``"--"`` does count as a path).

**Exemption: exactly two canonical owners, by symbol** (Decision
``01M4B6FZNNSTP6DPN2AAEDEQHZ``; ADR ``2026-09-30-1``: no allowlist). A hit is
exempt only when its enclosing top-level function (nested definitions count as
their top-level function) is one of an owner's ``symbols``, or is a
module-private (``_``-prefixed) top-level function of the same module that one
of those symbols calls directly by name. The callee set is computed here from
the AST, never listed by hand. Everything else in an owner's file is scanned
like any other file. :func:`census_source` never applies the exemption; the
planted cases and the positive controls use it.

**Exemption leak guard** (:func:`exempt_helper_leaks`): an exempt private helper
that itself holds a hit (``commit_helpers._commit_with_index_deletions``) is
exempt only because an owner symbol calls it, so it must be reached only from
there. Any other reference to it -- a call or reference from a non-owner
function of the owner file, or an attribute access or ``from ... import`` of it
in any other scanned file -- is a leak the gate reports.

**Out of scope / AST blind spots** (none of these shapes exists in ``src/``
today other than the plumbing commits; ``git grep -n "shell=True" -- src`` finds
only comments and docstrings): argv grown across statements (``+=``,
``.append``, ``.extend``); ``shlex.split(var)``; ``shell=True`` / ``os.system``
command strings; an argv held in a variable assigned in another function, or
passed to a runner whose name is not in :data:`GIT_RUNNER_NAMES`; function-local
string constants; an argv built by concatenation (``["git"] + [...]``, a
``BinOp``, is not a list literal, so it is never a candidate); a subcommand or
flag held in an f-string (``f"{verb}"`` is an unresolved token, so it never
satisfies a flag or subcommand test); clustered short options (``-am``); ``git rebase`` / ``pull``
/ ``am``, which replay or fetch commits and are outside FR-013's forms; and
**plumbing commits** (``git commit-tree`` + ``git update-ref``), which create a
commit without the porcelain ``commit`` subcommand. ``safe_commit``'s
expected-parent path uses them (``commit_helpers._create_expected_parent_commit``,
``_compare_and_swap_commit_ref``); they are outside this gate (follow-up:
"commit-scope gate: cover commit-tree/update-ref plumbing commits"). Those
plumbing commits run no hooks. The callers that reach them by passing
``expected_parent_sha`` are ``coordination/commit_router.py`` (``:357``,
``:736``) and ``cli/commands/agent/mission_finalize_planning_pin.py``
(``:586``, ``:788``).
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

from tests.architectural._destructive_op_census import (
    REPO_ROOT,
    SRC_ROOT,
    iter_py_files,
    module_string_constants,
    resolve_token,
)

__all__ = [
    "CANONICAL_OWNERS",
    "GIT_RUNNER_NAMES",
    "KINDS",
    "Hit",
    "OwnerSymbol",
    "OwnerSymbolMissing",
    "census",
    "census_source",
    "census_text",
    "classify_argv",
    "exempt_functions",
    "exempt_helper_leaks",
    "exempt_helper_leaks_text",
    "exempt_hit_holders",
    "src_files",
]


class OwnerSymbol(NamedTuple):
    """A canonical commit owner: a repo-relative file and the top-level functions that own the commit."""

    rel: str
    symbols: tuple[str, ...]


class OwnerSymbolMissing(AssertionError):
    """A canonical owner names a symbol its file no longer defines (a rename must fail the gate loudly)."""


class HelperLeak(NamedTuple):
    """A reference to an exempt, hit-holding private helper from outside its owner symbols."""

    path: str
    lineno: int
    helper: str
    referrer: str | None
    """The enclosing top-level function (``None`` at module level)."""


class Hit(NamedTuple):
    """One offending site: path, line, the form it matches, and the argv as the census resolved it."""

    path: str
    lineno: int
    kind: str
    argv_repr: str


#: Exactly two owners (Decision ``01M4B6FZNNSTP6DPN2AAEDEQHZ``). A third entry is a decision change.
CANONICAL_OWNERS: tuple[OwnerSymbol, ...] = (
    OwnerSymbol(rel="src/specify_cli/git/commit_helpers.py", symbols=("safe_commit",)),
    OwnerSymbol(rel="src/specify_cli/git/merge_conclusion.py", symbols=("run_committing_op", "conclude_in_progress_op")),
)

#: Callee names whose arguments are a git argv without the leading ``"git"``: ``_git_in(wt, [...], env)``,
#: ``run_git(cwd, *args)`` (``kernel/git/runner.py``), ``_run_git(args, cwd)`` and the like.
GIT_RUNNER_NAMES = frozenset({"_git_in", "run_git", "_run_git", "_git", "_run_git_for_commit"})

KINDS = frozenset(
    {
        "add-sweep",
        "commit-no-pathspec",
        "amend-no-pathspec",
        "commit-all",
        "hook-bypass",
        "committing-merge",
        "committing-revert",
        "committing-cherry-pick",
    }
)

_GIT = "git"
_PATHSPEC_SEPARATOR = "--"
_HOOKS_PATH_KEY = "core.hookspath="
_VALUED_GLOBALS = frozenset({"-C", "-c"})
_FLAG_GLOBALS = frozenset({"--literal-pathspecs", "--no-pager"})
_PREFIXED_GLOBALS = ("--git-dir=", "--work-tree=")
_ADD_SWEEPS = frozenset({"-A", "--all", ".", "-u", "--update", ":/", ":/*"})
_NO_VERIFY = "--no-verify"
_COMMIT_HOOK_BYPASS = frozenset({_NO_VERIFY, "-n"})
_COMMIT_ALL = frozenset({"-a", "--all"})
_NON_COMMITTING_MERGE = frozenset({"--no-commit", "--squash", "--ff-only", "--abort", "--quit"})
_NON_COMMITTING_PICK = frozenset({"--no-commit", "-n", "--abort", "--quit", "--skip"})
_PICK_KIND = {"revert": "committing-revert", "cherry-pick": "committing-cherry-pick"}
# Options whose value is the next token, so a message such as ``-m "-a"`` is never read as a flag.
_VALUED_OPTIONS: Mapping[str, frozenset[str]] = {
    "commit": frozenset(
        {"-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author", "--date", "--reuse-message", "--reedit-message", "--fixup", "--template", "--cleanup"}
    ),
    "merge": frozenset({"-m", "-F", "-s", "-X", "--message", "--file", "--strategy", "--strategy-option"}),
    "revert": frozenset({"-m", "-X", "--mainline", "--strategy", "--strategy-option"}),
    "cherry-pick": frozenset({"-m", "-X", "--mainline", "--strategy", "--strategy-option"}),
}

Tokens = Sequence[str | None]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _split_globals(tokens: Tokens) -> tuple[list[str], int]:
    """Walk git's global options; return the kinds they imply and the subcommand index."""
    kinds: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _VALUED_GLOBALS:
            value = tokens[i + 1] if i + 1 < len(tokens) else None
            if tok == "-c" and value is not None and value.lower().startswith(_HOOKS_PATH_KEY):
                kinds.append("hook-bypass")
            i += 2
        elif tok in _FLAG_GLOBALS or (tok is not None and tok.startswith(_PREFIXED_GLOBALS)):
            i += 1
        else:
            break
    return kinds, i


def _flags_and_paths(subcommand: str, rest: Tokens) -> tuple[set[str], list[str | None]]:
    """The resolved option tokens before ``--`` (option values skipped) and the tokens after it."""
    valued = _VALUED_OPTIONS.get(subcommand, frozenset())
    flags: set[str] = set()
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == _PATHSPEC_SEPARATOR:
            return flags, list(rest[i + 1 :])
        if tok is not None and tok.startswith("-"):
            flags.add(tok)
            if tok in valued:
                i += 1
        i += 1
    return flags, []


def _commit_kinds(flags: set[str], paths: list[str | None]) -> list[str]:
    kinds = ["hook-bypass"] if flags & _COMMIT_HOOK_BYPASS else []
    if flags & _COMMIT_ALL:
        kinds.append("commit-all")
    elif not paths:
        kinds.append("amend-no-pathspec" if "--amend" in flags else "commit-no-pathspec")
    return kinds


def _subcommand_kinds(subcommand: str, rest: Tokens) -> list[str]:
    if subcommand == "add":
        return ["add-sweep"] if {tok for tok in rest if tok is not None} & _ADD_SWEEPS else []
    flags, paths = _flags_and_paths(subcommand, rest)
    if subcommand == "commit":
        return _commit_kinds(flags, paths)
    kinds = ["hook-bypass"] if _NO_VERIFY in flags else []
    if subcommand == "merge" and not flags & _NON_COMMITTING_MERGE:
        kinds.append("committing-merge")
    elif subcommand in _PICK_KIND and not flags & _NON_COMMITTING_PICK:
        kinds.append(_PICK_KIND[subcommand])
    return kinds


def classify_argv(tokens: Tokens) -> list[str]:
    """Every form *tokens* (a git argv, with or without the leading ``"git"``) commits through.

    ``[]`` means the argv does not commit outside its paths. An unresolved
    (``None``) subcommand yields only what the global options imply.
    """
    body = list(tokens[1:]) if tokens and tokens[0] == _GIT else list(tokens)
    kinds, index = _split_globals(body)
    if index >= len(body) or body[index] is None:
        return kinds
    subcommand = body[index]
    assert subcommand is not None
    return kinds + _subcommand_kinds(subcommand, body[index + 1 :])


# ---------------------------------------------------------------------------
# Candidate extraction
# ---------------------------------------------------------------------------


def _token(node: ast.expr, consts: Mapping[str, str]) -> str | None:
    return None if isinstance(node, ast.Starred) else resolve_token(node, consts)


def _callee_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else None


def _runner_argv(call: ast.Call, consts: Mapping[str, str]) -> tuple[int, list[str | None]] | None:
    """``(lineno, tokens)`` of a git runner call's argv, or ``None`` when *call* is not a runner call."""
    if _callee_name(call) not in GIT_RUNNER_NAMES:
        return None
    for arg in call.args:
        if isinstance(arg, (ast.List, ast.Tuple)):
            return arg.lineno, [_token(elt, consts) for elt in arg.elts]
    return call.lineno, [_token(arg, consts) for arg in call.args[1:]]


def _candidates(tree: ast.Module, consts: Mapping[str, str]) -> Iterator[tuple[int, list[str | None]]]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            tokens = [_token(elt, consts) for elt in node.elts]
            if tokens and tokens[0] == _GIT:
                yield node.lineno, tokens
        elif isinstance(node, ast.Call):
            runner = _runner_argv(node, consts)
            if runner is not None:
                yield runner


def _render(tokens: Tokens) -> str:
    return "[" + ", ".join("<?>" if tok is None else repr(tok) for tok in tokens) + "]"


def _tree_hits(rel: str, tree: ast.Module) -> list[Hit]:
    consts = module_string_constants(tree)
    found: dict[tuple[int, str], str] = {}
    for lineno, tokens in _candidates(tree, consts):
        for kind in classify_argv(tokens):
            found.setdefault((lineno, kind), _render(tokens))
    return [Hit(rel, lineno, kind, argv) for (lineno, kind), argv in sorted(found.items())]


# ---------------------------------------------------------------------------
# Owner exemption (by symbol)
# ---------------------------------------------------------------------------


def _top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def exempt_functions(tree: ast.Module, symbols: Iterable[str]) -> frozenset[str]:
    """*symbols* plus every ``_``-private top-level function one of them calls directly by name.

    Raises :class:`OwnerSymbolMissing` when a symbol is not a top-level function of *tree*.
    """
    functions = _top_level_functions(tree)
    exempt: set[str] = set()
    for symbol in symbols:
        if symbol not in functions:
            raise OwnerSymbolMissing(f"canonical owner symbol {symbol!r} is not a top-level function; a rename must update CANONICAL_OWNERS")
        exempt.add(symbol)
        for node in ast.walk(functions[symbol]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                callee = node.func.id
                if callee.startswith("_") and callee in functions:
                    exempt.add(callee)
    return frozenset(exempt)


def _enclosing_top_level(tree: ast.Module, lineno: int) -> str | None:
    for name, node in _top_level_functions(tree).items():
        first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        if first <= lineno <= (node.end_lineno or node.lineno):
            return name
    return None


def _owner_for(rel: str) -> OwnerSymbol | None:
    return next((owner for owner in CANONICAL_OWNERS if owner.rel == rel), None)


# ---------------------------------------------------------------------------
# Public scans
# ---------------------------------------------------------------------------


def census_source(text: str, rel: str) -> list[Hit]:
    """Every hit in *text*; the owner exemption is never applied (planted cases, positive controls)."""
    return _tree_hits(rel, ast.parse(text, filename=rel))


def census_text(text: str, rel: str) -> list[Hit]:
    """Every hit in *text* (repo-relative *rel*), minus those an owner symbol of *rel* exempts."""
    tree = ast.parse(text, filename=rel)
    hits = _tree_hits(rel, tree)
    owner = _owner_for(rel)
    if owner is None:
        return hits
    exempt = exempt_functions(tree, owner.symbols)
    return [hit for hit in hits if _enclosing_top_level(tree, hit.lineno) not in exempt]


def exempt_hit_holders(text: str, rel: str) -> frozenset[str]:
    """The exempt module-private helpers of owner file *rel* that themselves hold a hit."""
    owner = _owner_for(rel)
    if owner is None:
        return frozenset()
    tree = ast.parse(text, filename=rel)
    helpers = exempt_functions(tree, owner.symbols) - set(owner.symbols)
    return frozenset(name for hit in _tree_hits(rel, tree) if (name := _enclosing_top_level(tree, hit.lineno)) in helpers)


def exempt_helper_leaks_text(text: str, rel: str, foreign_holders: Iterable[str] = ()) -> list[HelperLeak]:
    """References in *text* that reach an exempt, hit-holding helper other than through an owner symbol.

    In an owner file, any name reference to one of its own holders outside the owner's
    symbols is a leak. In every file, an attribute access or ``from ... import`` of a
    holder of another owner file (*foreign_holders*) is a leak.
    """
    tree = ast.parse(text, filename=rel)
    owner = _owner_for(rel)
    own = exempt_hit_holders(text, rel)
    foreign = frozenset(foreign_holders) - own
    leaks: list[HelperLeak] = []
    for node in ast.walk(tree):
        name: str | None = None
        if isinstance(node, ast.Name) and node.id in own:
            if owner is not None and _enclosing_top_level(tree, node.lineno) in owner.symbols:
                continue
            name = node.id
        elif isinstance(node, ast.Attribute) and node.attr in foreign:
            name = node.attr
        elif isinstance(node, ast.ImportFrom):
            name = next((alias.name for alias in node.names if alias.name in foreign), None)
        if name is not None:
            leaks.append(HelperLeak(rel, node.lineno, name, _enclosing_top_level(tree, node.lineno)))
    return leaks


def exempt_helper_leaks(paths: Iterable[Path]) -> list[HelperLeak]:
    """Leaks in every Python file in *paths*; holders come from the real owner files."""
    holders: set[str] = set()
    for owner in CANONICAL_OWNERS:
        owner_path = REPO_ROOT / owner.rel
        if owner_path.exists():
            holders |= exempt_hit_holders(owner_path.read_text(encoding="utf-8"), owner.rel)
    leaks: list[HelperLeak] = []
    for path in paths:
        if path.suffix == ".py":
            leaks.extend(exempt_helper_leaks_text(path.read_text(encoding="utf-8"), _rel(path), holders))
    return leaks


def _rel(path: Path) -> str:
    resolved = path.resolve()
    return resolved.relative_to(REPO_ROOT).as_posix() if resolved.is_relative_to(REPO_ROOT) else resolved.as_posix()


def census(paths: Iterable[Path]) -> list[Hit]:
    """Hits in every Python file in *paths*; only the two canonical owners' symbols are exempt."""
    hits: list[Hit] = []
    for path in paths:
        if path.suffix == ".py":
            hits.extend(census_text(path.read_text(encoding="utf-8"), _rel(path)))
    return hits


def src_files() -> list[Path]:
    """Every ``src/**/*.py`` file the gate scans."""
    return iter_py_files(SRC_ROOT)


def _verify_owners() -> None:
    """Import-time guard: two owners, and every named symbol exists in an owner file that exists.

    An owner file that does not exist exempts nothing (its sites are scanned
    wherever they moved); the gate's positive control requires both files.
    """
    if len(CANONICAL_OWNERS) != 2:
        raise OwnerSymbolMissing(f"CANONICAL_OWNERS must name exactly two owners (Decision 01M4B6FZNNSTP6DPN2AAEDEQHZ), got {len(CANONICAL_OWNERS)}")
    for owner in CANONICAL_OWNERS:
        path = REPO_ROOT / owner.rel
        if path.exists():
            exempt_functions(ast.parse(path.read_text(encoding="utf-8")), owner.symbols)


_verify_owners()
