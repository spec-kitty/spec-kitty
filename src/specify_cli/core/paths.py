"""Enhanced path resolution for spec-kitty CLI with worktree detection."""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.errors import GuardedReadError

from .constants import KITTIFY_DIR, LINT_REPORT_FILENAME, WORKTREES_DIR

logger = logging.getLogger(__name__)

_GITDIR_PREFIX = "gitdir:"


# ---------------------------------------------------------------------------
# Canonical safe-path-segment validator (FR-001 / D-1)
#
# Grammar decision (research.md D-1 / WP01 T001 dot-policy):
#   - Reconciles three divergent validators:
#       merge.py    ^[A-Za-z0-9_-]+$         (no dots)
#       transaction ^[A-Za-z0-9][A-Za-z0-9._-]*$  (interior dots ok)
#       aggregate   ^[A-Za-z0-9_-]+$         (no dots)
#   - Adopts the INTERIOR-DOT-ALLOWED form so transaction.py's real accepts
#     (mission_id/mid8) survive without change.
#   - Rejects: empty/whitespace, ".", "..", any "/" or "\", non-ASCII, leading
#     ".", and any value whose stripped form contains ".." as a substring.
#   - This WIDENS merge.py's slug acceptance to allow interior dots; that is
#     intentional — no caller relies on merge.py rejecting a dotted slug
#     (WP01 verified: merge.py callers only receive CLI-created slugs that
#     never emit interior dots; the widening is safe and non-breaking).
# ---------------------------------------------------------------------------
_SAFE_PATH_SEGMENT_RE: re.Pattern[str] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)


class UnsafePathSegmentError(GuardedReadError, ValueError):
    """Raised when a value is not a canonical safe path segment.

    Subclasses both :class:`kernel.errors.GuardedReadError` (mission
    cli-error-surface-seam — the global CLI hook catches it) and
    :class:`ValueError` (pre-existing contract — every ``except ValueError``
    call site keeps matching). MRO:
    ``[UnsafePathSegmentError, GuardedReadError, ValueError, Exception, ...]``.
    """


def assert_safe_path_segment(value: str) -> str:
    """Return ``value`` if it is a single safe path segment.

    Rejects empty/whitespace-only, ``"."``, ``".."``, any ``"/"`` or ``"\\"``
    (path separators), non-ASCII input, values beginning with ``"."`` (hidden-file
    style — leading-dot rejected as traversal risk), and any value whose stripped
    form contains ``".."`` as a substring (dotted-traversal guard: ``"..foo"``,
    ``"foo.."``, ``"a..b"`` — a grammar that only special-cases the two literal
    tokens would wrongly accept these).

    The grammar is the reconciled canonical form that admits every real-format
    mission-slug value (full 26-char ULID, ``<slug>-<mid8>`` directory names,
    numeric-prefix slugs, bare mid8) while preserving the traversal guard —
    proven by the NFR-006 union test.

    This is a **general safe-segment validator** (not slug-only): it is also used
    by WP02 for ``mission_id`` and ``mid8`` values, which carry the same format
    constraints.

    Args:
        value: The path segment to validate.

    Returns:
        ``value`` unchanged when valid.

    Raises:
        UnsafePathSegmentError: When ``value`` is not a safe single path segment.
    """
    stripped = value.strip() if value else value

    # Reject empty or whitespace-only
    if not stripped:
        raise UnsafePathSegmentError(
            f"Not a safe path segment: {value!r} — value must not be empty or whitespace-only."
        )

    # Reject leading or trailing whitespace — a value that differs from its
    # stripped form is ambiguous and would silently produce wrong path segments.
    if value != stripped:
        raise UnsafePathSegmentError(
            f"Not a safe path segment: {value!r} — value must not contain leading or trailing whitespace."
        )

    # Reject any ".." substring (covers ..foo, foo.., a..b, and literal ..)
    if ".." in stripped:
        raise UnsafePathSegmentError(
            f"Not a safe path segment: {value!r} — value must not contain '..' (traversal guard)."
        )

    # Reject leading dot (covers .hidden, .dot-only, etc.)
    if stripped.startswith("."):
        raise UnsafePathSegmentError(
            f"Not a safe path segment: {value!r} — value must not begin with '.' (traversal guard)."
        )

    # Reject path separators (/ and \) — catches a/b, a\b, /absolute, trailing/
    if "/" in stripped or "\\" in stripped:
        raise UnsafePathSegmentError(
            f"Not a safe path segment: {value!r} — value must not contain path separators."
        )

    # Reject non-ASCII and enforce the segment grammar
    if not _SAFE_PATH_SEGMENT_RE.fullmatch(stripped):
        raise UnsafePathSegmentError(
            f"Not a safe path segment: {value!r} — value must match the canonical segment grammar "
            f"(ASCII alphanumerics, hyphens, underscores, and interior dots only; "
            f"must begin with an alphanumeric character)."
        )

    return value


def safe_mission_slug(slug: str | None, fallback: str) -> str:
    """Return *slug* when it is a safe single path segment, else *fallback*.

    The mission slug carried on a status snapshot originates from UNTRUSTED
    event-record content (``StatusEvent.mission_slug``, copied verbatim from a
    ``status.events.jsonl`` row). Any sink that joins that slug into a path and
    creates/writes a directory (the ``derived/<slug>/`` view writers) must never
    let a crafted ``"../../../../tmp/evil"`` slug escape the derived root.

    This is the fail-closed chokepoint: an unsafe slug downgrades to *fallback*
    (the trusted ``feature_dir.name``), logging a warning. The downgrade is
    display-only — the slug is used solely as a path segment and a display label,
    so substituting the trusted directory name has no correctness cost.

    Args:
        slug: The candidate slug (may be ``None`` or empty).
        fallback: The trusted replacement (e.g. ``feature_dir.name``).

    Returns:
        ``slug`` when valid; otherwise ``fallback``.
    """
    if not slug:
        return fallback
    try:
        assert_safe_path_segment(slug)
    except ValueError as exc:
        logger.warning(
            "Refusing to use unsafe mission_slug %r as a path segment (traversal guard); "
            "falling back to trusted %r: %s",
            slug,
            fallback,
            exc,
        )
        return fallback
    return slug


