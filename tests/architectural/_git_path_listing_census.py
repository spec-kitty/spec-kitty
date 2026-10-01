"""Census of git path listings and hand-written git output parsing outside ``kernel.git``.

Mission git-paths-are-data (#5392/#5400). ``src/kernel/git/`` is the one owner
of reading paths from git: callers ask an intent-named query and never build a
path-listing argv or split git's output themselves. This module finds the
places that still do. WP03–WP07 reviewers run it over their owned files and
require zero hits; ``test_git_path_listing_owner.py`` runs it over ``src/``
with an empty allowlist.

A **listing argv** is any string sequence (a list/tuple literal, or the
positional arguments of a call such as ``_git(root, "status", "--porcelain")``)
that asks git to print paths:

* ``status`` with ``--porcelain*``, ``-s``, ``--short`` or ``-z``;
* ``diff``/``show``/``log``/``diff-tree``/``diff-index``/``diff-files`` with a
  path-printing flag (``--name-only``, ``--name-status``, ``--numstat``,
  ``--raw``, ``--stat``, ``--summary``), and bare ``diff-tree``/``diff-index``/
  ``diff-files`` (they print raw records) unless ``--quiet``; ``--name-only``,
  ``--name-status`` and ``--numstat`` count on their own, because a helper may
  supply the subcommand;
* ``ls-files`` and ``ls-tree``;
* ``check-ignore`` unless ``-q``/``--quiet``.

``-z`` does not exempt a site: a ``-z`` listing parsed by hand outside the
owner is the same defect class one step removed. ``worktree list`` parsing is
out of scope (follow-up #5475).

A **parsing tell** is text handling that only makes sense on git display
output: ``" -> " in x``, ``split``/``rsplit``/``partition``/``rpartition`` on
``" -> "`` or NUL, and ``[3:]`` slicing inside a function that mentions
``porcelain``.

Accepted blind spots (none occurs in ``src/`` at the mission's close; the
census is a gate on the forms the codebase uses, not a proof): a command
written as one shell string (``"git status --porcelain"``); argv grown across
statements (``cmd.append("--porcelain")``); function-local string constants
(only module constants resolve); an arrow held in a constant; ``.find`` /
``.index`` on git output; and ``git grep -l`` / ``rev-list --objects``.
Argv for the GitHub CLI (``["gh", "pr", "diff", "--name-only"]``) is not git
and is skipped.
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
    parse,
    resolve_token,
)

__all__ = ["OWNER_ROOT", "Hit", "census", "census_source", "classify_argv", "src_files"]

OWNER_ROOT = SRC_ROOT / "kernel" / "git"

_DIFF_VERBS = frozenset({"diff", "show", "log", "diff-tree", "diff-index", "diff-files"})
_RAW_DIFF_VERBS = frozenset({"diff-tree", "diff-index", "diff-files"})
_PATH_FLAGS = frozenset({"--name-only", "--name-status", "--numstat", "--raw", "--stat", "--summary"})
# Flags no other tool spells this way: a call passing one names a git path listing
# even when a helper supplies the subcommand (``_run_git_diff(root, base, "--name-only")``).
_GIT_ONLY_PATH_FLAGS = frozenset({"--name-only", "--name-status", "--numstat"})
_STATUS_FLAGS = frozenset({"-s", "--short", "-z"})
_QUIET = frozenset({"-q", "--quiet"})
_ARROW = " -> "
_NUL_SEPARATORS: tuple[object, ...] = ("\0", b"\0")
_SPLITTERS = frozenset({"split", "rsplit", "partition", "rpartition"})
_PORCELAIN_PREFIX_LEN = 3


class Hit(NamedTuple):
    """One offending site: repo-relative path, line, and what kind of offence."""

    rel: str
    lineno: int
    kind: str


def classify_argv(tokens: Sequence[str | None]) -> str | None:
    """The listing kind *tokens* ask git for, or ``None`` when they list no paths."""
    words = {tok for tok in tokens if tok is not None}
    if "worktree" in words or "gh" in words:
        return None
    if "status" in words and (_STATUS_FLAGS & words or any(w.startswith("--porcelain") for w in words)):
        return "status"
    if words & {"ls-files", "ls-tree"}:
        return "ls"
    if "check-ignore" in words and not _QUIET & words:
        return "check-ignore"
    if words & _DIFF_VERBS and words & _PATH_FLAGS or words & _GIT_ONLY_PATH_FLAGS:
        return "diff"
    if words & _RAW_DIFF_VERBS and "--quiet" not in words:
        return "diff"
    return None


def _call_tokens(call: ast.Call, consts: Mapping[str, str]) -> list[str | None]:
    return [None if isinstance(arg, ast.Starred) else resolve_token(arg, consts) for arg in call.args]


def _argv_kinds(tree: ast.Module, consts: Mapping[str, str]) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            tokens = [None if isinstance(elt, ast.Starred) else resolve_token(elt, consts) for elt in node.elts]
        elif isinstance(node, ast.Call):
            tokens = _call_tokens(node, consts)
        else:
            continue
        kind = classify_argv(tokens)
        if kind is not None:
            yield node.lineno, kind


def _is_arrow_membership(node: ast.Compare) -> bool:
    return isinstance(node.left, ast.Constant) and node.left.value == _ARROW and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops)


def _is_output_split(node: ast.Call) -> bool:
    if not (isinstance(node.func, ast.Attribute) and node.func.attr in _SPLITTERS and node.args):
        return False
    first = node.args[0]
    return isinstance(first, ast.Constant) and (first.value == _ARROW or first.value in _NUL_SEPARATORS)


def _is_porcelain_prefix_slice(node: ast.Subscript) -> bool:
    piece = node.slice
    return (
        isinstance(piece, ast.Slice)
        and isinstance(piece.lower, ast.Constant)
        and piece.lower.value == _PORCELAIN_PREFIX_LEN
        and piece.upper is None
        and piece.step is None
    )


def _mentions_porcelain(function: ast.AST) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and "porcelain" in node.id.lower():
            return True
        if isinstance(node, ast.arg) and "porcelain" in node.arg.lower():
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "porcelain" in node.value:
            return True
    return False


def _tells(tree: ast.Module) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and _is_arrow_membership(node):
            yield node.lineno, "arrow"
        elif isinstance(node, ast.Call) and _is_output_split(node):
            yield node.lineno, "split"
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and _mentions_porcelain(function):
            for node in ast.walk(function):
                if isinstance(node, ast.Subscript) and _is_porcelain_prefix_slice(node):
                    yield node.lineno, "slice"


def census_source(rel: str, tree: ast.Module) -> list[Hit]:
    """Every hit in one parsed module (deduplicated, line order)."""
    consts = module_string_constants(tree)
    found = {(line, kind) for line, kind in _argv_kinds(tree, consts)}
    found |= set(_tells(tree))
    return [Hit(rel, line, kind) for line, kind in sorted(found)]


def _is_owner(path: Path) -> bool:
    return OWNER_ROOT in path.resolve().parents


def census(paths: Iterable[Path]) -> list[Hit]:
    """Hits in every Python file in *paths*; files under ``src/kernel/git/`` are the owner and skipped."""
    hits: list[Hit] = []
    for path in paths:
        if path.suffix != ".py" or _is_owner(path):
            continue
        resolved = path.resolve()
        rel = resolved.relative_to(REPO_ROOT).as_posix() if REPO_ROOT in resolved.parents else resolved.as_posix()
        hits.extend(census_source(rel, parse(path)))
    return hits


def src_files() -> list[Path]:
    """Every source file the gate scans."""
    return iter_py_files(SRC_ROOT)
