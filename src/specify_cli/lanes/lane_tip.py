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

Plan.md Minors: this module must NEVER import ``consolidation.*``. The
``git merge-tree --write-tree`` version probe :func:`is_absorbed` needs is the
same one ``consolidation/git_probes.py`` uses; both import it from the neutral
:mod:`specify_cli.git.merge_tree_probe` rather than keeping two copies.
"""

from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Callable, Hashable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import TypeVar

from kernel.git import GitCommandError, GitPath, changed_paths, merge_tree, run_git, subtree_entries, tree_entry, tree_paths
from kernel.git.read_cache import cached_object_read, git_read_cache_active, is_object_id
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.git.merge_tree_probe import MERGE_TREE_WRITE_TREE_MIN_VERSION, merge_tree_write_tree_available
from specify_cli.git.ref_advance import delete_bookkeeping_ref, write_bookkeeping_ref

__all__ = [
    "LANE_TIP_REF_PREFIX",
    "AbsorptionUnsupported",
    "LaneTipListingError",
    "clear_tip",
    "is_absorbed",
    "is_absorbed_but_for_mission_bookkeeping",
    "is_ancestor",
    "is_landed_through_mission_branch",
    "read_tip",
    "record_tip",
    "record_tip_for_wp",
    "recorded_tip_branches",
    "tip_ref",
]

#: Namespace of the hidden, never-pushed lane work-tip refs. The recorder hook
#: (``policy/lane_tip_recorder.py``) renders this same constant into its script.
LANE_TIP_REF_PREFIX = "refs/spec-kitty/lane-tip/"


class LaneTipListingError(Exception):
    """Raised by :func:`recorded_tip_branches` when the lane-tip refs cannot be listed.

    An unreadable listing is *unknown*, never "no tips": callers must not read
    it as an empty set (#5573).
    """


class AbsorptionUnsupported(Exception):
    """Raised by :func:`is_absorbed` when the installed git cannot evaluate absorption.

    ``git merge-tree --write-tree`` needs git >= 2.38. Callers must fail
    CLOSED on this (refuse), never treat "cannot evaluate" as "absorbed".
    """


def tip_ref(branch: str) -> str:
    """Return the hidden ref name that records ``branch``'s lane work tip."""
    return f"{LANE_TIP_REF_PREFIX}{branch}"


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

    write_bookkeeping_ref(repo_root, tip_ref(branch), resolved)
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


def recorded_tip_branches(repo_root: Path) -> frozenset[str]:
    """Return every branch name with a recorded lane work tip, in one git call.

    Runs ``git for-each-ref --format=%(refname) refs/spec-kitty/lane-tip/`` and
    strips :data:`LANE_TIP_REF_PREFIX` (#5573: the frozen-lane preflight's
    evidence, NFR-001). Read-only. An empty result from a successful listing
    means no lane recorded a tip.

    Raises:
        LaneTipListingError: git could not list the refs -- a non-zero exit,
            not a repository, or no ``git`` binary at all. That is *unknown*,
            never "no tips".
    """
    try:
        listing = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname)", LANE_TIP_REF_PREFIX],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise LaneTipListingError(f"cannot run git to list the recorded lane work tips in {repo_root}: {exc}") from exc
    if listing.returncode != 0:
        detail = listing.stderr.strip() or f"git exited {listing.returncode}"
        raise LaneTipListingError(f"git could not list the recorded lane work tips in {repo_root}: {detail}")
    return frozenset(line.removeprefix(LANE_TIP_REF_PREFIX) for line in listing.stdout.splitlines() if line.startswith(LANE_TIP_REF_PREFIX))


def clear_tip(repo_root: Path, branch: str) -> None:
    """Delete the recorded lane-tip ref for ``branch``. A no-op when already absent."""
    delete_bookkeeping_ref(repo_root, tip_ref(branch))


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
        # ``show -s --format=%T <rev> --`` names the commit's tree without
        # composing a ``<rev>^{tree}`` revision string; the trailing ``--``
        # forces ``target`` to parse as a revision (unknown -> non-zero exit).
        ["git", "show", "-s", "--format=%T", target, "--"],
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
       creation base (the control case: nothing to strand). Trusted ONLY
       while the lane-tip recorder is verifiably active in this
       repository's effective hooks dir: otherwise commits never moved the
       tip, so an unmoved tip proves nothing and the answer is ``False``
       (fail closed -- the caller refuses and names the recovery), also
       skipping legs 2-3, which would trivially accept ``base`` itself.
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
        # Function-local: ``policy.lane_tip_recorder`` imports this package for
        # the branch-name grammar, so a top-level import here would be circular.
        from specify_cli.policy.lane_tip_recorder import lane_tip_recorder_active

        return bool(lane_tip_recorder_active(repo_root))

    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", tip, target],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if ancestor.returncode == 0:
        return True

    if not merge_tree_write_tree_available(repo_root):
        raise AbsorptionUnsupported(f"git merge-tree --write-tree needs git >= {MERGE_TREE_WRITE_TREE_MIN_VERSION[0]}.{MERGE_TREE_WRITE_TREE_MIN_VERSION[1]}")

    return _merge_tree_no_op(repo_root, target, tip)


