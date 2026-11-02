"""The one ceiling-aware ancestor walk (#7056).

Every repo/project-root walk in the stack — ``specify_cli.core.paths``'s four walks,
``task_utils.support.find_repo_root``, the checkout-identity, mission-metadata,
legacy-charter, coordination, gitignore, env-file, ledger-posture, middleware,
charter-lint, next-planner and catalog-diagnosis walks — asks the same question: "walk up
from this directory until a marker matches". Before this module each asked it with its
own ``[start, *start.parents]`` loop, and only three of them honoured
``GIT_CEILING_DIRECTORIES`` (#7022). This is the one walk, and the one reading of that
variable.

It lives at the ``kernel`` floor because ``charter`` and ``runtime`` need it and may not
import ``specify_cli`` (``tests/architectural/test_layer_rules.py``); ``kernel/paths.py``
reads its environment variable at the same floor for the same reason. It imports only
the standard library — ``specify_cli.bootstrap.env_file`` calls it during a bare
``import specify_cli`` and that import must stay cheap and silent.

The module holds no decision logic. A caller supplies its own marker predicate; this
module only decides *where the walk may go*.

Ceiling semantics (issue #7056 item 2, kept deliberately)
---------------------------------------------------------

A listed ceiling directory is **examined**, and the walk stops after it. This is one step
looser than git, which does not examine a ceiling directory unless the search starts
there; it is the reading #7022 shipped, and matching git exactly would change
``resolve_canonical_root``'s observable behaviour for every consumer. Relative entries
are ignored (as git ignores them) and every absolute entry is resolved (git leaves
entries after an empty entry unresolved). ``tests/kernel/test_ancestor_walk.py`` pins
each of those choices.

The variable is read on every call. The test harness sets it at runtime and tests
monkeypatch it per case, so a cached read would make a walk's verdict depend on which
test ran first.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Final

__all__ = [
    "GIT_CEILING_ENV",
    "find_ancestor",
    "git_ceiling_dirs",
    "iter_ancestors",
]

#: The variable git (and every root walk in this stack) reads for discovery ceilings.
GIT_CEILING_ENV: Final[str] = "GIT_CEILING_DIRECTORIES"


def git_ceiling_dirs(environ: Mapping[str, str] | None = None) -> frozenset[Path]:
    """The resolved absolute ``GIT_CEILING_DIRECTORIES`` entries, read per call.

    The single reading of the discovery ceiling. ``specify_cli.core.paths.
    git_ceiling_dirs`` delegates here and stays importable under its #7022 name.

    Args:
        environ: The environment to read. Defaults to :data:`os.environ`; pass one
            explicitly only in tests or when a caller owns the child environment.

    Returns:
        The resolved absolute entries. Empty and relative entries are dropped.
    """
    source = os.environ if environ is None else environ
    return frozenset(
        Path(part).resolve() for part in source.get(GIT_CEILING_ENV, "").split(os.pathsep) if part and Path(part).is_absolute()
    )


def iter_ancestors(
    start: Path | str,
    *,
    ceilings: frozenset[Path] | None = None,
) -> Iterator[Path]:
    """Yield ``start`` and each of its parents, never continuing above a ceiling.

    The walk yields the resolved start, then each parent in order. When a candidate is a
    ceiling entry it is yielded and the iteration ends — see the module docstring for why
    the ceiling directory is examined. Without a ceiling ancestor the walk ends at the
    filesystem root.

    Args:
        start: The directory to start from; resolved once, at the start of the walk.
        ceilings: The ceiling set. Defaults to :func:`git_ceiling_dirs`'s reading of the
            current environment; pass one only to reuse a single reading across several
            walks.

    Yields:
        Each candidate directory, nearest first.
    """
    resolved_start = Path(start).resolve()
    boundary = git_ceiling_dirs() if ceilings is None else ceilings

    for candidate in (resolved_start, *resolved_start.parents):
        yield candidate
        if candidate in boundary:
            return


def find_ancestor(
    start: Path | str,
    predicate: Callable[[Path], bool],
    *,
    ceilings: frozenset[Path] | None = None,
) -> Path | None:
    """Return the nearest ancestor of ``start`` (inclusive) that ``predicate`` accepts.

    The predicate is the caller's marker test — ``.git`` with a ``HEAD``, a worktree
    pointer, a ``.kittify`` directory, a ``pyproject.toml``. It receives resolved
    candidates and is evaluated at most once per candidate, in nearest-first order.

    Args:
        start: The directory to start from.
        predicate: Marker test applied to each candidate; the first acceptance wins.
        ceilings: The ceiling set. Defaults to :func:`git_ceiling_dirs`'s reading.

    Returns:
        The accepted candidate, or ``None`` when the walk ends without one.
    """
    for candidate in iter_ancestors(start, ceilings=ceilings):
        if predicate(candidate):
            return candidate
    return None
