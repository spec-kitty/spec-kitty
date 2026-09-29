"""The lane work-tip ref (#5115, ``contracts/lane-work-tip.md``).

Every lane commit's SHA is recorded in a hidden, never-pushed git ref --
``refs/spec-kitty/lane-tip/<full-lane-branch-name>`` -- so a destroyed lane's
committed work stays detectable (and recoverable) after its branch, worktree
and :class:`~specify_cli.workspace.context.WorkspaceContext` record are all
gone. See ``research.md`` R-6 for why a git ref rather than a
``WorkspaceContext`` field: the context is deleted by ``context cleanup``
(fail-open trap), a Python-hook write costs ~1.3s (blows NFR-001), and only a
ref survives branch/worktree deletion while keeping the commits reachable
through ``gc``.

Plan.md Minors: this module must NEVER import ``consolidation.*`` -- the
merge-tree absorption probe (:func:`is_absorbed`) is self-contained here,
reusing the *approach* (not the code) of the version probe at
``consolidation/reconciliation.py``/``consolidation/git_probes.py``.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

__all__ = [
    "AbsorptionUnsupported",
    "clear_tip",
    "is_absorbed",
    "read_tip",
    "record_tip",
    "record_tip_for_wp",
    "tip_ref",
]

_LANE_TIP_REF_PREFIX = "refs/spec-kitty/lane-tip/"

#: ``git merge-tree --write-tree`` (used by :func:`is_absorbed`'s squash leg)
#: is only available from git 2.38 onward. Mirrors
#: ``consolidation/git_probes.py``'s ``_MERGE_TREE_WRITE_TREE_MIN_VERSION``
#: without importing that module (plan.md Minors).
_MERGE_TREE_MIN_GIT: tuple[int, int] = (2, 38)
_GIT_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


class AbsorptionUnsupported(Exception):
    """Raised by :func:`is_absorbed` when the installed git cannot evaluate absorption.

    ``git merge-tree --write-tree`` needs git >= 2.38. Callers must fail
    CLOSED on this (refuse), never treat "cannot evaluate" as "absorbed".
    """


def tip_ref(branch: str) -> str:
    """Return the hidden ref name that records ``branch``'s lane work tip."""
    return f"{_LANE_TIP_REF_PREFIX}{branch}"


