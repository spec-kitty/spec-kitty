"""``finalize-tasks``: the single_branch pin's branch line and evidence-window guard (#7793, #7297).

A ``single_branch`` Mission's implementation evidence window is ``planning_commit..mission_branch``
(:func:`specify_cli.lanes.single_branch_landing.single_branch_evidence_window`). This module keeps
finalize's pin decisions consistent with that window (ADR ``2026-10-04-5`` Amendment 2026-11-22):

* :func:`resolve_pin_line` -- the branch the pin is captured from, refreshed against and derived on
  (``lanes.planning_base.pin_branch_line`` over the stored ``meta.json``).
* :func:`window_keeps_owned_work` -- a candidate pin is acceptable only when, for every work
  package whose ``owned_files`` the recorded window changes, the candidate window still changes
  them. It reads the same evidence the ``move-task`` gate and ``consolidate`` read
  (``consolidation.wp_evidence``), per work package as they do.
* :func:`follow_orphaned_pin` -- the rebased copy of an orphaned pin, matched by patch-id, or the
  named refusal code when there is none.

The window itself stays computed only in ``consolidation.wp_evidence``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from mission_runtime import OwnedCheckout

#: The orphaned pin's change is on no commit of the branch (or the pin has an empty diff).
NO_PATCH_ID_MATCH: Final = "PLANNING_PIN_NO_PATCH_ID_MATCH"
#: The orphaned pin's change is on more than one commit of the branch; finalize never guesses.
PATCH_ID_AMBIGUOUS: Final = "PLANNING_PIN_PATCH_ID_AMBIGUOUS"
#: The candidate pin would drop the committed owned-file work out of the evidence window.
WOULD_EMPTY_WINDOW: Final = "PLANNING_PIN_WOULD_EMPTY_WINDOW"
#: The one recovery no finalize run can do for the operator: a refresh records the branch tip and
#: derivation runs only when no pin is recorded, so a pin that leaves committed work outside the
#: window is corrected by hand (#7793, squad review).
MANUAL_PIN_REMEDY: Final = (
    "set planning_commit_sha in lanes.json by hand to the commit just before the Mission's first "
    "implementation commit, commit lanes.json on the mission branch, then retry"
)


class PinWindowUnreadable(Exception):
    """The window guard could not read a work package's ownership or the window itself (fail closed)."""


@dataclass(frozen=True)
class _PinLine:
    """Where this Mission's pin lives: the branch, whether the single_branch rules apply, and the
    upstream branches whose copy of the planning commit is never the Mission's own (#7793 B2)."""

    branch: str
    single_branch: bool
    upstream_refs: tuple[str, ...] = ()


def resolve_pin_line(repo_root: Path, mission_slug: str, target_branch: str, *, owned: OwnedCheckout | None = None) -> _PinLine:
    """The pin branch line of *mission_slug*, read from its stored ``meta.json`` (#7297 item 2).

    ``upstream_refs`` are the target branch and the repository's primary branch, less the pin line
    itself, each with its remote-tracking refs (``refs/remotes/<remote>/<name>``): a rebase moves a
    Mission onto one of them, often ``origin/main`` while the local ``main`` is stale, and a copy of
    the planning commit already there is that upstream's, not the Mission's (#7793 review B2).
    """
    from mission_runtime import is_single_branch

    from specify_cli.core.git_ops import resolve_primary_branch
    from specify_cli.lanes.planning_base import pin_branch_line
    from specify_cli.lanes.single_branch_landing import stored_mission_meta
    from specify_cli.migration.backfill_topology import stored_topology

    meta: dict[str, Any] = stored_mission_meta(repo_root, mission_slug, owned=owned)
    branch = pin_branch_line(meta, target_branch)
    single_branch = is_single_branch(stored_topology(meta))
    upstream: tuple[str, ...] = ()
    if single_branch:
        primary = resolve_primary_branch(repo_root, bias=False)
        names = [ref for ref in (target_branch, primary) if ref and ref != branch]
        upstream = tuple(dict.fromkeys([*names, *_remote_tracking_refs(repo_root, names)]))
    return _PinLine(branch=branch, single_branch=single_branch, upstream_refs=upstream)


