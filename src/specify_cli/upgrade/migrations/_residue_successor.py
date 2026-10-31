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
from .base import BaseMigration, MigrationResult

_WORKTREES_DIR = ".worktrees"


class ResidueProbes:
    """One git probe per checkout root, shared by every residue decision of one detect or apply (#6669).

    A successor that subclasses a shipped walker decides residue per folder through
    overridden predicates. Without this cache each folder would probe git again, and a
    git timeout would surface only after earlier folders had been repaired. Priming the
    cache (``partition_checkout_specs(project, probes)``) before the first write makes a
    timeout abort the run with nothing moved. A fresh instance per detect/apply keeps the
    answer from outliving the tree it was probed on.
    """

    def __init__(self) -> None:
        self._by_root: dict[Path, frozenset[str] | None] = {}

    def tracked(self, checkout_root: Path) -> frozenset[str] | None:
        """The ``tracked=`` set of *checkout_root*, probed on first use."""
        if checkout_root not in self._by_root:
            self._by_root[checkout_root] = probe_tracked_mission_paths(checkout_root)
        return self._by_root[checkout_root]

    def is_residue(self, folder: Path) -> bool:
        """Whether the ``kitty-specs/`` child *folder* is residue, judged against its own checkout."""
        root = folder.parent.parent
        return bool(is_kitty_specs_residue(folder, repo_root=root, tracked=self.tracked(root)))


def partition_kitty_specs(
    kitty_specs: Path,
    checkout_root: Path,
    probes: ResidueProbes | None = None,
) -> tuple[list[Path], list[Path]]:
    """Walk the children of *kitty_specs* once and split them into ``(missions, residue)`` (#6669).

    Both lists are sorted. A missing *kitty_specs* returns ``([], [])``. *probes*, when
    given, supplies (and keeps) the git probe of *checkout_root*.
    """
    if not kitty_specs.is_dir():
        return [], []
    tracked = probes.tracked(checkout_root) if probes is not None else probe_tracked_mission_paths(checkout_root)
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


def partition_checkout_specs(project_path: Path, probes: ResidueProbes | None = None) -> tuple[list[Path], list[Path]]:
    """Split every ``kitty-specs/`` child into ``(missions, residue)``, in the main checkout and each ``.worktrees/*`` one.

    A worktree's children are judged against that worktree as the checkout root. One probe per
    checkout (through *probes* when given).
    """
    main_specs = project_path / KITTY_SPECS_DIR
    missions, residue = partition_kitty_specs(main_specs, project_path, probes)
    worktrees_dir = project_path / _WORKTREES_DIR
    if worktrees_dir.is_dir():
        for worktree in sorted(worktrees_dir.iterdir()):
            if not worktree.is_dir():
                continue
            wt_specs = worktree / KITTY_SPECS_DIR
            wt_missions, wt_residue = partition_kitty_specs(wt_specs, worktree, probes)
            missions.extend(wt_missions)
            residue.extend(wt_residue)
    return missions, residue


class ResidueSafeLaneSuccessorMixin(BaseMigration):
    """The ``detect`` / ``apply`` wrappers shared by the subclassing 0.9.x successors (#6669).

    Listed first in the bases, before the shipped class, so ``super()`` here reaches the
    shipped walk. The successor keeps its per-folder overrides, which call :meth:`_is_residue`.
    ``predecessor_id`` (``BaseMigration``'s) names the superseded predecessor whose settlement
    makes the successor inert and whose unsettled outcome reopens the retry (#6688).
    """

    _probes: ResidueProbes | None = None

    def _is_residue(self, feature_path: Path) -> bool:
        """Residue decision through this run's probe cache (one git probe per checkout); uncached outside detect/apply."""
        if self._probes is None:
            return bool(is_kitty_specs_residue(feature_path))
        return self._probes.is_residue(feature_path)

    def detect(self, project_path: Path) -> bool:
        if settled_in_selection_view(project_path, self.predecessor_id):
            return False
        self._probes = ResidueProbes()
        try:
            return bool(super().detect(project_path))
        finally:
            self._probes = None

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        # Probe every checkout before the shipped walk moves a file: a git timeout then aborts with nothing moved.
        self._probes = ResidueProbes()
        try:
            _missions, residue = partition_checkout_specs(project_path, self._probes)
            result = super().apply(project_path, dry_run)
        finally:
            self._probes = None
        result.warnings.extend(residue_warnings(residue, project_path))
        return result