def _is_worktree_gitdir(gitdir: Path) -> bool:
    """Check if a gitdir path has the .git/worktrees/<name> topology.

    True git worktrees point to ``<main>/.git/worktrees/<wt-name>``.
    Bare-repo worktrees point to ``<repo>.git/worktrees/<wt-name>``.
    Submodules point to ``../.git/modules/<mod>`` and separate-git-dir
    clones point to an arbitrary directory.  Only the first two cases
    are worktrees.
    """
    # gitdir = …/.git/worktrees/<name>        (non-bare)
    # gitdir = …/<repo>.git/worktrees/<name>  (bare)
    #   gitdir.parent.name  == "worktrees"
    #   gitdir.parent.parent.name endswith ".git"
    return gitdir.parent.name == "worktrees" and gitdir.parent.parent.name.endswith(".git")


def _read_worktree_gitdir(git_marker: Path) -> Path | None:
    """Return the pointed gitdir when ``git_marker`` is a real worktree pointer."""
    try:
        content = git_marker.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None

    if not content.startswith(_GITDIR_PREFIX):
        return None

    gitdir = Path(content.split(":", 1)[1].strip())
    if not _is_worktree_gitdir(gitdir):
        return None

    return gitdir


def locate_project_root(start: Path | None = None, *, stop: Path | None = None) -> Path | None:
    """
    Locate the MAIN spec-kitty project root directory, even from within worktrees.

    This function correctly handles git worktrees by detecting when .git is a
    file (worktree pointer) vs a directory (main repo), and following the
    pointer back to the main repository.

    Resolution order:
    1. SPECIFY_REPO_ROOT environment variable (highest priority). When set and
       the named path is an existing directory, it is authoritative — it is
       honoured even if the path has no ``.kittify/`` directory (#1965).
       Missing or non-directory paths are ignored and resolution falls through
       to the walk-up. This makes the env var a deterministic override for
       CI/CD and tests; real ``.kittify/`` projects are unaffected because both
       branches flow through ``get_main_repo_root`` on the same directory
       (C-003).
    2. Walk up directory tree, detecting worktree .git files and following to main repo
    3. Fall back to .kittify/ marker search

    Args:
        start: Starting directory for search (defaults to current working directory)
        stop: Last directory examined by the walk-up (Tier 2/3). Production
            callers keep the unbounded default (``None``), which walks all the
            way to the filesystem root. Tests pass an explicit *stop* because
            nothing above a test's own temp tree is under test control — on a
            shared machine or under parallel test workers, a sibling test can
            leave a stray ``.git``/``.kittify`` in a shared ancestor, which
            would otherwise flip this walk's verdict non-deterministically
            (same class of bug as #130/#139's ``_find_project_root``).

    Returns:
        Path to MAIN project root (not worktree), or None if not found

    Examples:
        >>> # From main repo
        >>> root = locate_project_root()
        >>> assert (root / ".kittify").exists()

        >>> # From worktree - returns MAIN repo, not worktree
        >>> root = locate_project_root(Path(".worktrees/my-feature"))
        >>> assert ".worktrees" not in str(root)
    """
    # Tier 1: Check environment variable (authoritative override for CI/CD).
    # When the named directory exists it wins outright — a missing ``.kittify/``
    # is NOT a disqualifier (#1965). The ``is_dir()`` guard is retained so a
    # non-existent or file-valued path falls through to the walk-up instead of
    # returning a bogus root. Real ``.kittify/`` projects are unaffected: both
    # this branch and the walk-up resolve the same directory via
    # ``get_main_repo_root`` (C-003 regression-guarded).
    if env_root := os.getenv("SPECIFY_REPO_ROOT"):
        env_path = Path(env_root).resolve()
        if env_path.is_dir():
            return get_main_repo_root(env_path)
        # Missing or non-directory env var path - fall through to other methods

    # Tier 2: Walk up directory tree, handling worktree .git files
    current = (start or Path.cwd()).resolve()
    boundary = stop.resolve() if stop is not None else None

    for candidate in [current, *current.parents]:
        git_path = candidate / ".git"

        if git_path.is_file():
            # .git files with gitdir: pointers appear in worktrees,
            # submodules, and separate-git-dir clones.  Only follow the
            # pointer when it has the .git/worktrees/<name> topology.
            try:
                content = git_path.read_text(encoding="utf-8", errors="replace").strip()
                if content.startswith(_GITDIR_PREFIX):
                    gitdir = Path(content.split(":", 1)[1].strip())
                    if _is_worktree_gitdir(gitdir):
                        # Navigate: .git/worktrees/name -> .git -> main repo root
                        main_git_dir = gitdir.parent.parent
                        main_repo = main_git_dir.parent
                        if main_repo.exists() and (main_repo / KITTIFY_DIR).is_dir():
                            return main_repo
            except (OSError, ValueError):
                # If we can't read or parse the .git file, continue searching
                pass

        elif git_path.is_dir():
            # A ``.git`` *directory* is a repo boundary: a regular repo, the
            # main repo of a worktree set, OR a nested clone living inside an
            # outer primary. It is a usable project boundary when it carries
            # the canonical ``.kittify`` marker or a real Git ``HEAD``; an
            # empty directory marker is not a checkout. Stop at either shape
            # rather than walking UP past a nested clone's ``.git`` directory
            # into the enclosing primary (FR-007, #2610). Linked worktrees use
            # a ``.git`` *file* pointer (handled in the branch above), so this
            # boundary-stop never affects the deliberate worktree->primary
            # re-anchor.
            if (candidate / KITTIFY_DIR).is_dir() or (git_path / "HEAD").is_file():
                return candidate
            break

        # Also check for .kittify marker (fallback for non-git scenarios)
        kittify_path = candidate / KITTIFY_DIR
        broken_symlink = kittify_path.is_symlink() and not kittify_path.exists()
        if not broken_symlink and kittify_path.is_dir():
            return candidate

        if boundary is not None and candidate == boundary:
            break

    return None


