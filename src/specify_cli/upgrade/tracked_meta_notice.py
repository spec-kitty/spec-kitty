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

from kernel.git_anchor import UNRESOLVABLE_START_REASON, GitAnchor
from specify_cli.mission_metadata import TrackedMeta, UnreadableReason, read_tracked_meta


def _restore_command(path: str) -> str:
    """The file-restore remedy for notices whose tracked-state diagnostics support it.

    Rendered by the one home of destructive git advice (#3931, #7178). The import is deferred
    because ``specify_cli.cli.commands`` imports the whole command surface, which would cycle
    through ``upgrade`` at module load.
    """
    from specify_cli.cli.commands._git_remedies import checkout_file_recipe

    return checkout_file_recipe([path])


#: Stable codes of a refusal, printed in its notice and carried in ``BackfillResult.reason``.
CODE_UNAVAILABLE = "TRACKED_META_UNAVAILABLE"
CODE_STAGED_DIFFERS = "TRACKED_META_STAGED_DIFFERS"

_LEAD_ABSENT = "is missing from the working tree"
_LEAD_NO_IDENTITY = "has lost its mission_id"

#: What actually repairs each reason git could not answer (#7131). Each one says the tracked state
#: is *unknown* (git never established that the path is tracked), names the repair class, and rules
#: out the restore remedy: `git checkout -- <path>` fails for the same reason the read failed.
_UNREADABLE_TAIL: dict[UnreadableReason, str] = {
    "ownership": (
        "git reports an ownership-trust refusal for this checkout, so whether it is tracked here is "
        "unknown and no identity was minted — trusting the repository is an explicit operator decision, scoped to "
        "this checkout only (name that exact path in `safe.directory`, never `*`), and no file restore can "
        "succeed until git answers"
    ),
    "repository": (
        "git cannot identify a repository here (an unreadable or garbled `.git` marker, or a `GIT_DIR`/"
        "`GIT_WORK_TREE` naming elsewhere), so whether it is tracked is unknown and no identity was minted — "
        "repair the repository layout or environment first (`git status` in the checkout reports the cause), "
        "because no file restore can succeed until git answers"
    ),
    "objects": (
        "git could not read the committed content for it from this repository (for example, a missing or corrupt "
        "object, an unreadable ref, or an incomplete clone), so whether it is tracked is unknown and no identity "
        "was minted — check repository and object-store access first (`git fsck` can help diagnose the failure), "
        "because no file restore can succeed until git answers"
    ),
}

#: The tail for a git that could not be started while a repository sits above the folder (#7262).
_GIT_NOT_RUN_TAIL = (
    "git could not be started here (it is not installed, or this folder cannot be its working directory) while "
    "`{anchor}` is a repository above it, so whether it is tracked is unknown and no identity was minted — make git "
    "runnable here, then re-run"
)

#: The tail for a `.git` the classifier could not rule out (#7262). It names that `.git` and both real repairs,
#: and never tells the operator to delete it blindly: a repository that lost its `HEAD` still holds history.
_ANCHOR_TAIL = (
    "`{anchor}` is {why}: this check can neither confirm it as a repository nor rule it out as harmless residue, so whether it is "
    "tracked is unknown and no identity was minted — if it is a repository, repair it (for example restore its "
    "`HEAD`); if it is leftover residue that holds nothing you need, remove it; then re-run"
)

#: The tail for a folder whose own path cannot be resolved (#7262): the cause is the path, not a `.git`.
_UNRESOLVED_START_TAIL = (
    "the folder `{folder}` cannot be resolved (for example a symbolic-link loop in its path), so whether it is tracked "
    "is unknown and no identity was minted — fix that path, then re-run"
)

#: The tail for an explicit git redirect in the environment (#7262): the names on disk cannot rule out the store it selects.
_REDIRECT_TAIL = (
    "{why} and git could not answer, so whether it is tracked is unknown and no identity was minted — if that override "
    "is unintended, correct or unset it for this command; otherwise repair the repository it selects, then re-run"
)


