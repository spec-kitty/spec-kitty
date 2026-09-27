"""Three-way recency for PRIMARY-partition planning artifacts on squash (#3942).

The mission→target squash merge (``lanes/merge.py`` ``_merge_branch_into``) runs
a normal three-way ``git merge --squash <mission_branch>`` (#4892 dropped the old
blanket ``-X theirs``). The six driver-covered ``kitty-specs/**`` bookkeeping
classes reconcile through ``_MERGE_DRIVERS``, and ordinary source conflicts now
fail closed. For PRIMARY-partition planning artifacts (``spec.md`` /
``tasks/WP*.md`` among them) a same-region conflict is instead resolved by this
recency policy: when planning is refined on the *target* after the mission branch
forks, the target-newer content must win rather than being clobbered by the older
mission copy (#3942).

A git merge driver cannot fix this: a driver sees only three blobs (base / ours /
theirs) and has no history access, so it cannot decide *which side is newer*.
Recency is a repository-history question. This module answers it purely (git
reads only, no writes / no side effects) so the executor can capture the target's
pre-squash bytes and restore them after the squash when the target is newer.

Three-way rule (D-A3): a changed PRIMARY-partition planning path is *target-newer*
when the target diverged from ``merge-base(target, source)`` on that path while
the lane copy is base-or-ancestor (the lane did not advance it). When *both*
sides advanced the same path, the tiebreak is the committer-date of the last
commit that touched the path on each side — target wins on a strictly-later date
**or a tie** (the conservative "do not clobber the target" default; never mtime).
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

from mission_runtime import is_primary_artifact_kind, kind_for_mission_file
from specify_cli.core.vcs.git import git_diff_names, git_merge_base

__all__ = ["target_newer_primary_artifacts"]


def _is_primary_planning_path(rel: str) -> bool:
    """True iff ``rel`` classifies to a PRIMARY-partition (planning) artifact kind.

    Driver-covered ``kitty-specs/**`` bookkeeping kinds return False here (they
    are not in the primary partition), so they are left to their merge drivers
    (FR-003).
    """
    kind = kind_for_mission_file(rel)
    return kind is not None and is_primary_artifact_kind(kind)


def _last_commit_committer_date(repo: Path, ref: str, rel: str) -> int | None:
    """Committer-date (Unix seconds) of the last commit touching ``rel`` on ``ref``.

    Returns ``None`` when the path has no commit reachable from ``ref`` or git
    exits non-zero. Never raises for a git non-zero exit.
    """
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", ref, "--", rel],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    return int(raw) if raw else None


def _target_wins_tiebreak(repo: Path, target_ref: str, source_ref: str, rel: str) -> bool:
    """Both sides advanced ``rel``: decide by last-commit committer-date.

    Target wins on a strictly-later date **or a tie** — the conservative
    "do not clobber the target" default. When one side has no committer-date
    (a rename/unresolvable side), prefer the side that does; when neither does,
    the target does not win.
    """
    target_ct = _last_commit_committer_date(repo, target_ref, rel)
    source_ct = _last_commit_committer_date(repo, source_ref, rel)
    if target_ct is None or source_ct is None:
        return target_ct is not None
    return target_ct >= source_ct


def target_newer_primary_artifacts(
    repo: Path,
    target_ref: str,
    source_ref: str,
    changed_paths: Iterable[str] | None = None,
) -> list[Path]:
    """Return the repo-relative PRIMARY-partition paths the *target* should keep.

    A path is returned when it is a PRIMARY-partition planning artifact that the
    target advanced since ``merge-base(target, source)`` and the lane copy is
    base-or-ancestor (case 1), or when both sides advanced it and the
    committer-date tiebreak favours the target (case 3). Lane-advanced-only paths
    (case 2) are NOT returned — the mission (lane) copy is correct there.

    Pure: reads git only (merge-base, per-side name diffs, last-commit dates); it
    never writes and has no side effects. ``changed_paths``, when supplied,
    restricts the candidate set (e.g. the executor's known squash surface);
    otherwise every target-side changed path is considered.
    """
    merge_base = git_merge_base(repo, target_ref, source_ref)
    if merge_base is None:
        return []
    target_changed = set(git_diff_names(repo, merge_base, target_ref))
    source_changed = set(git_diff_names(repo, merge_base, source_ref))

    candidates = target_changed if changed_paths is None else set(changed_paths)

    result: list[Path] = []
    for rel in sorted(candidates):
        if rel not in target_changed:
            # Target did not advance this path since the merge-base — it cannot
            # be "target-newer", so the squash result is authoritative.
            continue
        if not _is_primary_planning_path(rel):
            continue
        if rel not in source_changed:
            result.append(Path(rel))  # case 1: target advanced, lane stale.
            continue
        if _target_wins_tiebreak(repo, target_ref, source_ref, rel):
            result.append(Path(rel))  # case 3: both advanced, target newer.
    return result