def lint_report_path(repo_root: Path) -> Path:
    """Return the canonical path of the repo-global charter-lint decay report.

    The lint engine writes ``<repo_root>/.kittify/lint-report.json``; the
    dashboard tile and the dossier stager read it back. This accessor is the
    single source of truth for that location — no caller should re-compose the
    ``.kittify`` / filename literals by hand (#2628 SSOT fold).
    """
    return Path(repo_root / KITTIFY_DIR / LINT_REPORT_FILENAME)


def is_worktree_context(path: Path) -> bool:
    """
    Detect if the given path is within a git worktree directory.

    Checks two conditions:
    1. '.worktrees' appears in the path hierarchy (spec-kitty managed worktrees)
    2. The nearest .git entry is a file with a gitdir: pointer (generic git worktree)

    Args:
        path: Path to check (typically current working directory)

    Returns:
        True if path is within any git worktree, False otherwise

    Examples:
        >>> is_worktree_context(Path("/repo/.worktrees/feature-001"))
        True
        >>> is_worktree_context(Path("/repo/kitty-specs"))
        False
        >>> # Also detects external worktrees (e.g. under /tmp)
        >>> is_worktree_context(Path("/tmp/my-worktree"))  # if .git is a gitdir pointer
        True
    """
    # Fast path: spec-kitty managed worktrees
    if WORKTREES_DIR in path.parts:
        return True

    # Generic detection: walk up to find .git file with gitdir pointer
    # Only recognise true worktrees (.git/worktrees/<name> topology),
    # NOT submodules (.git/modules/<mod>) or separate-git-dir clones.
    resolved = path.resolve()
    for candidate in [resolved, *resolved.parents]:
        git_path = candidate / ".git"
        if git_path.is_file():
            try:
                content = git_path.read_text(encoding="utf-8", errors="replace").strip()
                if content.startswith(_GITDIR_PREFIX):
                    gitdir = Path(content.split(":", 1)[1].strip())
                    if _is_worktree_gitdir(gitdir):
                        return True
            except OSError:
                pass
            break
        elif git_path.is_dir():
            # Main repo .git directory — not a worktree
            break

    return False


def resolve_with_context(start: Path | None = None) -> tuple[Path | None, bool]:
    """
    Resolve project root and detect worktree context in one call.

    Args:
        start: Starting directory for search (defaults to current working directory)

    Returns:
        Tuple of (project_root, is_worktree)
        - project_root: Path to repo root or None if not found
        - is_worktree: True if executing from within .worktrees/

    Examples:
        >>> # From main repo
        >>> root, in_worktree = resolve_with_context()
        >>> assert in_worktree is False

        >>> # From worktree
        >>> root, in_worktree = resolve_with_context(Path(".worktrees/my-feature"))
        >>> assert in_worktree is True
    """
    current = (start or Path.cwd()).resolve()
    root = locate_project_root(current)
    in_worktree = is_worktree_context(current)
    return root, in_worktree


def check_broken_symlink(path: Path) -> bool:
    """
    Check if a path is a broken symlink (symlink pointing to non-existent target).

    This helper is useful for graceful error handling when dealing with
    worktree symlinks that may become invalid.

    Args:
        path: Path to check

    Returns:
        True if path is a broken symlink, False otherwise

    Note:
        A broken symlink returns True for is_symlink() but False for exists().
        Always check is_symlink() before exists() to detect this condition.
    """
    return path.is_symlink() and not path.exists()


class WorkspaceRootNotFound(Exception):
    """Raised when a canonical mission repo root cannot be resolved.

    Owned here because :mod:`specify_cli.core.paths` is the single
    worktree-pointer parser (IC-04): the canonical-root resolver and its
    error type live together. ``specify_cli.workspace.root_resolver``
    re-exports this name for backwards compatibility with existing callers.
    """

    def __init__(self, cwd: Path | str) -> None:
        self.cwd = Path(cwd)
        super().__init__(f"No git repository found at or above {self.cwd}")


