"""The Mission base: the one authority for "the commit this Mission branch was cut from" (#7560).

The *Mission base* is the commit the Mission branch started at. It is not the claim base
(:func:`specify_cli.consolidation.reconciliation_bound._bound_claim_base`), which is the
target branch's tip before a consolidation run, and it is not the lane creation base, which
sits above the planning and pre-implement Mission commits.

:func:`resolve_mission_base` answers it in a fixed order, and fails closed:

1. **recorded** -- ``meta.json`` ``mission_base_sha``, written once where the Mission branch
   is created (the topic/protected mint, or the coordination-branch create; the write helper
   is :func:`specify_cli.mission_metadata.record_mission_base_sha`). It is used only when it
   is a full lowercase object id (40 or 64 hex characters) equal to what ``rev-parse --verify
   <value>^{commit}`` prints (a branch name, ``HEAD``, a short sha or a tag object never
   is), names a commit in this clone that is an ancestor of, or equal to, the Mission's
   *origin* -- the first parent of the earliest first-parent commit adding
   ``kitty-specs/<slug>/`` (so neither a Mission commit nor a side branch merged into the
   Mission branch after it started qualifies; without an origin the value is not used) --
   and the Mission directory is not reachable from it (``git log -1 --full-history <base> --
   kitty-specs/<slug>/`` is empty: a base the Mission directory is reachable from sits at or
   above the Mission's start). Beyond those checks the recorded value is trusted as
   tool-written and write-once: a hand-edited value that still passes them is accepted
   (operator ruling, Decision Moment 01M78XBQS8NE8PPMSTZHMDJ610).
2. **derived** -- the first parent of the earliest commit on the Mission branch's first-parent
   spine that adds a file under ``kitty-specs/<slug>/`` (a merge commit is diffed against its
   first parent). Validated the same way (on the branch, Mission directory not reachable).
   When that commit brought the Mission directory in
   by a rename (``git mv kitty-specs/old kitty-specs/<slug>``), its first parent can sit
   above Mission work done under the old name, so the derivation fails closed to
   **unavailable**; it never follows the rename.
3. **unavailable** -- no base. Any git probe failure lands here too; a base is never guessed.

Residuals of the derived step: the derivation follows git's rename detection only (``-M``, no
copy detection). A copy that leaves its source in place (``cp -r kitty-specs/old
kitty-specs/<slug>``) cannot be told apart from an ordinary scaffold that resembles an older
Mission, so it is not detected; nor is a move edited past git's 50% similarity threshold, nor
a copy whose source is deleted in a later commit. In each case the derived base is the
copying commit's first parent, which can sit above work done under the old name; a recorded
base (step 1) is unaffected.

:func:`pre_mission_history` lists the commits reachable from the Mission base and not from a
window base (``rev-list <window_base>..<base>``).

Cost (NFR-002): the budget covers the recorded case only. There, resolving the base and its
pre-Mission history takes six git invocations: ``log`` (the earliest scaffold commit), a
parent read (the origin), ``rev-parse`` (the recorded commit is in the clone, under its own
full id), ``merge-base --is-ancestor`` (it is below the origin), ``log -1`` (the Mission
directory is not reachable from it) and ``rev-list`` (the range). The derived case reuses the
scaffold commit and origin and adds one rename-only ``diff`` of the scaffold commit
(``-M --diff-filter=R``; milliseconds even on a large tree, because only the paths the commit
deletes are rename sources), and the same validation probes. A probe failure costs one more
``rev-parse`` (does the Mission branch resolve at all). A non-empty pre-Mission range adds the
claim builder's Mission-work guard (one status-log read and one lane-tip listing).

The claim builder (:func:`specify_cli.consolidation.reconciliation_claim.build_approved_wp_set`)
calls it once per claim build; the pre-Mission history it yields is exempted on the closed-world,
squash and patch-id axes (#7560).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from kernel.git import GitCommandError, changed_entries
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    commit_in_clone,
    commit_parents,
    commits_in_range,
    is_ancestor_strict,
    resolve_commit,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.git_ops import run_command
from specify_cli.meta_keys import MISSION_BASE_SHA_KEY
from specify_cli.mission_metadata import load_meta_or_empty

__all__ = [
    "MissionBase",
    "MissionBaseProvenance",
    "MissionBaseReason",
    "pre_mission_history",
    "resolve_mission_base",
]

_SHORT = 12
# A recorded base is a full lowercase object id (SHA-1 or SHA-256), never a name or expression.
_FULL_OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class MissionBaseProvenance(StrEnum):
    """Where a :class:`MissionBase` came from."""

    RECORDED = "recorded"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class MissionBaseReason(StrEnum):
    """Why a step gave no Mission base: the typed twin of :attr:`MissionBase.reason`.

    Callers decide on this kind, never on the reason's text (which can carry git stderr).
    """

    NOT_RECORDED = "not_recorded"
    RECORDED_NOT_A_SHA = "recorded_not_a_sha"
    RECORDED_NOT_ON_BRANCH = "recorded_not_on_branch"
    RECORDED_NOT_BELOW_ORIGIN = "recorded_not_below_origin"
    ABOVE_MISSION_START = "above_mission_start"
    NO_SCAFFOLD = "no_scaffold"
    ROOT_SCAFFOLD = "root_scaffold"
    RENAMED_INTO = "renamed_into"
    DERIVED_NOT_ON_BRANCH = "derived_not_on_branch"
    MISSION_BRANCH_UNRESOLVED = "mission_branch_unresolved"
    PROBE_FAILED = "probe_failed"
    RANGE_HOLDS_MISSION_WORK = "range_holds_mission_work"


@dataclass(frozen=True)
class MissionBase:
    """The commit a Mission branch was cut from, with its provenance.

    ``sha`` is ``None`` exactly when ``provenance`` is ``UNAVAILABLE``. A non-``None`` ``sha``
    resolved to a commit that is an ancestor of (or equal to) the Mission branch tip.
    ``reason`` says, in one short clause, why the base is derived or unavailable; ``kind`` is
    the same answer typed (for a derived base: why the recorded step gave none; for an
    unavailable one: why the last step gave none). Both are ``None`` for a recorded base.
    """

    sha: str | None
    provenance: MissionBaseProvenance
    reason: str | None = None
    kind: MissionBaseReason | None = None


@dataclass(frozen=True)
class _Candidate:
    """One step's answer: a validated sha, or the reason (and its kind) it gave none."""

    sha: str | None
    reason: str | None = None
    kind: MissionBaseReason | None = None


