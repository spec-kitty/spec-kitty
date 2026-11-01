"""The one operator notice for a Mission whose tracked ``meta.json`` is missing from the working tree (#6673).

Three upgrade seams can write a ``meta.json`` for a ``kitty-specs/`` folder: the ``2.0.6``
consistency sweep's baseline repair, the ``3.2.0a4`` lifecycle normalization and the
``3.2.6rc1`` runtime-state cutover's phase flip. Each has to say the same thing about a
Mission whose ``meta.json`` git tracks but the working tree has lost, so the text lives
here once and no seam can drift into a second wording.

The classification is a pure read: it never writes, and it is safe to call for every
Mission of a walk before the first repair write (C-005 of the mission spec), so a git
failure surfaces before anything has been changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specify_cli.mission_metadata import TrackedMeta, read_tracked_meta

#: The one repair command every variant ends with.
_RESTORE = "git checkout -- {path}"


@dataclass(frozen=True)
class MissingTrackedMeta:
    """What to tell the operator about one Mission whose working-tree ``meta.json`` is absent.

    ``refuse`` is True when the seam must not repair the folder: git knows the path but
    the content cannot be used, so any ``meta.json`` written for it would be a fabricated
    identity (#6673). ``notice`` is the single operator-facing line for both cases.
    """

    notice: str
    refuse: bool


def classify_missing_tracked_meta(feature_dir: Path, repo_root: Path) -> MissingTrackedMeta | None:
    """Classify *feature_dir*'s missing ``meta.json``; ``None`` when there is nothing to report.

    ``None`` covers both "the working-tree copy is there" and "git holds nothing for the
    path" (a pre-identity Mission): in both cases the existing repair is correct and no
    notice is owed.

    Args:
        feature_dir: The Mission directory.
        repo_root: The checkout the operator runs the upgrade from, used only to print a
            project-relative path (the command must be copy-pasteable).

    Returns:
        ``MissingTrackedMeta(notice, refuse=True)`` when git knows the path but its
        content cannot be read, or ``refuse=False`` when git holds a usable copy that the
        seam is about to rebuild the file from.
    """
    if (feature_dir / "meta.json").exists():
        return None
    tracked: TrackedMeta = read_tracked_meta(feature_dir)
    if tracked.unavailable:
        return MissingTrackedMeta(_refusal_notice(_display_path(feature_dir, repo_root), tracked), refuse=True)
    if tracked.meta is None:
        return None
    return MissingTrackedMeta(_restore_notice(_display_path(feature_dir, repo_root)), refuse=False)


def _restore_notice(path: str) -> str:
    """The notice for a usable tracked copy that a seam is rebuilding the file from."""
    return (
        f"{path}: tracked meta.json is missing from the working tree; its identity comes from the copy git holds "
        f"(restore yours with `{_RESTORE.format(path=path)}`)"
    )


def _refusal_notice(path: str, tracked: TrackedMeta) -> str:
    """The notice for a tracked copy git cannot give back, naming the real reason and the repair."""
    if tracked.staged_differs:
        return (
            f"{path}: meta.json is missing from the working tree and the index copy differs from the committed one (a staged edit); "
            f"no identity was minted and your staged edit was not discarded — commit it, or unstage it with "
            f"`git restore --staged {path}`, then restore the file with `{_RESTORE.format(path=path)}`"
        )
    if tracked.index_only:
        return (
            f"{path}: meta.json is missing from the working tree and git holds it only in the index (not committed); "
            f"no identity was minted — restore it with `{_RESTORE.format(path=path)}` and commit it"
        )
    if tracked.corrupt:
        # `git checkout -- <path>` would restore the same unusable bytes, so it is not the repair here.
        return (
            f"{path}: tracked meta.json is missing from the working tree and the committed copy is not a JSON object; "
            f"no identity was minted — repair the committed copy (`git show HEAD:{path}` shows it), commit the fix, "
            f"then restore it with `{_RESTORE.format(path=path)}`"
        )
    return (
        f"{path}: tracked meta.json is missing from the working tree and git could not produce its content; "
        f"no identity was minted — restore it with `{_RESTORE.format(path=path)}`"
    )


def _display_path(feature_dir: Path, repo_root: Path) -> str:
    """*feature_dir*'s path relative to *repo_root* (POSIX), or the absolute path when it is not below it."""
    try:
        return (feature_dir / "meta.json").relative_to(repo_root).as_posix()
    except ValueError:
        return (feature_dir / "meta.json").as_posix()