def resolve_canonical_root(cwd: Path | None = None) -> Path:
    """Return the canonical mission repo root for ``cwd``.

    This is the single worktree-pointer parser (IC-04): every consumer that
    asks "given some CWD (which may be a worktree), what is the canonical
    main-repo root?" resolves through here.  ``workspace/root_resolver``'s
    historical duplicate parser was collapsed into this function.

    Resolution rules (walking ancestors from ``cwd``):

    1. ``.git`` is a *directory*: this is a regular repo (or the main repo of
       a worktree set); return that ancestor.
    2. ``.git`` is a *file* with a ``gitdir:`` pointer of the
       ``.git/worktrees/<name>`` topology: follow the pointer back to the
       main repo working tree (reusing :func:`get_main_repo_root`).
    3. ``.git`` is a malformed/non-worktree pointer file (submodule /
       separate-git-dir): stop at this ancestor when it carries the canonical
       ``.kittify`` marker — mirroring :func:`locate_project_root`'s boundary
       check so the two root authorities agree on the submodule case (FR-007).
       Otherwise keep walking so an enclosing repo is still found if one exists.
    4. No git marker anywhere up the tree: raise :class:`WorkspaceRootNotFound`.

    ``GIT_CEILING_DIRECTORIES`` uses Git's ceiling semantics: a listed ancestor
    is still eligible, but discovery never continues above it. This keeps
    hermetic fixtures isolated from an ambient repository above their temporary
    root.

    Args:
        cwd: Starting directory. Defaults to :func:`Path.cwd`.

    Returns:
        Absolute, resolved path to the canonical repo root.

    Raises:
        WorkspaceRootNotFound: when ``cwd`` is not inside a git repo.
    """
    start = (cwd or Path.cwd()).resolve()
    ceilings = {
        Path(part).resolve()
        for part in os.environ.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep)
        if part
    }

    for candidate in [start, *start.parents]:
        git_path = candidate / ".git"

        if git_path.is_dir():
            # Regular repo (or main repo of a worktree set).
            return candidate.resolve()

        if git_path.is_file():
            if _read_worktree_gitdir(git_path) is None:
                # Malformed or non-worktree pointer (submodule / separate-git-dir).
                # Mirror locate_project_root's boundary check: if this ancestor
                # carries the canonical .kittify marker it is a self-contained
                # spec-kitty project (e.g. a submodule with its own .kittify), so
                # stop here rather than walking UP into an enclosing parent repo
                # (FR-007). The two root authorities must agree on this case.
                if (candidate / KITTIFY_DIR).is_dir():
                    return candidate.resolve()
                # No canonical marker — keep walking so an enclosing repo is still
                # resolved.
                continue
            # Real worktree pointer — follow it back to the main checkout.
            return get_main_repo_root(candidate)
        if candidate in ceilings:
            break

    raise WorkspaceRootNotFound(start)


def get_main_repo_root(current_path: Path) -> Path:
    """
    Get the main repository root, even if called from a worktree.

    When in a worktree, .git is a file pointing to the main repo's .git directory.
    This function follows that pointer to find the main repo root.

    Args:
        current_path: Current repo root (may be worktree or main repo)

    Returns:
        Path to the main repository root (resolves worktree pointers)

    Examples:
        >>> # From main repo - returns same path
        >>> get_main_repo_root(Path("/repo"))
        Path('/repo')

        >>> # From worktree - returns main repo
        >>> get_main_repo_root(Path("/repo/.worktrees/feature-001"))
        Path('/repo')
    """
    git_file = current_path / ".git"

    if git_file.is_file():
        try:
            git_content = git_file.read_text(encoding="utf-8", errors="replace").strip()
            if git_content.startswith(_GITDIR_PREFIX):
                gitdir_str = git_content.split(":", 1)[1].strip()
                # Validate the gitdir path is not empty (bug discovered via mutation testing)
                if gitdir_str:
                    gitdir = Path(gitdir_str)
                    if not _is_worktree_gitdir(gitdir):
                        return current_path.resolve()
                    # Navigate: .git/worktrees/name -> .git -> main repo root
                    main_git_dir = gitdir.parent.parent
                    main_repo_root = main_git_dir.parent
                    return main_repo_root
        except (OSError, ValueError):
            pass

    # Not a worktree - return the resolved current path
    return current_path.resolve()


class StatusReadUnsupported(RuntimeError):
    """Raised when a status command does not support detached-worktree invocation.

    Commands that require comparison across worktrees (or that have an explicit
    constraint against detached-worktree reads) should call
    ``assert_worktree_supported()`` at their entry point.  The error message
    names the command and describes the constraint so the operator can act.
    """


class MissionMetaReadError(GuardedReadError, RuntimeError):
    """Raised when meta.json exists but cannot be decoded.

    Distinguishes a *read failure* (corrupt JSON or I/O error) from a
    *field-absent* read (meta.json present and valid but the requested key is
    absent — callers handle that case via the documented default branch).

    Never raised when meta.json is simply missing; a missing file is the
    field-absent case and callers receive ``None`` from
    :func:`read_target_branch_from_meta`.

    (FR-005 / #2139 — fail-closed doctrine; precedent: #2065)

    Attributes:
        meta_path: The path of the file that could not be decoded.
        cause: The underlying exception (``ValueError`` wrapping
               ``JSONDecodeError`` or ``OSError``).
    """

    def __init__(self, meta_path: Path, cause: Exception) -> None:
        self.meta_path = meta_path
        self.cause = cause
        super().__init__(
            f"Cannot read {meta_path}: {cause}"
            " — fail-closed (meta.json exists but is corrupt or unreadable)"
        )
        # Populate the GuardedReadError envelope path (contracts/error-envelope.md).
        # Set only ``path`` — ``reason`` would override the crafted __str__ message.
        self.path = str(meta_path)


def _is_detached_worktree(start: Path | None = None) -> bool:
    """Return True when the current working directory is inside a git worktree.

    A git worktree has a ``.git`` *file* (not directory) whose content starts
    with ``gitdir:`` and points to ``<main>/.git/worktrees/<name>`` — the
    canonical .git/worktrees topology.  Submodules and separate-git-dir clones
    also produce a ``.git`` file, but they do *not* use the worktrees topology,
    so this function correctly excludes them.

    Args:
        start: Starting directory (defaults to ``Path.cwd()``).

    Returns:
        True when running inside a worktree, False otherwise.
    """
    cwd = (start or Path.cwd()).resolve()
    for ancestor in [cwd, *cwd.parents]:
        git_marker = ancestor / ".git"
        if git_marker.is_file():
            return _read_worktree_gitdir(git_marker) is not None
        if git_marker.is_dir():
            # Main repo .git directory — not a worktree
            return False
    return False


