"""The one ceiling-aware ancestor walk (#7056).

The repo/project-root walks of the stack — ``specify_cli.core.paths``'s four walks,
``task_utils.support.find_repo_root``, the checkout-identity, mission-metadata,
legacy-charter, coordination, gitignore, env-file, ledger-posture, middleware,
charter-lint, next-planner and catalog-diagnosis walks — ask the same question: "walk up
from this directory until a marker matches". Before this module each asked it with its
own ``[start, *start.parents]`` loop, and only three of them honoured
``GIT_CEILING_DIRECTORIES`` (#7022). This is the one walk, and the one reading of that
variable.

``cli.commands.session_start._find_project_root`` joined the walk and retired its
test-only ``stop=`` (#7122). Not yet on it: five walks written as a
``while``/``range(N)`` loop over ``.parent`` (#7269). A gate that keeps hand-rolled root
walks out is still owed by #7056;
it lands separately, once it can start without an exemption list (#7304, ADR
``2026-09-30-1``).

It lives at the ``kernel`` floor because ``charter`` and ``runtime`` need it and may not
import ``specify_cli`` (``tests/architectural/test_layer_rules.py``); ``kernel/paths.py``
reads its environment variable at the same floor for the same reason. It imports only
the standard library and ``kernel.resolution`` (itself stdlib-only) —
``specify_cli.bootstrap.env_file`` calls it during a bare
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
each of those choices. For negative Git-context evidence, :func:`git_ceiling_dirs` leaves
post-empty entries unresolved on request (``resolve_after_empty=False``). It also drops an
entry whose spelling ``Path`` rewrites, such as a trailing ``/.`` or doubled separator,
rather than turn it into a boundary Git did not match. This platform-local spelling check
is conservative, not a portable Git parser: it can also drop entries Git would honour.
Removing a stop only broadens this walk's search and may refuse a legitimate absence;
it cannot invent one. Every other caller keeps the resolved reading.

Where the two readings disagree, the walk normally sees *more* than git: it examines the
ceiling directory, which git does not. One disagreement runs the other way. git ignores a
ceiling entry that *is* the directory the search starts in -- such an entry bounds only a
search that starts below it -- while this walk stops at the start. A caller cannot infer
absence from a walk that sees less than git did, so negative Git evidence has to drop that
start-equal entry before it concludes anything, decline lossy post-empty spellings in the
kernel parser, and treat a start it cannot resolve as unknown rather than absent; the
Mission identity reader (``mission_metadata``) does this
when Git did not establish a worktree context. Everywhere the walk instead sees more
than git, that means refusing, never minting an identity over a copy git
holds (#6673 NFR-002). This module's default readings are unchanged for every other
caller, and a future change to match git exactly must be reviewed against that.

A path that cannot be resolved (an unreadable component, or a symbolic-link loop, which
``kernel.resolution.resolve_rejecting_loops`` reports as ``OSError`` on every supported
interpreter) never escapes as an exception: a ceiling
entry is kept as written, and the start is walked as its absolute, unresolved path, which
is what the hand-rolled walks did. Such a sequence is lexical while the ceilings are
resolved, so a walk that fell back this way also compares each candidate's own real
identity against the ceilings: a ceiling reached through a symbolic-link alias still ends
the walk instead of carrying it above its own boundary. The extra comparison does not
match a candidate that cannot itself be resolved; it only adds stops to the lexical walk.

The variable is read on every call. The test harness sets it at runtime and tests
monkeypatch it per case, so a cached read would make a walk's verdict depend on which
test ran first.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Final

from kernel.resolution import resolve_rejecting_loops

__all__ = [
    "find_ancestor",
    "git_ceiling_dirs",
    "iter_ancestors",
]

#: The variable git and the migrated parent-enumerating root walks read for discovery ceilings.
GIT_CEILING_ENV: Final[str] = "GIT_CEILING_DIRECTORIES"


def git_ceiling_dirs(
    environ: Mapping[str, str] | None = None,
    *,
    resolve_after_empty: bool = True,
) -> frozenset[Path]:
    """The absolute ``GIT_CEILING_DIRECTORIES`` entries, read per call.

    The single reading of the discovery ceiling. ``specify_cli.core.paths.
    git_ceiling_dirs`` delegates here and stays importable under its #7022 name.

    Args:
        environ: The environment to read. Defaults to :data:`os.environ`; pass one
            explicitly only in tests or when a caller owns the child environment.
        resolve_after_empty: Whether absolute entries listed *after* an empty entry are
            resolved. Defaults to ``True``, the general root-walk reading: each absolute
            entry compares physically with the resolved walk. ``False`` is the conservative
            negative-Git-evidence reading: entries after an empty entry stay unresolved,
            and those whose spelling ``Path`` rewrites are dropped. Removing such stops can
            refuse an absence, but cannot claim one from a boundary Git never honoured.

    Returns:
        The absolute entries. Empty and relative entries are dropped.
    """
    source = os.environ if environ is None else environ
    resolved: set[Path] = set()
    resolve = True
    for part in source.get(GIT_CEILING_ENV, "").split(os.pathsep):
        if not part:
            resolve = resolve and resolve_after_empty
            continue
        path = Path(part)
        if not path.is_absolute():
            continue
        if resolve:
            resolved.add(_resolved(path))
        elif str(path) == part:
            resolved.add(path)
    return frozenset(resolved)


def _resolved(path: Path) -> Path:
    """*path* resolved, or its absolute form when it cannot be (see the module docstring).

    :func:`kernel.resolution.resolve_rejecting_loops` turns a symlink loop into ``OSError``
    on every supported interpreter (#3189), so one ``except`` covers loops and unreadable
    components alike.
    """
    try:
        return resolve_rejecting_loops(path)
    except OSError:
        return path.absolute()


def _is_a_ceiling_alias(candidate: Path, ceilings: frozenset[Path]) -> bool:
    """Whether *candidate*'s real identity is one of *ceilings*.

    Only consulted for a walk whose start could not be resolved: that candidate sequence is
    lexical while the ceilings are resolved, so a ceiling reached through a symbolic-link
    alias would never compare equal. An unresolvable candidate adds no stop; the original
    lexical comparison still applies.
    """
    if not ceilings:
        return False
    try:
        return resolve_rejecting_loops(candidate) in ceilings
    except OSError:
        return False


def iter_ancestors(
    start: Path | str,
    *,
    ceilings: frozenset[Path] | None = None,
) -> Iterator[Path]:
    """Yield ``start`` and each of its parents, never continuing above a ceiling.

    The walk yields the resolved start, then each parent in order — or the absolute,
    unresolved start when it cannot be resolved (see the module docstring). When a
    candidate is a ceiling entry it is yielded and the iteration ends — see the module
    docstring for why the ceiling directory is examined. Without a ceiling ancestor the
    walk ends at the filesystem root.

    Args:
        start: The directory to start from; resolved once, at the start of the walk.
        ceilings: The ceiling set. Defaults to :func:`git_ceiling_dirs`'s reading of the
            current environment; pass one only to reuse a single reading across several
            walks.

    Yields:
        Each candidate directory, nearest first.
    """
    raw_start = Path(start)
    try:
        resolved_start = resolve_rejecting_loops(raw_start)
        fell_back = False
    except OSError:
        resolved_start = raw_start.absolute()
        fell_back = True
    boundary = git_ceiling_dirs() if ceilings is None else ceilings

    for candidate in (resolved_start, *resolved_start.parents):
        yield candidate
        if candidate in boundary or (fell_back and _is_a_ceiling_alias(candidate, boundary)):
            return


def find_ancestor(
    start: Path | str,
    predicate: Callable[[Path], bool],
    *,
    ceilings: frozenset[Path] | None = None,
) -> Path | None:
    """Return the nearest ancestor of ``start`` (inclusive) that ``predicate`` accepts.

    The predicate is the caller's marker test — ``.git`` with a ``HEAD``, a worktree
    pointer, a ``.kittify`` directory, a ``pyproject.toml``. It receives each candidate as
    the walk produced it (resolved, or the start's lexical path when the start could not be
    resolved) and is evaluated at most once per candidate, in nearest-first order.

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
