"""Which worktrees under ``.worktrees/`` ``spec-kitty upgrade`` may write (#7173).

``spec-kitty upgrade`` writes project-global state once, in the repository root
checkout. Two kinds of worktree under ``.worktrees/`` are treated differently:

* a **Mission worktree** (a ``kitty/mission-…`` mission, lane or coordination
  branch, or a detached HEAD) receives that state by integration and is never
  written (#5457, :func:`is_integrating_worktree`);
* every other worktree (an operator's own ``wip/…`` checkout, a landed branch
  left behind, ...) is written and committed **only when the operator opts it
  in**: ``--include-worktree PATH`` names one (repeatable), ``--all-worktrees``
  names them all. The default selects none (FR-007, FR-008).

:func:`worktree_dispositions` is the one rule both the preview and the run read,
so what the preview names is what the run does (FR-009, FR-010).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from specify_cli.core.constants import WORKTREES_DIR
from specify_cli.core.git_ops import get_current_branch
from specify_cli.lanes.branch_naming import parse_mission_slug_from_branch

#: The refusal code for a ``--include-worktree`` path that is not a worktree.
UPGRADE_WORKTREE_NOT_FOUND = "UPGRADE_WORKTREE_NOT_FOUND"


class SelectionMode(StrEnum):
    """How the operator selected non-Mission worktrees."""

    NONE = "none"
    NAMED = "named"
    ALL = "all"


@dataclass(frozen=True)
class WorktreeSelection:
    """The operator's opt-in for non-Mission worktrees; the default selects none."""

    mode: SelectionMode
    named: tuple[Path, ...] = ()

    @classmethod
    def none(cls) -> WorktreeSelection:
        return cls(mode=SelectionMode.NONE)

    @classmethod
    def all(cls) -> WorktreeSelection:
        return cls(mode=SelectionMode.ALL)

    @classmethod
    def named_paths(cls, paths: Iterable[Path]) -> WorktreeSelection:
        return cls(mode=SelectionMode.NAMED, named=tuple(paths))

    def selects(self, worktree: Path) -> bool:
        """Whether this selection opts ``worktree`` in (Mission rule not applied)."""
        if self.mode is SelectionMode.ALL:
            return True
        if self.mode is SelectionMode.NONE:
            return False
        resolved = worktree.resolve()
        return any(path.resolve() == resolved for path in self.named)

    def to_json(self, *, relative_to: Path | None = None) -> dict[str, object]:
        return {"mode": self.mode.value, "named": [_display_path(path, relative_to) for path in self.named]}


class DispositionAction(StrEnum):
    """What upgrade does with one worktree under ``.worktrees/``."""

    SKIP_MISSION = "skip_mission"
    SKIP_NOT_SELECTED = "skip_not_selected"
    UPGRADE = "upgrade"


@dataclass(frozen=True)
class WorktreeDisposition:
    """One worktree under ``.worktrees/`` and what upgrade does with it.

    ``git_worktree`` is False for a plain directory (no ``.git``), so its
    missing branch is never read as a detached HEAD. ``selectable`` is False for
    an entry that does not resolve in place to a direct child of
    ``.worktrees/`` (a symlink to elsewhere): no selection can opt it in, the
    same rule :func:`validate_named` applies. Neither field is in the JSON.
    """

    path: Path
    branch: str | None
    action: DispositionAction
    git_worktree: bool = True
    selectable: bool = True

    def to_json(self, *, relative_to: Path | None = None) -> dict[str, object]:
        return {"path": _display_path(self.path, relative_to), "branch": self.branch, "action": self.action.value}


class WorktreeOutcome(StrEnum):
    """What the worktree pass actually did with one worktree (FR-009, post-run)."""

    SKIPPED_MISSION = "skipped_mission"
    SKIPPED_NOT_SELECTED = "skipped_not_selected"
    UPGRADED_COMMITTED = "upgraded_committed"
    UPGRADED_NOT_COMMITTED = "upgraded_not_committed"
    NOTHING_TO_UPGRADE = "nothing_to_upgrade"
    WOULD_UPGRADE = "would_upgrade"
    FAILED = "failed"


@dataclass(frozen=True)
class WorktreeRunResult:
    """One worktree's disposition and what the run did with it."""

    disposition: WorktreeDisposition
    outcome: WorktreeOutcome

    @property
    def path(self) -> Path:
        return self.disposition.path


def initial_results(dispositions: Iterable[WorktreeDisposition]) -> dict[Path, WorktreeRunResult]:
    """Results before the pass runs: skips are final, a selected worktree has nothing yet."""
    out: dict[Path, WorktreeRunResult] = {}
    for disposition in dispositions:
        if disposition.action is DispositionAction.SKIP_MISSION:
            outcome = WorktreeOutcome.SKIPPED_MISSION
        elif disposition.action is DispositionAction.SKIP_NOT_SELECTED:
            outcome = WorktreeOutcome.SKIPPED_NOT_SELECTED
        else:
            outcome = WorktreeOutcome.NOTHING_TO_UPGRADE
        out[disposition.path] = WorktreeRunResult(disposition=disposition, outcome=outcome)
    return out