def get_status_read_root(start: Path | None = None) -> Path:
    """Resolve the root for read-only status commands.

    Prefers the *current worktree root* over the primary checkout so that
    ``spec-kitty agent tasks status`` invoked from a detached worktree reads
    THAT worktree's ``status.events.jsonl``, not the primary checkout's
    potentially-divergent state.  This is the fix for #984.

    Algorithm:
      1. Walk ancestors from ``start`` (or ``Path.cwd()``).
      2. If a ``.git`` *file* with a worktrees-topology ``gitdir:`` pointer is
         found, return that ancestor — it is the worktree root.
      3. If a ``.git`` *directory* is found, return that ancestor — it is the
         main repo root.
      4. Fall back to ``get_main_repo_root(start or Path.cwd())`` for the rare
         case where no ``.git`` marker is found in the tree.

    Use this for READ paths only.  For write paths (commits, file mutations,
    canonical serialization), continue to use ``get_main_repo_root()``.

    Args:
        start: Starting directory (defaults to ``Path.cwd()``).

    Returns:
        Current worktree root when called from a worktree; main repo root
        otherwise.

    Examples:
        >>> # From main repo
        >>> get_status_read_root(Path("/repo"))
        PosixPath('/repo')

        >>> # From worktree — returns the *worktree* root, not the main repo
        >>> get_status_read_root(Path("/repo/.worktrees/feature-001"))
        PosixPath('/repo/.worktrees/feature-001')
    """
    cwd = (start or Path.cwd()).resolve()
    # Walk up until we find a .git file (worktree) OR a .git directory (main).
    for ancestor in [cwd, *cwd.parents]:
        git_marker = ancestor / ".git"
        if git_marker.is_file():
            if _read_worktree_gitdir(git_marker) is not None:
                # This ancestor is the worktree root — read events from here.
                return ancestor
            # .git file present but not a recognised worktree pointer — break and
            # fall through to the main-repo resolver.
            break
        if git_marker.is_dir():
            # .git is a directory: this is the main repo root.
            return ancestor
    # Fallback: defer to existing main-repo resolver (very rare path).
    return get_main_repo_root(cwd)


def assert_worktree_supported(command_name: str, start: Path | None = None) -> None:
    """Raise with a clear diagnostic when the current context is a detached
    worktree and the command does not support that context.

    As of WP05 this helper exists but is NOT called by any active command — all
    read-only status commands work correctly from both worktrees and the main
    checkout after the ``get_status_read_root()`` routing fix.  This function is
    available for future commands that genuinely cannot serve from a detached
    worktree (e.g., cross-worktree comparison commands).

    Args:
        command_name: Human-readable name of the subcommand (used in the error).
        start: Starting directory override (defaults to ``Path.cwd()``).

    Raises:
        StatusReadUnsupported: When invoked from a detached worktree.
    """
    if _is_detached_worktree(start):
        raise StatusReadUnsupported(
            f"command '{command_name}' does not support detached-worktree invocation. "
            f"Run from the primary checkout or document the constraint."
        )


def load_meta_fail_closed(feature_dir: Path) -> dict[str, Any] | None:
    """Load meta.json fail-closed on corruption -- the ONE public reader (FR-007).

    This is the single place that owns the field-absent vs read-failure
    decision.  Every fail-closed ``meta.json`` reader delegates here; there is
    deliberately **no** second authority (FR-007 / #3140).  The canonical
    *parser* remains :func:`specify_cli.mission_metadata.load_meta` -- which
    itself delegates the malformed *definition* to the L1 kernel primitive
    :func:`kernel.meta_decode.decode_meta` -- this function adds only the typed
    fail-closed **contract** on top of it, so a corrupt ``meta.json`` never
    surfaces a raw :class:`ValueError` to a caller.

    Callers that must stay deliberately silent about corruption (placement
    probes, best-effort displays) keep using
    :func:`specify_cli.mission_metadata.load_meta_or_empty` or the canonical
    reader's ``on_malformed="none"`` arm instead -- they are not routed here.

    Args:
        feature_dir: Mission directory containing (or expected to contain)
            ``meta.json``.

    Returns:
        ``None`` when meta.json is absent (caller treats as field-absent).
        The parsed mapping when meta.json is present and valid.

    Raises:
        MissionMetaReadError: When meta.json exists but is corrupt, non-object,
            or unreadable.  Never raised for a missing file.
    """
    # Deferred import (LOAD-BEARING -- do NOT hoist to module level): core.paths
    # is loaded very early; mission_metadata imports back from core (e.g.
    # safe_mission_slug), so a module-level import re-forms the
    # ``core.paths <-> mission_metadata`` circular import (research.md D4).
    # Publishing this function (FR-007) does not change that -- the import
    # stays in-function. ``mission_metadata.load_meta`` itself routes the
    # malformed decode through the kernel L1 seam
    # (:func:`kernel.meta_decode.decode_meta`), so this delegation introduces
    # no new ``json.loads`` call site (FR-010).
    from specify_cli.mission_metadata import load_meta  # noqa: PLC0415

    meta_path = feature_dir / "meta.json"
    try:
        # allow_missing=True  -> None when file is absent (field-absent case)
        # on_malformed="raise" -> ValueError when file exists but is corrupt
        meta: dict[str, Any] | None = load_meta(
            feature_dir, allow_missing=True, on_malformed="raise"
        )
        return meta
    except ValueError as exc:
        raise MissionMetaReadError(meta_path, exc) from exc


