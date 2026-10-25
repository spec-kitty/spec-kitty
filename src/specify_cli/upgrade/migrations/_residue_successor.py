"""Shared plumbing for the residue-safe successor migrations (#6669).

Private, non-migration module (no ``m_`` prefix, so auto-discovery never
imports it as a migration; it registers nothing). It gives each successor one
copy of the predecessor-settled check and the ``kitty-specs/`` residue walk.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.context.mission_resolver import (
    is_kitty_specs_residue,
    probe_tracked_mission_paths,
    residue_notice,
)
from specify_cli.core.constants import KITTY_SPECS_DIR

from ..registry import settled_in_selection_view

_WORKTREES_DIR = ".worktrees"


def predecessor_settled(project_path: Path, predecessor_id: str) -> bool:
    """True when *predecessor_id* is settled in the selection view of *project_path* (#6669)."""
    settled: bool = settled_in_selection_view(project_path, predecessor_id)
    return settled


def partition_kitty_specs(kitty_specs: Path, checkout_root: Path) -> tuple[list[Path], list[Path]]:
    """Walk the children of *kitty_specs* once and split them into ``(missions, residue)`` (#6669).

    Both lists are sorted. A missing *kitty_specs* returns ``([], [])``.
    """
    if not kitty_specs.is_dir():
        return [], []
    tracked = probe_tracked_mission_paths(checkout_root)
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


def partition_checkout_specs(project_path: Path) -> tuple[list[Path], list[Path]]:
    """Split every ``kitty-specs/`` child into ``(missions, residue)``, in the main checkout and each ``.worktrees/*`` one.

    A worktree's children are judged against that worktree as the checkout root.
    """
    main_specs = project_path / KITTY_SPECS_DIR
    missions, residue = partition_kitty_specs(main_specs, project_path)
    worktrees_dir = project_path / _WORKTREES_DIR
    if worktrees_dir.is_dir():
        for worktree in sorted(worktrees_dir.iterdir()):
            if not worktree.is_dir():
                continue
            wt_specs = worktree / KITTY_SPECS_DIR
            wt_missions, wt_residue = partition_kitty_specs(wt_specs, worktree)
            missions.extend(wt_missions)
            residue.extend(wt_residue)
    return missions, residue
