"""Project path resolution helpers for Spec Kitty."""

from __future__ import annotations

from pathlib import Path


def locate_project_root(start: Path | None = None) -> Path | None:
    """Delegates to the authoritative implementation in :mod:`specify_cli.core.paths`.

    All resolution authority — ``SPECIFY_REPO_ROOT`` env-var check (Tier 1),
    git worktree ``.git`` pointer following (Tier 2), and ``.kittify`` directory
    walk (Tier 3) — lives in :func:`specify_cli.core.paths.locate_project_root`.

    The import is deferred to the function body (not module-level) to preserve
    import-cycle safety: ``core/__init__.py`` imports from this module, and a
    module-level import of ``paths`` here could trigger ``specify_cli`` package
    initialisation before it finishes loading. The deferred pattern fires only at
    call time, after the package is fully loaded. This is the same mechanism used
    by ``paths.py`` itself for its ``git_ops`` and ``_read_path_resolver``
    deferred imports. Reverting to a module-level import is a regression. (#1971)
    """
    from specify_cli.core.paths import locate_project_root as _authoritative

    result: Path | None = _authoritative(start)
    return result


__all__ = [
    "locate_project_root",
]
