"""Canonical-root re-exports + feature-dir canonicalization (FR-013, IC-04).

Historically this module carried its *own* worktree-pointer parser
(``_read_worktree_pointer`` / ``_canonical_from_worktree_gitdir`` /
``resolve_canonical_root``), duplicating the parser in
:mod:`specify_cli.core.paths`.  Two parsers meant two opinions about the
canonical ``primary_root`` — the Cluster C split-brain (research R-B).

WP05 (IC-04 / C-005) collapses to a **single** worktree-pointer parser in
:mod:`specify_cli.core.paths`.  ``resolve_canonical_root`` and
``WorkspaceRootNotFound`` are now re-exported from there so existing callers
keep their import sites unchanged (C-004 strangler: re-point before delete).
What remains here is :func:`canonicalize_feature_dir`, which is *not* a
worktree-pointer parser — it is a feature-dir rewrite helper that *consumes*
the single resolver.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import (
    WorkspaceRootNotFound,
    resolve_canonical_root,
)

__all__ = [
    "WorkspaceRootNotFound",
    "canonicalize_feature_dir",
    "resolve_canonical_root",
    "resolve_status_lock_root",
]


def resolve_status_lock_root(feature_dir: Path, repo_root: Path | None = None) -> Path:
    """Resolve the repo root used for per-feature status locking.

    Single shared implementation for both write-side lock sites
    (``status.emit`` and ``status.work_package_lifecycle``).

    Mis-routing a status *lock* root is a concurrency defect: two processes
    anchored on the same mission via different worktrees would acquire
    different locks (no mutual exclusion). This helper routes every case
    through the single :func:`specify_cli.core.paths.resolve_canonical_root`
    parser so every process—regardless of CWD—locks against the same
    canonical main-repo root (C-ROOT, SC-002).

    Args:
        feature_dir: Path to the ``kitty-specs/<slug>`` mission directory.
        repo_root: Optional explicit repo root override. When provided the
            caller already knows the root; skip resolution entirely.

    Returns:
        The resolved repo root path to use for acquiring the status lock.
    """
    if repo_root is not None:
        return repo_root
    if feature_dir.parent.name != KITTY_SPECS_DIR:
        # Feature dir not under kitty-specs/ (ad-hoc / test dirs): use the
        # feature_dir itself as the lock anchor — unchanged from the legacy
        # behaviour for this case.
        return feature_dir
    try:
        return resolve_canonical_root(feature_dir)
    except WorkspaceRootNotFound:
        # Non-git tree (e.g. ad-hoc test dirs that have a kitty-specs/ ancestor
        # but no actual git repo): fall back to the historical parent.parent shape
        # so the lock still lands in a deterministic location.
        return feature_dir.parent.parent


def _reset_cache() -> None:
    """No-op cache reset (test-compatibility shim).

    The collapsed single parser (:func:`specify_cli.core.paths.resolve_canonical_root`)
    is cheap and stateless, so there is no module-level cache to clear. This
    shim is retained so existing tests that called the old caching parser's
    ``_reset_cache`` continue to import cleanly.
    """


def _is_default_mission_topic_holder(canonical_root: Path, canonical_feature_dir: Path, feature_dir: Path) -> bool:
    """FR-061 / WP05 obligation N1: *feature_dir* is a default Mission's PRIMARY home (its topic holder).

    The one topic-holder locator decides; the repository root checkout's copy is then a stale
    copy and a write never redirects onto it.
    """
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.missions._read_path_resolver import default_mission_topic_dir

    try:
        held = default_mission_topic_dir(canonical_root, canonical_feature_dir)
    except MissionMetaReadError:
        return False
    return held is not None and held.resolve() == feature_dir.resolve()


def canonicalize_feature_dir(feature_dir: Path) -> Path:
    """Return the canonical-root version of ``feature_dir`` when possible.

    Many emit callers construct ``feature_dir = repo_root / KITTY_SPECS_DIR /
    <slug>`` from a *worktree* repo_root. When that happens, status emit,
    charter writes, and config writes would land inside the worktree's
    stale copy of the mission artifacts instead of the canonical repo.

    This helper rewrites such paths to point at the canonical repo's
    ``kitty-specs/<slug>`` directory. When ``feature_dir`` cannot be
    canonicalized (no enclosing git repo, unexpected layout, etc.) the
    original value is returned unchanged so callers degrade gracefully.

    Args:
        feature_dir: Path to a kitty-specs/<slug> directory (or anything
            else; non-conforming inputs are returned as-is).

    Returns:
        The canonical-root-rooted feature directory, or ``feature_dir``
        when canonicalization does not apply.
    """
    from specify_cli.coordination.surface_resolver import (
        WorktreeRegistryUnavailable,
        is_registered_coord_worktree,
    )

    feature_dir = Path(feature_dir)
    parent = feature_dir.parent
    if parent.name != KITTY_SPECS_DIR:
        return feature_dir

    # A *registered* coordination worktree's feature dir is already canonical —
    # never rewrite it back to the primary checkout (that is the #1589/#1821
    # split-brain). Name proposes (the ``-coord`` suffix); the git registry
    # disposes — a husk ``-coord`` dir (suffix present, NOT registered) falls
    # through to canonicalization below, killing the husk-write split-brain.
    # When the registry is unreadable (ad-hoc test dirs outside a git repo), we
    # cannot canonicalize anyway, so degrade to the path-shape proposal to keep
    # those callers working.
    try:
        if is_registered_coord_worktree(feature_dir):
            return feature_dir
    except WorktreeRegistryUnavailable:
        for candidate in (feature_dir, *feature_dir.parents):
            if candidate.parent.name == ".worktrees" and candidate.name.endswith(
                "-coord"
            ):
                return feature_dir

    try:
        canonical_root = resolve_canonical_root(feature_dir)
    except WorkspaceRootNotFound:
        return feature_dir

    canonical_feature_dir = canonical_root / KITTY_SPECS_DIR / feature_dir.name
    if _is_default_mission_topic_holder(canonical_root, canonical_feature_dir, feature_dir):
        return feature_dir
    # Only redirect when the canonical path actually exists; this keeps
    # tests that build ad-hoc feature dirs outside a git repo working.
    if canonical_feature_dir.exists():
        return canonical_feature_dir
    return feature_dir
