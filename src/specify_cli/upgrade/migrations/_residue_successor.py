"""Shared plumbing for the residue-safe successor migrations (#6669).

Private, non-migration module (no ``m_`` prefix, so auto-discovery never
imports it as a migration; it registers nothing). It gives each successor one
copy of the predecessor-settled check and the ``kitty-specs/`` residue walk.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git import GitCommandError

from specify_cli.context.mission_resolver import (
    is_kitty_specs_residue,
    residue_notice,
    tracked_mission_paths,
)

from ..registry import settled_in_selection_view


def predecessor_settled(project_path: Path, predecessor_id: str) -> bool:
    """True when *predecessor_id* is settled in the selection view of *project_path* (#6669)."""
    return settled_in_selection_view(project_path, predecessor_id)


def _probe_tracked(checkout_root: Path) -> frozenset[str] | None:
    """Probe the tracked paths once; unusable git (not a timeout) means file-presence mode (#6669)."""
    try:
        tracked: frozenset[str] | None = tracked_mission_paths(checkout_root)
    except GitCommandError as exc:
        if exc.timed_out:
            raise
        return None
    return tracked


def partition_kitty_specs(kitty_specs: Path, checkout_root: Path) -> tuple[list[Path], list[Path]]:
    """Walk the children of *kitty_specs* once and split them into ``(missions, residue)`` (#6669).

    Both lists are sorted. A missing *kitty_specs* returns ``([], [])``.
    """
    if not kitty_specs.is_dir():
        return [], []
    tracked = _probe_tracked(checkout_root)
    missions: list[Path] = []
    residue: list[Path] = []
    for child in sorted(kitty_specs.iterdir()):
        if not child.is_dir():
            continue
        if is_kitty_specs_residue(child, repo_root=checkout_root, tracked=tracked):
            residue.append(child)
        else:
            missions.append(child)
    return missions, residue


def residue_warnings(residue: list[Path], project_path: Path) -> list[str]:
    """One residue notice per folder, naming its project-relative POSIX path (#6669)."""
    return [residue_notice(folder.relative_to(project_path).as_posix()) for folder in residue]