@dataclass(frozen=True)
class MissingTrackedMeta:
    """What to tell the operator about one Mission whose working-tree ``meta.json`` is absent.

    ``refuse`` is True when the seam must not repair the folder: git knows the path but
    the content cannot be used, so any ``meta.json`` written for it would be a fabricated
    identity (#6673). ``notice`` is the single operator-facing line for both cases: the
    reason git could not produce a copy, and the repair that actually applies (#7131).
    ``code`` is the refusal's stable code (``None`` for a usable copy), also printed at the
    end of the notice.
    """

    notice: str
    refuse: bool
    code: str | None = None


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
        content cannot be read, or when git could not answer for the repository at all
        (#7131) — the notice then names the repair class instead of a file restore — or
        ``refuse=False`` when git holds a usable copy that the seam is about to rebuild
        the file from.
    """
    if (feature_dir / "meta.json").exists():
        return None
    tracked: TrackedMeta = read_tracked_meta(feature_dir)
    if tracked.unavailable:
        return _refusal(_display_path(feature_dir, repo_root), tracked, _LEAD_ABSENT, repo_root)
    if tracked.meta is None:
        return None
    return MissingTrackedMeta(_restore_notice(_display_path(feature_dir, repo_root)), refuse=False)


def tracked_meta_refusal(feature_dir: Path, repo_root: Path, tracked: TrackedMeta) -> MissingTrackedMeta | None:
    """The refusal for a present ``meta.json`` that lost its ``mission_id`` while git's copy cannot supply one (#6673).

    *tracked* is the caller's own :func:`~specify_cli.mission_metadata.read_tracked_meta` answer.
    ``None`` when git can supply the identity or holds nothing for the path (a pre-identity Mission).

    A caller inside an ``if tracked.unavailable:`` guard therefore always holds a refusal, and may
    state that as an assertion rather than re-testing for ``None`` (pythonbugs:S2583, #7113). A
    caller outside that guard must still branch on the ``None``.
    """
    if not tracked.unavailable:
        return None
    return _refusal(_display_path(feature_dir, repo_root), tracked, _LEAD_NO_IDENTITY, repo_root)


def _refusal(path: str, tracked: TrackedMeta, lead: str, repo_root: Path) -> MissingTrackedMeta:
    """The coded refusal for a tracked copy git cannot give back."""
    code = CODE_STAGED_DIFFERS if tracked.staged_differs else CODE_UNAVAILABLE
    return MissingTrackedMeta(f"{_refusal_notice(path, tracked, lead, repo_root)} [{code}]", refuse=True, code=code)


def _restore_notice(path: str) -> str:
    """The notice for a usable tracked copy that a seam is rebuilding the file from."""
    return f"{path}: tracked meta.json is missing from the working tree; its identity comes from the copy git holds (restore yours with `{_restore_command(path)}`)"


def _refusal_notice(path: str, tracked: TrackedMeta, lead: str, repo_root: Path) -> str:
    """The notice for a tracked copy git cannot give back, naming the real reason and the repair."""
    if tracked.unreadable_reason == "anchor" and tracked.anchor is not None:
        return f"{path}: meta.json {lead} and {_anchor_tail(tracked.anchor, repo_root)}"
    if tracked.unreadable_reason == "git-not-run" and tracked.anchor is not None and tracked.anchor.path is not None:
        return f"{path}: meta.json {lead} and {_GIT_NOT_RUN_TAIL.format(anchor=_shown(tracked.anchor.path, repo_root))}"
    if tracked.unreadable_reason is not None:
        # Git never answered, so the subject is not "tracked meta.json": whether the path is
        # tracked is exactly what could not be established (#7131).
        tail = _UNREADABLE_TAIL.get(tracked.unreadable_reason, _UNREADABLE_TAIL["repository"])
        return f"{path}: meta.json {lead} and {tail}"
    if tracked.staged_differs:
        return (
            f"{path}: meta.json {lead} and the index copy differs from the committed one (a staged edit); "
            f"no identity was minted and your staged edit was not discarded — commit it, or unstage it with "
            f"`git restore --staged {path}`, then restore the file with `{_restore_command(path)}`"
        )
    if tracked.index_only:
        return (
            f"{path}: meta.json {lead} and git holds it only in the index (not committed); "
            f"no identity was minted — restore it with `{_restore_command(path)}` and commit it"
        )
    if tracked.corrupt:
        # `git checkout -- <path>` would restore the same unusable bytes, so it is not the repair here.
        return (
            f"{path}: tracked meta.json {lead} and the committed copy is not a JSON object; "
            f"no identity was minted — repair the committed copy (`git show HEAD:{path}` shows it), commit the fix, "
            f"then restore it with `{_restore_command(path)}`"
        )
    return f"{path}: tracked meta.json {lead} and git could not produce its content; no identity was minted — restore it with `{_restore_command(path)}`"


def _anchor_tail(anchor: GitAnchor, repo_root: Path) -> str:
    """The repair tail for a `.git` the classifier could not rule out, naming that `.git` (#7262)."""
    if anchor.path is None:
        return _REDIRECT_TAIL.format(why=anchor.reason)
    if anchor.reason == UNRESOLVABLE_START_REASON:
        return _UNRESOLVED_START_TAIL.format(folder=_shown(anchor.path, repo_root))
    return _ANCHOR_TAIL.format(anchor=_shown(anchor.path, repo_root), why=anchor.reason)


def _shown(path: Path, repo_root: Path) -> str:
    """*path* relative to *repo_root* (POSIX), or absolute when it is not below it."""
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _display_path(feature_dir: Path, repo_root: Path) -> str:
    """*feature_dir*'s path relative to *repo_root* (POSIX), or the absolute path when it is not below it."""
    try:
        return (feature_dir / "meta.json").relative_to(repo_root).as_posix()
    except ValueError:
        return (feature_dir / "meta.json").as_posix()
