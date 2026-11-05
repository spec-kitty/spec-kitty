"""A planning-commit base derived from git history (#7209, #7210).

The implementation-evidence gate (:mod:`specify_cli.consolidation.wp_evidence`)
needs a planning commit to open its window at. ``finalize-tasks`` records one in
``lanes.json``. Two kinds of Mission have none:

* a ``consolidate --skip-lanes`` Mission with no ``lanes.json`` at all, whose
  manifest is synthesized (#7209);
* a Mission whose ``lanes.json`` predates the pin, which plain ``finalize-tasks``
  could not fill in (#7210).

For both, the base is read from git: the parent of the first commit on the
target branch that added a given Mission file. That is a fact about history; it
claims nothing about review (operator ruling 2026-11-05, ADR
``2026-10-04-5`` Amendment 2026-11-05). The resulting window can be slightly wider
than one a timely ``finalize-tasks`` would have recorded.

This module only answers the git question. The evidence window itself stays
computed in :mod:`specify_cli.consolidation.wp_evidence` alone.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git.runner import GitCommandError, run_git

__all__ = [
    "SKIP_LANES_SYNTHESIS_SOURCE",
    "derive_base_before_first_add",
    "mission_meta_pathspec",
    "mission_wp_tasks_pathspec",
]

#: ``LanesManifest.computed_from`` of the manifest ``consolidate --skip-lanes`` synthesizes
#: when a Mission has no ``lanes.json`` (its planning commit, if any, is derived from git).
SKIP_LANES_SYNTHESIS_SOURCE = "skip-lanes direct-on-target synthesis (T021, FR-012)"


def mission_meta_pathspec(mission_slug: str) -> str:
    """Pathspec of the Mission's ``meta.json`` (the file a Mission is created with)."""
    return f":(literal)kitty-specs/{mission_slug}/meta.json"


def mission_wp_tasks_pathspec(mission_slug: str) -> str:
    """Pathspec of the Mission's work package task files (``tasks/WP*.md``)."""
    return f":(glob)kitty-specs/{mission_slug}/tasks/WP*.md"


def _first_adding_commit(repo_root: Path, target_ref: str, pathspec: str) -> str | None:
    try:
        result = run_git(
            repo_root,
            "log",
            "--reverse",
            "--diff-filter=A",
            "--format=%H",
            "--end-of-options",
            target_ref,
            "--",
            pathspec,
        )
    except GitCommandError:
        return None
    lines = result.stdout.decode("ascii", "replace").split()
    return lines[0] if lines else None


def _parent_of(repo_root: Path, commit: str) -> str | None:
    result = run_git(repo_root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{commit}^1^{{commit}}", check=False)
    if result.returncode != 0:
        return None
    parent = result.stdout.decode("ascii", "replace").strip()
    return parent or None


def derive_base_before_first_add(repo_root: Path, target_ref: str, pathspec: str) -> str | None:
    """Parent of the first commit reachable from *target_ref* that added a path matching *pathspec*.

    Returns ``None`` when git cannot answer, when no commit added such a path, or when
    the adding commit is a root commit (it has no parent to stand in for a base).
    Never raises.
    """
    try:
        commit = _first_adding_commit(repo_root, target_ref, pathspec)
        if commit is None:
            return None
        return _parent_of(repo_root, commit)
    except GitCommandError:
        return None
