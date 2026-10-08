"""Shared DoctrineService project-root candidate resolution.

Both ``src/charter/activation/compiler.py::_default_doctrine_service`` and
``src/charter/activation/context.py::_build_doctrine_service`` use the same candidate-list
ordering.  This module is the **single source of truth** for that ordering so
the two call-sites cannot drift apart.

Candidate ordering (FR-009 / T024 / T025):

1. the project pack root     — ``.kittify/charter-packs/`` (read through
                              :func:`kernel.charter_pack_paths.resolve_project_pack_read_root`,
                              so a project still on the retired
                              ``.kittify/doctrine/`` tree is read there);
                              present only after a successful
                              ``spec-kitty charter synthesize`` run.
2. ``src/charter/offering/``        — code-local built-in-layer path (legacy 3.x default).
3. ``doctrine/``            — flat built-in-layer fallback.

Discovery is **conditional on directory presence**: if the project pack root
does not exist the resolver returns the next matching candidate, preserving
byte-identical behaviour for legacy (pre-synthesis) projects (R-2 mitigation).
"""

from __future__ import annotations

from pathlib import Path

from kernel.charter_pack_paths import resolve_project_pack_read_root

# ---------------------------------------------------------------------------
# Candidate list (ordered: synthesis-aware first, built-in-layer fallbacks after)
# ---------------------------------------------------------------------------

#: Repo-relative built-in-layer fallbacks, tried after the project pack root.
_BUILT_IN_FALLBACK_CANDIDATES: tuple[str, ...] = (
    "src/charter/offering",  # relocated code-local built-in-layer path
    "doctrine",  # existing — flat built-in-layer fallback
)


def _project_root_candidates(repo_root: Path) -> tuple[Path, ...]:
    """Return the ordered candidate directories for *repo_root*.

    The first candidate is the project pack root, decided by the kernel
    resolver (FR-016), never by a path string spelled here.
    """
    project_pack = resolve_project_pack_read_root(repo_root, quiet=True)
    return (project_pack, *(repo_root / candidate for candidate in _BUILT_IN_FALLBACK_CANDIDATES))


def resolve_project_root(repo_root: Path) -> Path | None:
    """Return the first existing project-doctrine directory for *repo_root*.

    Returns ``None`` when none of the candidates exist on disk, which means
    ``DoctrineService`` will be constructed with ``project_root=None`` (built-in
    layer only — identical to the pre-Phase-3 default).

    The function is intentionally a thin directory-presence check: it does
    **not** inspect the directory's contents.  An empty project pack root
    directory is still a valid candidate (the ``DoctrineService`` will simply
    surface an empty project layer with no built-in-layer impact).

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        The first matching :class:`~pathlib.Path` or ``None``.
    """
    for path in _project_root_candidates(repo_root):
        if path.is_dir():
            return path
    return None


# _project_root_candidates / _BUILT_IN_FALLBACK_CANDIDATES: internal; no
# cross-module src/ from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
__all__ = ["resolve_project_root"]
