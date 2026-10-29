"""Implementation evidence and review independence of approved work packages (#6715, #5939).

The single authority for the question "may this approved work package land as reviewed?",
asked by ``consolidate`` (claim time, :func:`~specify_cli.consolidation.reconciliation.build_approved_wp_set`),
``orchestrator-api consolidate-mission`` / ``accept-mission`` and, through the same predicate,
``accept`` and ``move-task``. It is a separate axis from the approval bound
(:mod:`~specify_cli.consolidation.approved_bound`, unchanged): the bound refuses content a lane
gained after its approval; this axis refuses an approval with no owned content behind it, or one
recorded by the implementer itself.

Per approved (or ``done``), non-canceled work package, first match wins (data-model.md):

1. ``EVIDENCE_WINDOW_UNCOMPUTABLE``: ``lanes.json`` records no planning commit.
2. ``IMPLEMENTATION_UNREADABLE``: the window's tree diff cannot be read (fail closed, NFR-002).
3. ``IMPLEMENTATION_MISSING``: no non-bookkeeping changed path of the window matches the work
   package's ``owned_files`` and no no-implementation attestation is in force for it (one recorded
   since the work package last left ``{approved, done}``).
4. ``REVIEW_NOT_INDEPENDENT``: :func:`~specify_cli.consolidation.preflight._independent_reviewer_confirmed`
   (the #5939 ``tool:model:profile`` identities, compared segment-wise by
   :func:`~specify_cli.status.actor_identities_independent`, operator ruling R1) is False.

The evidence window is ``planning_commit_sha..<tip>``: the lane branch for a code lane, the target
branch for a planning lane, the Mission branch for a single_branch Mission
(:func:`~specify_cli.lanes.single_branch_landing.single_branch_evidence_window`). It is a tree diff,
so a change committed and then reverted counts as nothing. At most one diff is taken per lane
(NFR-001). Matching every changed path of the window against a work package's ``owned_files``
rests on the disjoint-owner model, as the #5939 axis did.

single_branch Missions keep emitting the ``SINGLE_BRANCH_*`` codes and their refusal text; every
other topology emits the neutral codes. :data:`_SINGLE_BRANCH_ALIASES` maps one onto the other.
"""

from __future__ import annotations

import fnmatch
import logging
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY
from specify_cli.consolidation.git_probes import GitProbeError, changed_paths_in_range
from specify_cli.lanes.compute import is_planning_lane, lane_created_branch, lane_fully_canceled
from specify_cli.lanes.for_review_gate import status_only_excluded_prefixes
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status import is_migration_actor

logger = logging.getLogger(__name__)

IMPLEMENTATION_MISSING = "IMPLEMENTATION_MISSING"
REVIEW_NOT_INDEPENDENT = "REVIEW_NOT_INDEPENDENT"
IMPLEMENTATION_UNREADABLE = "IMPLEMENTATION_UNREADABLE"
EVIDENCE_WINDOW_UNCOMPUTABLE = "EVIDENCE_WINDOW_UNCOMPUTABLE"
_NEUTRAL_CODES: tuple[str, ...] = (IMPLEMENTATION_MISSING, REVIEW_NOT_INDEPENDENT, IMPLEMENTATION_UNREADABLE, EVIDENCE_WINDOW_UNCOMPUTABLE)

SINGLE_BRANCH_IMPLEMENTATION_MISSING = "SINGLE_BRANCH_IMPLEMENTATION_MISSING"
SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT = "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT"
_SINGLE_BRANCH_EVIDENCE_UNREADABLE = "SINGLE_BRANCH_EVIDENCE_UNREADABLE"
SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE = "SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE"
SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE = "SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE"

#: Documented aliases (same meaning) of the neutral codes; single_branch still emits them.
_SINGLE_BRANCH_ALIASES: Mapping[str, str] = {
    SINGLE_BRANCH_IMPLEMENTATION_MISSING: IMPLEMENTATION_MISSING,
    SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT: REVIEW_NOT_INDEPENDENT,
    _SINGLE_BRANCH_EVIDENCE_UNREADABLE: IMPLEMENTATION_UNREADABLE,
    SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE: IMPLEMENTATION_UNREADABLE,
    SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE: EVIDENCE_WINDOW_UNCOMPUTABLE,
}