class UnknownWorktreeError(ValueError):
    """A ``--include-worktree`` path that is not a direct child of ``.worktrees/``."""

    code = UPGRADE_WORKTREE_NOT_FOUND

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"{UPGRADE_WORKTREE_NOT_FOUND}: {path} is not a worktree directory directly under {WORKTREES_DIR}/")


def _display_path(path: Path, relative_to: Path | None) -> str:
    if relative_to is None:
        return str(path)
    try:
        return path.resolve().relative_to(relative_to.resolve()).as_posix()
    except ValueError:
        return str(path)


def _branch_of(worktree: Path) -> str | None:
    if not (worktree / ".git").exists():
        return None
    branch: str | None = get_current_branch(worktree)
    return branch


def _is_direct_child(worktrees_dir_resolved: Path, candidate_resolved: Path) -> bool:
    return candidate_resolved.parent == worktrees_dir_resolved and candidate_resolved.is_dir()


def _resolves_in_place(worktrees_dir_resolved: Path, entry: Path) -> bool:
    """True when ``entry`` is itself a direct child of ``.worktrees/``, not a symlink to elsewhere."""
    return entry.resolve() == worktrees_dir_resolved / entry.name and _is_direct_child(worktrees_dir_resolved, entry.resolve())


def is_integrating_worktree(worktree: Path) -> bool:
    """Return True when ``worktree`` integrates back into its mission's target branch (#5457).

    An *integrating worktree* (a Mission worktree) receives project-global
    upgrade state (``.kittify/metadata.yaml``, ``.gitattributes``, ...) through
    integration and must never carry its own upgrade writes or upgrade commit,
    or every lane and coordination branch diverges on bookkeeping that
    ``consolidate`` and the lane auto-rebase then refuse.

    The rule:

    * no ``.git`` entry (a plain directory, not a git worktree): not
      integrating;
    * a branch that cannot be read (detached HEAD): integrating (fail safe);
    * otherwise integrating iff the branch is a mission, lane or coordination
      branch, as recognised by the branch-naming authority.
    """
    if not (worktree / ".git").exists():
        return False
    branch = get_current_branch(worktree)
    if branch is None:
        return True
    return parse_mission_slug_from_branch(branch) is not None


def worktree_dispositions(worktrees_dir: Path, selection: WorktreeSelection) -> list[WorktreeDisposition]:
    """Every directory under ``worktrees_dir`` with its disposition, in name order.

    A Mission (or detached) worktree is ``SKIP_MISSION`` whatever the
    selection. An entry that does not resolve in place to a direct child of
    ``.worktrees/`` (a symlink to elsewhere) is never selectable, matching
    :func:`validate_named`, so it is ``SKIP_NOT_SELECTED`` even under
    ``--all-worktrees``. Any other is ``UPGRADE`` when the selection opts it in
    and ``SKIP_NOT_SELECTED`` otherwise. Reads only; writes nothing.
    """
    if not worktrees_dir.is_dir():
        return []
    root = worktrees_dir.resolve()
    out: list[WorktreeDisposition] = []
    for worktree in sorted(worktrees_dir.iterdir(), key=lambda p: p.name):
        if not worktree.is_dir():
            continue
        selectable = _resolves_in_place(root, worktree)
        if is_integrating_worktree(worktree):
            action = DispositionAction.SKIP_MISSION
        elif selectable and selection.selects(worktree):
            action = DispositionAction.UPGRADE
        else:
            action = DispositionAction.SKIP_NOT_SELECTED
        out.append(
            WorktreeDisposition(
                path=worktree,
                branch=_branch_of(worktree),
                action=action,
                git_worktree=(worktree / ".git").exists(),
                selectable=selectable,
            )
        )
    return out


def validate_named(project_path: Path, named: Iterable[Path]) -> list[Path]:
    """Resolve each ``--include-worktree`` path, refusing one that is not a worktree.

    A path is absolute or relative to ``project_path`` and must resolve to an
    existing directory that is a direct child of ``<project>/.worktrees/``.
    Raises :class:`UnknownWorktreeError` naming the first path that does not.
    """
    worktrees_dir = (project_path / WORKTREES_DIR).resolve()
    resolved: list[Path] = []
    for path in named:
        candidate = (path if path.is_absolute() else project_path / path).resolve()
        if not _is_direct_child(worktrees_dir, candidate):
            raise UnknownWorktreeError(path)
        resolved.append(candidate)
    return resolved
