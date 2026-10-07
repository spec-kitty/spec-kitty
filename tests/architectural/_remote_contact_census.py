"""Census of remote-contacting git commands outside ``kernel.git`` (FR-013, C-004, SC-005).

Mission second-clone-origin-reconciliation. ``src/kernel/git/remote.py`` is the
one owner of git commands that contact a remote: callers ask an intent-named
function (``remote_heads``, ``fetch_branches``, ``clone_repository`` ...) and
never build the argv. This module finds the places that still do.

A **contact argv** is any string sequence (a list/tuple literal, or the
positional arguments of a call such as ``_run([...])``, ``_git(root, "fetch")``
or ``run_git(cwd, "fetch", ...)``) whose git subcommand is:

* ``fetch``, ``ls-remote``, ``pull`` or ``clone``;
* ``remote show`` without ``-n`` (``remote show -n`` reads local config only);
* ``remote update``, ``remote prune`` and ``remote set-head`` with ``-a``/``--auto``
  (each asks the remote; ``set-head <remote> <branch>`` and ``-d`` do not).

The subcommand is the first resolved token once a leading ``"git"`` and any
``-C <dir>`` / ``-c <k=v>`` global option are skipped, so wrapper calls that
omit ``"git"`` and carry unresolved arguments (a ``cwd`` expression) before the
subcommand are caught. ``push`` is out of scope (FR-015).

Accepted blind spots: a command written as one shell string (``"git fetch origin"``
with ``shell=True``, or ``"git fetch origin".split()``); ``remote add -f``; and
git reached through a library rather than an argv. None occurs in ``src/``. Module string
constants resolve; function-local constants and argv grown across statements do
not (accepted blind spots, same as the sibling path-listing census). A wrapper
call is recognized by its first resolved argument, so ``print("fetch")`` would
be a (fail-closed) false positive; none exists in ``src/``.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path

from tests.architectural._destructive_op_census import REPO_ROOT, SRC_ROOT, iter_py_files, module_string_constants, parse, resolve_token
from tests.architectural._git_path_listing_census import OWNER_ROOT, Hit, _call_tokens, src_files

__all__ = ["OWNER_ROOT", "Hit", "census", "census_source", "classify_argv", "src_files", "REPO_ROOT", "SRC_ROOT", "iter_py_files", "parse"]

_CONTACT_VERBS = frozenset({"fetch", "ls-remote", "pull", "clone"})
_OPTIONS_WITH_VALUE = frozenset({"-C", "-c"})
_LOCAL_ONLY = frozenset({"-n", "--no-query"})
_REMOTE_CONTACT_SUBCOMMANDS = frozenset({"update", "prune"})
_AUTO_FLAGS = frozenset({"-a", "--auto"})
# Registering a CLI command or argparse subcommand named ``fetch``/``pull`` runs no git.
# Only the registration SHAPE is skipped: the call's single positional is the command
# name (``app.command("fetch")``). A call carrying more positionals
# (``self.callback(root, "fetch", "origin")``) is argv for a wrapper and is scanned.
_REGISTRATION_CALLS = frozenset({"command", "add_parser", "add_argument", "add_typer", "callback"})


def _subcommand_tail(tokens: Sequence[str | None]) -> list[str]:
    """Resolved tokens from the git subcommand on, after dropping ``git`` and ``-C``/``-c`` options."""
    out: list[str] = []
    skip_next = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if tok is None:
            continue
        if not out and tok == "git":
            continue
        if not out and tok in _OPTIONS_WITH_VALUE:
            skip_next = True
            continue
        out.append(tok)
    return out


def classify_argv(tokens: Sequence[str | None]) -> str | None:
    """The remote-contact kind *tokens* run, or ``None`` when they contact no remote."""
    tail = _subcommand_tail(tokens)
    if not tail:
        return None
    verb = tail[0]
    if verb in _CONTACT_VERBS:
        return verb
    if verb == "remote":
        return _remote_subcommand_kind(tail[1:])
    return None


def _remote_subcommand_kind(rest: Sequence[str]) -> str | None:
    """Contact kind of ``git remote <rest>``; ``None`` for the local-only forms."""
    if not rest:
        return None
    sub, flags = rest[0], set(rest[1:])
    if sub == "show" and not _LOCAL_ONLY & flags:
        return "remote-show"
    if sub in _REMOTE_CONTACT_SUBCOMMANDS:
        return f"remote-{sub}"
    if sub == "set-head" and _AUTO_FLAGS & flags:
        return "remote-set-head"
    return None


def _is_registration(call: ast.Call) -> bool:
    """``app.command("fetch")`` shape: a registration method whose only positional is the name."""
    return isinstance(call.func, ast.Attribute) and call.func.attr in _REGISTRATION_CALLS and len(call.args) == 1


def _argv_kinds(tree: ast.Module, consts: Mapping[str, str]) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            tokens = [None if isinstance(elt, ast.Starred) else resolve_token(elt, consts) for elt in node.elts]
        elif isinstance(node, ast.Call):
            if _is_registration(node):
                continue
            tokens = _call_tokens(node, consts)
        else:
            continue
        kind = classify_argv(tokens)
        if kind is not None:
            yield node.lineno, kind


def census_source(rel: str, tree: ast.Module) -> list[Hit]:
    """Every hit in one parsed module (deduplicated, line order)."""
    consts = module_string_constants(tree)
    return [Hit(rel, line, kind) for line, kind in sorted(set(_argv_kinds(tree, consts)))]


def _is_owner(path: Path) -> bool:
    return OWNER_ROOT in path.resolve().parents


def census(paths: Iterable[Path], *, skip_owner: bool = True) -> list[Hit]:
    """Hits in every Python file in *paths*; ``src/kernel/git/`` is the owner and skipped unless *skip_owner* is off."""
    hits: list[Hit] = []
    for path in paths:
        if path.suffix != ".py" or (skip_owner and _is_owner(path)):
            continue
        resolved = path.resolve()
        rel = resolved.relative_to(REPO_ROOT).as_posix() if REPO_ROOT in resolved.parents else resolved.as_posix()
        hits.extend(census_source(rel, parse(path)))
    return hits