def resolve_mission_base(
    repo_root: Path,
    feature_dir: Path | None,
    *,
    mission_branch: str,
    mission_slug: str,
) -> MissionBase:
    """Resolve the Mission base: recorded, else derived, else unavailable. Never raises on git.

    *feature_dir* holds the Mission's ``meta.json`` (``None`` skips the recorded step).
    *mission_branch* is the Mission branch (a ref git resolves in *repo_root*); *mission_slug*
    names the ``kitty-specs/<slug>/`` directory the derivation looks for.
    """
    try:
        scaffold = _earliest_scaffold_commit(repo_root, mission_branch, mission_slug)
        origin = _first_parent(repo_root, scaffold)
        recorded = _recorded_base(repo_root, feature_dir, mission_slug, origin)
        if recorded.sha is not None:
            return MissionBase(recorded.sha, MissionBaseProvenance.RECORDED)
        derived = _derived_base(repo_root, mission_branch, mission_slug, scaffold, origin)
    except GitProbeError as exc:
        return _probe_failure(repo_root, mission_branch, exc)
    if derived.sha is not None:
        return MissionBase(derived.sha, MissionBaseProvenance.DERIVED, recorded.reason, recorded.kind)
    return MissionBase(None, MissionBaseProvenance.UNAVAILABLE, _join_reasons(recorded.reason, derived.reason), derived.kind)


def _probe_failure(repo_root: Path, mission_branch: str, exc: GitProbeError) -> MissionBase:
    """The unavailable base for a failed probe: ``MISSION_BRANCH_UNRESOLVED`` when the branch itself is gone.

    Probes only after a failure (one ``rev-parse``), so a resolved base costs nothing extra.
    """
    try:
        resolve_commit(repo_root, mission_branch)
    except GitProbeError:
        return MissionBase(None, MissionBaseProvenance.UNAVAILABLE, "the Mission branch does not resolve", MissionBaseReason.MISSION_BRANCH_UNRESOLVED)
    return MissionBase(None, MissionBaseProvenance.UNAVAILABLE, f"git probe failed: {exc}", MissionBaseReason.PROBE_FAILED)


