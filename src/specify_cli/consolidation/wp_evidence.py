"""Implementation evidence and review independence of approved work packages (#6715, #5939).

The single authority for the question "may this approved work package land as reviewed?",
asked by ``consolidate`` (claim time, :func:`~specify_cli.consolidation.reconciliation.build_approved_wp_set`),
``orchestrator-api consolidate-mission`` / ``accept-mission`` and, through the same predicate,
``accept`` and ``move-task``. It is a separate axis from the approval bound
(:mod:`~specify_cli.consolidation.approved_bound`, unchanged): the bound refuses content a lane
gained after its approval; this axis refuses an approval with no owned content behind it, or one
recorded by the implementer itself.

Per approved (or ``done``), non-canceled work package, first match wins (data-model.md):

1. ``EVIDENCE_WINDOW_UNCOMPUTABLE``: ``lanes.json`` records no planning commit (for a
   ``consolidate --skip-lanes`` Mission with no ``lanes.json``: none could be derived from git, #7209).
2. ``IMPLEMENTATION_UNREADABLE``: the window's tree diff cannot be read (fail closed, NFR-002). When
   the window's tip is a branch ref that is truly absent, the refusal says which shape that is
   (:func:`absent_lane_window_cause`): restore actual lane history if it existed, or escalate an
   absent lane window without fabricating one; the verified-landing route stays available (#7120).
3. ``OWNERSHIP_UNRESOLVED`` (#7149): the work package is absent from the resolved ownership map
   (its task file, or the whole ``tasks/`` directory, could not be read), so there is no
   ``owned_files`` declaration to judge against. It is decided before the owned-change test, so the
   verdict below means only "ownership resolved, no owned change". No attestation lifts it.
4. ``IMPLEMENTATION_MISSING``: no non-bookkeeping changed path of the window matches the work
   package's ``owned_files`` and no no-implementation attestation is in force for it (one recorded
   since the work package last left ``{approved, done}``). An authored ``owned_files`` list,
   an empty one included, is a resolved declaration and lands here.
5. ``REVIEW_NOT_INDEPENDENT``: :func:`~specify_cli.consolidation.preflight._independent_reviewer_confirmed`
   (the #5939 ``tool:model:profile`` identities, compared segment-wise by
   :func:`~specify_cli.status.actor_identities_independent`, operator ruling R1) is False.

The evidence window is ``planning_commit_sha..<tip>``: the lane branch for a code lane, the target
branch for a planning lane, the Mission branch for a single_branch Mission
(:func:`~specify_cli.lanes.single_branch_landing.single_branch_evidence_window`). It is a tree diff,
so a change committed and then reverted counts as nothing. At most one diff is taken per lane
(NFR-001). Matching every changed path of the window against a work package's ``owned_files``
rests on the disjoint-owner model, as the #5939 axis did.

A Mission landed through a pull request never runs ``consolidate``, and its lane branches are
normally pruned once the landing is on the target (#6780). A caller that has verified the PR
landing commit (``accept --mode pr --merge-commit``) passes it as *landed_commit*; a lane whose
window tip no longer resolves is then judged on ``planning_commit..landed_commit`` — same base,
same owned-content criterion — instead of refusing the whole lane as unreadable
(:func:`_landed_window`). Only the PR's own side counts (``landing^1..landing``), only a landing
that is a true merge commit can stand in, and a work package whose ``owned_files`` overlap another
approved work package's is refused on that path. Without a landing commit the window stays
fail-closed and the refusal names the absent ref and both remedies.

single_branch Missions keep emitting the ``SINGLE_BRANCH_*`` codes and their refusal text; every
other topology emits the neutral codes. :data:`_SINGLE_BRANCH_ALIASES` maps one onto the other.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY
from specify_cli.consolidation.git_probes import GitProbeError, changed_paths_in_range, commit_parents, sha_reachable_from
from specify_cli.lanes.compute import is_planning_lane, lane_created_branch, lane_fully_canceled
from specify_cli.lanes.derived_planning_base import SKIP_LANES_SYNTHESIS_SOURCE
from specify_cli.lanes.for_review_gate import status_only_excluded_prefixes
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status import is_migration_actor

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout

logger = logging.getLogger(__name__)

IMPLEMENTATION_MISSING = "IMPLEMENTATION_MISSING"
REVIEW_NOT_INDEPENDENT = "REVIEW_NOT_INDEPENDENT"
IMPLEMENTATION_UNREADABLE = "IMPLEMENTATION_UNREADABLE"
EVIDENCE_WINDOW_UNCOMPUTABLE = "EVIDENCE_WINDOW_UNCOMPUTABLE"
OWNERSHIP_UNRESOLVED = "OWNERSHIP_UNRESOLVED"
_NEUTRAL_CODES: tuple[str, ...] = (
    IMPLEMENTATION_MISSING,
    REVIEW_NOT_INDEPENDENT,
    IMPLEMENTATION_UNREADABLE,
    EVIDENCE_WINDOW_UNCOMPUTABLE,
    OWNERSHIP_UNRESOLVED,
)

SINGLE_BRANCH_IMPLEMENTATION_MISSING = "SINGLE_BRANCH_IMPLEMENTATION_MISSING"
SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT = "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT"
_SINGLE_BRANCH_EVIDENCE_UNREADABLE = "SINGLE_BRANCH_EVIDENCE_UNREADABLE"
SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE = "SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE"
SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE = "SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE"
_SINGLE_BRANCH_OWNERSHIP_UNRESOLVED = "SINGLE_BRANCH_OWNERSHIP_UNRESOLVED"

#: Documented aliases (same meaning) of the neutral codes; single_branch still emits them.
_SINGLE_BRANCH_ALIASES: Mapping[str, str] = {
    SINGLE_BRANCH_IMPLEMENTATION_MISSING: IMPLEMENTATION_MISSING,
    SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT: REVIEW_NOT_INDEPENDENT,
    _SINGLE_BRANCH_EVIDENCE_UNREADABLE: IMPLEMENTATION_UNREADABLE,
    SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE: IMPLEMENTATION_UNREADABLE,
    SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE: EVIDENCE_WINDOW_UNCOMPUTABLE,
    _SINGLE_BRANCH_OWNERSHIP_UNRESOLVED: OWNERSHIP_UNRESOLVED,
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


def _wp_task_dir(repo_root: Path, mission_slug: str, feature_dir: Path, *, owned: OwnedCheckout | None = None) -> Path:
    """The mission dir the ``tasks/`` work-package files are read from.

    Without *owned*, ``WORK_PACKAGE_TASK`` belongs to PRIMARY, never a possibly stale
    coordination copy (#2118). A validated *owned* fact selects the placement seam's
    owned authority instead (#7099). Missing ownership fails closed in either case;
    *feature_dir* is retained for compatibility, never used as a fallback.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    del feature_dir  # never a fallback: see the docstring
    primary: Path = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    return primary


_REASON_MAX = 160
_WP_PREFIX = re.compile(r"^(WP\d+)")


def _failure_summary(exc: Exception) -> str:
    """One line naming the error class and a short message (pydantic errors read as ``msg: 'field'``)."""
    from pydantic import ValidationError

    if isinstance(exc, ValidationError):
        message = "; ".join(f"{err['msg']}: {', '.join(repr(str(part)) for part in err['loc'])}" for err in exc.errors())
    else:
        message = " ".join(str(exc).split())
    if len(message) > _REASON_MAX:
        message = message[: _REASON_MAX - 3] + "..."
    return f"{type(exc).__name__}: {message}"


def _read_ownership(
    repo_root: Path,
    mission_slug: str,
    feature_dir: Path,
    wp_ids: Iterable[str],
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[dict[str, tuple[str, ...]], dict[str, str], Path]:
    """The wanted work packages' authored ownership globs, why each other one is unresolved, and the ``tasks/`` dir read.

    Ownership comes from static frontmatter, never runtime state. A work package that is absent from
    the first mapping is unresolved (fail closed, #7149) and :func:`_judge` refuses it as
    ``OWNERSHIP_UNRESOLVED``; the second mapping holds a one-line reason for it. Unresolved means a
    missing or unreadable ``tasks/`` directory, a task file that exists but could not be read or
    validated, no task file declaring the id, or an id declared by more than one task file (or by one
    file while another could not be read), so no single declaration can be trusted. A key that is
    present, even with an empty tuple, is an authored declaration judged on the evidence: a task file
    that omits ``owned_files`` reads as an authored empty list (``WPMetadata.owned_files`` defaults to
    ``[]``), which keeps the pre-#7149 ``IMPLEMENTATION_MISSING`` verdict. *owned* threads the
    validated owned-checkout fact to the one ``tasks/`` read (:func:`_wp_task_dir`, #7099).
    """
    from specify_cli.status import read_authored_wp_frontmatter, wp_task_files

    wanted = set(wp_ids)
    tasks_dir = _wp_task_dir(repo_root, mission_slug, feature_dir, owned=owned) / "tasks"
    try:
        wp_files = wp_task_files(tasks_dir)
    except OSError as exc:
        logger.debug("evidence: could not list %s", tasks_dir, exc_info=True)
        return {}, dict.fromkeys(wanted, f"the tasks directory could not be read ({tasks_dir}: {_failure_summary(exc)})"), tasks_dir
    resolved: dict[str, tuple[str, ...]] = {}
    declared_in: dict[str, list[str]] = {}
    failures: dict[str, str] = {}
    unattributed: list[str] = []
    for wp_file in wp_files:
        try:
            meta, _body = read_authored_wp_frontmatter(wp_file)
        except Exception as exc:  # noqa: BLE001 — an unreadable WP file leaves it unresolved; the caller fails closed
            logger.debug("evidence: could not read WP frontmatter at %s", wp_file, exc_info=True)
            prefix = _WP_PREFIX.match(wp_file.name)
            if prefix:
                failures.setdefault(prefix.group(1), f"its task file {wp_file.name} exists but could not be read ({_failure_summary(exc)})")
            else:
                unattributed.append(wp_file.name)
            continue
        if meta.work_package_id in wanted:
            declared_in.setdefault(meta.work_package_id, []).append(wp_file.name)
            resolved[meta.work_package_id] = owned_patterns(meta.owned_files)
    conflicts: dict[str, str] = {}
    for wp, names in declared_in.items():
        if len(names) > 1:
            conflicts[wp] = f"{wp} is declared by {len(names)} task files: {', '.join(names)}"
        elif wp in failures:
            conflicts[wp] = f"{failures[wp]}, while {names[0]} also declares {wp}"
    for wp in conflicts:
        del resolved[wp]
    suffix = f" ({len(unattributed)} task file(s) could not be read: {', '.join(unattributed)})" if unattributed else ""

    def _default(wp: str) -> str:
        if not tasks_dir.is_dir():
            return f"the tasks directory does not exist ({tasks_dir})"
        return f"no task file under {tasks_dir} declares work_package_id {wp}{suffix}"

    reasons = {wp: conflicts.get(wp) or failures.get(wp) or _default(wp) for wp in wanted if wp not in resolved}
    return resolved, reasons, tasks_dir


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
    tasks_dir: Path
    verdicts: dict[str, str] = field(default_factory=dict)
    unresolved_reasons: dict[str, str] = field(default_factory=dict)
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


def _unresolved_line(scan: _Scan, wp_id: str, code: str) -> str:
    return (
        f"{code}: {wp_id} owned_files could not be read from {scan.tasks_dir}: "
        f"{scan.unresolved_reasons.get(wp_id, 'its task file is missing or unreadable')}, so implementation evidence cannot be judged."
    )


def _judge(
    scan: _Scan,
    wp_id: str,
    paths: frozenset[str],
    missing_line: Callable[[str], str],
    not_independent_code: str,
    unresolved_code: str,
) -> None:
    """Verdicts 3 to 5 for one work package whose window was read (unresolved ownership first)."""
    if wp_id not in scan.owned:
        scan.add(wp_id, _unresolved_line(scan, wp_id, unresolved_code))
        return
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
    codes = _refusal_codes("\n".join(lines))
    unresolved = _SINGLE_BRANCH_OWNERSHIP_UNRESOLVED in codes
    scope = " for the other work packages" if unresolved else ""
    body_parts = list(lines)
    if unresolved:
        body_parts.append(
            f"Recovery for {_SINGLE_BRANCH_OWNERSHIP_UNRESOLVED}: restore or commit the work package's task file with its owned_files, "
            "or re-run from the checkout that owns the Mission (for `accept`, pass `--owned-checkout <path>`), then re-run. A task file rejected for an unknown "
            "or retired key needs that key removed (its validation error names it). No attestation lifts this."
        )
    if not unresolved or len(codes) > 1:
        body_parts.append(
            f"Recovery{scope}: implement the work package (commit a real change in its owned_files on the "
            "mission branch) and have a reviewer who is not the implementer approve it, then re-run consolidate."
        )
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
        _judge(scan, wp_id, paths, missing, SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT, _SINGLE_BRANCH_OWNERSHIP_UNRESOLVED)
    if not scan.lines:
        return None
    return _single_branch_refusal_text(lanes_manifest.mission_slug, [line for _wp, line in scan.lines])


# ---------------------------------------------------------------- lanes / coord (#6715)

_RECOVERY: Mapping[str, str] = {
    EVIDENCE_WINDOW_UNCOMPUTABLE: (
        f"Recovery for {EVIDENCE_WINDOW_UNCOMPUTABLE}: run `spec-kitty agent mission finalize-tasks` to record the planning commit, then re-run."
    ),
    IMPLEMENTATION_UNREADABLE: (
        f"Recovery for {IMPLEMENTATION_UNREADABLE}: restore or fetch the branch the window ends at (and the recorded planning commit) so it is readable again, "
        "or, for a Mission that landed through a pull request merge commit (not a squash), re-run `spec-kitty accept --mode pr --merge-commit <sha>` "
        "with the verified PR landing commit so the evidence is judged against the landed tree. Restore a lane branch only from its actual recorded history; "
        "a lane that never existed has no lane window to restore. If work exists only on the target branch and no verified PR landing commit is available, "
        "escalate the evidence-policy question (#7120) instead of retrying that window. Do not manufacture a lane branch to satisfy this gate."
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
    OWNERSHIP_UNRESOLVED: (
        f"Recovery for {OWNERSHIP_UNRESOLVED}: restore or commit the work package's task file with its owned_files, or re-run from the "
        "checkout that owns the Mission (for `accept`, pass `--owned-checkout <path>`), then re-run. A task file rejected for an unknown or retired key "
        "needs that key removed (its validation error names it). No attestation lifts this."
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


def branch_ref_absent(repo_root: Path, branch: str) -> bool:
    """True only when the local branch *branch* is truly absent (``git show-ref --verify`` exit 1).

    A valid ref pointing at a missing object yields exit 128, not absence. Other statuses and
    OS errors also fail closed. This preserves #6780's Git-status rule, not a filesystem-integrity
    check: Git may ignore a malformed loose-ref file and return 1. Never raises.

    Public since #7120, so a surface outside this module (``move-task``'s evidence gate) applies
    the same rule instead of reading a failed diff as a missing branch.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet", "--", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 1


@dataclass(frozen=True)
class _LandedWindow:
    """The window actually judged for a lane, plus what it stands in for (#6780).

    ``absent_ref`` names the window tip that no longer resolves (``None`` while it still
    does); ``landed_commit`` is the caller-verified PR landing commit that stands in for it,
    or ``None`` when none was supplied (the window is then the absent one, and its diff
    fails closed as before). The two are independent: a pruned tip with no stand-in keeps
    ``absent_ref`` so the refusal can name it, and a stand-in is only ever recorded beside
    the ref it replaces.
    """

    window: tuple[str, str]
    absent_ref: str | None = None
    landed_commit: str | None = None


def _code_lane_branches(lanes_manifest: LanesManifest) -> tuple[str, ...]:
    """The branch each CODE lane of *lanes_manifest* would have, in manifest order (planning lanes excluded)."""
    return tuple(lane_created_branch(lanes_manifest, lane.lane_id) for lane in lanes_manifest.lanes if not is_planning_lane(lane))


def _lane_branches_absent_locally(repo_root: Path, lanes_manifest: LanesManifest, branch: str) -> bool:
    """True when *branch* is a code lane's branch and no code lane of the Mission has a local branch (#7120).

    A LOCAL fact, never a history: an absent ref cannot distinguish a branch that was never created
    from one pruned here or never fetched. That is why it is only used to choose the wording of a
    refusal, and why the wording states the shape as a possibility rather than a finding. False when
    *branch* is not a code lane's branch (a planning lane's tip is the target branch) and False when
    any probe cannot be read (:func:`branch_ref_absent` fails closed), so an unknown never reads as
    the never-created shape.
    """
    code_branches = _code_lane_branches(lanes_manifest)
    if branch not in code_branches:
        return False
    return all(branch_ref_absent(repo_root, candidate) for candidate in code_branches)


def absent_lane_window_cause(repo_root: Path, lanes_manifest: LanesManifest, branch: str) -> str:
    """Why a window that ends at an absent *branch* cannot be read, and the honest next step (#7120).

    Three local shapes share the failed diff; none establishes the missing branch's history:

    * *branch* is not a code lane's branch — a planning lane's window ends at the target branch, and
      a ``single_branch`` Mission's at its Mission branch. Neither is a lane window, so neither the
      lane-tip ref nor the never-created shape is named; the branch is simply missing here.
    * *branch* is a code lane's branch but not every code-lane ref is confirmed absent. A sibling
      may exist or be unreadable; neither proves this lane ever existed. Restoration is conditional
      on actual recorded lane history, never a new branch pointed at target-branch work.
    * Every code-lane ref is absent locally: that is indistinguishable from target-branch execution
      without lane branches, but also from pruning or an incomplete fetch. State only the local fact.

    Both code-lane shapes share conditional restoration and the anti-fabrication caution. A lane
    that never existed has no lane window to restore; absent a verified PR landing commit, the
    remaining route is the open evidence-policy question. Callers ask this once per failed lane
    window without a landing stand-in, never per work package.
    """
    lane_tip = f"refs/spec-kitty/lane-tip/{branch}"
    if branch not in _code_lane_branches(lanes_manifest):
        return f"the branch {branch} does not exist in this checkout; fetch it (or restore the commit the window ends at), then re-run"
    local_fact = f"the lane branch {branch} does not exist in this checkout"
    if _lane_branches_absent_locally(repo_root, lanes_manifest, branch):
        local_fact += (
            ", and no lane of this Mission has a branch here. "
            f"That is indistinguishable from a Mission whose work was committed on the target branch ({lanes_manifest.target_branch}) "
            "without ever creating a lane branch"
        )
    return (
        f"{local_fact}. Local refs do not establish whether this lane previously existed. "
        f"If it did exist and was pruned or never fetched here, restore its recorded tip from `{lane_tip}` or a "
        "verified copy of that lane's history in the pull request's head, then re-run. "
        "If the lane never existed, there is no lane window to restore; stop retrying that window. "
        "Without a verified PR landing commit, ask the Mission's maintainer for an evidence-policy decision "
        "(limitation tracked at https://github.com/spec-kitty/spec-kitty/issues/7120), naming the Mission, "
        "this refusal and the implementation commit. Do not point a new lane branch at target-branch work to "
        "satisfy this gate: that fabricates the evidence it checks"
    )


def _landed_window(repo_root: Path, window: tuple[str, str], landed_commit: str | None) -> _LandedWindow:
    """Resolve the window to judge, standing a verified landing commit in for a pruned tip (#6780).

    A Mission landed through a pull request never runs ``consolidate``, and its lane branches
    are normally pruned once the landing is on the target, so the branch the planning window
    ended at is gone even though every deliverable is on the target. When the caller supplies
    *landed_commit* — the commit it has already verified as this Mission's PR landing commit —
    the window becomes ``landing^1..landing``: the net change the merge brought onto the target,
    i.e. the pull request's own side, so unrelated work that reached the target before the merge
    never reads as evidence. The owned-content match, the bookkeeping exclusion and the
    independence check are unchanged. The window is still WIDER than one lane's (it holds every
    work package of the PR), which :func:`_overlapping_owners` compensates for by refusing a work
    package whose ownership overlaps another's.

    The stand-in applies only when the branch ref is truly absent (:func:`branch_ref_absent`),
    the planning commit is an ancestor of the landing, the landing is a merge commit and the
    planning commit sits on a non-first-parent side of it. Otherwise it is refused rather than
    diffed: such a window would not describe this Mission's work. A ref that exists but cannot be
    read is never treated as pruned. Raises :class:`GitProbeError` when any of those cannot be
    proven.

    A tip whose ref is present is always used as it is (the lane window stays the first choice).
    """
    base, tip = window
    if landed_commit is None or not branch_ref_absent(repo_root, tip):
        return _LandedWindow(window)
    if not sha_reachable_from(repo_root, base, landed_commit):
        raise GitProbeError(
            f"the verified landing commit {landed_commit} does not contain the recorded planning commit {base} "
            f"(the window {base}..{landed_commit} would not describe this Mission's work)"
        )
    parents = commit_parents(repo_root, landed_commit)
    if len(parents) < 2:
        raise GitProbeError(
            f"the verified landing commit {landed_commit} is not a merge commit (a squash or fast-forward landing), so the pull request's own "
            "change cannot be separated from unrelated work on the target; restore the lane branch from "
            f"`refs/spec-kitty/lane-tip/{tip}` or the pull request's head, then re-run"
        )
    if not any(sha_reachable_from(repo_root, base, parent) for parent in parents[1:]):
        raise GitProbeError(
            f"the recorded planning commit {base} is not on the merged-in side of the landing commit {landed_commit}, "
            "so that merge did not land this Mission; restore the lane branch from "
            f"`refs/spec-kitty/lane-tip/{tip}` or the pull request's head, then re-run"
        )
    return _LandedWindow((parents[0], landed_commit), absent_ref=tip, landed_commit=landed_commit)


def _naming_an_absent_tip(repo_root: Path, judged: _LandedWindow) -> _LandedWindow:
    """*judged* with ``absent_ref`` filled in when its window tip no longer resolves (#6780).

    A failed diff is not proof that the tip is gone (the object store may be unreadable for
    another reason), so the tip is probed here — on the failure path only. A window that
    still reads pays no extra probe, and a refusal can name the pruned branch instead of
    quoting git's own paraphrase of the refspec.
    """
    if judged.absent_ref is not None or not branch_ref_absent(repo_root, judged.window[1]):
        return judged
    return replace(judged, absent_ref=judged.window[1])


def _patterns_overlap(left: Sequence[str], right: Sequence[str]) -> bool:
    """True when some ownership glob of *left* can match what some glob of *right* owns (and vice versa).

    A conservative, glob-aware approximation (it reuses :func:`matches_owned`, treating each glob as a
    path of the other side): identical globs, one glob matching the other, or one being a directory
    prefix of the other all overlap. It errs toward reporting an overlap, which only refuses.
    """
    return any(a == b or matches_owned(a, [b]) or matches_owned(b, [a]) for a in left for b in right)


def _overlapping_owners(scan: _Scan, approved: Sequence[str]) -> dict[str, list[str]]:
    """Each of *approved* whose ``owned_files`` overlap another approved work package's, with those others (#6780)."""
    overlaps: dict[str, list[str]] = {}
    for wp_id in approved:
        patterns = scan.owned.get(wp_id, ())
        others = sorted(other for other, theirs in scan.owned.items() if other != wp_id and _patterns_overlap(patterns, theirs))
        if others:
            overlaps[wp_id] = others
    return overlaps


def _overlap_line(wp_id: str, lane: ExecutionLane, judged: _LandedWindow, others: Sequence[str]) -> str:
    base, tip = judged.window
    branch = judged.absent_ref
    return (
        f"{IMPLEMENTATION_UNREADABLE}: {wp_id}'s evidence window {base}..{tip} ({lane.lane_id}) cannot be attributed: the lane branch {branch} was pruned and "
        f"{wp_id}'s owned_files overlap {', '.join(others)}'s, so the landing merge alone cannot say which work package made a change there; restore the lane "
        f"branch from `refs/spec-kitty/lane-tip/{branch}` or the pull request's head, then re-run, {_CANNOT_VERIFY}"
    )


def _unreadable_line(wp_id: str, lane: ExecutionLane, judged: _LandedWindow, exc: GitProbeError, absence_cause: str | None) -> str:
    """The per-work-package ``IMPLEMENTATION_UNREADABLE`` line, naming the cause (#6780, #7120).

    A window whose tip no longer resolves is reported as such — with the stand-in it fell back
    to, or with the remedies that exist when the caller supplied no verified landing commit —
    instead of a blanket "could not be diffed". *absence_cause* is
    :func:`absent_lane_window_cause`'s answer for this window, resolved ONCE by the caller (it costs
    a probe per code lane, so it is never recomputed per work package); ``None`` keeps the generic
    unreadable wording.
    """
    base, tip = judged.window
    if judged.absent_ref is not None and judged.landed_commit is not None:
        cause = (
            f"the lane branch {judged.absent_ref} no longer exists, so the verified landing commit {tip} stands in for it; the window could not be diffed ({exc})"
        )
    elif judged.absent_ref is not None and absence_cause is not None:
        cause = (
            f"the window tip {judged.absent_ref} no longer exists: {absence_cause}. "
            "For a Mission that landed through a pull request merge commit (not a squash), pass `--merge-commit <sha>` with the verified PR landing commit "
            "on `spec-kitty accept --mode pr` to judge this work package against the landed tree"
        )
    else:
        cause = f"the window could not be diffed ({exc})"
    return f"{IMPLEMENTATION_UNREADABLE}: {wp_id}'s evidence window {base}..{tip} ({lane.lane_id}) cannot be read: {cause}, {_CANNOT_VERIFY}"


def _dependency_evidence_windows(repo_root: Path, lanes_manifest: LanesManifest, lane: ExecutionLane, tip: str | None = None) -> list[tuple[str, str]]:
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
    # The lane's EFFECTIVE tip: the lane branch, or the verified landing commit standing in
    # for a pruned one (#6780). Probing a deleted branch here would raise and take the whole
    # lane down with it, so the caller passes the tip it actually judged.
    effective_tip = tip if tip is not None else lane_created_branch(lanes_manifest, lane.lane_id)
    by_id = {other.lane_id: other for other in lanes_manifest.lanes}
    for dependency_id in lane.depends_on_lanes:
        dependency = by_id.get(dependency_id)
        if dependency is None or is_planning_lane(dependency):
            continue
        branch = lane_created_branch(lanes_manifest, dependency_id)
        if branch_exists(repo_root, branch):
            windows.append((_merge_base(repo_root, branch, effective_tip), effective_tip))
    return windows


def _widened_paths(repo_root: Path, lanes_manifest: LanesManifest, lane: ExecutionLane, paths: frozenset[str], tip: str | None = None) -> frozenset[str]:
    """*paths* plus the paths each dependency window changes (:func:`_dependency_evidence_windows`)."""
    windows = _dependency_evidence_windows(repo_root, lanes_manifest, lane, tip)
    widened = set(paths)
    for window in windows:
        widened |= evidence_paths(repo_root, window, lanes_manifest.mission_slug)
    return frozenset(widened)


def widened_lane_paths(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    paths: frozenset[str],
    pattern_sets: Iterable[Sequence[str]],
    *,
    tip: str | None = None,
) -> frozenset[str]:
    """*paths* of *lane*'s planning window, widened by its dependency windows when some work package shows no owned change.

    The one rule (consolidate's claim axis and ``move-task`` both call it): a lane with
    dependency lanes whose planning window lacks an owned change for any of *pattern_sets*
    (one ownership pattern set per judged work package) adds the paths of
    :func:`_dependency_evidence_windows`. Raises :class:`GitProbeError` when a window cannot be read.

    *tip* is the effective tip of the lane's own window when a caller judged a window other
    than ``planning_commit..<lane branch>`` (the verified landing commit standing in for a
    pruned lane branch, #6780); ``None`` reads the lane branch, as every other caller does.
    """
    if lane.depends_on_lanes and not all(has_owned_change(paths, patterns) for patterns in pattern_sets):
        return _widened_paths(repo_root, lanes_manifest, lane, paths, tip)
    return paths


def _no_window_cause(lanes_manifest: LanesManifest, lane: ExecutionLane) -> str:
    """Why *lane* has no evidence window: no recorded planning commit, or none derivable for ``--skip-lanes`` (#7209)."""
    if lanes_manifest.computed_from == SKIP_LANES_SYNTHESIS_SOURCE:
        return (
            f"{lane.lane_id}: --skip-lanes found no lanes.json, and no planning base could be derived from git, because "
            f"kitty-specs/{lanes_manifest.mission_slug}/meta.json was added in a root commit or is not on {lanes_manifest.target_branch}"
        )
    return f"{lane.lane_id}: lanes.json records no planning commit"


def _scan_lane(repo_root: Path, lanes_manifest: LanesManifest, scan: _Scan, lane: ExecutionLane, approved: Sequence[str], landed_commit: str | None = None) -> None:
    window = lane_evidence_window(lanes_manifest, lane)
    if window is None:
        cause = _no_window_cause(lanes_manifest, lane)
        for wp_id in approved:
            scan.add(wp_id, f"{EVIDENCE_WINDOW_UNCOMPUTABLE}: {wp_id} has no evidence window ({cause}), {_CANNOT_VERIFY}")
        return
    try:
        judged = _landed_window(repo_root, window, landed_commit)
    except GitProbeError as exc:
        base, tip = window
        for wp_id in approved:
            scan.add(
                wp_id,
                f"{IMPLEMENTATION_UNREADABLE}: {wp_id}'s evidence window {base}..{tip} ({lane.lane_id}) cannot be read: {exc}, {_CANNOT_VERIFY}",
            )
        return
    base, tip = judged.window
    try:
        paths = evidence_paths(repo_root, judged.window, lanes_manifest.mission_slug)
    except GitProbeError as exc:
        judged = _naming_an_absent_tip(repo_root, judged)
        absence_cause = (
            absent_lane_window_cause(repo_root, lanes_manifest, judged.absent_ref) if judged.absent_ref is not None and judged.landed_commit is None else None
        )
        for wp_id in approved:
            scan.add(wp_id, _unreadable_line(wp_id, lane, judged, exc, absence_cause))
        return

    def missing(wp_id: str) -> str:
        line = f"{IMPLEMENTATION_MISSING}: {wp_id} was approved with no change to its owned_files in its evidence window {base}..{tip} ({lane.lane_id})."
        if judged.landed_commit is not None:
            line += f" The lane branch {judged.absent_ref} was pruned, so the verified landing commit stands in for it."
        return line

    if judged.landed_commit is not None:
        # The landed window holds the whole pull request, not this lane's work: an overlapping owner cannot be told apart.
        overlaps = _overlapping_owners(scan, approved)
        for wp_id, others in overlaps.items():
            scan.add(wp_id, _overlap_line(wp_id, lane, judged, others))
        approved = [wp_id for wp_id in approved if wp_id not in overlaps]
    try:
        paths = widened_lane_paths(repo_root, lanes_manifest, lane, paths, [scan.owned.get(wp_id, ()) for wp_id in approved], tip=judged.window[1])
    except GitProbeError as exc:
        for wp_id in approved:
            scan.add(
                wp_id,
                f"{IMPLEMENTATION_UNREADABLE}: {wp_id}'s window against its dependency lanes ({lane.lane_id}) could not be diffed ({exc}), {_CANNOT_VERIFY}",
            )
        return
    for wp_id in approved:
        _judge(scan, wp_id, paths, missing, REVIEW_NOT_INDEPENDENT, OWNERSHIP_UNRESOLVED)


def _lanes_scan(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    scan: _Scan,
    work_packages: Mapping[str, Any],
    excluded: frozenset[str],
    landed_commit: str | None = None,
) -> str | None:
    for lane in lanes_manifest.lanes:
        approved = _lane_approved(lane, work_packages, excluded)
        if approved:
            _scan_lane(repo_root, lanes_manifest, scan, lane, approved, landed_commit)
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
    landed_commit: str | None = None,
    owned: OwnedCheckout | None = None,
) -> EvidenceReport:
    """The evidence + independence verdict for every approved work package of a Mission.

    *work_packages* is the reduced snapshot's map; *events* returns the status events in append
    order (or ``None`` when the log cannot be read) and is called at most once, only when an
    attestation could matter. *is_single_branch* is the STORED topology; ``None`` reads it.
    *landed_commit* is a commit the CALLER has already verified as this Mission's PR landing
    commit; a lanes/coord lane whose window tip no longer resolves is then judged on
    ``planning_commit..landed_commit`` instead (:func:`_landed_window`, #6780). ``None`` keeps
    every other caller on the lane window, unchanged. The validated *owned* fact selects
    ownership and stored-topology authority; ``None`` preserves PRIMARY reads. If both are
    supplied, an explicit ``is_single_branch`` outranks ``owned``: the argument is the caller's
    own topology verdict, so the owned checkout's stored topology is only read to fill the gap
    while the argument is ``None``.
    """
    from specify_cli.lanes.single_branch_landing import is_single_branch_mission, single_branch_evidence_window

    excluded = frozenset(excluded_canceled_wp_ids)
    approved = _approved_wp_ids(work_packages, excluded)
    if not approved:
        return EvidenceReport()
    mission_slug = lanes_manifest.mission_slug
    patterns, reasons, tasks_dir = _read_ownership(repo_root, mission_slug, feature_dir, approved, owned=owned)
    scan = _Scan(feature_dir, events, patterns, [], set(), tasks_dir, unresolved_reasons=reasons)
    single_branch = is_single_branch_mission(repo_root, lanes_manifest, owned=owned) if is_single_branch is None else is_single_branch
    if single_branch:
        window = single_branch_evidence_window(repo_root, lanes_manifest, assume_single_branch=True)
        refusal = _single_branch_scan(repo_root, lanes_manifest, scan, approved, window)
    else:
        refusal = _lanes_scan(repo_root, lanes_manifest, scan, work_packages, excluded, landed_commit)
    return EvidenceReport(refusal=refusal, lifted_wp_ids=frozenset(scan.lifted), verdicts=dict(scan.verdicts))


def mission_evidence_report(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    *,
    excluded_canceled_wp_ids: Iterable[str] = (),
    landed_commit: str | None = None,
    owned: OwnedCheckout | None = None,
) -> EvidenceReport:
    """Public entry for callers outside the claim builder (``accept``, ``orchestrator-api``).

    Reads WP membership through :func:`specify_cli.status.materialize_snapshot` exactly as the
    claim builder does. A snapshot or status log that cannot be read raises (``StoreError``) so
    the caller refuses; nothing here passes on an unreadable input. *landed_commit* is passed
    straight to :func:`evaluate_evidence` (a caller-verified PR landing commit, #6780).
    *owned* carries the caller's validated checkout authority into the evidence reads.
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
        landed_commit=landed_commit,
        owned=owned,
    )


__all__ = [
    "ATTEST_NO_IMPLEMENTATION_FLAG",
    "EVIDENCE_WINDOW_UNCOMPUTABLE",
    "EvidenceReport",
    "IMPLEMENTATION_MISSING",
    "IMPLEMENTATION_UNREADABLE",
    "NO_IMPLEMENTATION",
    "OWNERSHIP_UNRESOLVED",
    "REVIEW_NOT_INDEPENDENT",
    "SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE",
    "SINGLE_BRANCH_IMPLEMENTATION_MISSING",
    "SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE",
    "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT",
    "absent_lane_window_cause",
    "branch_ref_absent",
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