def _remote_tracking_refs(repo_root: Path, names: list[str]) -> list[str]:
    """Every ``refs/remotes/<remote>/<name>`` that exists for *names* (none when git cannot list them)."""
    from kernel.git import GitCommandError, run_git

    if not names:
        return []
    try:
        listed = run_git(repo_root, "for-each-ref", "--format=%(refname)", "refs/remotes").stdout.decode("utf-8", "replace").split()
    except GitCommandError:
        return []
    wanted = set(names)
    return [ref for ref in listed if ref.count("/") >= 3 and ref.split("/", 3)[3] in wanted]


def _owned_patterns_by_wp(planning_dir: Path) -> dict[str, tuple[str, ...]]:
    """Each work package's normalized ``owned_files`` patterns (``tasks/WP*.md``), keyed by file name.

    Raises:
        PinWindowUnreadable: a work package task file cannot be read, so its ownership is unknown.
    """
    from specify_cli.frontmatter import FrontmatterError
    from specify_cli.ownership.matching import owned_patterns
    from specify_cli.status import read_authored_wp_frontmatter

    by_wp: dict[str, tuple[str, ...]] = {}
    for wp_file in sorted((planning_dir / "tasks").glob("WP*.md")):
        try:
            metadata, _body = read_authored_wp_frontmatter(wp_file)
        except (FrontmatterError, ValueError, OSError) as exc:  # ValueError covers pydantic's ValidationError
            raise PinWindowUnreadable(f"the work package task file {wp_file} could not be read ({type(exc).__name__})") from exc
        by_wp[wp_file.name] = tuple(owned_patterns(metadata.owned_files))
    return by_wp


def window_keeps_owned_work(
    repo_root: Path,
    mission_slug: str,
    planning_dir: Path,
    *,
    recorded: str | None,
    candidate: str,
    tip: str,
    upstream_refs: tuple[str, ...] = (),
) -> bool:
    """False when *candidate*..*tip* loses a work package's committed owned-file change (#7793).

    The work at risk is the Mission's own: the commits on *tip* reachable from neither *recorded*
    nor an upstream ref that does not contain *recorded* (``git log tip --not recorded upstreams``;
    a ref that already reaches the pin is downstream, see :func:`_bounds_the_mission`). Reading the recorded window
    ``recorded..tip`` instead would count an upstream change a rebase brought in as the Mission's
    work, and refuse a correct re-pin whenever the upstream touched a file a not-yet-started work
    package owns (squad F1). Judged per work package, as the gates judge it: every work package
    with an owned change among the Mission's own commits must keep one in the candidate window.
    True when nothing bounds the Mission's own commits (no recorded pin and no upstream), or no
    work package has committed owned work.

    Raises:
        PinWindowUnreadable: the ownership or either window cannot be read (the caller fails closed).
    """
    from specify_cli.consolidation import wp_evidence
    from specify_cli.consolidation.git_probes import GitProbeError

    if recorded is not None and recorded == candidate:
        return True
    by_wp = {wp: patterns for wp, patterns in _owned_patterns_by_wp(planning_dir).items() if patterns}
    if not by_wp:
        return True
    if recorded is not None and not _resolves(repo_root, recorded):
        raise PinWindowUnreadable(f"the recorded planning commit {recorded} cannot be read")
    bounds = ([recorded] if recorded else []) + [ref for ref in upstream_refs if _bounds_the_mission(repo_root, ref, recorded)]
    if not bounds:
        return True
    own = _own_changed_paths(repo_root, tip, bounds)
    at_risk = [patterns for patterns in by_wp.values() if wp_evidence.has_owned_change(own, patterns)]
    if not at_risk:
        return True
    try:
        after = wp_evidence.evidence_paths(repo_root, (candidate, tip), mission_slug)
    except GitProbeError as exc:
        raise PinWindowUnreadable(f"the evidence window could not be read: {exc}") from exc
    return all(wp_evidence.has_owned_change(after, patterns) for patterns in at_risk)