def pre_mission_history(repo_root: Path, window_base: str | None, base: MissionBase) -> tuple[str, ...]:
    """Commits reachable from the Mission base and not from the window base (``rev-list window_base..base``).

    Empty when the window base already reaches the Mission base, when *window_base* is ``None``,
    and when the base is unavailable. A :class:`GitProbeError` propagates, because an empty
    tuple would hide the error: the caller
    (:func:`~specify_cli.consolidation.reconciliation_closed_world._pre_mission_attribution`)
    degrades on it to today's bound (the base marked unavailable), which exempts nothing.
    """
    if window_base is None or base.sha is None:
        return ()
    return tuple(commits_in_range(repo_root, window_base, base.sha))


def _first_parent(repo_root: Path, commit: str | None) -> str | None:
    """*commit*'s first parent, ``None`` for no commit or a root commit."""
    if commit is None:
        return None
    parents = commit_parents(repo_root, commit)
    return parents[0] if parents else None


def _recorded_base(repo_root: Path, feature_dir: Path | None, mission_slug: str, origin: str | None) -> _Candidate:
    """Step 1: the ``meta.json`` value, when it is a commit on the history the Mission started from.

    *origin* is the first parent of the Mission's earliest first-parent scaffold commit. The
    recorded base must be an ancestor of (or equal to) it: a commit on a side branch merged into
    the Mission branch after it started, or any Mission commit, is not. Without an origin the
    recorded value cannot be anchored and is not used (fail-closed).
    """
    if feature_dir is None:
        return _Candidate(None, "no meta.json to read", MissionBaseReason.NOT_RECORDED)
    value = load_meta_or_empty(feature_dir).get(MISSION_BASE_SHA_KEY)
    if not isinstance(value, str) or not value.strip():
        return _Candidate(None, f"no {MISSION_BASE_SHA_KEY} recorded", MissionBaseReason.NOT_RECORDED)
    sha = value.strip()
    if not _FULL_OBJECT_ID.fullmatch(sha):
        return _Candidate(None, f"recorded {MISSION_BASE_SHA_KEY} {sha[:_SHORT]!r} is not a full commit id", MissionBaseReason.RECORDED_NOT_A_SHA)
    resolved = _commit_id_in_clone(repo_root, sha)
    if resolved is not None and resolved != sha:
        return _Candidate(None, f"recorded {MISSION_BASE_SHA_KEY} {sha[:_SHORT]!r} is not a full commit id", MissionBaseReason.RECORDED_NOT_A_SHA)
    if resolved is None:
        return _Candidate(None, f"recorded {MISSION_BASE_SHA_KEY} {sha[:_SHORT]} is not on the Mission branch", MissionBaseReason.RECORDED_NOT_ON_BRANCH)
    if origin is None or not is_ancestor_strict(repo_root, sha, origin):
        return _Candidate(
            None,
            f"recorded {MISSION_BASE_SHA_KEY} {sha[:_SHORT]} is not on the history the Mission started from",
            MissionBaseReason.RECORDED_NOT_BELOW_ORIGIN,
        )
    return _below_mission_start(repo_root, sha, mission_slug, f"recorded {MISSION_BASE_SHA_KEY}")


def _derived_base(repo_root: Path, mission_branch: str, mission_slug: str, scaffold: str | None, base: str | None) -> _Candidate:
    """Step 2: *base*, the first parent of *scaffold* (the earliest first-parent commit adding ``kitty-specs/<slug>/``)."""
    if scaffold is None:
        return _Candidate(None, f"no commit on the Mission branch's first-parent history adds {KITTY_SPECS_DIR}/{mission_slug}/", MissionBaseReason.NO_SCAFFOLD)
    if base is None:
        return _Candidate(None, f"the Mission's first commit {scaffold[:_SHORT]} is a root commit", MissionBaseReason.ROOT_SCAFFOLD)
    arrived = _renamed_into(repo_root, base, scaffold, mission_slug)
    if arrived is not None:
        return _Candidate(
            None,
            f"the Mission's first commit {scaffold[:_SHORT]} brought {KITTY_SPECS_DIR}/{mission_slug}/ in by a "
            f"rename from {arrived}; the base is not derived across it",
            MissionBaseReason.RENAMED_INTO,
        )
    if not _is_on_branch(repo_root, base, mission_branch):
        return _Candidate(None, f"derived base {base[:_SHORT]} is not on the Mission branch", MissionBaseReason.DERIVED_NOT_ON_BRANCH)
    return _below_mission_start(repo_root, base, mission_slug, "derived base")