# --- #7747: the landing proof that sets aside Mission bookkeeping the lane never authored ---------

_MISSION_ROOT = KITTY_SPECS_DIR
_WORK_PACKAGE_PROMPT = "WP*.md"


_T = TypeVar("_T")


def _by_objects(repo_root: Path, revs: tuple[str, ...], key: Hashable, compute: Callable[[], _T]) -> _T:
    """``compute()``, read once per consolidate run when *revs* are all commit ids (#7848).

    Both landing proofs of one run (the Mission branch projection and lane cleanup) walk the same
    commits by id; an answer keyed only on object ids cannot change within the run.
    """
    return cached_object_read(repo_root, revs, ("lane_tip", key), compute)


def _git_lines(repo_root: Path, *args: str, revs: tuple[str, ...] = ()) -> tuple[str, ...]:
    """The output lines of ``git <args>``; *revs* are the revisions the answer is a function of."""

    def read() -> tuple[str, ...]:
        return tuple(run_git(repo_root, *args).stdout.decode("utf-8", "replace").splitlines())

    return _by_objects(repo_root, revs, args, read)


def _diff_paths(repo_root: Path, old: str, new: str) -> tuple[str, ...]:
    """The paths that differ between ``old`` and ``new`` (decoded by ``kernel.git``)."""
    return _by_objects(repo_root, (old, new), ("diff", old, new), lambda: tuple(str(path) for path in changed_paths(repo_root, old, new)))


