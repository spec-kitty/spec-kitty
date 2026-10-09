"""Canonical repo root resolution via ``git rev-parse --git-common-dir``.

Contract: ``kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/canonical-root-resolver.contract.md``

Key invariant: ``git rev-parse --git-common-dir`` stdout is CWD-relative in
the common case (e.g. ``.git`` or ``../../.git``). It is absolute only for
linked worktrees. Callers MUST resolve the returned path against ``cwd``.

This module is the sole canonical-root authority for the unified charter
bundle chokepoint (FR-003, FR-006, NFR-003). It raises loudly per C-001 — no
fallback handlers, no silent degradation.

In addition, this module is the charter-layer facade for resolution-tier
types from ``charter.offering.resolver`` (``ResolutionResult``, ``ResolutionTier``).
The runtime → charter → charter.offering boundary (ADR 2026-03-27-1, tightened by
mission ``charter-mediated-doctrine-selection-01KRTZCA``) requires runtime
modules under ``src/specify_cli/`` to reach charter offering artifacts only through
charter facades. ``ResolutionResult`` and ``ResolutionTier`` are re-exported
here as **pure re-exports** (object identity preserved). No behaviour, no
wrappers, no type aliases.
"""
from __future__ import annotations

from pathlib import Path

# Charter facade re-exports for charter.offering.resolver — see mission
# charter-mediated-doctrine-selection-01KRTZCA, contract
# contracts/charter-facade-modules.md.
from charter.offering.resolver import ResolutionResult, ResolutionTier

# The single git-topology probe (mission write-path-integrity-01KZZD69 WP01,
# #3373). This resolver is the richest historical copy — cached, classifying
# not-a-repo, ``.git``-interior detecting — and now consumes the unified
# primitive so the whole write path shares ONE canonicalization contract.
from kernel.git_topology import (
    GitTopologyUnavailableError,
    NotAGitRepositoryError,
    clear_caches as _clear_topology_caches,
    git_common_dir,
    git_configured_worktree,
)

# The directory name git gives a git dir that sits inside its working tree.
_DOT_GIT = ".git"


class NotInsideRepositoryError(RuntimeError):
    """Raised when ``resolve_canonical_repo_root`` is called outside any git repo.

    Also raised when the input path resolves to a location inside a ``.git/``
    directory itself, which the resolver treats as "not a valid project root".
    """

    def __init__(self, path: Path):
        self.path = path
        super().__init__(
            f"Path {path!r} is not inside a git repository. "
            f"Charter resolution requires a git-tracked project root."
        )


class GitCommonDirUnavailableError(RuntimeError):
    """Raised when ``git rev-parse --git-common-dir`` cannot be invoked.

    Covers binary-missing (``FileNotFoundError`` from ``subprocess.run``) and
    non-"not a git repository" failures (corrupt ``.git``, permission denied,
    etc.). Per C-001, neither failure has a fallback handler.
    """

    def __init__(self, path: Path, detail: str):
        self.path = path
        self.detail = detail
        super().__init__(
            f"git rev-parse --git-common-dir failed for {path!r}: {detail}. "
            f"Install a supported git binary and retry."
        )


def resolve_canonical_repo_root(path: Path) -> Path:
    """Resolve ``path`` to the canonical (main-checkout) project root.

    See ``contracts/canonical-root-resolver.contract.md`` for the full
    behavioral matrix and error surface. That contract is a frozen archived
    mission dossier (immutable under the archive-freeze gate), so #5353's
    changes are recorded here in live code rather than by editing it: both its
    submodule row (``<repo>/.git/modules``) and its "not parsing ``.git/config``
    for ``core.worktree``" non-goal are superseded by the submodule rule below
    (#5353) — this facade now reads a non-``.git`` common dir's own
    ``core.worktree`` to map a submodule back to its working tree. The function performs at most one
    ``git rev-parse --git-common-dir`` invocation per cold call and zero on
    warm (LRU-cached) calls. A common dir that is not named ``.git`` (a
    submodule's absorbed ``<super>/.git/modules/<name>``) costs one extra cold
    ``git config --get core.worktree`` probe, also cached.

    The probe itself is delegated to the unified
    :func:`kernel.git_topology.git_common_dir` primitive (mission
    write-path-integrity-01KZZD69 WP01, #3373); this facade preserves the
    repo-**root** return shape, the cache, and the historical error surface by
    mapping the primitive's typed errors onto
    :class:`NotInsideRepositoryError` / :class:`GitCommonDirUnavailableError`.

    The root is the main working tree that owns the common dir:

    * a common dir named ``.git`` sits inside its working tree, so the root is
      its parent (plain checkouts and their linked worktrees);
    * otherwise the root is the common dir's configured ``core.worktree``. For
      a submodule that is the submodule's own working tree (``<super>/submod``,
      what ``git rev-parse --show-toplevel`` prints there), never the
      superproject (#2011) and never ``<super>/.git/modules``. A linked
      worktree of a submodule resolves to the submodule's main working tree;
    * with no ``core.worktree`` configured (e.g. ``--separate-git-dir``), the
      parent of the common dir is kept as before.

    Args:
        path: Any path (file or directory). May be absolute or relative. File
            inputs are normalized to their parent directory before invocation.

    Returns:
        Absolute path to the canonical project root (the main checkout).

    Raises:
        NotInsideRepositoryError: ``path`` is not inside any git repo, or is
            inside a ``.git/`` directory.
        GitCommonDirUnavailableError: ``git`` binary missing or
            ``git rev-parse --git-common-dir`` failed for any other reason.
    """
    abs_path = path.resolve()
    try:
        common_dir = git_common_dir(abs_path)
        if common_dir.name == _DOT_GIT:
            return common_dir.parent
        configured = git_configured_worktree(common_dir)
    except NotAGitRepositoryError as exc:
        raise NotInsideRepositoryError(exc.path) from exc
    except GitTopologyUnavailableError as exc:
        raise GitCommonDirUnavailableError(exc.path, exc.detail) from exc
    return configured if configured is not None else common_dir.parent


# Expose ``cache_clear`` on the public surface so tests that mutate the
# filesystem layout mid-run can reset the shared topology cache without
# reaching into the primitive. The attribute-assignment pattern is a
# deliberate, pre-existing shape mypy cannot model on a plain function.
resolve_canonical_repo_root.cache_clear = _clear_topology_caches  # type: ignore[attr-defined]


__all__ = [
    "GitCommonDirUnavailableError",
    "NotInsideRepositoryError",
    "ResolutionResult",
    "ResolutionTier",
    "resolve_canonical_repo_root",
]
