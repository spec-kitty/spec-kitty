"""Run-scoped cache for repeated read-only git queries (#7689).

One ``spec-kitty consolidate`` run used to spawn about 670 ``git`` processes,
many of them the same read asked again and again (``worktree list``, the
``origin/HEAD`` symbolic ref, the checked-out branch, a branch's tip, the remote
default branch). On a Windows runner a process spawn costs roughly a tenth of a
second, so the repeats alone pushed the run past the acceptance suite's
two-minute ceiling.

The cache answers a repeated read without a process, and only when the answer
cannot have changed:

* **Opt-in scope.** Nothing is cached outside :func:`git_read_cache_scope`.
  A command opens one scope for its run; every other command keeps spawning git
  exactly as before.
* **Declared dependencies, validated on every lookup.** Each cached read names
  the git metadata its answer is a function of (:class:`Depends`): one ref, the
  checkout's ``HEAD``, the repository config, or all of it. An entry stores a
  *fingerprint* of those files, taken just before the read ran. A lookup
  recomputes the fingerprint from the files themselves (no process) and reuses
  the entry only when it is byte-for-byte identical. Any write that could change
  the answer (a ref update, branch create or delete, checkout, worktree add,
  remove, lock or prune, a config write, ``pack-refs``) rewrites one of those
  files, so it invalidates the entry whichever code path, or outside process,
  performed it. File *content* is compared, never timestamps, so a coarse
  filesystem clock cannot hide a write.
* **Stored only when stable.** The fingerprint is taken again after the read;
  when it differs (something wrote while git ran) the answer is returned but not
  stored, so a stored answer always belongs to the state it is filed under.
* **Fails open to git.** When the repository cannot be located from the
  filesystem, or a ``GIT_*`` variable redirects git to other metadata, the read
  simply runs, uncached. A read that raises is never cached.

Only reads whose answer is a function of the declared metadata may be routed
through :func:`cached_git_read`. Working-tree and index reads (``status``,
``diff``, ``add``) are not, and must never be.

Reads keyed only on full object ids (:func:`cached_object_read`, #7848) need
no ref at all: an object id names immutable content. What they do depend on is
what rewrites the commit graph git presents for those ids (replace refs, the
``shallow`` file, ``info/grafts``), and that is their fingerprint.

The one deliberate exception, documented at its call site, is the remote's
advertised default branch (``git remote show``). It is remote state, which no
local mutation of the run can change; within one run it is read once per local
state of the inputs that select it instead of contacting the remote every time.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
from collections.abc import Callable, Hashable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar, cast

__all__ = [
    "Depends",
    "cached_git_read",
    "cached_object_read",
    "cached_ref_read",
    "git_read_cache_active",
    "git_read_cache_scope",
    "is_object_id",
]

T = TypeVar("T")

#: Environment variables that point git at metadata other than the one found by
#: walking up from the working directory. With any of them set, the filesystem
#: fingerprint may not describe what git reads, so the cache steps aside.
#: Config injected through ``GIT_CONFIG_COUNT`` / ``GIT_CONFIG_PARAMETERS`` is
#: not listed: it is fixed for the life of the process, so it cannot make two
#: reads under one fingerprint differ.
_REDIRECTING_ENV = (
    "GIT_DIR",
    "GIT_COMMON_DIR",
    "GIT_WORK_TREE",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_CONFIG",
)

#: Every ref lookup may be answered by a loose file, ``packed-refs`` or the
#: reftable stack, so a ref dependency always covers the last two.
_REF_STORES = ("packed-refs", "reftable/tables.list")

#: Symbolic refs are followed at most this deep (git's own limit is 5).
_MAX_SYMREF_DEPTH = 5

#: Files directly under the common git directory that the whole-metadata
#: fingerprint covers.
_COMMON_FILES = ("HEAD", "packed-refs", "config", "config.worktree", "shallow", "reftable/tables.list")

#: Files that rewrite the commit graph git presents for an object id (plus the
#: ``refs/replace/`` tree): ``packed-refs`` and the reftable stack can hold
#: replace refs, and ``config`` carries ``core.useReplaceRefs``. A reftable
#: repository never reaches a fingerprint (:func:`_uses_reftable`); its stack
#: file is listed as a backstop.
_HISTORY_FILES = ("shallow", "info/grafts", "packed-refs", "reftable/tables.list", "config")

#: Environment variables that change which commit graph git presents for an
#: object id, through state the history fingerprint does not read. With any of
#: them set, an object read steps aside.
_HISTORY_ENV = ("GIT_REPLACE_REF_BASE", "GIT_NO_REPLACE_OBJECTS", "GIT_GRAFT_FILE", "GIT_SHALLOW_FILE")

#: A full SHA-1 or SHA-256 object id, as git prints it.
_OBJECT_ID_RE = re.compile(r"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")

#: Files under each ``worktrees/<name>/`` administrative directory.
_WORKTREE_FILES = ("HEAD", "gitdir", "locked", "config.worktree", "commondir")


@dataclass(frozen=True)
class Depends:
    """The git metadata a cached read's answer is a function of.

    ``refs`` are full ref names (``refs/heads/main``); each covers its loose
    file (following a symbolic ref), ``packed-refs`` and the reftable stack.
    ``head`` covers the ``HEAD`` of the checkout the read runs in. ``config``
    covers the repository config files. ``everything`` covers every ref, every
    ``HEAD``, the config and the linked-worktree administrative files (what
    ``git worktree list`` reads). ``history`` covers what rewrites the commit
    graph git presents for an object id: replace refs, ``shallow`` and
    ``info/grafts``.
    """

    refs: tuple[str, ...] = ()
    head: bool = False
    config: bool = False
    everything: bool = False
    history: bool = False


#: The whole-metadata dependency.
EVERYTHING = Depends(everything=True)

#: The dependency of a read keyed only on object ids (reached only through :func:`cached_object_read`).
_HISTORY = Depends(history=True)


@dataclass
class _GitReadCacheStats:
    """Lookup counters of the active scope (for tests and diagnostics)."""

    hits: int = 0
    misses: int = 0
    bypassed: int = 0


@dataclass
class _Scope:
    entries: dict[Hashable, tuple[bytes, object]] = field(default_factory=dict)
    stats: _GitReadCacheStats = field(default_factory=_GitReadCacheStats)
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass(frozen=True)
class _Repo:
    git_dir: Path  # the checkout's own git directory (``HEAD`` lives here)
    common_dir: Path  # shared refs, config and ``worktrees/``


_ACTIVE: ContextVar[_Scope | None] = ContextVar("kernel_git_read_cache", default=None)


@contextmanager
def git_read_cache_scope() -> Iterator[_GitReadCacheStats]:
    """Enable the cache for the enclosed block; a nested scope reuses the outer one."""
    outer = _ACTIVE.get()
    if outer is not None:
        yield outer.stats
        return
    scope = _Scope()
    token = _ACTIVE.set(scope)
    try:
        yield scope.stats
    finally:
        _ACTIVE.reset(token)


def git_read_cache_active() -> bool:
    """Whether a :func:`git_read_cache_scope` is open (a caller may then batch reads it will repeat)."""
    return _ACTIVE.get() is not None


def is_object_id(text: str) -> bool:
    """A full, lowercase SHA-1 or SHA-256 object id (never a ref name, an abbreviation or ``^id``).

    Judged by shape alone: in a SHA-256 repository git would read a 40-hex string as an
    abbreviation. Callers pass ids git itself printed, which are full ids of the repository's
    own object format.
    """
    return _OBJECT_ID_RE.match(text) is not None


def cached_git_read(
    cwd: Path,
    key: Hashable,
    compute: Callable[[], T],
    *,
    depends: Depends = EVERYTHING,
    env: Mapping[str, str] | None = None,
    store_if: Callable[[T], bool] | None = None,
) -> T:
    """Return ``compute()``, reusing an earlier answer while *depends* is unchanged.

    *store_if*, when given, decides whether an answer may be reused: an answer it
    rejects is returned but not stored, so the next call runs the read again (for
    example a lookup that failed for a transient reason).

    *cwd* is where the read runs (it locates the repository); *key* names the
    query and must include every argument that shapes its answer. *env* is the
    environment the read passes to git, when it passes one: a redirecting
    ``GIT_*`` variable there bypasses the cache like one in the process
    environment. Outside a scope, or when the repository cannot be located,
    this is exactly ``compute()``.
    """
    scope = _ACTIVE.get()
    if scope is None:
        return compute()
    repo = None if _redirects(env) else _locate(cwd)
    if repo is None:
        with scope.lock:
            scope.stats.bypassed += 1
        return compute()
    scoped_key: Hashable = (str(repo.common_dir), str(repo.git_dir) if depends.head else "", key)
    before = _fingerprint(repo, depends)
    with scope.lock:
        cached = scope.entries.get(scoped_key)
        if cached is not None and cached[0] == before:
            scope.stats.hits += 1
            return cast(T, cached[1])
        scope.stats.misses += 1
    value = compute()
    if store_if is not None and not store_if(value):
        return value
    if _fingerprint(repo, depends) == before:
        with scope.lock:
            scope.entries[scoped_key] = (before, value)
    return value


def cached_ref_read(
    cwd: Path,
    ref: str,
    key: Hashable,
    compute: Callable[[], T],
    *,
    env: Mapping[str, str] | None = None,
    store_if: Callable[[T], bool] | None = None,
) -> T:
    """Cache a read whose answer is a function of one full ref name (``refs/...``) only.

    Peeling (``^{commit}``) is allowed in the read: objects are content-addressed
    and immutable, so only the ref's own value can change the answer. A *ref*
    that is not a full ``refs/`` name falls back to the whole-metadata
    dependency, since git may resolve a short name against several refs.
    *store_if* is as for :func:`cached_git_read`.
    """
    depends = Depends(refs=(ref,)) if ref.startswith("refs/") else EVERYTHING
    return cached_git_read(cwd, ("ref", ref, key), compute, depends=depends, env=env, store_if=store_if)


def cached_object_read(
    cwd: Path,
    revs: tuple[str, ...],
    key: Hashable,
    compute: Callable[[], T],
    *,
    env: Mapping[str, str] | None = None,
    store_if: Callable[[T], bool] | None = None,
) -> T:
    """Cache a read whose answer is a function of the objects *revs* name only (#7848).

    Every entry of *revs* must be a full object id (:func:`is_object_id`); otherwise the
    read simply runs, uncached, since a ref name or an abbreviation can name another
    object later. *key* must include every other argument that shapes the answer. The
    entry stays valid until something rewrites the commit graph (:data:`HISTORY`).
    """
    if not revs or not all(is_object_id(rev) for rev in revs) or _env_has(env, _HISTORY_ENV):
        if (scope := _ACTIVE.get()) is not None:
            with scope.lock:
                scope.stats.bypassed += 1
        return compute()
    return cached_git_read(cwd, ("objects", revs, key), compute, depends=_HISTORY, env=env, store_if=store_if)


# ---------------------------------------------------------------------------
# Locating the repository (filesystem only)
# ---------------------------------------------------------------------------


def _env_has(env: Mapping[str, str] | None, names: tuple[str, ...]) -> bool:
    return any((env or {}).get(name) for name in names) or any(os.environ.get(name) for name in names)


def _redirects(env: Mapping[str, str] | None) -> bool:
    return _env_has(env, _REDIRECTING_ENV)


def _locate(cwd: Path) -> _Repo | None:
    """Find the checkout's git directory and the common directory, or ``None``."""
    if _redirects(None):
        return None
    try:
        start = Path(os.path.abspath(cwd))
    except (OSError, ValueError):
        return None
    for directory in (start, *start.parents):
        dotgit = directory / ".git"
        try:
            if dotgit.is_dir():
                return _repo_from_git_dir(dotgit)
            if dotgit.is_file():
                text = dotgit.read_text(encoding="utf-8").strip()
                if not text.startswith("gitdir:"):
                    return None
                git_dir = Path(text[len("gitdir:") :].strip())
                if not git_dir.is_absolute():
                    git_dir = directory / git_dir
                return _repo_from_git_dir(git_dir)
        except (OSError, UnicodeDecodeError):
            return None
    return None


def _repo_from_git_dir(git_dir: Path) -> _Repo | None:
    try:
        git_dir = Path(os.path.realpath(git_dir))
        commondir = git_dir / "commondir"
        if commondir.is_file():
            target = Path(commondir.read_text(encoding="utf-8").strip())
            common = Path(os.path.realpath(target if target.is_absolute() else git_dir / target))
        else:
            common = git_dir
    except (OSError, UnicodeDecodeError):
        return None
    if not (git_dir / "HEAD").is_file() or not (common / "HEAD").is_file():
        return None
    if _uses_reftable(common):
        return None
    return _Repo(git_dir=git_dir, common_dir=common)


#: ``extensions.refStorage = reftable`` in a git config file (section headers and keys are case-insensitive).
_REFTABLE_RE = re.compile(r"^\s*refstorage\s*=\s*reftable\s*$", re.IGNORECASE | re.MULTILINE)


def _uses_reftable(common_dir: Path) -> bool:
    """Whether the repository stores refs in reftable (#7689 landing fold).

    The fingerprint models the files backend (loose refs, ``packed-refs``). Under reftable a
    linked worktree keeps its ``HEAD`` in ``worktrees/<id>/reftable/``, which the fingerprint
    does not read, so a checkout there would go unseen. Until reftable is modelled, such a
    repository runs every read uncached. An unreadable config is treated the same way.
    """
    try:
        text = (common_dir / "config").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    return _REFTABLE_RE.search(text) is not None


# ---------------------------------------------------------------------------
# Fingerprints (file content, never timestamps)
# ---------------------------------------------------------------------------


def _fingerprint(repo: _Repo, depends: Depends) -> bytes:
    digest = hashlib.blake2b(digest_size=32)
    if depends.everything:
        _feed_everything(digest, repo.common_dir)
        return digest.digest()
    for name in _REF_STORES if (depends.refs or depends.head) else ():
        _feed_file(digest, repo.common_dir, name)
    if depends.history:
        for name in _HISTORY_FILES:
            _feed_file(digest, repo.common_dir, name)
        _feed_tree(digest, repo.common_dir, "refs/replace")
    for ref in depends.refs:
        _feed_ref(digest, repo, ref, _MAX_SYMREF_DEPTH)
    if depends.head:
        _feed_ref(digest, repo, "HEAD", _MAX_SYMREF_DEPTH)
    if depends.config:
        _feed_file(digest, repo.common_dir, "config")
        _feed_file(digest, repo.git_dir, "config.worktree")
    return digest.digest()


def _ref_home(repo: _Repo, ref: str) -> Path:
    """Where git keeps *ref*: per-checkout pseudo refs in the checkout, the rest shared."""
    if ref == "HEAD" or ref.startswith(("refs/bisect/", "refs/worktree/", "refs/rewritten/")):
        return repo.git_dir
    return repo.common_dir


def _feed_ref(digest: hashlib.blake2b, repo: _Repo, ref: str, depth: int) -> None:
    data = _feed_file(digest, _ref_home(repo, ref), ref)
    if data is None or depth <= 0:
        return
    text = data.decode("utf-8", "replace").strip()
    if text.startswith("ref:"):
        target = text[len("ref:") :].strip()
        _feed_ref(digest, repo, target, depth - 1)


def _feed_everything(digest: hashlib.blake2b, common_dir: Path) -> None:
    for name in _COMMON_FILES:
        _feed_file(digest, common_dir, name)
    _feed_tree(digest, common_dir, "refs")
    try:
        names = sorted(entry.name for entry in os.scandir(common_dir / "worktrees") if entry.is_dir(follow_symlinks=False))
    except OSError:
        names = []
    for name in names:
        admin = f"worktrees/{name}"
        digest.update(b"\0W" + name.encode("utf-8", "surrogateescape"))
        for file_name in _WORKTREE_FILES:
            _feed_file(digest, common_dir, f"{admin}/{file_name}")
        _feed_tree(digest, common_dir, f"{admin}/refs")
        _feed_checkout_presence(digest, common_dir / admin / "gitdir")


def _feed_file(digest: hashlib.blake2b, root: Path, relative: str) -> bytes | None:
    digest.update(b"\0F" + relative.encode("utf-8", "surrogateescape"))
    try:
        data = (root / relative).read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        digest.update(b"\0-")
        return None
    except OSError:
        # Unreadable (for example a transient Windows sharing violation): make
        # the fingerprint unique so neither the lookup nor the store can match.
        digest.update(b"\0?" + os.urandom(16))
        return None
    digest.update(b"\0+" + len(data).to_bytes(8, "big") + data)
    return data


def _feed_tree(digest: hashlib.blake2b, root: Path, relative: str) -> None:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root / relative):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        found.extend(f"{rel_dir}/{name}" for name in sorted(filenames))
    digest.update(b"\0T" + relative.encode("utf-8", "surrogateescape") + len(found).to_bytes(8, "big"))
    for rel in found:
        _feed_file(digest, root, rel)


def _feed_checkout_presence(digest: hashlib.blake2b, gitdir_file: Path) -> None:
    """Whether the linked checkout still exists (``git worktree list`` reports ``prunable`` otherwise)."""
    try:
        target = Path(gitdir_file.read_text(encoding="utf-8").strip())
        present = target.exists()
    except (OSError, UnicodeDecodeError):
        present = False
    digest.update(b"\0P1" if present else b"\0P0")