#: ``policy_metadata[ATTESTATION_KEY]`` value of a no-implementation attestation (written by
#: ``consolidation.no_implementation_attestation``); it lifts ``IMPLEMENTATION_MISSING`` only.
NO_IMPLEMENTATION = "no_implementation"
#: The CLI flag (on ``accept`` and ``consolidate``) that records that attestation.
ATTEST_NO_IMPLEMENTATION_FLAG = "--attest-no-implementation"

_APPROVED_MEMBERSHIP_LANES: frozenset[str] = frozenset({"approved", "done"})
_ALL_CODES: tuple[str, ...] = (*_NEUTRAL_CODES, *_SINGLE_BRANCH_ALIASES)

_CANNOT_VERIFY = "so implementation evidence cannot be verified."
_NOT_INDEPENDENT_DETAIL = (
    "was approved without a confirmable independent review "
    "(the implementer of record and the approving actor are the same identity, or one of them is not recorded)."
)


def _canonical_code(code: str) -> str:
    """The neutral code for *code*: a ``SINGLE_BRANCH_*`` alias maps to its neutral code, anything else is returned as is."""
    return _SINGLE_BRANCH_ALIASES.get(code, code)


def _refusal_codes(text: str) -> list[str]:
    """Every distinct evidence code (neutral or alias) that leads a line of *text*, first-seen first."""
    pattern = "|".join(re.escape(code) for code in sorted(_ALL_CODES, key=len, reverse=True))
    return list(dict.fromkeys(re.findall(rf"^({pattern}): ", text, flags=re.MULTILINE)))


def owned_patterns(owned_files: Iterable[str]) -> tuple[str, ...]:
    """Normalized ownership globs for a work package (blank entries dropped, ``./`` and ``\\`` normalized)."""
    return tuple(pattern.replace("\\", "/").removeprefix("./") for pattern in owned_files if pattern.strip())


def matches_owned(path: str, patterns: Sequence[str]) -> bool:
    """Glob match of a repo-relative *path* against ownership *patterns*: the evidence axis' matcher.

    ``move-task`` and the evidence axis share it. It mirrors the commit guard's own matcher
    (``policy.commit_guard._matches_any_glob``), a separate, pre-existing authority for commit
    scoping that this does not replace.
    """
    normalized = path.replace("\\", "/").removeprefix("./")
    for pattern in patterns:
        if fnmatch.fnmatch(normalized, pattern):
            return True
        prefix = pattern.replace("/**", "").replace("/*", "").rstrip("/")
        if prefix and normalized.startswith(prefix + "/"):
            return True
    return False


def _bookkeeping_prefixes(mission_slug: str) -> tuple[str, ...]:
    """Path prefixes that never count as implementation (the one evidence / ``for_review`` exclusion list)."""
    prefixes: tuple[str, ...] = status_only_excluded_prefixes(mission_slug)
    return prefixes


def _is_evidence_path(path: str, mission_slug: str) -> bool:
    """True when *path* is not Mission bookkeeping (the status log, ``meta.json``, ``.kittify/`` and the other tool-written Mission files)."""
    return not path.replace("\\", "/").startswith(_bookkeeping_prefixes(mission_slug))


def lane_evidence_window(lanes_manifest: LanesManifest, lane: ExecutionLane) -> tuple[str, str] | None:
    """``(planning_commit_sha, tip)`` for a lanes/coord lane, or ``None`` when no planning commit is recorded.

    The tip is the lane branch for a code lane and the target branch for a planning lane
    (planning-artifact work lands on the target, never on a lane branch).
    """
    base = lanes_manifest.planning_commit_sha
    if not base:
        return None
    if is_planning_lane(lane):
        return (base, lanes_manifest.target_branch)
    tip: str = lane_created_branch(lanes_manifest, lane.lane_id)
    return (base, tip)


def evidence_paths(repo_root: Path, window: tuple[str, str], mission_slug: str) -> frozenset[str]:
    """The non-bookkeeping paths whose content differs across *window*; raises :class:`GitProbeError` when unreadable."""
    base, tip = window
    return frozenset(path for _status, path in changed_paths_in_range(repo_root, base, tip) if _is_evidence_path(path, mission_slug))