def _bounds_the_mission(repo_root: Path, ref: str, recorded: str | None) -> bool:
    """True when upstream *ref* resolves and does not already contain the *recorded* pin.

    A ref that reaches the recorded pin is downstream of the Mission (gitflow: ``develop`` merged
    into ``main``): the Mission's work it also carries is still the Mission's, so it bounds nothing
    (Tier R review B1). In the rebase case the orphaned pin is unreachable from the upstream, which
    therefore still bounds the Mission's own commits (squad F1).

    Raises:
        PinWindowUnreadable: the ancestry probe fails for a reason other than "not an ancestor".
    """
    from kernel.git import GitCommandError, run_git

    if not _resolves(repo_root, ref):
        return False
    if recorded is None:
        return True
    try:
        run_git(repo_root, "merge-base", "--is-ancestor", recorded, ref)
    except GitCommandError as exc:
        if exc.returncode == 1:
            return True  # the pin is not on the ref: it is upstream of the Mission's work
        raise PinWindowUnreadable(f"could not tell whether {ref} contains the recorded planning commit: {exc}") from exc
    return False


def _resolves(repo_root: Path, ref: str) -> bool:
    """True when *ref* names a commit here."""
    from kernel.git import run_git

    return run_git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).returncode == 0


def _own_changed_paths(repo_root: Path, tip: str, bounds: list[str]) -> frozenset[str]:
    """Paths the non-merge commits on *tip* reachable from none of *bounds* change.

    The commits are the intersection of each ``bound..tip`` range; each one's paths come from
    ``kernel.git.commit_paths``. A merge contributes its combined-diff paths (conflict-resolved
    and evil-merge paths), so the walk can only over-count the work at risk, never miss it.

    Raises:
        PinWindowUnreadable: git cannot list them.
    """
    from kernel.git import GitCommandError, commit_paths
    from specify_cli.consolidation.git_probes import GitProbeError, commits_in_range

    try:
        ranges = [set(commits_in_range(repo_root, bound, tip)) for bound in bounds]
        own = set.intersection(*ranges) if ranges else set()
        return frozenset(str(path) for commit in sorted(own) for path in commit_paths(repo_root, commit))
    except (GitCommandError, GitProbeError) as exc:
        raise PinWindowUnreadable(f"the Mission's own commits could not be listed: {exc}") from exc


@dataclass(frozen=True)
class _OrphanFollow:
    """The re-pin target for an orphaned pin, or the refusal code and reason when there is none."""

    sha: str | None
    error_code: str | None = None
    reason: str = ""


def follow_orphaned_pin(repo_root: Path, recorded: str, tip: str, *, upstream_refs: tuple[str, ...] = ()) -> _OrphanFollow:
    """The rebased copy of the orphaned *recorded* pin on *tip*'s history, by patch-id (#7793).

    A copy reachable from one of *upstream_refs* is the upstream's, never the Mission's (B2).

    Raises:
        PinWindowUnreadable: a git probe failed (never read as "no match").
    """
    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.lanes.planning_base import follow_pin_by_patch_id

    try:
        follow = follow_pin_by_patch_id(repo_root, recorded, tip, upstream_refs=upstream_refs)
    except GitProbeError as exc:
        raise PinWindowUnreadable(f"the patch-id of the recorded planning commit could not be followed: {exc}") from exc
    if follow.sha is not None:
        return _OrphanFollow(sha=follow.sha)
    if follow.miss == "ambiguous":
        return _OrphanFollow(sha=None, error_code=PATCH_ID_AMBIGUOUS, reason=f"its change is on {len(follow.candidates)} commits ({', '.join(follow.candidates)})")
    if follow.miss == "upstream_only":
        return _OrphanFollow(
            sha=None,
            error_code=NO_PATCH_ID_MATCH,
            reason=(
                f"its change is only on the upstream ({', '.join(upstream_refs)}): the rebase dropped the Mission's copy as "
                "already applied, and pinning the upstream copy would count the upstream's later commits as this Mission's work"
            ),
        )
    if follow.miss == "no_patch_id":
        return _OrphanFollow(sha=None, error_code=NO_PATCH_ID_MATCH, reason="it has an empty diff, so there is no change to follow")
    return _OrphanFollow(sha=None, error_code=NO_PATCH_ID_MATCH, reason="no commit on the branch carries its change (the rebase dropped or rewrote it)")
