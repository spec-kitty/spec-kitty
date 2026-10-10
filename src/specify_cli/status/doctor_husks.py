"""Doctor check for workspace husks (#1833, FR-007).

A "husk" is an entry under ``.worktrees/`` that lacks a ``.git`` entry, so it
is not a usable git worktree: git commands run inside it silently walk up to
the primary repository. Once the fall-through-is-failure guards (Class D)
land, pre-existing husks start producing structured resolution errors — this
check makes operator recovery a single command:

    spec-kitty doctor workspaces        # report
    spec-kitty doctor workspaces --fix  # remove unregistered husks

Deletion safety (R5): ``--fix`` removes ONLY husks that are NOT registered in
``git worktree list``. A registered-but-broken worktree (e.g. its ``.git``
file was deleted) is never removed automatically; it is reported for manual
``git worktree repair`` / ``git worktree remove``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from specify_cli.git.destructive_guard import DestructiveOpRefused, guarded_tree_delete

__all__ = [
    "WORKTREES_DIRNAME",
    "RegisteredWorktreePaths",
    "WorkspaceHuskRegistrationError",
    "fix_workspace_husks",
    "registered_worktree_paths",
    "scan_workspace_husks",
]

WORKTREES_DIRNAME = ".worktrees"


@dataclass(frozen=True)
class HuskEntry:
    """One ``.worktrees/`` entry that lacks a ``.git`` entry."""

    path: str  # relative to repo root
    # True when `git worktree list` still registers the path; None when
    # registration state could not be read safely.
    registered: bool | None


@dataclass(frozen=True)
class HuskReport:
    """Scan result for the workspace husk check."""

    worktrees_dir: str
    husks: list[HuskEntry] = field(default_factory=list)
    registration_error: str | None = None

    @property
    def healthy(self) -> bool:
        return not self.husks and self.registration_error is None

    def to_dict(self) -> dict[str, object]:
        return {
            "worktrees_dir": self.worktrees_dir,
            "healthy": self.healthy,
            "registration_error": self.registration_error,
            "husks": [
                {"path": entry.path, "registered": entry.registered}
                for entry in self.husks
            ],
        }


@dataclass(frozen=True)
class HuskFixResult:
    """Outcome of ``--fix``: what was removed and what was preserved."""

    removed: list[str] = field(default_factory=list)
    skipped_registered: list[str] = field(default_factory=list)
    skipped_appeared_valid: list[str] = field(default_factory=list)
    # Husks the destructive guard refused to delete because they hold the only
    # copy of something (#5965): preserved in place for the operator to inspect.
    skipped_unsafe: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "removed": list(self.removed),
            "skipped_registered": list(self.skipped_registered),
            "skipped_appeared_valid": list(self.skipped_appeared_valid),
            "skipped_unsafe": list(self.skipped_unsafe),
        }


class _HuskResidue:
    """Residue context for a husk: it belongs to no known Mission, so nothing in it is regenerable.

    A husk whose ``.git`` entry is gone can still hold the only copy of a lane's
    work, so no path is disposable and the guard decides on local state alone.
    """

    def is_disposable(self, path: str) -> bool:  # noqa: ARG002 -- ResidueClassifier protocol signature
        return False

    def for_checkout(self, repo_root: Path, worktree: Path) -> _HuskResidue:  # noqa: ARG002 -- ResidueClassifier protocol signature
        return self


@dataclass(frozen=True)
class RegisteredWorktreePaths:
    paths: set[Path] = field(default_factory=set)
    error: str | None = None


class WorkspaceHuskRegistrationError(RuntimeError):
    """Raised when husk registration state cannot be read safely."""


def registered_worktree_paths(repo_root: Path) -> RegisteredWorktreePaths:
    """Return resolved paths registered in ``git worktree list --porcelain``."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    registered: set[Path] = set()
    if result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit {result.returncode}"
        )
        return RegisteredWorktreePaths(
            error=f"git worktree list --porcelain failed: {detail}"
        )
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            raw = line[len("worktree "):].strip()
            try:
                registered.add(Path(raw).resolve())
            except OSError:
                continue
    return RegisteredWorktreePaths(paths=registered)


def scan_workspace_husks(repo_root: Path) -> HuskReport:
    """List ``.worktrees/*`` directories lacking a ``.git`` entry.

    Each husk is annotated with whether ``git worktree list`` still registers
    it (registered husks need manual ``git worktree repair``/``remove``).
    """
    worktrees_dir = repo_root / WORKTREES_DIRNAME
    report = HuskReport(worktrees_dir=str(worktrees_dir))
    if not worktrees_dir.is_dir():
        return report

    registered = registered_worktree_paths(repo_root)
    husks: list[HuskEntry] = []
    for entry in sorted(worktrees_dir.iterdir(), key=lambda path: path.name):
        if not entry.is_dir():
            continue
        if (entry / ".git").exists():
            continue
        husks.append(
            HuskEntry(
                path=str(entry.relative_to(repo_root)),
                registered=None
                if registered.error is not None
                else entry.resolve() in registered.paths,
            )
        )
    return HuskReport(
        worktrees_dir=str(worktrees_dir),
        husks=husks,
        registration_error=registered.error,
    )


def fix_workspace_husks(repo_root: Path) -> tuple[HuskReport, HuskFixResult]:
    """Remove unregistered husks; never touch registered worktrees (R5).

    Returns the pre-fix report plus the fix outcome.
    """
    report = scan_workspace_husks(repo_root)
    if report.registration_error is not None:
        raise WorkspaceHuskRegistrationError(report.registration_error)
    removed: list[str] = []
    skipped_registered: list[str] = []
    skipped_appeared_valid: list[str] = []
    skipped_unsafe: list[str] = []
    for entry in report.husks:
        if entry.registered:
            skipped_registered.append(entry.path)
            continue
        husk_path = repo_root / entry.path
        if (husk_path / ".git").exists():
            skipped_appeared_valid.append(entry.path)
            continue
        try:
            guarded_tree_delete(husk_path, context=_HuskResidue())
        except DestructiveOpRefused:
            skipped_unsafe.append(entry.path)
            continue
        removed.append(entry.path)
    return report, HuskFixResult(
        removed=removed,
        skipped_registered=skipped_registered,
        skipped_appeared_valid=skipped_appeared_valid,
        skipped_unsafe=skipped_unsafe,
    )