def has_owned_change(paths: Iterable[str], patterns: Sequence[str]) -> bool:
    """True when some changed path matches the work package's ownership *patterns* (none: never)."""
    return bool(patterns) and any(matches_owned(path, patterns) for path in paths)


def _is_no_implementation_attestation(event: Any) -> bool:
    metadata = getattr(event, "policy_metadata", None) or {}
    return metadata.get(ATTESTATION_KEY) == NO_IMPLEMENTATION and not is_migration_actor(getattr(event, "actor", ""))


#: Lanes a work package may sit in without voiding its no-implementation attestation.
_ATTESTATION_KEEPING_LANES = frozenset({"approved", "done"})


def _in_force_attestations(events: Iterable[Any]) -> dict[str, Any]:
    """Work package id -> its no-implementation attestation in force, read in APPEND order.

    Operator ruling 2026-10-27: an attestation counts only while the work package has stayed in
    ``{approved, done}`` since it was recorded. Any later non-migration event of that work package
    whose ``to_lane`` is outside that set (a reopen, a rejection, a re-claim) voids it, so a
    re-approval needs a fresh attestation. Consolidate's own ``approved -> done``, forced
    self-transitions (a second attestation, ``--attest-approved-reviewed``) and a resume keep it.
    Migration actors neither record nor void one. The order is the log's append order (as
    ``preflight._latest_actor_for_transition`` reads it), never the wall clock.
    """
    in_force: dict[str, Any] = {}
    for event in events:
        if is_migration_actor(getattr(event, "actor", "")):
            continue
        wp_id = str(getattr(event, "wp_id", ""))
        if _is_no_implementation_attestation(event):
            in_force[wp_id] = event
        elif str(getattr(event, "to_lane", "")) not in _ATTESTATION_KEEPING_LANES:
            in_force.pop(wp_id, None)
    return in_force


def in_force_no_implementation_attestation(events: Iterable[Any], wp_id: str) -> Any | None:
    """The no-implementation attestation of *wp_id* that is in force (the newest unvoided one), or ``None``."""
    return _in_force_attestations(events).get(wp_id)


def _attested_no_implementation(events: Iterable[Any], wp_id: str) -> bool:
    """True iff *wp_id* has a no-implementation attestation in force (see :func:`_in_force_attestations`)."""
    return in_force_no_implementation_attestation(events, wp_id) is not None


def _no_implementation_attested_wp_ids(events: Iterable[Any]) -> frozenset[str]:
    """Every work package with a no-implementation attestation in force."""
    return frozenset(_in_force_attestations(events))