def _lane_own_commits(repo_root: Path, tip: str, landing_ref: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The lane's own commits, each with its parents: first-parent commits no merged-in branch's line holds.

    A lane forks from the coordination branch and syncs with it by merging it in, so its
    first-parent chain also walks the coordination history it started from. Every non-first parent
    of a first-parent merge names a branch the lane took in whole; the commits on that branch's own
    first-parent line (and the landing ref's history) are not the lane's own. A lane commit the
    branch merged back is not on its first-parent line, so it stays the lane's.
    """
    revs = (tip, landing_ref)
    chain = [line.split() for line in _git_lines(repo_root, "rev-list", "--first-parent", "--parents", tip, f"^{landing_ref}", revs=revs)]
    merged_in = sorted({parent for entry in chain for parent in entry[2:]})
    # Only a merged-in branch's own first-parent line is history the lane took: a lane commit that
    # branch merged back (the coordination branch consolidating the lane, then a resync) stays the lane's.
    taken = {sha for parent in merged_in for sha in _git_lines(repo_root, "rev-list", "--first-parent", parent, f"^{landing_ref}", revs=(parent, landing_ref))}
    return tuple((entry[0], tuple(entry[1:])) for entry in chain if entry[0] not in taken)


def _blob_scope(path: str) -> str:
    """The subtree one listing reads for ``path``: its Mission's folder, else its top-level entry."""
    parts = PurePosixPath(path).parts
    if len(parts) > 2 and parts[0] == _MISSION_ROOT:
        return f"{parts[0]}/{parts[1]}"
    return parts[0] if parts else path


def _subtree_oids(repo_root: Path, rev: str, scope: str) -> Mapping[str, str]:
    """Every entry at or under ``scope`` in commit ``rev``: path to object id (blobs and trees)."""

    def read() -> Mapping[str, str]:
        return MappingProxyType({str(entry.path): entry.oid for entry in subtree_entries(repo_root, rev, scope)})

    return _by_objects(repo_root, (rev,), ("subtree", scope), read)


def _blob_id(repo_root: Path, rev: str, path: str) -> str | None:
    """The object id of ``path`` in ``rev`` (a tree for a directory), or ``None`` when ``rev`` has none.

    Inside a consolidate run, a commit id's subtree is listed once and every path in it is answered
    from that listing (#7848); a ref name, or a read outside a run, asks git for the one path.
    """
    if git_read_cache_active() and is_object_id(rev):
        wanted = str(GitPath.parse(path))
        return _subtree_oids(repo_root, rev, _blob_scope(wanted)).get(wanted)
    entry = tree_entry(repo_root, rev, path)
    return entry.oid if entry is not None else None


def _paths_changed_by(repo_root: Path, commit: str, parents: Sequence[str]) -> list[str]:
    """The paths ``commit`` changed against its first parent (every path of a root commit), via ``kernel.git``.

    Paths come decoded from ``kernel.git``, so a name git would quote (``core.quotePath``) still matches.
    """
    if parents:
        return list(_diff_paths(repo_root, parents[0], commit))
    return list(_by_objects(repo_root, (commit,), ("tree-paths",), lambda: tuple(str(path) for path in tree_paths(repo_root, commit))))


def _taken_whole_from_merged_in(repo_root: Path, commit: str, merged_in: Sequence[str], path: str) -> bool:
    """A merge's version of ``path`` equals one of its merged-in parents' versions (no resolution of its own)."""
    version = _blob_id(repo_root, commit, path)
    return any(_blob_id(repo_root, parent, path) == version for parent in merged_in)


def _authored_paths(repo_root: Path, tip: str, landing_ref: str) -> frozenset[str]:
    """Paths a commit the lane made itself changed.

    A merge authors a path only when its result is none of its merged-in parents' versions: a
    merge driver's or a conflict resolution's result counts as the lane's own authoring.
    """
    authored: set[str] = set()
    for commit, parents in _lane_own_commits(repo_root, tip, landing_ref):
        for path in _paths_changed_by(repo_root, commit, parents):
            if len(parents) > 1 and _taken_whole_from_merged_in(repo_root, commit, parents[1:], path):
                continue
            authored.add(path)
    return frozenset(authored)


def _event_lines(repo_root: Path, rev: str, path: str) -> set[str] | None:
    oid = _blob_id(repo_root, rev, path)
    if oid is None:
        return None
    blob = oid

    def read() -> frozenset[str]:
        text = run_git(repo_root, "cat-file", "blob", blob).stdout.decode("utf-8", "replace")
        return frozenset(line for line in text.splitlines() if line.strip())

    return set(_by_objects(repo_root, (blob,), ("event-lines",), read))


def _status_log_contained(repo_root: Path, tip: str, landing_ref: str, log_path: str) -> bool:
    """Every event line of the lane's copy of the status log is also in the landing's copy (append-only, #6736)."""
    lane = _event_lines(repo_root, tip, log_path)
    if lane is None:
        return True  # the lane carries no copy: nothing of it can be lost
    landed = _event_lines(repo_root, landing_ref, log_path)
    return landed is not None and lane <= landed


def _in_landing_history(repo_root: Path, landing_ref: str, path: str, blob: str) -> bool:
    """The landing ref's own history of ``path`` holds the version ``blob`` (it was recorded there, then moved past)."""
    commits = _git_lines(repo_root, "rev-list", "--full-history", landing_ref, "--", path, revs=(landing_ref,))
    return any(_blob_id(repo_root, commit, path) == blob for commit in commits)


def _is_bookkeeping(path: str, mission_dir: str) -> bool:
    """``meta.json`` or a ``tasks/WP*.md`` prompt of the lane's own Mission (the snapshot is judged by its log)."""
    pure = PurePosixPath(path)
    if str(pure.parent) == mission_dir:
        return pure.name == "meta.json"
    return str(pure.parent) == f"{mission_dir}/tasks" and fnmatch.fnmatchcase(pure.name, _WORK_PACKAGE_PROMPT)


class _MissionFileJudge:
    """Research R3: whether one differing ``kitty-specs/`` path loses nothing if the lane goes."""

    def __init__(self, repo_root: Path, tip: str, landing_ref: str, mission_slug: str, *, integrated_by: str | None = None) -> None:
        from specify_cli.status import EVENTS_FILENAME, SNAPSHOT_FILENAME

        self._repo_root = repo_root
        self._tip = tip
        self._landing_ref = landing_ref
        self._integrated_by = integrated_by  # the Mission branch tip the lane was proven into (#7747, A)
        self._mission_dir = f"{_MISSION_ROOT}/{mission_slug}"
        self._log_path = f"{self._mission_dir}/{EVENTS_FILENAME}"
        self._snapshot_path = f"{self._mission_dir}/{SNAPSHOT_FILENAME}"
        self._authored = _authored_paths(repo_root, tip, landing_ref)
        self._bases = _git_lines(repo_root, "merge-base", "--all", tip, landing_ref, revs=(tip, landing_ref))

    def _unchanged_since_base(self, path: str, lane_blob: str | None) -> bool:
        """The lane's copy is the merge base's copy: the lane changed nothing there (a blob comparison, no merge)."""
        return bool(self._bases) and all(_blob_id(self._repo_root, base, path) == lane_blob for base in self._bases)

    def accounted(self, path: str) -> bool:
        if path == self._snapshot_path:
            # The snapshot is the log's projection: it follows the log's verdict, and its own
            # authorship is never read (operator ruling 2026-11-24, C).
            return self.accounted(self._log_path)
        if path == self._log_path:
            # A log the lane never wrote holds no lane event (B); one it wrote is judged by its
            # events, append-only (#6736).
            return path not in self._authored or _status_log_contained(self._repo_root, self._tip, self._landing_ref, path)
        lane_blob = _blob_id(self._repo_root, self._tip, path)
        if path not in self._authored:
            if path.startswith(f"{self._mission_dir}/"):
                return True  # ruling 2026-11-24, B: a file of its own Mission the lane never wrote
            # Another Mission's file: the lane made no change there, or it has no copy and deleted none.
            return lane_blob is None or self._unchanged_since_base(path, lane_blob)
        if lane_blob is None or not _is_bookkeeping(path, self._mission_dir):
            return False
        if _blob_id(self._repo_root, self._landing_ref, path) is None:
            return False
        histories = (self._landing_ref,) if self._integrated_by is None else (self._landing_ref, self._integrated_by)
        return any(_in_landing_history(self._repo_root, ref, path, lane_blob) for ref in histories)


def _mission_files_accounted(repo_root: Path, tip: str, landing_ref: str, mission_slug: str, *, integrated_by: str | None = None) -> bool:
    """Every ``kitty-specs/`` difference between ``tip`` and ``landing_ref`` is accounted for (:class:`_MissionFileJudge`)."""
    judge = _MissionFileJudge(repo_root, tip, landing_ref, mission_slug, integrated_by=integrated_by)
    mission_paths = [path for path in _diff_paths(repo_root, landing_ref, tip) if path.startswith(f"{_MISSION_ROOT}/")]
    return all(judge.accounted(path) for path in mission_paths)


def _outside_mission_files(paths: Sequence[object]) -> list[str]:
    return [str(path) for path in paths if not str(path).startswith(f"{_MISSION_ROOT}/")]


def _product_absorbed(repo_root: Path, tip: str, landing_ref: str) -> bool:
    """Merging ``tip`` into ``landing_ref`` conflicts on and changes nothing outside ``kitty-specs/``.

    The merge's result for a ``kitty-specs/`` path is never read: a merge driver can resolve a
    Mission file to the landing ref's bytes and hide a lane edit (#7302 item 3).
    """
    merged = merge_tree(repo_root, landing_ref, tip)
    if not merged.tree or _outside_mission_files(merged.conflicted):
        return False
    return not _outside_mission_files(_diff_paths(repo_root, landing_ref, merged.tree))


def is_ancestor(repo_root: Path, tip: str, landing_ref: str) -> bool:
    """``True`` only when git confirms ``tip`` is an ancestor of ``landing_ref``; any error is ``False`` (no proof)."""

    def read() -> int:
        return run_git(repo_root, "merge-base", "--is-ancestor", tip, landing_ref, check=False).returncode

    # Only a definite answer (0 yes, 1 no) is kept: an error is asked again next time.
    returncode = cached_object_read(repo_root, (tip, landing_ref), ("lane_tip", "is-ancestor"), read, store_if=lambda code: code in (0, 1))
    return returncode == 0


def _pinned(repo_root: Path, landing_ref: str) -> str:
    """Inside a consolidate run, the commit a landing ref name points at now; else ``landing_ref`` unchanged.

    Lane cleanup hands the proof ``refs/heads/<target>`` (#7848): pinned once, every read of the
    proof is keyed on one commit id, so the run's read cache can answer its repeats, and the whole
    proof judges one commit even if the ref moves while it runs. Raises
    :class:`~kernel.git.GitCommandError` when the ref does not name a commit.
    """
    if not git_read_cache_active() or is_object_id(landing_ref):
        return landing_ref
    resolved = run_git(repo_root, "rev-parse", "--verify", "--end-of-options", f"{landing_ref}^{{commit}}")
    return resolved.stdout.decode("utf-8", "replace").strip()


def is_absorbed_but_for_mission_bookkeeping(repo_root: Path, tip: str, landing_ref: str, mission_slug: str) -> bool:
    """Return True iff no lane content is lost when the lane at ``tip`` goes, given ``landing_ref``.

    The one landing proof for lane cleanup (consolidate) and ``doctor workspaces`` (released
    Mission lanes) -- #7747, operator rulings 2026-11-22 and 2026-11-23 (Option A). It holds when
    ``tip`` is an ancestor of ``landing_ref``, or when every difference is accounted for:

    * outside ``kitty-specs/``: merging ``tip`` into ``landing_ref`` conflicts on and changes nothing;
    * the lane's own Mission status log: every lane event line is in the landing's log (#6736); its
      ``status.json`` is that log's projection and is judged the same way, never by authorship
      (operator ruling 2026-11-24, C);
    * any other file of the lane's own Mission that the lane never authored -- no commit the lane
      made itself changed it, a merge counting only when its result is none of its merged-in
      parents' versions (ruling 2026-11-24, B);
    * ``meta.json`` and ``tasks/WP*.md`` the lane authored, when the landing ref's history holds the
      lane's version;
    * another Mission's ``kitty-specs/`` file the lane did not author whose lane copy is the merge
      base's copy (only the landing ref moved it), or that the lane has no copy of: nothing to lose.

    Everything else is ``False``: another change the lane made to a ``kitty-specs/`` file, a deletion
    the lane made (except of its own Mission's status log: the log is append-only and its events are
    judged by containment, so a lane without a copy has none to lose), a git error, an unknown ref,
    or a git without ``merge-tree --write-tree``. A merge or merge-driver result is never evidence for
    a ``kitty-specs/`` path. Residual (ADR 2026-11-06-1, Amendment 2026-11-23): a version merged in
    from a branch other than the coordination branch counts as not authored on this lane. A lane
    whose lines a later lane rewrote is proven by :func:`is_landed_through_mission_branch` instead.
    """
    try:
        landing_ref = _pinned(repo_root, landing_ref)
        if is_ancestor(repo_root, tip, landing_ref):
            return True
        if not _product_absorbed(repo_root, tip, landing_ref):
            return False
        return _mission_files_accounted(repo_root, tip, landing_ref, mission_slug)
    except (GitCommandError, OSError):
        return False


def _mission_branch_landed(repo_root: Path, mission_tip: str, landing_ref: str) -> bool:
    """Every product path the Mission branch changed since its merge base with the landing has its blob there."""
    bases = _git_lines(repo_root, "merge-base", "--all", mission_tip, landing_ref, revs=(mission_tip, landing_ref))
    if not bases:
        return False
    integrated = {path for base in bases for path in _diff_paths(repo_root, base, mission_tip)}
    return all(_blob_id(repo_root, landing_ref, path) == _blob_id(repo_root, mission_tip, path) for path in _outside_mission_files(sorted(integrated)))


def _lane_changed_product_paths(repo_root: Path, tip: str, landing_ref: str) -> list[str]:
    """The product paths ``tip`` changed since its merge base(s) with the landing.

    Read from the tree diff, not from authorship, so a fast-forwarded lane (whose own commit sits
    behind a second parent) is still judged path by path (Tier R confirm N1).
    """
    bases = _git_lines(repo_root, "merge-base", "--all", tip, landing_ref, revs=(tip, landing_ref))
    if not bases:
        raise GitCommandError(argv=("merge-base", "--all", tip, landing_ref), cwd=repo_root, returncode=1, stderr="no merge base")
    changed = {path for base in bases for path in _diff_paths(repo_root, base, tip)}
    return _outside_mission_files(sorted(changed))


def _own_changes(repo_root: Path, lane_tip: str, landing_ref: str) -> list[tuple[str, frozenset[str]]]:
    """The lane's own non-merge commits with the paths each changed (the authorship walk's commits)."""
    return [
        (commit, frozenset(_paths_changed_by(repo_root, commit, parents)))
        for commit, parents in _lane_own_commits(repo_root, lane_tip, landing_ref)
        if len(parents) <= 1
    ]


class _ApprovedWork:
    """Later approved work: other approved lanes' own non-merge commits on the Mission branch."""

    def __init__(self, repo_root: Path, tip: str, mission_tip: str, landing_ref: str, approved_tips: Sequence[str]) -> None:
        self._repo_root = repo_root
        self._tip = tip
        # The Mission branch's own first-parent line is coordination history, never a lane's work: a
        # lane forked from it walks those commits on its own first-parent chain (Tier R confirm 2 B1).
        coordination = set(_git_lines(repo_root, "rev-list", "--first-parent", mission_tip, f"^{landing_ref}", revs=(mission_tip, landing_ref)))
        self._commits = [
            (commit, paths)
            for other in approved_tips
            if other != tip
            for commit, paths in _own_changes(repo_root, other, landing_ref)
            if commit not in coordination and not is_ancestor(repo_root, commit, tip) and is_ancestor(repo_root, commit, mission_tip)
        ]

    def supersedes(self, path: str) -> bool:
        """An approved lane's own commit built on this lane's last change to ``path`` changed it again.

        Only a commit descending from the lane's version counts (Tier R confirm B1): a parallel lane
        that touched the same file is not "later". Only another lane's own commit counts (B2): a
        commit it merged in, such as an out-of-workflow rewrite carried by a resync, is not its work,
        and neither is a commit on the Mission branch's own first-parent line that the lane forked
        from (confirm 2 B1).
        """
        lane_commit = _git_lines(self._repo_root, "rev-list", "-n", "1", self._tip, "--", path, revs=(self._tip,))
        if not lane_commit:
            return False
        return any(path in paths and is_ancestor(self._repo_root, lane_commit[0], commit) for commit, paths in self._commits)


def _lane_product_landed_or_superseded(repo_root: Path, tip: str, mission_tip: str, landing_ref: str, approved_tips: Sequence[str]) -> bool:
    """Every product path the lane changed landed with the lane's blob, or later approved work changed it.

    Operator ruling 2026-11-24 on Tier R B1, option (b); "later approved work" per the Tier R confirm
    pass (:class:`_ApprovedWork`). A revert or rewrite made on the Mission branch outside any lane
    keeps the lane.
    """
    work: _ApprovedWork | None = None
    for path in _lane_changed_product_paths(repo_root, tip, landing_ref):
        if _blob_id(repo_root, landing_ref, path) == _blob_id(repo_root, tip, path):
            continue
        work = work or _ApprovedWork(repo_root, tip, mission_tip, landing_ref, approved_tips)
        if not work.supersedes(path):
            return False
    return True


def is_landed_through_mission_branch(
    repo_root: Path,
    tip: str,
    mission_tip: str,
    landing_ref: str,
    mission_slug: str,
    *,
    approved_tips: Sequence[str],
) -> bool:
    """A lane landed through the Mission branch it was consolidated into (#7747, operator ruling 2026-11-24, A).

    A squash landing's merge base is the pre-Mission tip, so a lane whose lines a dependent lane later
    rewrote conflicts with the landing in ``merge-tree``: its exact version is not on the target,
    although approved work superseded it. While the Mission branch still exists, the lane's work is
    proven landed when:

    * ``tip`` is an ancestor of ``mission_tip`` (the Mission branch integrated all of it);
    * every path outside ``kitty-specs/`` the lane changed since its merge base with ``landing_ref``
      either has the lane's own final blob on ``landing_ref``, or was changed again by an own
      non-merge commit of another of ``approved_tips`` that is on the Mission branch and descends
      from the lane's last commit changing that path; a revert or rewrite made outside the
      workflow, a parallel edit and work another lane only merged in keep the lane (operator
      ruling 2026-11-24, Tier R B1 (b), and the Tier R confirm pass);
    * every path outside ``kitty-specs/`` the Mission branch changed since its merge base with
      ``landing_ref`` (the reconciliation PASS anchor) has the Mission branch's blob on
      ``landing_ref``: what the Mission branch integrated is what landed, while the target keeps its
      own content elsewhere;
    * every ``kitty-specs/`` difference between ``tip`` and ``landing_ref`` is accounted for by the
      same rules as :func:`is_absorbed_but_for_mission_bookkeeping`, where a ``meta.json`` or
      ``tasks/WP*.md`` version the lane authored may also be in the Mission branch's history (a
      squash keeps only that branch's last version).

    Anything else, an unknown revision and a git error included, is ``False``.
    """
    try:
        if not is_ancestor(repo_root, tip, mission_tip) or not _mission_branch_landed(repo_root, mission_tip, landing_ref):
            return False
        if not _lane_product_landed_or_superseded(repo_root, tip, mission_tip, landing_ref, approved_tips):
            return False
        return _mission_files_accounted(repo_root, tip, landing_ref, mission_slug, integrated_by=mission_tip)
    except (GitCommandError, OSError):
        return False