def read_target_branch_from_meta(feature_dir: Path) -> str | None:
    """Read ``target_branch`` from ``feature_dir/meta.json``.

    The single authority for the field-absent vs read-failure distinction
    (FR-005 / #2139 — fail-closed doctrine; precedent: #2065).  All
    ``target_branch`` readers in this codebase are thin adapters over this
    function.

    Args:
        feature_dir: Mission directory containing (or expected to contain)
            ``meta.json``.

    Returns:
        The ``target_branch`` value as a string, or ``None`` when the field
        is absent or meta.json does not exist.  Callers MUST apply the
        documented default (usually the primary branch) when ``None`` is
        returned.

    Raises:
        MissionMetaReadError: When meta.json exists but is corrupt or
            unreadable.  Callers MUST NOT silently swallow this — the error
            must propagate so corruption is visible (fail-closed doctrine).
    """
    data = load_meta_fail_closed(feature_dir)
    if not data:
        return None
    value = data.get("target_branch")
    return str(value) if value else None


def read_retention_from_meta(
    primary_meta_dir: Path,
) -> tuple[object | None, object | None]:
    """Read raw ``retain_branches`` / ``retain_worktrees`` from meta.json.

    Thin adapter over :func:`load_meta_fail_closed`, mirroring
    :func:`read_target_branch_from_meta`. Values are returned RAW
    (uncoerced) so :func:`resolve_merge_retention` can distinguish a real
    JSON boolean from a malformed value (e.g. ``""``, ``0``, ``"true"``)
    that must never be silently ``bool()``-coerced (fail-closed doctrine,
    #3131 NFR-001).

    Args:
        primary_meta_dir: Mission directory (primary partition) containing
            (or expected to contain) ``meta.json``.

    Returns:
        ``(retain_branches_raw, retain_worktrees_raw)``. Both are ``None``
        when meta.json is absent or the field is absent.

    Raises:
        MissionMetaReadError: When meta.json exists but is corrupt or
            unreadable. Callers MUST NOT silently swallow this — the error
            must propagate so corruption is visible (fail-closed doctrine).
    """
    data = load_meta_fail_closed(primary_meta_dir)
    if not data:
        return None, None
    return data.get("retain_branches"), data.get("retain_worktrees")


def get_feature_target_branch(repo_root: Path, mission_slug: str) -> str:
    """Get target branch for a feature by reading meta.json directly.

    Thin adapter over :func:`read_target_branch_from_meta`.

    Reads the ``target_branch`` field from the primary meta.json.  Returns the
    documented default (primary branch) when the field is absent or meta.json
    does not exist.  Raises :class:`MissionMetaReadError` when meta.json
    exists but is corrupt or unreadable (fail-closed).

    Args:
        repo_root: Repository root path (may be worktree — resolved to main).
        mission_slug: Feature slug (e.g., "025-cli-event-log-integration").

    Returns:
        Target branch name (e.g., ``"main"`` or ``"2.x"``).
    """
    # Anchor the meta.json read on the PRIMARY surface — NOT the topology-aware
    # candidate. Under coordination topology that candidate resolves to the
    # coordination worktree, whose mission dir has no meta.json; reading it found
    # nothing and silently fell back to the repo default (main), so the resolved
    # commit/branch surface was the protected primary instead of the mission's
    # ``target_branch`` (the finalize-tasks / implement-loop refusal-to-main bug,
    # WP00 / FR-004). This mirrors ``resolve_merge_target_branch`` below exactly.
    #
    # read-side-seam-primary-primitive-closure-01KYKMMT WP07/WP08 (T034/T035,
    # FR-005 / NFR-009): RECORDED FOUNDATION SITE 1/4, deliberately UNROUTED.
    # This read feeds the write-side composition root
    # (``resolve_placement_only``). ``PlacementSeam.read_dir`` never reaches this
    # target-branch resolution -- it routes to ``resolve_retrospective_home`` or
    # ``resolve_artifact_surface``, neither of which calls
    # ``get_feature_target_branch`` -- so routing here would NOT close the
    # literal cycle a naive reading suggests. The real constraints are (a)
    # import-layering: ``core/paths.py`` is imported very early, so this pulls
    # the missions layer in via a deferred import to dodge the missions<->core
    # import cycle, and (b) behaviour-preservation: this leaf call is
    # byte-identical to the deleted wrapper's pre-delegation body. WP08 deleted
    # the public wrapper (``primary_feature_dir_for_mission``) this site used to
    # import, so this now calls the module-private ``_compose_primary_feature_dir``
    # leaf directly -- see ``tests/architectural/test_no_read_side_bypass.py``'s
    # ``_FOUNDATION_SANCTION_SEED`` entry for ``get_feature_target_branch``
    # (token re-pointed in the same commit).
    from specify_cli.core.git_ops import resolve_primary_branch
    from specify_cli.missions._read_path_resolver import (
        _canonicalize_primary_read_handle,
        _compose_primary_feature_dir,
    )

    main_root = get_main_repo_root(repo_root)
    feature_dir = _compose_primary_feature_dir(
        main_root,
        _canonicalize_primary_read_handle(main_root, mission_slug),
    )
    fallback = str(resolve_primary_branch(main_root))
    branch = read_target_branch_from_meta(feature_dir)
    return branch if branch is not None else fallback


