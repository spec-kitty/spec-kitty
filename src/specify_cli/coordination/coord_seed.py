"""Coordination write-location core: establish, seed, refuse (mission coord-artifact-single-home-01M3V4BE, WP03).

The single answer to "where does a COORD write go" for a coordination-routed
Mission (``establish_coord_write_location``), and the one-time carry-over from
the repository-root checkout to the coordination surface (the module-private
``_seed_coord_surface``). See ``contracts/write-location-accessor.md`` and
``contracts/seed.md``.

Cold-import discipline: every ``specify_cli`` submodule this module needs
(``specify_cli.status.locking``, ``specify_cli.missions._read_path_resolver``,
``specify_cli.coordination.surface_resolver`` / ``workspace`` /
``commit_router``, ``specify_cli.git.protection_policy``) is imported inside
the function that needs it, never at module level, so a future cold-import
caller of this module never drags the whole status/coordination stack in
just to read a type.

**Review cycle 2 note (dead-symbol governance, charter Burn-down Policy a):**
``SeedRequest`` / ``seed_coord_surface`` are module-private (``_SeedRequest`` /
``_seed_coord_surface``) because, by contract design, their only caller is
this module (``establish_coord_write_location``); tests import the private
names directly. ``COORD_SEED_TRAILER``, ``CoordSeedForkRefused`` and
``coord_branch_is_post_fix`` are genuine cross-WP vocabulary with no
cross-module caller *yet* -- they are deliberately left un-allowlisted (an
accepted transitional red on ``test_no_dead_symbols``, cured when their
consumer WP lands; see the WP03 Activity Log for the curing-WP mapping).
"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn

from kernel.git import GitCommandError, status_entries, tree_paths
from kernel.tree_removal import remove_tool_owned_tree

from mission_runtime import (
    ActionContextError,
    Establishment,
    MissionArtifactKind,
    OwnedCheckout,
    OwnedRefusalCode,
    SeedReport,
    TopologySurface,
    WriteLocation,
    is_primary_artifact_kind,
    routes_through_coordination,
    placement_seam,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.coordination.event_prefix import (
    DuplicateEventIdError,
    MalformedEventLogLineError,
    PrefixVerdict,
    classify_prefix,
    event_ids_of,
    non_blank_lines_of,
    merged_log_bytes,
)

if TYPE_CHECKING:
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.missions._read_path_resolver import CoordState

__all__ = [
    "COORD_SEED_TRAILER",
    "CoordBranchUndeclaredAndAbsent",
    "CoordSeedForkRefused",
    "coord_branch_is_post_fix",
    "establish_coord_write_location",
]

logger = logging.getLogger(__name__)

#: The ONE commit-trailer key every seed commit (and the create-time commit,
#: WP06 T031) carries, keyed by ``mission_id`` -- the D4 post-fix discriminator.
COORD_SEED_TRAILER = "Spec-Kitty-Coordination-Seed"

_COORD_SEED_FORK_REFUSED_CODE = "COORD_SEED_FORK_REFUSED"
_COORD_SEED_EVENT_LOG_MALFORMED_CODE = "COORD_SEED_EVENT_LOG_MALFORMED"
_COORD_SEED_DUPLICATE_EVENT_ID_CODE = "COORD_SEED_DUPLICATE_EVENT_ID"
_COORD_SEED_GIT_PROBE_FAILED_CODE = "COORD_SEED_GIT_PROBE_FAILED"
_COORD_BRANCH_UNDECLARED_AND_ABSENT_CODE = "COORD_BRANCH_UNDECLARED_AND_ABSENT"
_STATUS_LOG_FILENAME = "status.events.jsonl"
_DECISION_LOG_FILENAME = "decisions.events.jsonl"
_LOG_FILENAMES: tuple[str, ...] = (_STATUS_LOG_FILENAME, _DECISION_LOG_FILENAME)
_STATUS_COMMITTED = "committed"
_STATUS_UNCHANGED = "unchanged"


class CoordSeedForkRefused(ActionContextError):
    """A coordination log stream has forked from its root-checkout counterpart (D3).

    Raised **before** anything is written (I-SEED-4): neither surface is
    touched. ``.code`` is ``"COORD_SEED_FORK_REFUSED"`` (``ActionContextError``
    stores ``.code``, never ``.error_code`` -- binding correction).
    """

    error_code = _COORD_SEED_FORK_REFUSED_CODE

    def __init__(
        self,
        *,
        root_path: Path,
        coord_path: str,
        coord_ref: str,
        first_divergence_root: str | None,
        first_divergence_coord: str | None,
        reconcile_steps: tuple[str, ...],
    ) -> None:
        message = (
            f"coordination seed refused: {root_path} and {coord_ref}:{coord_path} "
            "have diverged (first divergence: "
            f"root event_id={first_divergence_root!r}, "
            f"coordination event_id={first_divergence_coord!r}). " + "; ".join(reconcile_steps) + "."
        )
        super().__init__(self.error_code, message)
        self.root_path = root_path
        self.coord_path = coord_path
        self.coord_ref = coord_ref
        self.first_divergence_root = first_divergence_root
        self.first_divergence_coord = first_divergence_coord
        self.reconcile_steps = reconcile_steps


class CoordBranchUndeclaredAndAbsent(ActionContextError):
    """A coordination-routed topology declares no branch, and the deterministically-derived one does not exist either.

    Review cycle 2 (B1-residual, Decision ``plan.design.undeclared-coord-
    branch`` -- supersedes the plain "refuse" half of the cycle-1 B1 ruling):
    ``coordination_branch`` in ``meta.json`` is only a RECORD of the branch,
    never its source of truth -- ``CoordinationWorkspace`` / mission create
    mint it by ONE deterministic naming grammar
    (``lanes.branch_naming.coord_reconstruct_branch``). When the record is
    missing (a bootstrap window, a stale owned copy, or a caller/fixture that
    never persisted it) on a STORED topology that routes through coordination
    (``COORD`` / ``LANES_WITH_COORD``), silently degrading to the declared-
    PRIMARY write location is the exact fail-open the accessor's contract
    forbids -- so the name is derived and checked against git directly:

    - the derived branch EXISTS → the caller proceeds EXACTLY as if it had
      been declared (never raised, never reached here);
    - the derived branch does NOT exist (or no mid8 could even be resolved
      to derive one) → this refusal, BEFORE anything is written (I-SEED-4
      precedent).

    A coord-less / topology-less (legacy, un-backfilled) meta is UNCHANGED by
    this gate -- it still returns the declared-PRIMARY location (the historical
    control).
    """

    error_code = _COORD_BRANCH_UNDECLARED_AND_ABSENT_CODE

    def __init__(self, *, mission_slug: str, derived_branch: str | None) -> None:
        if derived_branch:
            detail = f"the deterministically-derived branch {derived_branch!r} does not exist in git either"
        else:
            detail = "no mid8 disambiguator could be resolved to even derive a candidate branch name"
        message = (
            f"mission {mission_slug!r} has a coordination-routed topology with no declared "
            f"'coordination_branch' in meta.json, and {detail}. Declare 'coordination_branch' "
            "in meta.json if that branch should exist, or run "
            "'spec-kitty migrate backfill-topology' to flatten this mission to a coord-less "
            "topology if it never had one."
        )
        super().__init__(self.error_code, message)
        self.mission_slug = mission_slug
        self.derived_branch = derived_branch


class _CoordGitProbeError(ActionContextError):
    """A git probe that must distinguish "absent" from "command failed" hit the failure case (B8).

    Raised by :func:`_coord_tip_relpaths`, :func:`_coord_side_text` and
    :func:`coord_branch_is_post_fix` on a genuine git command failure --
    never on a legitimate "path/ref absent" result, which they return as
    ``None``/``()``/``False`` instead. The coordination branch is already
    known to exist by every call site (state EMPTY or MATERIALIZED), so a
    non-zero git exit at this point is an infrastructure error, not an
    absence, and must never silently flip a pre-fix/post-fix or a fork/no-fork
    decision.
    """

    error_code = _COORD_SEED_GIT_PROBE_FAILED_CODE

    def __init__(self, message: str) -> None:
        super().__init__(self.error_code, message)


@dataclass(frozen=True, kw_only=True)
class _SeedRequest:
    """Everything the seed needs for one attempt (data-model.md §3).

    Module-private (review cycle 2, B7): by contract, the only caller of
    the seed entry point is this module.
    """

    repo_root: Path
    mission_slug: str
    mission_dir_name: str
    mid8: str
    mission_id: str
    coordination_branch: str
    coord_worktree: Path
    root_mission_dir: Path
    #: ``True`` when this is the post-fix restore-then-seed leg (the branch
    #: already carries the seed trailer). The restore from the branch tip now
    #: happens INSIDE the lock (B1/B2), driven by this flag.
    post_fix: bool = False
    owned: OwnedCheckout | None = None


@dataclass(frozen=True)
class _StreamMerge:
    relpath: str
    merged_text: str | None
    carried: bool


@dataclass(frozen=True)
class _MergeResult:
    stream_merges: tuple[_StreamMerge, ...]
    non_log_files: tuple[tuple[str, bytes], ...]
    carried: tuple[str, ...]
    warnings: tuple[str, ...]
    fork: CoordSeedForkRefused | None


def _lock_root(request: _SeedRequest) -> Path:
    return request.owned.owned_root if request.owned is not None else request.repo_root


def _is_coord_relpath(relpath: str) -> bool:
    """Whether the seed carries *relpath*: the one coordination-kind predicate the fold and the gate share (#5651)."""
    from specify_cli.coordination.coherence import is_coordination_kind_file

    return is_coordination_kind_file(relpath)


def _walk_root_coord_relpaths(root_mission_dir: Path) -> tuple[str, ...]:
    if not root_mission_dir.exists():
        return ()
    relpaths = []
    for candidate in sorted(root_mission_dir.rglob("*")):
        if not candidate.is_file():
            continue
        relpath = candidate.relative_to(root_mission_dir).as_posix()
        if _is_coord_relpath(relpath):
            relpaths.append(relpath)
    return tuple(relpaths)


def _coord_tip_relpaths(repo_root: Path, coordination_branch: str, mission_dir_name: str) -> tuple[str, ...]:
    """List the COORD-kind paths at the coordination branch tip (B8: raises on a real git failure)."""
    prefix = f"{KITTY_SPECS_DIR}/{mission_dir_name}/"
    try:
        tip_paths = sorted(str(path) for path in tree_paths(repo_root, coordination_branch, pathspecs=(prefix,)))
    except GitCommandError as exc:
        # A readable branch whose subtree is simply empty lists nothing and
        # does not raise -- a failure here means the ref itself is unreadable,
        # which the branch is already known to exist by this point (state
        # EMPTY/MATERIALIZED), so this is an error, not an absence.
        raise _CoordGitProbeError(f"git ls-tree {coordination_branch} -- {prefix} failed: {exc}") from exc
    relpaths = []
    for line in tip_paths:
        if not line.startswith(prefix):
            continue
        relpath = line[len(prefix) :]
        if _is_coord_relpath(relpath):
            relpaths.append(relpath)
    return tuple(relpaths)


def _read_text_newline_preserving(path: Path) -> str:
    """Read *path* as text without universal-newline translation (byte-faithful).

    ``Path.read_text(newline=...)`` is Python 3.13+ only; this is the
    3.11/3.12-portable equivalent via the file object's own ``newline``
    support.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


_GIT_SHOW_ABSENT_MARKERS = ("does not exist in", "exists on disk, but not in")


def _coord_side_text(
    repo_root: Path,
    coord_worktree: Path,
    coordination_branch: str,
    mission_dir_name: str,
    relpath: str,
) -> str | None:
    """Return the coordination-side content for *relpath*: disk first, else the branch tip blob (D3).

    B8: a genuinely absent path at the tip (``git show`` naming it "does not
    exist") returns ``None``; any OTHER non-zero exit (a bad ref, an
    unreadable repo) raises -- it is never silently treated as "absent".
    """
    disk_path = coord_worktree / KITTY_SPECS_DIR / mission_dir_name / relpath
    if disk_path.exists():
        return _read_text_newline_preserving(disk_path)
    pathspec = f"{KITTY_SPECS_DIR}/{mission_dir_name}/{relpath}"
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{coordination_branch}:{pathspec}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout
    if any(marker in result.stderr for marker in _GIT_SHOW_ABSENT_MARKERS):
        return None
    raise _CoordGitProbeError(f"git show {coordination_branch}:{pathspec} failed: {result.stderr.strip()}")


def _reconcile_steps() -> tuple[str, ...]:
    return (
        "inspect with `spec-kitty doctor decisions`",
        "keep the coordination log",
        "re-open any root-only decisions with `spec-kitty agent decision open ...`",
        "then remove the root copy",
    )


def _raise_event_log_error(
    request: _SeedRequest,
    *,
    filename: str,
    side: Literal["root", "coordination"],
    location_hint: str,
    exc: MalformedEventLogLineError | DuplicateEventIdError,
) -> NoReturn:
    """Translate an event_prefix parse error into a structured, actionable refusal.

    Review cycle 2 B7/T016-step-6: ``MalformedEventLogLineError`` /
    ``DuplicateEventIdError`` never escape this module as bare ``ValueError``s
    with no context -- every coord_seed error names the Mission, the
    coordination branch and a recovery command.
    """
    code = _COORD_SEED_EVENT_LOG_MALFORMED_CODE if isinstance(exc, MalformedEventLogLineError) else _COORD_SEED_DUPLICATE_EVENT_ID_CODE
    raise ActionContextError(
        code,
        f"coordination seed cannot classify mission {request.mission_slug!r}'s {side} "
        f"{filename!r} ({location_hint}): {exc}. The coordination branch is "
        f"{request.coordination_branch!r}. Inspect and repair the malformed/duplicate "
        "row by hand (it is never silently skipped, NFR-002), then retry the write.",
    ) from exc


def _event_ids_or_raise(
    request: _SeedRequest,
    lines: tuple[str, ...],
    *,
    filename: str,
    side: Literal["root", "coordination"],
    location_hint: str,
) -> tuple[str, ...]:
    try:
        event_ids: tuple[str, ...] = event_ids_of(lines)
    except (MalformedEventLogLineError, DuplicateEventIdError) as exc:
        _raise_event_log_error(request, filename=filename, side=side, location_hint=location_hint, exc=exc)
    return event_ids


def _merge_stream(request: _SeedRequest, filename: str) -> _StreamMerge | CoordSeedForkRefused | None:
    root_path = request.root_mission_dir / filename
    root_text = _read_text_newline_preserving(root_path) if root_path.exists() else ""
    coord_text = _coord_side_text(request.repo_root, request.coord_worktree, request.coordination_branch, request.mission_dir_name, filename) or ""
    root_lines = non_blank_lines_of(root_text.splitlines(keepends=True))
    coord_lines = non_blank_lines_of(coord_text.splitlines(keepends=True))
    root_ids = _event_ids_or_raise(request, root_lines, filename=filename, side="root", location_hint=str(root_path))
    coord_ids = _event_ids_or_raise(
        request,
        coord_lines,
        filename=filename,
        side="coordination",
        location_hint=f"{request.coordination_branch}:{KITTY_SPECS_DIR}/{request.mission_dir_name}/{filename}",
    )
    verdict: PrefixVerdict = classify_prefix(root_ids, coord_ids)
    if verdict.kind == "fork":
        coord_ref_path = f"{KITTY_SPECS_DIR}/{request.mission_dir_name}/{filename}"
        return CoordSeedForkRefused(
            root_path=root_path,
            coord_path=coord_ref_path,
            coord_ref=request.coordination_branch,
            first_divergence_root=verdict.first_divergence[0],
            first_divergence_coord=verdict.first_divergence[1],
            reconcile_steps=_reconcile_steps(),
        )
    if verdict.kind == "nothing" and not coord_lines:
        return None
    merged = merged_log_bytes(root_lines, coord_lines, verdict).decode("utf-8")
    return _StreamMerge(relpath=filename, merged_text=merged, carried=verdict.kind == "carry_tail")


def _merge_non_log_files(request: _SeedRequest) -> tuple[tuple[tuple[str, bytes], ...], tuple[str, ...], tuple[str, ...]]:
    """I-SEED-5: carry a root-only non-log COORD file; keep the coordination copy on conflict (warn, never discard)."""
    root_relpaths = {p for p in _walk_root_coord_relpaths(request.root_mission_dir) if p not in _LOG_FILENAMES}
    coord_relpaths = {p for p in _coord_tip_relpaths(request.repo_root, request.coordination_branch, request.mission_dir_name) if p not in _LOG_FILENAMES}
    non_log_files: list[tuple[str, bytes]] = []
    carried: list[str] = []
    warnings: list[str] = []
    for relpath in sorted(root_relpaths | coord_relpaths):
        coord_text = _coord_side_text(request.repo_root, request.coord_worktree, request.coordination_branch, request.mission_dir_name, relpath)
        root_path = request.root_mission_dir / relpath
        if coord_text is not None:
            if root_path.exists() and _read_text_newline_preserving(root_path) != coord_text:
                warnings.append(f"{relpath}: root and coordination copies differ; keeping the coordination copy")
            continue
        if root_path.exists():
            non_log_files.append((relpath, root_path.read_bytes()))
            carried.append(relpath)
    return tuple(non_log_files), tuple(carried), tuple(warnings)


def _merge_coord_content(request: _SeedRequest) -> _MergeResult:
    stream_merges: list[_StreamMerge] = []
    carried: list[str] = []
    for filename in _LOG_FILENAMES:
        merge = _merge_stream(request, filename)
        if isinstance(merge, CoordSeedForkRefused):
            return _MergeResult(stream_merges=(), non_log_files=(), carried=(), warnings=(), fork=merge)
        if merge is None:
            continue
        stream_merges.append(merge)
        if merge.carried:
            carried.append(merge.relpath)
    non_log_files, non_log_carried, warnings = _merge_non_log_files(request)
    carried.extend(non_log_carried)
    return _MergeResult(
        stream_merges=tuple(stream_merges),
        non_log_files=non_log_files,
        carried=tuple(carried),
        warnings=warnings,
        fork=None,
    )


def _write_merge_files(target_dir: Path, merge: _MergeResult) -> None:
    for stream in merge.stream_merges:
        if stream.merged_text is None:
            continue
        path = target_dir / stream.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(stream.merged_text)
    for relpath, content in merge.non_log_files:
        path = target_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


# Review cycle 1 N2: the scratch dir for the temp-rename write lives OUTSIDE
# ``kitty-specs/`` entirely -- a sibling of it directly under the coord
# worktree root, same filesystem (``os.rename`` below stays atomic), so
# neither this cleanup sweep nor the write below ever enumerates raw
# kitty-specs/ entries. That removes the need for the walker gate's
# (``tests/architectural/test_mission_resolver_walker_gate.py``)
# function-level exemption this scratch dir used to require when it lived
# under ``kitty-specs/``.
_SEED_TEMP_DIR_NAME = ".spec-kitty-seed-tmp"


def _seed_temp_root(coord_worktree: Path) -> Path:
    return coord_worktree / _SEED_TEMP_DIR_NAME


def _cleanup_stale_seed_temp_dirs(request: _SeedRequest) -> None:
    temp_root = _seed_temp_root(request.coord_worktree)
    if not temp_root.exists():
        return
    stale_prefix = f"{request.mission_dir_name}.seed-"
    for candidate in temp_root.iterdir():
        if candidate.is_dir() and candidate.name.startswith(stale_prefix):
            _remove_tree(candidate, owned_root=temp_root)


def _remove_tree(path: Path, *, owned_root: Path) -> None:
    """Best-effort removal of a seed scratch tree; ``owned_root`` is the scratch root the seed created."""
    remove_tool_owned_tree(path, owned_root=owned_root, reason="coordination seed scratch directory", best_effort=True)


def _write_merge_via_temp_rename(request: _SeedRequest, merge: _MergeResult) -> Path:
    # Explicit ``Path`` annotations: ``KITTY_SPECS_DIR`` is typed ``Any`` under
    # the project's ``follow_imports = "skip"`` mypy config, which would
    # otherwise poison the ``/`` chain below with ``Any``.
    specs_dir: Path = request.coord_worktree / KITTY_SPECS_DIR
    specs_dir.mkdir(parents=True, exist_ok=True)
    final_dir: Path = specs_dir / request.mission_dir_name
    temp_root = _seed_temp_root(request.coord_worktree)
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir: Path = temp_root / f"{request.mission_dir_name}.seed-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    temp_dir.mkdir(parents=True)
    _write_merge_files(temp_dir, merge)
    try:
        os.rename(temp_dir, final_dir)
    except OSError:
        # L3: never leave the temp dir behind on a failed rename -- the
        # caller re-probes once to tell a genuine failure apart from a
        # same-lock-window race (impossible for cooperating lock holders,
        # but cheap to make the state machine honest either way).
        _remove_tree(temp_dir, owned_root=temp_root)
        raise
    return final_dir


def _write_merge_in_place(request: _SeedRequest, merge: _MergeResult) -> Path:
    final_dir: Path = request.coord_worktree / KITTY_SPECS_DIR / request.mission_dir_name
    final_dir.mkdir(parents=True, exist_ok=True)
    _write_merge_files(final_dir, merge)
    return final_dir


def _to_repo_relpath(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _git_status_entry(repo_root: Path, repo_relpath: str) -> str | None:
    """Return the raw ``XY`` porcelain code for *repo_relpath*, or ``None`` if clean."""
    try:
        entries = status_entries(repo_root, pathspecs=(repo_relpath,))
    except GitCommandError:
        return None
    return entries[0].xy if entries else None


def _git_path_status(repo_root: Path, repo_relpath: str) -> Literal["dirty", "untracked", "staged_new", "clean"]:
    code = _git_status_entry(repo_root, repo_relpath)
    if code is None:
        return "clean"
    if code == "??":
        return "untracked"
    if code[0] == "A":
        # L4: staged-new (added to the index, absent at HEAD). ``git checkout
        # -- <path>`` restores from the INDEX, not HEAD, so it is a no-op for
        # a path with no HEAD version at all and the file silently stays on
        # disk. Handled separately below: unstage, then remove.
        return "staged_new"
    return "dirty"


def _restore_root_files(request: _SeedRequest, carried: tuple[str, ...]) -> tuple[str, ...]:
    """Restore the root-checkout copies of *carried* COORD records (I-SEED-8).

    WP04-review binding first step (coord-artifact-single-home-01M3V4BE
    WP07): anchored on :func:`_lock_root` -- ``owned.owned_root`` for an
    owned checkout, else ``request.repo_root`` -- never on the bare
    ``request.repo_root`` unconditionally. ``request.root_mission_dir``
    itself already lives under that same root (the placement seam resolves
    it there), so a hand composition onto ``request.repo_root`` for an
    owned checkout is not merely the wrong git repo to probe/restore
    against: the path is not even a subpath of it, so
    ``Path.relative_to`` previously raised ``ValueError`` outright.
    """
    restored: list[str] = []
    root = _lock_root(request)
    for relpath in carried:
        root_path = request.root_mission_dir / relpath
        if not root_path.exists():
            continue
        repo_relpath = _to_repo_relpath(root, root_path)
        status = _git_path_status(root, repo_relpath)
        if status == "untracked":
            root_path.unlink()
            restored.append(repo_relpath)
        elif status == "staged_new":
            subprocess.run(["git", "-C", str(root), "restore", "--staged", "--", repo_relpath], check=True, capture_output=True)
            root_path.unlink()
            restored.append(repo_relpath)
        elif status == "dirty":
            subprocess.run(["git", "-C", str(root), "checkout", "--", repo_relpath], check=True, capture_output=True)
            restored.append(repo_relpath)
        # "clean": pre-fix history stays untouched (C-004).
    return tuple(restored)


def _commit_seed(request: _SeedRequest, commit_paths: tuple[Path, ...]) -> CommitRouterResult:
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = (
        ProtectionPolicy.resolve_for_owned(request.owned, request.mission_slug)
        if request.owned is not None
        else ProtectionPolicy.resolve_for_mission(request.repo_root, request.mission_slug)
    )
    message = f"chore({request.mission_slug}): seed coordination surface\n\n{COORD_SEED_TRAILER}: {request.mission_id}"
    return commit_for_mission(
        request.repo_root,
        request.mission_slug,
        files=commit_paths,
        message=message,
        policy=policy,
        kind=MissionArtifactKind.STATUS_STATE,
        owned=request.owned,
    )


def _coord_kind_relpaths_on_disk(final_dir: Path) -> tuple[str, ...]:
    if not final_dir.exists():
        return ()
    relpaths = []
    for candidate in sorted(final_dir.rglob("*")):
        if not candidate.is_file():
            continue
        relpath = candidate.relative_to(final_dir).as_posix()
        if _is_coord_relpath(relpath):
            relpaths.append(relpath)
    return tuple(relpaths)


def _seed_has_carry_basis(
    request: _SeedRequest,
    merge: _MergeResult,
    restored_from_branch: tuple[str, ...],
) -> bool:
    """True when the on-disk coordination content ORIGINATES from the seed's own sources.

    The seed carries ROOT-checkout coordination records onto the coordination
    surface (I-SEED-7) and commits every coordination-kind file now on disk --
    not merely what THIS attempt carried -- so a retry of a previously-refused
    seed still commits the content a prior attempt left untracked (I-SEED-10).
    That superset is sound only while the disk content comes from a seed source:
    what this attempt carried (``merge.carried``), what it restored from the
    coordination tip (``restored_from_branch``), or what still lives in the root
    checkout (a refused-then-retried carry keeps its root copy, so
    ``merge.carried`` is empty on the retry yet the root copy is present -- see
    ``test_refused_seed_commit_then_retried``).

    When all three are empty the coordination worktree holds content the seed
    never carried: a caller wrote it directly onto the coordination worktree and
    will commit it itself through the owning ``BookkeepingTransaction`` (the
    ``MissionStatus.save`` escape hatch -- "callers that have already staged
    writes directly on the coord worktree"). The seed must NOT pre-empt that
    commit; doing so lands the content first and leaves the caller's own strict
    ``commit`` with an empty changeset (``SafeCommitStagedTreeUnchanged``).

    #5651's directory-alias classification is what made this pre-emption
    reachable: a bare-slug coordination Mission's composed-directory
    (``<slug>-<mid8>``) status files now route to the COORDINATION partition
    instead of being misclassified to the primary partition and no-op'd at the
    seed's ``commit_for_mission`` call, so the seed's commit of the caller's own
    content stopped failing closed. This basis check restores the pre-#5651
    deferral for that escape hatch while leaving the composed-directory routing
    the seed genuinely needs during consolidation (where it carries the status
    pair out of the root checkout) untouched.
    """
    if merge.carried or restored_from_branch:
        return True
    return bool(_walk_root_coord_relpaths(request.root_mission_dir))


def _commit_and_restore(
    request: _SeedRequest,
    merge: _MergeResult,
    final_dir: Path,
    *,
    restored_from_branch: tuple[str, ...] = (),
) -> SeedReport:
    """Commit every COORD-kind file now on disk (I-SEED-7), then restore the root checkout (I-SEED-8).

    Committing everything on disk -- not merely ``merge.carried`` -- matters
    for a RETRY of a previously-refused seed commit (I-SEED-10): the dir
    already holds the fully-merged, fork-checked content from the attempt
    that built it; this attempt's own ``merge.carried`` may be empty (root is
    already a prefix of what is on disk), yet the untracked files still need
    their first commit. The everything-on-disk commit runs only when the seed
    has a genuine basis for the content (:func:`_seed_has_carry_basis`); content
    a caller wrote directly onto the coordination worktree, which the seed never
    carried, is left for that caller's own transaction to commit.
    """
    warnings = list(merge.warnings)
    coord_commit: str | None = None
    commit_refused: str | None = None
    uncommitted_paths: tuple[str, ...] = ()
    # Which root copies to restore (I-SEED-8) depends on the commit outcome:
    #   committed -- the coordination copy is durable, so restore what THIS attempt
    #                carried AND every path it just committed. A RETRY of a refused
    #                commit carries nothing (``merge.carried`` is empty: root is
    #                already a prefix of what is on disk), yet its root copies are
    #                still untracked and must go once the commit finally lands;
    #   unchanged / nothing to commit -- already durable, restore ``merge.carried`` only;
    #   refused   -- the only copy of the carried records is untracked content in
    #                the coordination worktree, so the root copies stay until a
    #                later write commits them.
    restore_relpaths: tuple[str, ...] = merge.carried
    commit_relpaths = _coord_kind_relpaths_on_disk(final_dir)
    if commit_relpaths and _seed_has_carry_basis(request, merge, restored_from_branch):
        commit_paths = tuple(final_dir / relpath for relpath in commit_relpaths)
        result = _commit_seed(request, commit_paths)
        if result.status == _STATUS_COMMITTED:
            coord_commit = result.commit_hash
            restore_relpaths = tuple(dict.fromkeys((*merge.carried, *commit_relpaths)))
        elif result.status != _STATUS_UNCHANGED:
            restore_relpaths = ()
            reason = f", reason={result.reason!r}" if result.reason else ""
            commit_refused = f"status={result.status!r}{reason}"
            uncommitted_paths = tuple((final_dir / relpath).relative_to(request.coord_worktree).as_posix() for relpath in commit_relpaths)
            warnings.append(
                f"seed commit not applied ({commit_refused}); the mission dir is present but uncommitted. The next coordination write retries the commit."
            )
    restored_root = _restore_root_files(request, restore_relpaths)
    if merge.carried or warnings or restored_from_branch:
        logger.warning(
            "coordination seed for mission %s: carried=%s restored_root=%s restored_from_branch=%s coord_commit=%s warnings=%s",
            request.mission_slug,
            merge.carried,
            restored_root,
            restored_from_branch,
            coord_commit,
            warnings,
        )
    return SeedReport(
        carried=merge.carried,
        restored_root=restored_root,
        restored_from_branch=restored_from_branch,
        coord_commit=coord_commit,
        commit_refused=commit_refused,
        uncommitted_paths=uncommitted_paths,
        warnings=tuple(warnings),
    )


def coord_branch_is_post_fix(repo_root: Path, coordination_branch: str, mission_id: str) -> bool:
    """Return whether *coordination_branch*'s history carries the seed trailer for *mission_id* (D4).

    The ONE public post-fix discriminator (cross-WP vocabulary, WP04 T021
    imports it lazily): a Mission is post-fix iff its coordination branch
    history carries ``Spec-Kitty-Coordination-Seed: <mission_id>``. Read-only,
    no writes. B8: raises on a genuine git failure rather than silently
    reading "pre-fix" -- the branch is already known to exist by every call
    site, so a non-zero ``git log`` exit here is an error, not an absence.
    """
    if not mission_id:
        return False
    result = subprocess.run(
        ["git", "-C", str(repo_root), "log", f"--format=%(trailers:key={COORD_SEED_TRAILER},valueonly)", coordination_branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise _CoordGitProbeError(f"git log {coordination_branch} failed: {result.stderr.strip()}")
    return mission_id in {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _whole_dir_untracked_fast(coord_worktree: Path, mission_dir_name: str) -> bool:
    """B3: the cheap, config-independent "is the whole Mission dir untracked" check.

    ``--untracked-files=normal`` is passed EXPLICITLY so the result never
    depends on the operator's ``status.showUntrackedFiles`` -- with ``all``
    git would otherwise list one line per file instead of collapsing an
    untracked directory into one ``?? <dir>/`` entry, and with ``no`` it
    would print nothing at all; either misreading silently makes a pending
    seed commit un-retryable forever. ``-z`` is parsed (NUL-separated,
    unquoted paths) rather than ``splitlines()``.
    """
    repo_relpath = f"{KITTY_SPECS_DIR}/{mission_dir_name}/"
    try:
        entries = status_entries(coord_worktree, pathspecs=(repo_relpath,), untracked="normal")
    except GitCommandError as exc:
        raise _CoordGitProbeError(f"git status -- {repo_relpath} failed: {exc}") from exc
    return len(entries) == 1 and entries[0].is_untracked and entries[0].is_directory and str(entries[0].path) == repo_relpath.rstrip("/")


def _seed_pending(request: _SeedRequest) -> bool:
    """I-SEED-10: pending iff the Mission dir is wholly untracked AND has no trailer/committed blob."""
    if not _whole_dir_untracked_fast(request.coord_worktree, request.mission_dir_name):
        return False
    if coord_branch_is_post_fix(request.repo_root, request.coordination_branch, request.mission_id):
        return False
    return not _coord_tip_relpaths(request.repo_root, request.coordination_branch, request.mission_dir_name)


def _restore_coord_kind_paths_from_tip(
    repo_root: Path,
    coordination_branch: str,
    mission_dir_name: str,
    coord_worktree: Path,
) -> tuple[str, ...]:
    relpaths = _coord_tip_relpaths(repo_root, coordination_branch, mission_dir_name)
    if not relpaths:
        return ()
    pathspecs = [f"{KITTY_SPECS_DIR}/{mission_dir_name}/{relpath}" for relpath in relpaths]
    subprocess.run(
        ["git", "-C", str(coord_worktree), "checkout", coordination_branch, "--", *pathspecs],
        check=True,
        capture_output=True,
    )
    return tuple(sorted(relpaths))


def _run_merge_and_commit(
    request: _SeedRequest,
    *,
    in_place: bool,
    restored_from_branch: tuple[str, ...] = (),
) -> SeedReport:
    """Merge (with a full fork re-check, I-SEED-4), write, commit, restore.

    Used by both the fresh pre-fix/post-fix paths and the MATERIALIZED
    pending-seed retry (I-SEED-10): the fork check always re-runs against the
    CURRENT root content, regardless of whatever happens to already sit on
    disk, so a retry never blindly trusts stale or adversarial disk content.
    This can carry NEW root records on a retry too (a deliberate superset of
    I-SEED-6's "carries nothing new" wording -- accepted, review cycle 1).
    """
    merge = _merge_coord_content(request)
    if merge.fork is not None:
        raise merge.fork
    if in_place:
        final_dir = _write_merge_in_place(request, merge)
    else:
        try:
            final_dir = _write_merge_via_temp_rename(request, merge)
        except OSError:
            from specify_cli.missions._read_path_resolver import CoordState, probe_coord_state

            re_probed = probe_coord_state(request.repo_root, request.mission_slug, request.mid8, coordination_branch=request.coordination_branch)
            if re_probed is CoordState.MATERIALIZED:
                # L3: another cooperating holder of this same lock already
                # materialized it first (re-entrant call); nothing lost.
                return SeedReport()
            raise
    return _commit_and_restore(request, merge, final_dir, restored_from_branch=restored_from_branch)


def _seed_coord_surface_locked(request: _SeedRequest) -> SeedReport:
    from specify_cli.missions._read_path_resolver import CoordState, probe_coord_state

    state = probe_coord_state(request.repo_root, request.mission_slug, request.mid8, coordination_branch=request.coordination_branch)
    if state is CoordState.MATERIALIZED:
        if not _seed_pending(request):
            return SeedReport()
        return _run_merge_and_commit(request, in_place=True)

    restored_from_branch: tuple[str, ...] = ()
    if request.post_fix and state is CoordState.EMPTY:
        # B1/B2: the restore-from-tip now happens HERE, under the lock, after
        # a fresh re-probe -- never outside it. If another writer already won
        # (state is MATERIALIZED by the time we got the lock), we fall
        # through to the ordinary pending check above on THIS call's own
        # probe, so a concurrent restore can never race a concurrent
        # triggering write for the same Mission dir.
        restored_from_branch = _restore_coord_kind_paths_from_tip(request.repo_root, request.coordination_branch, request.mission_dir_name, request.coord_worktree)

    _cleanup_stale_seed_temp_dirs(request)
    # Once the tip content (if any) is restored, the merge pipeline below
    # compares CURRENT root content against it and carries any root-only
    # records forward too (B1) -- never just the restored tip in isolation.
    return _run_merge_and_commit(request, in_place=request.post_fix, restored_from_branch=restored_from_branch)


def _seed_coord_surface(request: _SeedRequest) -> SeedReport:
    """Carry root-checkout COORD records onto the coordination surface exactly once.

    See ``contracts/seed.md``. Runs under the mission status lock (I-SEED-1);
    re-entrant, so a caller already holding it (``BookkeepingTransaction``) is
    not deadlocked. Module-private (review cycle 2, B7): by contract, the
    only caller is :func:`establish_coord_write_location` in this module.
    """
    from specify_cli.status import (
        BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
        feature_status_lock,
        mission_lock_key,
    )
    from specify_cli.status import registered_hold

    lock_root = _lock_root(request)
    key = mission_lock_key(request.root_mission_dir, repo_root=lock_root)
    with (
        feature_status_lock(lock_root, key, timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS),
        registered_hold(lock_root, request.root_mission_dir.name, key),
    ):
        return _seed_coord_surface_locked(request)


# ---------------------------------------------------------------------------
# establish_coord_write_location
# ---------------------------------------------------------------------------


def _primary_write_location(repo_root: Path, mission_slug: str, kind: MissionArtifactKind, owned: OwnedCheckout | None) -> WriteLocation:
    path = placement_seam(repo_root, mission_slug, owned=owned).read_dir(kind)
    checkout_root = owned.owned_root if owned is not None else repo_root
    return WriteLocation(
        path=path,
        surface_root=checkout_root,
        surface=TopologySurface.PRIMARY,
        coord_state_before=None,
        establishment=Establishment.NONE,
    )


def _resolve_coord_worktree_root(repo_root: Path, mission_slug: str, mid8: str, owned: OwnedCheckout | None) -> Path:
    from specify_cli.coordination.workspace import CoordinationWorkspace

    root = owned.repository_root if owned is not None else repo_root
    worktree: Path = CoordinationWorkspace.worktree_path(root, mission_slug, mid8)
    return worktree


def _establish_owned_coord_workspace(owned: OwnedCheckout, mission_slug: str, mid8: str) -> None:
    from runtime.next.runtime_bridge import _resolve_owned_coordination_workspace
    from specify_cli.coordination.workspace import CoordinationWorkspace

    _resolve_owned_coordination_workspace(CoordinationWorkspace, owned.repository_root, mission_slug, mid8)


def _materialize_for_write(
    repo_root: Path,
    mission_slug: str,
    mid8: str,
    coordination_branch: str,
    owned: OwnedCheckout | None,
) -> CoordState:
    from specify_cli.missions._read_path_resolver import probe_coord_state

    if owned is not None:
        try:
            _establish_owned_coord_workspace(owned, mission_slug, mid8)
        except Exception as exc:  # translated into the owned refusal code (C-001: no new error type)
            raise ActionContextError(
                OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value,
                f"owned coordination workspace unavailable for mission {mission_slug!r}: {exc}",
            ) from exc
    else:
        from specify_cli.coordination.surface_resolver import materialize_coord_surface_for_write

        # Review cycle 2 (B1-residual): pass the ALREADY-resolved identity
        # (declared OR deterministically derived, Decision plan.design.
        # undeclared-coord-branch) explicitly rather than letting this call
        # re-derive it from meta.json a second, narrower way -- a re-derivation
        # that only sees a DECLARED branch would no-op for a genuinely
        # coordination-routed Mission whose branch is merely undeclared,
        # silently leaving the worktree UNMATERIALIZED.
        materialize_coord_surface_for_write(repo_root, mission_slug, coordination_branch=coordination_branch, mid8=mid8)
    return probe_coord_state(repo_root, mission_slug, mid8, coordination_branch=coordination_branch)


def _raise_coord_branch_deleted(
    repo_root: Path,
    mission_slug: str,
    mid8: str,
    coordination_branch: str,
    primary_candidate: Path,
) -> NoReturn:
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    raise CoordinationBranchDeleted.for_mission(
        repo_root=repo_root,
        mission_slug=mission_slug,
        mid8=mid8,
        coordination_branch=coordination_branch,
        primary_candidate=primary_candidate,
    )


@dataclass(frozen=True, kw_only=True)
class _EstablishContext:
    repo_root: Path
    mission_slug: str
    mission_dir_name: str
    mid8: str
    mission_id: str
    coordination_branch: str
    coord_worktree: Path
    root_mission_dir: Path
    owned: OwnedCheckout | None


def _to_seed_request(ctx: _EstablishContext, *, post_fix: bool) -> _SeedRequest:
    return _SeedRequest(
        repo_root=ctx.repo_root,
        mission_slug=ctx.mission_slug,
        mission_dir_name=ctx.mission_dir_name,
        mid8=ctx.mid8,
        mission_id=ctx.mission_id,
        coordination_branch=ctx.coordination_branch,
        coord_worktree=ctx.coord_worktree,
        root_mission_dir=ctx.root_mission_dir,
        post_fix=post_fix,
        owned=ctx.owned,
    )


def _handle_materialized(
    ctx: _EstablishContext,
    coord_state_before: CoordState,
    *,
    base_establishment: Establishment,
) -> WriteLocation:
    """L2: a cheap, lock-free fast path skips the whole seed call (and its 10s-bounded
    lock acquisition) for the overwhelming common case -- a MATERIALIZED
    surface with nothing pending. The full, lock-protected check in
    :func:`_seed_coord_surface_locked` still runs whenever this fast path
    cannot already rule pending out, so a false negative here is never a
    correctness risk, only a missed optimisation.
    """
    coord_dir = ctx.coord_worktree / KITTY_SPECS_DIR / ctx.mission_dir_name
    if not _whole_dir_untracked_fast(ctx.coord_worktree, ctx.mission_dir_name):
        return WriteLocation(
            path=coord_dir,
            surface_root=ctx.coord_worktree,
            surface=TopologySurface.COORD,
            coord_state_before=coord_state_before,
            establishment=base_establishment,
            seed=None,
        )
    report = _seed_coord_surface(_to_seed_request(ctx, post_fix=False))
    seed = report if (report.carried or report.coord_commit or report.warnings) else None
    return WriteLocation(
        path=coord_dir,
        surface_root=ctx.coord_worktree,
        surface=TopologySurface.COORD,
        coord_state_before=coord_state_before,
        establishment=base_establishment,
        seed=seed,
    )


def _handle_empty_pre_fix(ctx: _EstablishContext, coord_state_before: CoordState) -> WriteLocation:
    report = _seed_coord_surface(_to_seed_request(ctx, post_fix=False))
    coord_dir = ctx.coord_worktree / KITTY_SPECS_DIR / ctx.mission_dir_name
    return WriteLocation(
        path=coord_dir,
        surface_root=ctx.coord_worktree,
        surface=TopologySurface.COORD,
        coord_state_before=coord_state_before,
        establishment=Establishment.SEEDED,
        seed=report,
    )


def _handle_empty_post_fix(ctx: _EstablishContext, coord_state_before: CoordState) -> WriteLocation:
    """B1/B2: the restore-from-tip and the root-only-record carry now both
    happen inside :func:`_seed_coord_surface`'s locked, re-probed section --
    this handler only logs the loud warning and reports the outcome.
    """
    logger.warning(
        "coordination Mission dir missing from worktree for mission %s (branch %s); restoring from branch tip.",
        ctx.mission_slug,
        ctx.coordination_branch,
    )
    report = _seed_coord_surface(_to_seed_request(ctx, post_fix=True))
    coord_dir = ctx.coord_worktree / KITTY_SPECS_DIR / ctx.mission_dir_name
    return WriteLocation(
        path=coord_dir,
        surface_root=ctx.coord_worktree,
        surface=TopologySurface.COORD,
        coord_state_before=coord_state_before,
        establishment=Establishment.RESTORED_FROM_BRANCH,
        seed=report,
    )


def _handle_unmaterialized(repo_root: Path, mission_slug: str, ctx: _EstablishContext) -> WriteLocation:
    from specify_cli.missions._read_path_resolver import CoordState

    new_state = _materialize_for_write(repo_root, mission_slug, ctx.mid8, ctx.coordination_branch, ctx.owned)
    materialized_ctx = replace(ctx, coord_worktree=_resolve_coord_worktree_root(repo_root, mission_slug, ctx.mid8, ctx.owned))
    if new_state is CoordState.MATERIALIZED:
        # B5: the state machine just transitioned UNMATERIALIZED ->
        # MATERIALIZED -- report WORKTREE_MATERIALIZED (contract + T016),
        # unless the pending-seed check inside ``_handle_materialized``
        # finds a genuine seed to run, in which case ``seed`` is populated
        # too (the WriteLocation still names the base establishment as the
        # transition that happened; a populated ``seed`` tells the caller
        # more happened than a bare materialization).
        return _handle_materialized(materialized_ctx, CoordState.UNMATERIALIZED, base_establishment=Establishment.WORKTREE_MATERIALIZED)
    if new_state is CoordState.EMPTY:
        if not coord_branch_is_post_fix(repo_root, ctx.coordination_branch, ctx.mission_id):
            return _handle_empty_pre_fix(materialized_ctx, CoordState.UNMATERIALIZED)
        return _handle_empty_post_fix(materialized_ctx, CoordState.UNMATERIALIZED)
    # Materialization is documented to leave only MATERIALIZED/EMPTY on
    # success (surface_resolver.materialize_coord_surface_for_write); any
    # other outcome means it already raised.
    raise AssertionError(f"unexpected coord state after materialization: {new_state!r}")


def _stored_topology_routes_through_coordination(meta: dict[str, object], owned: OwnedCheckout | None) -> bool:
    """Return whether this write should route through coordination, per the STORED topology.

    Review cycle 2 (B1-residual, Decision ``plan.design.undeclared-coord-
    branch``): the topology gate for an UNDECLARED ``coordination_branch`` is
    keyed on the ONE canonical predicate (:func:`routes_through_coordination`)
    over the STORED topology -- never on branch presence (SC-001, the retired
    inference B1-residual's root cause restated). The owned arm additionally
    consults ``owned.topology`` -- the fact's OWN minted topology, independent
    of whatever an (possibly stale/absent) owned meta copy says -- because a
    real owned coordination-routed Mission can mint its coordination branch
    without ever recording it in meta.json (the O8 shape, cycle-1 N1 comment).
    A topology-less / un-backfilled legacy meta (``stored_topology_from_meta``
    returns ``None``) is coord-LESS here -- the historical "declare nothing ->
    PRIMARY" control stays unchanged.
    """
    from specify_cli.missions._read_path_resolver import stored_topology_from_meta

    stored_topology = stored_topology_from_meta(meta)
    if stored_topology is not None and routes_through_coordination(stored_topology):
        return True
    return owned is not None and routes_through_coordination(owned.topology)


def _derive_branch_for_undeclared(
    repo_root: Path,
    mission_slug: str,
    meta: dict[str, object],
    mid8: str,
    owned: OwnedCheckout | None,
) -> str | None:
    """Resolve an UNDECLARED ``coordination_branch`` without ever degrading a coord-routed topology to PRIMARY.

    Review cycle 2 (B1-residual, Decision ``plan.design.undeclared-coord-
    branch`` -- supersedes the plain "refuse" half of the cycle-1 B1 ruling).
    ``meta.json``'s ``coordination_branch`` is only a RECORD; the branch itself
    is minted by the ONE deterministic naming grammar
    (:func:`~specify_cli.lanes.branch_naming.coord_reconstruct_branch`, the
    SAME naming :class:`~specify_cli.coordination.workspace.CoordinationWorkspace`
    uses). When the record is missing this derives the name a second way and
    checks git directly BEFORE ever falling back to PRIMARY.

    Returns:
        ``None`` when the stored topology is coord-LESS (legacy / topology-
        less meta, or a genuinely coord-less stored shape) -- the caller takes
        the historical "declare nothing -> PRIMARY" leg, UNCHANGED.

        The derived branch name when the topology routes through coordination
        AND that branch exists in git -- the caller proceeds EXACTLY as if it
        had been declared.

    Raises:
        CoordBranchUndeclaredAndAbsent: when the topology routes through
            coordination and the derived branch does not exist (or no mid8
            could even be resolved to derive one) -- NEVER degrades to
            PRIMARY for a coordination-routed topology.
    """
    if not _stored_topology_routes_through_coordination(meta, owned):
        return None
    if not mid8:
        raise CoordBranchUndeclaredAndAbsent(mission_slug=mission_slug, derived_branch=None)
    from specify_cli.coordination.surface_resolver import _coord_branch_exists
    from specify_cli.lanes.branch_naming import coord_reconstruct_branch

    # ``coord_reconstruct_branch`` is typed ``-> str`` but the
    # ``follow_imports=skip`` boundary on ``specify_cli.*`` widens it to
    # ``Any``; bind explicitly so the declared return narrows back (the same
    # pattern ``resolution.py``'s ``primary_dir: Path = resolve_planning_
    # read_dir(...)`` already uses for the same mypy-config artifact).
    derived_branch: str = coord_reconstruct_branch(mission_slug, mid8=mid8)
    if not _coord_branch_exists(repo_root, derived_branch):
        raise CoordBranchUndeclaredAndAbsent(mission_slug=mission_slug, derived_branch=derived_branch)
    return derived_branch


def establish_coord_write_location(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    *,
    owned: OwnedCheckout | None = None,
) -> WriteLocation:
    """Resolve, materialize, seed or refuse the write location for a COORD write.

    See ``contracts/write-location-accessor.md``. Absorbs the coordination
    write gate (research D22): the old refusal for an ``UNMATERIALIZED``
    local-head coordination branch that already carries committed content is
    replaced by materializing and letting the state machine below decide.

    A non-owned caller may pass a lane worktree as ``repo_root``.
    :meth:`PlacementSeam.read_dir` re-anchors that checkout to the main
    repository. This function does the same before it composes the
    coordination worktree, so a lane caller cannot grow a second
    coordination home under the lane checkout.
    """
    if owned is None:
        from specify_cli.core.paths import get_main_repo_root

        repo_root = get_main_repo_root(repo_root)
    if is_primary_artifact_kind(kind):
        return _primary_write_location(repo_root, mission_slug, kind, owned)

    from specify_cli.coordination.surface_resolver import resolve_declared_mid8
    from specify_cli.missions._read_path_resolver import (
        CoordState,
        coord_feature_dir,
        probe_coord_state,
        read_primary_meta,
    )

    # <owned>-aware meta read (declared out-of-map fix, coord-artifact-single-
    # home-01M3V4BE WP09): ``read_primary_meta`` composes
    # ``repo_root/KITTY_SPECS_DIR/<slug>`` directly and is NOT owned-aware --
    # for an owned Mission, ``meta.json`` lives at ``owned.mission_dir`` (the
    # owned checkout P), never under the real repository root R. Reading the
    # wrong (empty) location silently found no ``coordination_branch``,
    # degrading EVERY owned coordination-kind write to the declared-PRIMARY
    # fallback regardless of the Mission's real (coordination-routed)
    # topology -- latent since this function shipped, surfaced by WP09's
    # migration of ``DecisionGitLog``'s owned arm onto this accessor (the
    # prior inline ladder had its OWN owned-aware identity read and never
    # reached this function for an owned caller at all). ``root_mission_dir``
    # (needed either way, below) IS the owned-aware primary dir
    # ``placement_seam`` already resolves correctly for both arms --
    # resolved once, here, and reused for the meta read on the owned arm
    # instead of a second, owned-blind resolution.
    root_mission_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    if owned is not None:
        from specify_cli.core.paths import load_meta_fail_closed

        meta = load_meta_fail_closed(root_mission_dir) or {}
        if not meta.get("coordination_branch"):
            # Fallback (review cycle 1, B1): an owned fact's own PRIMARY dir
            # may legitimately carry no ``meta.json`` yet, or one that has not
            # been copied/kept in sync with the declaring repository-root
            # checkout (a bootstrap window, or a caller/fixture that never
            # populated the owned copy) -- while the REAL repository-root
            # checkout already declares ``coordination_branch`` for this
            # Mission. Silently treating the owned-aware miss as "this Mission
            # is coord-less" (the regression the owned-aware read above fixed
            # a different way introduced) is a fail-open the accessor's
            # contract forbids: a caller whose coordination workspace is
            # genuinely unavailable must see that refusal, not a quiet
            # PRIMARY write. Trying the repository-root meta.json ONLY when
            # the owned-aware read found nothing keeps the owned read
            # authoritative (an owned copy that DOES declare the branch is
            # never second-guessed) while still discovering a real
            # coordination-routed Mission whose owned copy is merely stale/
            # absent, so materialization (and its own failure propagation,
            # `test_owned_arm_translates_workspace_failure`) is still
            # attempted instead of degraded past.
            fallback_meta, _ = read_primary_meta(owned.repository_root, mission_slug)
            if fallback_meta.get("coordination_branch"):
                meta = fallback_meta
    else:
        meta, _declares_coordination = read_primary_meta(repo_root, mission_slug)
    raw_branch = meta.get("coordination_branch")
    coordination_branch = str(raw_branch) if raw_branch else None
    mid8 = resolve_declared_mid8(meta, mission_slug)
    if coordination_branch is None:
        coordination_branch = _derive_branch_for_undeclared(repo_root, mission_slug, meta, mid8, owned)
        if coordination_branch is None:
            return _primary_write_location(repo_root, mission_slug, kind, owned)
    mission_id = str(meta.get("mission_id") or "")
    mission_dir_name = coord_feature_dir(repo_root, mission_slug, mid8).name

    state = probe_coord_state(repo_root, mission_slug, mid8, coordination_branch=coordination_branch)
    coord_worktree = _resolve_coord_worktree_root(repo_root, mission_slug, mid8, owned)
    ctx = _EstablishContext(
        repo_root=repo_root,
        mission_slug=mission_slug,
        mission_dir_name=mission_dir_name,
        mid8=mid8,
        mission_id=mission_id,
        coordination_branch=coordination_branch,
        coord_worktree=coord_worktree,
        root_mission_dir=root_mission_dir,
        owned=owned,
    )

    if state is CoordState.DELETED:
        _raise_coord_branch_deleted(repo_root, mission_slug, mid8, coordination_branch, root_mission_dir)
    if state is CoordState.UNMATERIALIZED:
        return _handle_unmaterialized(repo_root, mission_slug, ctx)
    if state is CoordState.MATERIALIZED:
        return _handle_materialized(ctx, CoordState.MATERIALIZED, base_establishment=Establishment.NONE)
    # state is EMPTY.
    if not coord_branch_is_post_fix(repo_root, coordination_branch, mission_id):
        return _handle_empty_pre_fix(ctx, CoordState.EMPTY)
    return _handle_empty_post_fix(ctx, CoordState.EMPTY)