def _below_mission_start(repo_root: Path, sha: str, mission_slug: str, what: str) -> _Candidate:
    """*sha* as the base, unless the Mission directory is reachable from it: then it sits at or above the Mission's start.

    One ``git log -1 --full-history <sha> -- kitty-specs/<slug>/``: any commit reachable from
    the base that ever touched the Mission directory (``--full-history``, so a side branch a
    merge made TREESAME is not pruned) means the base is not below the Mission. A ``git log``
    failure raises :class:`GitProbeError`.
    """
    argv = ["git", "log", "-1", "--full-history", "--format=%H", sha, "--", f"{KITTY_SPECS_DIR}/{mission_slug}/"]
    ret, out, err = run_command(argv, capture=True, check_return=False, cwd=repo_root)
    if ret != 0:
        raise GitProbeError(f"git log -1 {sha[:_SHORT]} -- {KITTY_SPECS_DIR}/{mission_slug}/ failed (exit {ret}): {(err or '').strip()}")
    touched = (out or "").strip()
    if touched:
        return _Candidate(
            None,
            f"{what} {sha[:_SHORT]} reaches {KITTY_SPECS_DIR}/{mission_slug}/ (commit {touched[:_SHORT]}), so it is not below the Mission's start",
            MissionBaseReason.ABOVE_MISSION_START,
        )
    return _Candidate(sha)


def _earliest_scaffold_commit(repo_root: Path, mission_branch: str, mission_slug: str) -> str | None:
    """The oldest first-parent commit of *mission_branch* that adds a file under the Mission directory."""
    argv = [
        "git",
        "log",
        "--first-parent",
        "--diff-merges=first-parent",
        "--no-patch",
        "--reverse",
        "--diff-filter=A",
        "--format=%H",
        mission_branch,
        "--",
        f"{KITTY_SPECS_DIR}/{mission_slug}/",
    ]
    ret, out, err = run_command(argv, capture=True, check_return=False, cwd=repo_root)
    if ret != 0:
        raise GitProbeError(f"git log --first-parent {mission_branch} failed (exit {ret}): {(err or '').strip()}")
    for line in (out or "").splitlines():
        if line.strip():
            return line.strip()
    return None


def _renamed_into(repo_root: Path, parent: str, commit: str, mission_slug: str) -> str | None:
    """The source path of a rename into the Mission directory in *commit*, or ``None``.

    Diffs *commit* against *parent* (its first parent) through ``kernel.git`` with rename
    detection only (``-M``, ``--diff-filter=R``), so a source outside the Mission directory
    still pairs with its destination. Copy detection is deliberately off: with copy detection
    every new scaffold pairs with another Mission's identical ``.gitkeep`` or similar
    ``README.md``. git's default rename limit applies (a rename inside a commit with more
    candidate paths than that limit is not detected; a documented residual). A ``git diff``
    failure raises :class:`GitProbeError`.
    """
    try:
        entries = changed_entries(repo_root, parent, commit, renames=True, diff_filter="R")
    except GitCommandError as exc:
        raise GitProbeError(f"git diff {parent[:_SHORT]} {commit[:_SHORT]} failed: {exc}") from exc
    prefix = f"{KITTY_SPECS_DIR}/{mission_slug}/"
    for entry in entries:
        if entry.status[:1] == "R" and entry.orig_path is not None and str(entry.path).startswith(prefix):
            return str(entry.orig_path)
    return None


def _is_on_branch(repo_root: Path, sha: str, mission_branch: str) -> bool:
    """True when *sha* is a commit in this clone and an ancestor of (or equal to) *mission_branch*.

    A sha absent from the clone is a "no"; any other git failure raises :class:`GitProbeError`.
    """
    if not commit_in_clone(repo_root, sha):
        return False
    return bool(is_ancestor_strict(repo_root, sha, mission_branch))


def _commit_id_in_clone(repo_root: Path, sha: str) -> str | None:
    """The commit id ``rev-parse --verify --quiet <sha>^{commit}`` prints, ``None`` when absent from the clone.

    A full id that names a tag object prints the tagged commit's id, which differs from *sha*.
    Any failure other than "absent" raises :class:`GitProbeError`.
    """
    ret, out, err = run_command(["git", "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"], capture=True, check_return=False, cwd=repo_root)
    if ret == 1:
        return None
    if ret != 0:
        raise GitProbeError(f"git rev-parse --verify {sha[:_SHORT]} exited {ret}: {(err or '').strip()}")
    return (out or "").strip()


def _join_reasons(*reasons: str | None) -> str:
    return "; ".join(reason for reason in reasons if reason) or "no Mission base found"