def resolve_merge_target_branch(
    repo_root: Path,
    mission_slug: str | None,
    explicit_target: str | None,
    *,
    persisted_target: str | None = None,
) -> tuple[str, str]:
    """Resolve the branch a mission merges into, with provenance.

    Thin adapter over :func:`load_meta_fail_closed`.

    The single source of truth shared by ``spec-kitty merge`` and
    ``orchestrator-api merge-mission`` so the two never disagree.

    Order: explicit ``--target`` > persisted ``MergeState.target_branch`` >
    primary-meta ``merge_target_branch`` > primary-meta ``target_branch`` >
    repo default.

    terminus-merge-integrity-01M380R6 WP09 (C-1, FR-007, D5, #4985/#4991): the
    landing branch is resolved ONCE and persisted into ``MergeState``; every
    later phase and every ``--resume`` reads that single authority. The
    ``persisted_target`` argument is the merge-state value the caller
    (``merge/resolve.py``) loads — it ranks BELOW an explicit ``--target`` (the
    operator re-stating the target always wins) but ABOVE meta.json, so a
    crashed ``merge --target develop`` followed by a bare ``--resume`` resolves
    ``develop`` (persisted) rather than re-deriving ``main`` from stale meta.
    An empty/blank persisted value is treated as absent (not authoritative).

    The merge target lives in the PRIMARY-checkout meta.json (like
    ``coordination_branch``), so it is read via the module-private
    ``_compose_primary_feature_dir`` leaf — NOT the topology-aware candidate.
    Under coordination topology that candidate
    resolves to the coordination worktree, whose mission dir has no meta.json;
    reading it found nothing and silently fell back to the repo default (main),
    merging the mission into the wrong branch.

    Returns ``(branch, source)`` where ``source`` is ``"flag"``, ``"meta.json"``,
    or ``"primary_branch"``.

    Raises:
        MissionMetaReadError: When meta.json exists but is corrupt or
            unreadable (fail-closed).
    """
    if explicit_target is not None:
        return explicit_target, "flag"

    if persisted_target and persisted_target.strip():
        return persisted_target, "merge_state"

    # Deferred imports: core.paths is imported very early; these pull in the
    # missions/git layers that import back into core — module-level imports would
    # form a circular import.
    #
    # read-side-seam-primary-primitive-closure-01KYKMMT WP07/WP08 (T034/T035,
    # FR-005 / NFR-009): RECORDED FOUNDATION SITE 2/4, deliberately UNROUTED —
    # same import-layering + behaviour-preservation rationale as
    # ``get_feature_target_branch`` above (``PlacementSeam.read_dir`` never
    # reaches this target-branch resolution, so no literal cycle is at stake;
    # the constraints are the early-import deferred-import layering noted above
    # and behaviour-preservation with the deleted wrapper's pre-delegation
    # body). WP08 deleted the public wrapper this site imported; calls the
    # module-private ``_compose_primary_feature_dir`` leaf directly
    # (``_FOUNDATION_SANCTION_SEED`` token re-pointed in the same commit).
    from specify_cli.core.git_ops import resolve_primary_branch
    from specify_cli.missions._read_path_resolver import (
        _canonicalize_primary_read_handle,
        _compose_primary_feature_dir,
    )

    main_root = get_main_repo_root(repo_root)
    fallback = str(resolve_primary_branch(main_root))
    if not mission_slug:
        return fallback, "primary_branch"

    feature_dir = _compose_primary_feature_dir(
        main_root,
        _canonicalize_primary_read_handle(main_root, mission_slug),
    )
    data = load_meta_fail_closed(feature_dir)
    if data:
        for key in ("merge_target_branch", "target_branch"):
            value = data.get(key)
            if value:  # non-null, non-empty
                return str(value), "meta.json"
    return fallback, "primary_branch"


@dataclass(frozen=True)
class RetentionDecision:
    """Effective post-merge cleanup decision (#3131).

    Produced by :func:`resolve_merge_retention`, the single authority that
    turns tri-state CLI flags plus mission ``meta.json`` retention policy
    into the resolved cleanup decision consumed by the merge executor, the
    dry-run forecast, and the abort path -- see
    ``contracts/retention-resolver-contract.md``.

    Attributes:
        delete_branch: Whether lane/mission branches are deleted.
        remove_worktree: Whether lane worktrees are removed.
        teardown_coordination: Coupled coord decision -- ``delete_branch
            AND remove_worktree`` (tear down coord topology only when
            both resources are being cleaned up).
        branch_source: Provenance of ``delete_branch`` -- one of ``"cli"``,
            ``"meta"``, ``"default"``.
        worktree_source: Provenance of ``remove_worktree`` -- one of
            ``"cli"``, ``"meta"``, ``"default"``.
        warnings: Operator-visible messages (retention honored, or a
            malformed meta value was treated as retaining).
        override_notices: Recorded notices when an explicit CLI delete
            overrode a mission retention policy.
    """

    delete_branch: bool
    remove_worktree: bool
    teardown_coordination: bool
    branch_source: str
    worktree_source: str
    warnings: tuple[str, ...]
    override_notices: tuple[str, ...]


def _resolve_one(
    *, label: str, explicit: bool | None, raw_retain: object | None
) -> tuple[bool, str, str | None, str | None]:
    """Resolve one retention field: explicit CLI flag > meta.json > default.

    Precedence per ``contracts/retention-resolver-contract.md`` (#3131):
    an explicit CLI flag always wins; otherwise a real JSON ``True`` in
    meta.json retains the resource (with a warning); a present-but-not-a
    real-``bool`` meta value is ambiguous and is ALSO treated as retaining
    (fail-closed -- ``isinstance(True, int)`` is ``True``, so this checks
    ``isinstance(value, bool)`` explicitly and never falls back to
    ``bool()`` coercion); absence or ``False`` falls through to the default
    (delete/remove).

    Args:
        label: Human-readable resource name for messages (``"branches"`` or
            ``"worktrees"``).
        explicit: The tri-state CLI flag for this resource (``None`` means
            the flag was not supplied).
        raw_retain: The RAW ``retain_<label>`` value read from meta.json
            (see :func:`read_retention_from_meta`).

    Returns:
        ``(effective, source, warning, override_notice)``. ``effective`` is
        ``True`` when the resource should be deleted/removed. ``warning``
        and ``override_notice`` are ``None`` when not applicable.
    """
    meta_is_malformed = raw_retain is not None and not isinstance(raw_retain, bool)
    meta_retains = raw_retain is True or meta_is_malformed

    if explicit is not None:
        override = None
        if explicit and meta_retains:
            override = f"explicit delete overrode retention policy for {label}"
        return explicit, "cli", None, override

    if raw_retain is True:
        warning = f"retention honored for {label} (source: meta.json)"
        return False, "meta", warning, None

    if meta_is_malformed:
        warning = (
            f"malformed retain_{label} value in meta.json ({raw_retain!r}); "
            "treated as retaining (fail-closed)"
        )
        return False, "meta", warning, None

    return True, "default", None, None