def _approved_wp_ids(work_packages: Mapping[str, Any], excluded_canceled_wp_ids: frozenset[str]) -> list[str]:
    """Approved (or already-done), non-canceled work package ids of the reduced snapshot, sorted."""
    return sorted(
        wp for wp, state in work_packages.items() if wp not in excluded_canceled_wp_ids and str((state or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES
    )


def _wp_task_dir(repo_root: Path, mission_slug: str, feature_dir: Path) -> Path:
    """The mission dir the ``tasks/`` work-package files are read from.

    ``WORK_PACKAGE_TASK`` is a PRIMARY-partition kind: under coordination topology the
    coord-aware *feature_dir* is the coordination worktree, which carries only the status and
    matrix artifacts, so a ``tasks/`` read there comes back empty and every work package would
    read as "ownership unresolved" (#2118). The kind-aware placement seam resolves the
    topology-blind primary dir, and it is the only dir read: a coordination copy of ``tasks/``
    may be stale, so no ``tasks/`` on the primary partition leaves ownership unresolved (every
    approved work package then refuses, fail closed). *feature_dir* is accepted for the call
    shape only.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    del feature_dir  # never a fallback: see the docstring
    primary: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    return primary


def _owned_patterns_by_wp(repo_root: Path, mission_slug: str, feature_dir: Path, wp_ids: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """Each wanted work package's authored ownership globs (static frontmatter, never runtime state).

    A work package file that cannot be read stays unresolved; the caller reads an absent or empty
    pattern set as "implementation cannot be proven" and refuses (fail closed).
    """
    from specify_cli.status import read_authored_wp_frontmatter, wp_task_files

    wanted = set(wp_ids)
    resolved: dict[str, tuple[str, ...]] = {}
    for wp_file in wp_task_files(_wp_task_dir(repo_root, mission_slug, feature_dir) / "tasks"):
        try:
            meta, _body = read_authored_wp_frontmatter(wp_file)
        except Exception:  # noqa: BLE001 — an unreadable WP file leaves it unresolved; the caller fails closed
            logger.debug("evidence: could not read WP frontmatter at %s", wp_file, exc_info=True)
            continue
        if meta.work_package_id in wanted:
            resolved[meta.work_package_id] = owned_patterns(meta.owned_files)
    return resolved


@dataclass(frozen=True)
class EvidenceReport:
    """The axis' verdict for one Mission: the refusal text (``None`` = pass) and the attested work packages.

    ``lifted_wp_ids`` names every work package whose ``IMPLEMENTATION_MISSING`` an attestation
    lifted (it may still refuse for another reason), so callers can say so in their output.
    ``verdicts`` maps each refused work package to its first (neutral) code; a work package
    absent from it passed.
    """

    refusal: str | None = None
    lifted_wp_ids: frozenset[str] = frozenset()
    verdicts: Mapping[str, str] = field(default_factory=dict)

    @property
    def codes(self) -> list[str]:
        """Every distinct code the refusal names, first-seen first (empty on a pass)."""
        return _refusal_codes(self.refusal) if self.refusal else []


@dataclass
class _Scan:
    """One Mission's evaluation state: inputs resolved once, findings collected per work package."""

    feature_dir: Path
    events: Callable[[], Sequence[Any] | None]
    owned: dict[str, tuple[str, ...]]
    lines: list[tuple[str, str]]
    lifted: set[str]
    verdicts: dict[str, str] = field(default_factory=dict)
    _attested: frozenset[str] | None = None

    def attested(self, wp_id: str) -> bool:
        if self._attested is None:
            events = self.events()
            # An unreadable log yields no attestation, so IMPLEMENTATION_MISSING stands (fail closed).
            self._attested = _no_implementation_attested_wp_ids(events) if events is not None else frozenset()
        return wp_id in self._attested

    def add(self, wp_id: str, line: str) -> None:
        self.lines.append((wp_id, line))
        self.mark((wp_id,), line.partition(": ")[0])

    def mark(self, wp_ids: Iterable[str], code: str) -> None:
        """Record *code* as the verdict of each of *wp_ids* that has none yet (first match wins)."""
        for wp_id in wp_ids:
            self.verdicts.setdefault(wp_id, _canonical_code(code))


def _independent(feature_dir: Path, wp_id: str) -> bool:
    from specify_cli.consolidation.preflight import _independent_reviewer_confirmed

    confirmed: bool = _independent_reviewer_confirmed(feature_dir, wp_id)
    return confirmed


def _judge(scan: _Scan, wp_id: str, paths: frozenset[str], missing_line: Callable[[str], str], not_independent_code: str) -> None:
    """Verdicts 3 and 4 for one work package whose window was read."""
    if not has_owned_change(paths, scan.owned.get(wp_id, ())):
        if not scan.attested(wp_id):
            scan.add(wp_id, missing_line(wp_id))
            return
        scan.lifted.add(wp_id)
    if not _independent(scan.feature_dir, wp_id):
        scan.add(wp_id, f"{not_independent_code}: {wp_id} {_NOT_INDEPENDENT_DETAIL}")


# ---------------------------------------------------------------- single_branch (#5939)


def _single_branch_refusal_text(mission_slug: str, lines: Sequence[str]) -> str:
    """The #5939 refusal text: a header, a line per work package (code-led), one recovery line.

    The ``mission_slug`` is interpolated as PROSE (a ``": "`` sentence boundary), never joined as a
    name operand, so this builds a human-readable message, not a lane/branch/worktree name.
    """
    recovery = (
        "Recovery: implement the work package (commit a real change in its owned_files on the "
        "mission branch) and have a reviewer who is not the implementer approve it, then re-run consolidate."
    )
    body_parts = [*lines, recovery]
    body = "\n".join(body_parts)
    return f"Mission {mission_slug}: single_branch work packages cannot be landed as reviewed:\n{body}"


def _single_branch_scan(repo_root: Path, lanes_manifest: LanesManifest, scan: _Scan, approved: Sequence[str], window: tuple[str, str] | None) -> str | None:
    if window is None:
        line = (
            f"{SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE}: the implementation-evidence window "
            "(planning_commit..mission_branch) cannot be computed for this single_branch mission "
            f"(no recorded planning commit), {_CANNOT_VERIFY} "
            "Recovery: run `spec-kitty agent mission finalize-tasks` to record the planning commit, then re-run."
        )
        scan.mark(approved, SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE)
        return _single_branch_refusal_text(lanes_manifest.mission_slug, [line])
    base, tip = window
    try:
        paths = evidence_paths(repo_root, window, lanes_manifest.mission_slug)
    except GitProbeError:
        line = f"{_SINGLE_BRANCH_EVIDENCE_UNREADABLE}: the implementation-evidence window {base}..{tip} could not be diffed, {_CANNOT_VERIFY}"
        scan.mark(approved, _SINGLE_BRANCH_EVIDENCE_UNREADABLE)
        return _single_branch_refusal_text(lanes_manifest.mission_slug, [line])

    def missing(wp_id: str) -> str:
        detail = f"was approved with no implementation commit touching its owned_files in the mission branch window {base}..{tip}."
        return f"{SINGLE_BRANCH_IMPLEMENTATION_MISSING}: {wp_id} {detail}"

    for wp_id in approved:
        _judge(scan, wp_id, paths, missing, SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT)
    if not scan.lines:
        return None
    return _single_branch_refusal_text(lanes_manifest.mission_slug, [line for _wp, line in scan.lines])


# ---------------------------------------------------------------- lanes / coord (#6715)

_RECOVERY: Mapping[str, str] = {
    EVIDENCE_WINDOW_UNCOMPUTABLE: (
        f"Recovery for {EVIDENCE_WINDOW_UNCOMPUTABLE}: run `spec-kitty agent mission finalize-tasks` to record the planning commit, then re-run."
    ),
    IMPLEMENTATION_UNREADABLE: (
        f"Recovery for {IMPLEMENTATION_UNREADABLE}: make the lane branch and the recorded planning commit readable (restore or fetch them), then re-run."
    ),
    IMPLEMENTATION_MISSING: (
        f"Recovery for {IMPLEMENTATION_MISSING}: commit the work package's change to its owned_files (on its lane branch, or on the "
        "target branch for a planning-artifact work package) and have it reviewed and approved again. A work package that owes no "
        f'implementation is recorded with `{ATTEST_NO_IMPLEMENTATION_FLAG} <WP> --attest-reason "<why>"` on `spec-kitty accept` or '
        "`spec-kitty consolidate`."
    ),
    REVIEW_NOT_INDEPENDENT: (
        f"Recovery for {REVIEW_NOT_INDEPENDENT}: have a reviewer who is not the implementer review and approve the work package "
        "(`spec-kitty agent action review <WP> --agent <reviewer>`), then re-run. No attestation lifts this."
    ),
}


def _lanes_refusal_text(mission_slug: str, lines: Sequence[str]) -> str:
    """The lanes/coord refusal text: a header, a line per work package (code-led), one recovery line per code named."""
    codes = {_canonical_code(code) for code in _refusal_codes("\n".join(lines))}
    recovery = [_RECOVERY[code] for code in _NEUTRAL_CODES if code in codes]
    body_parts = [*lines, *recovery]
    body = "\n".join(body_parts)
    return f"Mission {mission_slug}: work packages cannot be landed as reviewed:\n{body}"


def _lane_approved(lane: ExecutionLane, work_packages: Mapping[str, Any], excluded: frozenset[str]) -> list[str]:
    if lane_fully_canceled(lane, excluded):
        return []
    return [wp for wp in lane.wp_ids if wp not in excluded and str((work_packages.get(wp) or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES]


def _merge_base(repo_root: Path, left: str, right: str) -> str:
    """:func:`~specify_cli.core.vcs.git.git_merge_base`, failing closed: raises :class:`GitProbeError` when it cannot be read."""
    from specify_cli.core.vcs.git import git_merge_base

    sha: str | None = git_merge_base(repo_root, left, right)
    if not sha:
        raise GitProbeError(f"git merge-base {left} {right} could not be read")
    return sha


def _dependency_evidence_windows(repo_root: Path, lanes_manifest: LanesManifest, lane: ExecutionLane) -> list[tuple[str, str]]:
    """``(merge-base(dependency tip, lane tip), lane tip)`` for each dependency lane whose branch exists.

    A lane takes its dependencies' content in by merge, so a work package whose reviewed
    deliverable removes or reverts content it absorbed from a dependency nets to nothing against
    the planning commit although it authored a real, reviewed change. Each window starts where
    the lane last absorbed the dependency (their merge base), so it holds only this lane's OWN
    commits since then: a dependency that advances after that point adds nothing (review cycle 1,
    #6715), and a work package that only undid its own commit still shows nothing. Read only when
    the planning window found no owned change, so the common case stays at one diff per lane
    (NFR-001). Raises :class:`GitProbeError` when a merge base cannot be read.
    """
    from specify_cli.lanes._git import branch_exists

    windows: list[tuple[str, str]] = []
    tip = lane_created_branch(lanes_manifest, lane.lane_id)
    by_id = {other.lane_id: other for other in lanes_manifest.lanes}
    for dependency_id in lane.depends_on_lanes:
        dependency = by_id.get(dependency_id)
        if dependency is None or is_planning_lane(dependency):
            continue
        branch = lane_created_branch(lanes_manifest, dependency_id)
        if branch_exists(repo_root, branch):
            windows.append((_merge_base(repo_root, branch, tip), tip))
    return windows


def _widened_paths(repo_root: Path, lanes_manifest: LanesManifest, lane: ExecutionLane, paths: frozenset[str]) -> frozenset[str]:
    """*paths* plus the paths each dependency window changes (:func:`_dependency_evidence_windows`)."""
    widened = set(paths)
    for window in _dependency_evidence_windows(repo_root, lanes_manifest, lane):
        widened |= evidence_paths(repo_root, window, lanes_manifest.mission_slug)
    return frozenset(widened)


def widened_lane_paths(
    repo_root: Path, lanes_manifest: LanesManifest, lane: ExecutionLane, paths: frozenset[str], pattern_sets: Iterable[Sequence[str]]
) -> frozenset[str]:
    """*paths* of *lane*'s planning window, widened by its dependency windows when some work package shows no owned change.

    The one rule (consolidate's claim axis and ``move-task`` both call it): a lane with
    dependency lanes whose planning window lacks an owned change for any of *pattern_sets*
    (one ownership pattern set per judged work package) adds the paths of
    :func:`_dependency_evidence_windows`. Raises :class:`GitProbeError` when a window cannot be read.
    """
    if lane.depends_on_lanes and not all(has_owned_change(paths, patterns) for patterns in pattern_sets):
        return _widened_paths(repo_root, lanes_manifest, lane, paths)
    return paths


def _scan_lane(repo_root: Path, lanes_manifest: LanesManifest, scan: _Scan, lane: ExecutionLane, approved: Sequence[str]) -> None:
    window = lane_evidence_window(lanes_manifest, lane)
    if window is None:
        for wp_id in approved:
            scan.add(
                wp_id,
                f"{EVIDENCE_WINDOW_UNCOMPUTABLE}: {wp_id} has no evidence window ({lane.lane_id}: lanes.json records no planning commit), {_CANNOT_VERIFY}",
            )
        return
    base, tip = window
    try:
        paths = evidence_paths(repo_root, window, lanes_manifest.mission_slug)
    except GitProbeError as exc:
        for wp_id in approved:
            scan.add(
                wp_id,
                f"{IMPLEMENTATION_UNREADABLE}: {wp_id}'s evidence window {base}..{tip} ({lane.lane_id}) could not be diffed ({exc}), {_CANNOT_VERIFY}",
            )
        return

    def missing(wp_id: str) -> str:
        return f"{IMPLEMENTATION_MISSING}: {wp_id} was approved with no change to its owned_files in its evidence window {base}..{tip} ({lane.lane_id})."

    try:
        paths = widened_lane_paths(repo_root, lanes_manifest, lane, paths, [scan.owned.get(wp_id, ()) for wp_id in approved])
    except GitProbeError as exc:
        for wp_id in approved:
            scan.add(
                wp_id,
                f"{IMPLEMENTATION_UNREADABLE}: {wp_id}'s window against its dependency lanes ({lane.lane_id}) could not be diffed ({exc}), {_CANNOT_VERIFY}",
            )
        return
    for wp_id in approved:
        _judge(scan, wp_id, paths, missing, REVIEW_NOT_INDEPENDENT)


def _lanes_scan(repo_root: Path, lanes_manifest: LanesManifest, scan: _Scan, work_packages: Mapping[str, Any], excluded: frozenset[str]) -> str | None:
    for lane in lanes_manifest.lanes:
        approved = _lane_approved(lane, work_packages, excluded)
        if approved:
            _scan_lane(repo_root, lanes_manifest, scan, lane, approved)
    laned = {wp for lane in lanes_manifest.lanes for wp in lane.wp_ids}
    for wp_id in _approved_wp_ids(work_packages, excluded):
        if wp_id not in laned:
            # Judged like every approved work package (the single_branch path judges all): one in
            # no lane of lanes.json has no lane to window, so its evidence cannot be read.
            scan.add(wp_id, f"{EVIDENCE_WINDOW_UNCOMPUTABLE}: {wp_id} is approved but in no lane of lanes.json, {_CANNOT_VERIFY}")
    if not scan.lines:
        return None
    ordered = [line for _wp, line in sorted(scan.lines, key=lambda item: item[0])]
    return _lanes_refusal_text(lanes_manifest.mission_slug, ordered)


def evaluate_evidence(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: Iterable[str] = (),
    *,
    events: Callable[[], Sequence[Any] | None],
    is_single_branch: bool | None = None,
) -> EvidenceReport:
    """The evidence + independence verdict for every approved work package of a Mission.

    *work_packages* is the reduced snapshot's map; *events* returns the status events in append
    order (or ``None`` when the log cannot be read) and is called at most once, only when an
    attestation could matter. *is_single_branch* is the STORED topology; ``None`` reads it.
    """
    from specify_cli.lanes.single_branch_landing import is_single_branch_mission, single_branch_evidence_window

    excluded = frozenset(excluded_canceled_wp_ids)
    approved = _approved_wp_ids(work_packages, excluded)
    if not approved:
        return EvidenceReport()
    scan = _Scan(feature_dir, events, _owned_patterns_by_wp(repo_root, lanes_manifest.mission_slug, feature_dir, approved), [], set())
    single_branch = is_single_branch_mission(repo_root, lanes_manifest) if is_single_branch is None else is_single_branch
    if single_branch:
        window = single_branch_evidence_window(repo_root, lanes_manifest, assume_single_branch=True)
        refusal = _single_branch_scan(repo_root, lanes_manifest, scan, approved, window)
    else:
        refusal = _lanes_scan(repo_root, lanes_manifest, scan, work_packages, excluded)
    return EvidenceReport(refusal=refusal, lifted_wp_ids=frozenset(scan.lifted), verdicts=dict(scan.verdicts))


def mission_evidence_report(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    *,
    excluded_canceled_wp_ids: Iterable[str] = (),
) -> EvidenceReport:
    """Public entry for callers outside the claim builder (``accept``, ``orchestrator-api``).

    Reads WP membership through :func:`specify_cli.status.materialize_snapshot` exactly as the
    claim builder does. A snapshot or status log that cannot be read raises (``StoreError``) so
    the caller refuses; nothing here passes on an unreadable input.
    """
    from specify_cli.status import materialize_snapshot, read_events

    snapshot = materialize_snapshot(feature_dir)
    return evaluate_evidence(
        repo_root,
        feature_dir,
        lanes_manifest,
        snapshot.work_packages or {},
        excluded_canceled_wp_ids,
        events=lambda: read_events(feature_dir),
    )


__all__ = [
    "ATTEST_NO_IMPLEMENTATION_FLAG",
    "EVIDENCE_WINDOW_UNCOMPUTABLE",
    "EvidenceReport",
    "IMPLEMENTATION_MISSING",
    "IMPLEMENTATION_UNREADABLE",
    "NO_IMPLEMENTATION",
    "REVIEW_NOT_INDEPENDENT",
    "SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE",
    "SINGLE_BRANCH_IMPLEMENTATION_MISSING",
    "SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE",
    "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT",
    "evaluate_evidence",
    "evidence_paths",
    "has_owned_change",
    "in_force_no_implementation_attestation",
    "lane_evidence_window",
    "matches_owned",
    "mission_evidence_report",
    "owned_patterns",
    "widened_lane_paths",
]