def record_tip(repo_root: Path, branch: str, sha: str | None = None) -> str | None:
    """Write the lane-tip ref for ``branch``, returning the recorded SHA.

    Uses ``branch``'s current HEAD (via ``git rev-parse --verify
    refs/heads/<branch>``) when ``sha`` is omitted. Returns ``None`` (a no-op
    -- nothing is written) when ``branch`` does not resolve to a local
    branch and no explicit ``sha`` was supplied: there is nothing to record.
    """
    resolved = sha
    if resolved is None:
        rev = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if rev.returncode != 0:
            return None
        resolved = rev.stdout.strip()

    subprocess.run(
        ["git", "update-ref", tip_ref(branch), resolved],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return resolved


def record_tip_for_wp(repo_root: Path, mission_slug: str, wp_id: str) -> None:
    """Best-effort: record the current lane tip for ``wp_id``'s CODE lane.

    Called from the two for_review transition surfaces that do not always
    auto-commit -- ``agent status emit`` and the orchestrator ``transition``
    command (T032, #5115 review cycle 2 Issue 2). Under a foreign
    post-commit hook (C-010 skip), those transitions are the only chance to
    record a lane's tip before some later touch (``move-task``, self-heal
    re-entry); without this call the tip stays at the FRESH fork point
    (``== base``), which the destroyed-lane guard would then misread as
    "absorbed" and silently re-cut an empty lane over real,
    for_review-ready committed work -- exactly the #5115 failure mode.

    Never raises and never fails the transition it is called from: a
    missing/unreadable lanes manifest, a planning (repo-root) lane, or a
    branch that does not currently resolve are all treated as "nothing to
    record" and swallowed. Delegates to :func:`record_tip` with ``sha=None``,
    so only the branch's CURRENT HEAD is ever written -- this can never move
    the tip backwards.
    """
    try:
        from mission_runtime import MissionArtifactKind, placement_seam

        from specify_cli.lanes.branch_naming import code_lane_branch_name
        from specify_cli.lanes.compute import is_planning_lane
        from specify_cli.lanes.persistence import read_lanes_json

        planning_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
        manifest = read_lanes_json(planning_dir)
        if manifest is None:
            return
        lane = manifest.lane_for_wp(wp_id)
        if lane is None or is_planning_lane(lane):
            return
        branch = code_lane_branch_name(mission_slug, lane.lane_id)
    except Exception:  # noqa: BLE001 -- best-effort recording must never fail a transition
        return
    record_tip(repo_root, branch)


def read_tip(repo_root: Path, branch: str) -> str | None:
    """Return the recorded lane-tip SHA for ``branch``, or ``None`` if unrecorded."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", tip_ref(branch)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def clear_tip(repo_root: Path, branch: str) -> None:
    """Delete the recorded lane-tip ref for ``branch``. A no-op when already absent."""
    subprocess.run(
        ["git", "update-ref", "-d", tip_ref(branch)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )


def _git_supports_merge_tree_write_tree(repo_root: Path) -> bool:
    """Probe the installed git for ``merge-tree --write-tree`` support (>= 2.38).

    Probed via ``git --version`` rather than invoking the flag itself (mirrors
    ``consolidation/git_probes.py::merge_tree_write_tree_available``'s
    rationale, reimplemented here without importing it -- plan.md Minors). A
    failing ``git --version``, or output with no recognizable ``X.Y[.Z]``
    version, is treated as unavailable -- fail-closed.
    """
    result = subprocess.run(["git", "--version"], cwd=str(repo_root), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return False
    match = _GIT_VERSION_PATTERN.search(result.stdout or "")
    if not match:
        return False
    version = (int(match.group(1)), int(match.group(2)))
    return version >= _MERGE_TREE_MIN_GIT


def _merge_tree_no_op(repo_root: Path, target: str, tip: str) -> bool:
    """Return True iff merging ``tip`` into ``target`` is a squash-absorbed no-op.

    Runs ``git merge-tree --write-tree <target> <tip>``:

    * exit 0 (clean) and the produced tree equals ``target^{tree}`` -> True
      (every hunk ``tip`` carries is already present in ``target``, e.g. a
      squash-merge landed it and the lane was then destroyed);
    * exit 0 but a DIFFERENT tree, or exit 1 (conflict) -> False (real,
      un-landed work, or a conflicting divergence -- contract: "conflict
      means not absorbed");
    * any other exit status -> :class:`AbsorptionUnsupported` (an
      unrecognized git behavior, treated the same as an old git rather than
      silently guessing).
    """
    merge_tree = subprocess.run(
        ["git", "merge-tree", "--write-tree", target, tip],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if merge_tree.returncode == 1:
        return False
    if merge_tree.returncode != 0:
        raise AbsorptionUnsupported(f"git merge-tree --write-tree returned unrecognized exit status {merge_tree.returncode}")

    produced_tree = merge_tree.stdout.strip().splitlines()[0] if merge_tree.stdout.strip() else ""
    target_tree = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{target}^{{tree}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if target_tree.returncode != 0:
        raise AbsorptionUnsupported(f"cannot resolve target tree for {target!r} to compare absorption")
    return produced_tree == target_tree.stdout.strip()


def is_absorbed(repo_root: Path, tip: str, target: str, base: str | None) -> bool:
    """Return True iff ``tip``'s committed work has already landed in ``target``.

    Checked in order (contract ``lane-work-tip.md``):

    1. ``tip == base`` -- no work was ever committed beyond the lane's
       creation base (the control case: nothing to strand).
    2. ``git merge-base --is-ancestor tip target`` -- a real (non-squash)
       merge already carried ``tip`` into ``target``.
    3. ``git merge-tree --write-tree target tip`` produces a tree equal to
       ``target^{tree}`` -- squash-absorbed: every hunk is already present,
       just under different commit(s).

    ``base`` may be ``None`` (e.g. the lane's ``WorkspaceContext`` record was
    deleted and no creation base is known) -- leg 1 is then simply skipped,
    never a false match.

    Raises:
        AbsorptionUnsupported: the installed git cannot run ``git merge-tree
            --write-tree`` (< 2.38, or unrecognized behavior). Callers fail
            CLOSED on this (refuse), never treat "unsupported" as "absorbed".
    """
    if base is not None and tip == base:
        return True

    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", tip, target],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if ancestor.returncode == 0:
        return True

    if not _git_supports_merge_tree_write_tree(repo_root):
        raise AbsorptionUnsupported(f"git merge-tree --write-tree needs git >= {_MERGE_TREE_MIN_GIT[0]}.{_MERGE_TREE_MIN_GIT[1]}")

    return _merge_tree_no_op(repo_root, target, tip)