def resolve_merge_retention(
    primary_meta_dir: Path,
    *,
    explicit_delete_branch: bool | None,
    explicit_remove_worktree: bool | None,
) -> RetentionDecision:
    """Resolve the effective post-merge cleanup decision (#3131).

    Thin adapter over :func:`read_retention_from_meta`, mirroring the shape
    of :func:`resolve_merge_target_branch`. The single authority shared by
    the merge executor, the dry-run forecast, and the abort path so they
    never disagree about what gets cleaned up.

    A resolver, NOT a pure function (#3833): it performs ``meta.json`` I/O
    via :func:`read_retention_from_meta` → :func:`load_meta_fail_closed`
    (exactly like :func:`resolve_merge_target_branch` reads its meta), so a
    caller must not assume it is I/O-free.

    Args:
        primary_meta_dir: Mission directory (primary partition) containing
            (or expected to contain) ``meta.json``.
        explicit_delete_branch: Tri-state ``--delete-branch`` /
            ``--keep-branch`` CLI resolution (``None`` = flag unset).
        explicit_remove_worktree: Tri-state ``--remove-worktree`` /
            ``--keep-worktree`` CLI resolution (``None`` = flag unset).

    Returns:
        The resolved :class:`RetentionDecision`.

    Raises:
        MissionMetaReadError: When meta.json exists but is corrupt or
            unreadable. Callers MUST NOT silently swallow this -- the error
            must propagate so corruption is visible (fail-closed doctrine);
            the caller aborts the merge with a non-zero exit.
    """
    raw_branches, raw_worktrees = read_retention_from_meta(primary_meta_dir)

    delete_branch, branch_source, branch_warning, branch_override = _resolve_one(
        label="branches", explicit=explicit_delete_branch, raw_retain=raw_branches
    )
    remove_worktree, worktree_source, worktree_warning, worktree_override = (
        _resolve_one(
            label="worktrees",
            explicit=explicit_remove_worktree,
            raw_retain=raw_worktrees,
        )
    )

    warnings = tuple(w for w in (branch_warning, worktree_warning) if w is not None)
    override_notices = tuple(
        n for n in (branch_override, worktree_override) if n is not None
    )

    return RetentionDecision(
        delete_branch=delete_branch,
        remove_worktree=remove_worktree,
        teardown_coordination=delete_branch and remove_worktree,
        branch_source=branch_source,
        worktree_source=worktree_source,
        warnings=warnings,
        override_notices=override_notices,
    )


def require_explicit_feature(feature: str | None, *, command_hint: str = "") -> str:
    """Require an explicit feature slug; raise if not provided.

    Replaces heuristic detection.  Every CLI command that needs a feature slug
    must receive it via ``--mission`` (or equivalent).  No scanning, no env
    var magic, no git branch guessing.

    When the feature is missing, scans ``kitty-specs/`` for available features
    and includes them in the error message so agents can self-correct.

    Args:
        feature: The feature slug provided by the user (may be None).
        command_hint: Name of the CLI flag to mention in the error message.

    Returns:
        The feature slug (guaranteed non-empty string).

    Raises:
        ValueError: If ``feature`` is None or empty.
    """
    if feature and feature.strip():
        return feature.strip()

    flag = command_hint or "--mission <slug>"

    # Scan for available features to include in the error message
    available = ""
    try:
        root = locate_project_root()
        if root is None:
            raise RuntimeError("project root not found")
        mission_specs = root / KITTY_SPECS_DIR
        if mission_specs.is_dir():
            slugs = sorted(
                d.name for d in mission_specs.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )
            if slugs:
                listing = "\n".join(f"  - {s}" for s in slugs[:15])
                if len(slugs) > 15:
                    listing += f"\n  ... and {len(slugs) - 15} more"
                available = f"\nAvailable missions:\n{listing}\n"
    except Exception:
        pass

    example_slug = "057-canonical-context-architecture-cleanup"
    if available:
        # Use the first real slug as the example
        try:
            root = locate_project_root()
            if root is None:
                raise RuntimeError("project root not found")
            first = sorted(
                d.name for d in (root / KITTY_SPECS_DIR).iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )[0]
            example_slug = first
        except Exception:
            pass

    flag_name = flag.split()[0]  # e.g., "--mission"
    msg = (
        f"Mission slug is required. Provide it explicitly: {flag}\n"
        "No auto-detection is performed (branch scanning / env vars removed).\n"
        f"{available}"
        f"Example:\n"
        f"  spec-kitty agent context resolve --action tasks {flag_name} {example_slug} --json\n"
        f"  spec-kitty agent mission finalize-tasks {flag_name} {example_slug} --json"
    )
    raise ValueError(msg)


__all__ = [
    "UnsafePathSegmentError",
    "assert_safe_path_segment",
    "locate_project_root",
    "lint_report_path",
    "is_worktree_context",
    "resolve_with_context",
    "check_broken_symlink",
    "get_main_repo_root",
    "resolve_canonical_root",
    "WorkspaceRootNotFound",
    "get_status_read_root",
    "StatusReadUnsupported",
    "assert_worktree_supported",
    "MissionMetaReadError",
    "load_meta_fail_closed",
    "read_target_branch_from_meta",
    "get_feature_target_branch",
    "resolve_merge_target_branch",
    "require_explicit_feature",
]
