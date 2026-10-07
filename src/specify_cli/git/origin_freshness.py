"""Origin freshness check: the ONE intent module every evidence gate calls (FR-006/007/009/010/017).

An *evidence gate* (consolidate, accept, the orchestrator-api accept/consolidate
commands, review preparation) reads a Mission's status log and approved lane
branches from a clone. In a second clone that local copy can lag the remote
(#5780, #5758, #5759). This module turns kernel ref facts
(:mod:`kernel.git.remote`) into *freshness verdicts*, applies the per-gate
policy, resolves the operator opt-out and produces the refusal data and text.

It is data-only toward rendering: it never prints, never imports
``consolidation.entry_preflight`` and returns plain strings for callers to render.
A failed contact is NEVER read as "the branch is absent" (FR-006): it yields
``unreachable``, never ``remote_missing``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from kernel.git.remote import RemoteUnreachable, divergence, fetch_branches, remote_heads, resolve_remote, tracking_ref
from mission_runtime import MissionArtifactKind, OwnedCheckout, placement_seam
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted, CoordinationWorktreeUnmaterialized
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.compute import is_planning_lane, lane_created_branch, lane_fully_canceled
from specify_cli.lanes.models import LanesManifest
from specify_cli.missions._read_path_resolver import mission_dir_aliases
from specify_cli.status import StoreError, read_events, reduce

__all__ = [
    "ORIGIN_CHECK_ENV",
    "ORIGIN_LANE_DIVERGED",
    "READ_ONLY_ORIGIN_CHECK",
    "FreshnessState",
    "FreshnessVerdict",
    "OriginCheckMode",
    "OriginCheckSetting",
    "OriginFreshnessRefused",
    "ReviewLaneAction",
    "ReviewLaneKind",
    "approved_lane_branches",
    "check_mission_branches",
    "enforce_merge_gate",
    "lane_diverged_text",
    "plan_review_lane",
    "review_warning_text",
    "resolve_origin_check_mode",
]

ORIGIN_CHECK_ENV = "SPEC_KITTY_ORIGIN_CHECK"

ORIGIN_STATUS_STALE = "ORIGIN_STATUS_STALE"
ORIGIN_LANE_STALE = "ORIGIN_LANE_STALE"
ORIGIN_LANE_DIVERGED = "ORIGIN_LANE_DIVERGED"
ORIGIN_UNREACHABLE = "ORIGIN_UNREACHABLE"

_STATUS_LOG = "status.events.jsonl"


# --------------------------------------------------------------------------- mode (T014)


class OriginCheckMode(StrEnum):
    """How an evidence gate treats a failing freshness verdict."""

    ENFORCE = "enforce"
    WARN = "warn"


OriginCheckSource = Literal["default", "flag", "environment", "read-only"]


@dataclass(frozen=True)
class OriginCheckSetting:
    """The resolved mode, where it came from, and an optional diagnostic about the input."""

    mode: OriginCheckMode
    source: OriginCheckSource
    warning: str | None = None


#: Read-only commands (``accept --no-commit`` / ``--diagnose``) always warn (plan policy table).
READ_ONLY_ORIGIN_CHECK = OriginCheckSetting(OriginCheckMode.WARN, "read-only")

_ALLOWED_MODE_VALUES: frozenset[str] = frozenset(mode.value for mode in OriginCheckMode)


def _parse_mode(value: str) -> OriginCheckMode | None:
    normalized = value.strip().lower()
    return OriginCheckMode(normalized) if normalized in _ALLOWED_MODE_VALUES else None


def resolve_origin_check_mode(flag: str | None) -> OriginCheckSetting:
    """Resolve the opt-out: ``--origin-check`` flag beats ``SPEC_KITTY_ORIGIN_CHECK`` beats ``enforce``.

    An unknown *environment* value enforces and carries a warning naming it; an
    unknown *flag* value is a programming error here (typer validates it as a
    Choice at the call sites) and raises :class:`ValueError`.
    """
    if flag is not None:
        parsed = _parse_mode(flag)
        if parsed is None:
            raise ValueError(f"unknown --origin-check value {flag!r}; expected one of: {', '.join(sorted(_ALLOWED_MODE_VALUES))}")
        return OriginCheckSetting(parsed, "flag")
    raw = os.environ.get(ORIGIN_CHECK_ENV, "").strip()
    if not raw:
        return OriginCheckSetting(OriginCheckMode.ENFORCE, "default")
    parsed = _parse_mode(raw)
    if parsed is None:
        warning = f"{ORIGIN_CHECK_ENV}={raw!r} is not one of {', '.join(sorted(_ALLOWED_MODE_VALUES))}; enforcing the origin freshness check."
        return OriginCheckSetting(OriginCheckMode.ENFORCE, "default", warning)
    return OriginCheckSetting(parsed, "environment")


# --------------------------------------------------------------------------- verdicts (T015, T016)


class FreshnessState(StrEnum):
    """Foundation-agnostic classification of one local branch against its remote."""

    UP_TO_DATE = "up_to_date"
    BEHIND = "behind"
    AHEAD = "ahead"
    DIVERGED = "diverged"
    LOCAL_MISSING = "local_missing"
    REMOTE_MISSING = "remote_missing"
    UNREACHABLE = "unreachable"
    NO_REMOTE = "no_remote"


@dataclass(frozen=True)
class FreshnessVerdict:
    """One branch's freshness verdict.

    ``up_to_date`` and ``remote_missing`` are concluded only when the remote
    answered in this invocation. ``remote_sha`` is the tip the remote listed
    (absent for ``remote_missing``/``unreachable``/``no_remote``); the fetch
    that follows can only move the tracking ref forward from it.
    """

    branch: str
    remote: str | None
    state: FreshnessState
    behind: int = 0
    ahead: int = 0
    scope: str | None = None
    detail: str | None = None
    remote_sha: str | None = None


@dataclass(frozen=True)
class MissionFreshness:
    """Status-evidence verdict plus one verdict per lane branch, from one contact per remote."""

    evidence: FreshnessVerdict
    lanes: list[FreshnessVerdict]


@dataclass(frozen=True)
class _Probe:
    """One branch to check; a non-empty *scope* path-limits the ``behind`` count (status evidence)."""

    branch: str
    scope: tuple[str, ...] = ()


def _scope_text(probe: _Probe) -> str | None:
    return ", ".join(probe.scope) or None


def _classify(behind: int, ahead: int, *, scoped: bool) -> FreshnessState:
    """Counts to state. Scoped (status evidence): local-only commits never refuse (spec US1-3)."""
    if behind > 0:
        return FreshnessState.DIVERGED if ahead > 0 else FreshnessState.BEHIND
    if ahead > 0 and not scoped:
        return FreshnessState.AHEAD
    return FreshnessState.UP_TO_DATE


def _compare(repo_root: Path, remote: str, probe: _Probe, remote_sha: str) -> FreshnessVerdict:
    """Compare a fetched, locally present branch with its tracking ref."""
    remote_ref = tracking_ref(remote, probe.branch)
    total = divergence(repo_root, probe.branch, remote_ref)
    behind = divergence(repo_root, probe.branch, remote_ref, paths=probe.scope).behind if probe.scope else total.behind
    return FreshnessVerdict(
        branch=probe.branch,
        remote=remote,
        state=_classify(behind, total.ahead, scoped=bool(probe.scope)),
        behind=behind,
        ahead=total.ahead,
        scope=_scope_text(probe),
        remote_sha=remote_sha,
    )


def _check_remote(repo_root: Path, remote: str, probes: Sequence[_Probe]) -> list[FreshnessVerdict]:
    """ONE ``ls-remote`` and ONE ``fetch`` for every probe that resolved to *remote* (NFR-001)."""
    names = list(dict.fromkeys(probe.branch for probe in probes))
    try:
        heads = remote_heads(repo_root, remote, names)
        fetch_branches(repo_root, remote, [name for name in names if name in heads])
    except RemoteUnreachable as exc:
        return [FreshnessVerdict(p.branch, remote, FreshnessState.UNREACHABLE, scope=_scope_text(p), detail=str(exc)) for p in probes]
    verdicts: list[FreshnessVerdict] = []
    for probe in probes:
        sha = heads.get(probe.branch)
        if sha is None:
            verdicts.append(FreshnessVerdict(probe.branch, remote, FreshnessState.REMOTE_MISSING, scope=_scope_text(probe)))
        elif not branch_exists(repo_root, probe.branch):
            verdicts.append(FreshnessVerdict(probe.branch, remote, FreshnessState.LOCAL_MISSING, scope=_scope_text(probe), remote_sha=sha))
        else:
            verdicts.append(_compare(repo_root, remote, probe, sha))
    return verdicts


def _check_probes(repo_root: Path, probes: Sequence[_Probe]) -> list[FreshnessVerdict]:
    """Resolve each probe's remote (FR-017), contact each remote once, keep input order."""
    by_remote: dict[str, list[int]] = {}
    found: dict[int, FreshnessVerdict] = {}
    for index, probe in enumerate(probes):
        remote = resolve_remote(repo_root, probe.branch)
        if remote is None:
            found[index] = FreshnessVerdict(probe.branch, None, FreshnessState.NO_REMOTE, scope=_scope_text(probe))
        else:
            by_remote.setdefault(remote, []).append(index)
    for remote, indexes in by_remote.items():
        found.update(zip(indexes, _check_remote(repo_root, remote, [probes[i] for i in indexes]), strict=True))
    return [found[index] for index in range(len(probes))]


def check_branches(repo_root: Path, branches: Sequence[str]) -> list[FreshnessVerdict]:
    """Unscoped freshness verdicts for *branches*, one remote contact per remote, in input order."""
    return _check_probes(repo_root, [_Probe(branch) for branch in branches])


def _evidence_probe(repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> _Probe:
    """Status evidence branch (side-effect-free seam read) and its alias-scoped status-log paths (ADR 2026-10-05-1)."""
    branch = placement_seam(repo_root, mission_slug, owned=owned).write_target(MissionArtifactKind.STATUS_STATE).ref
    aliases = sorted(mission_dir_aliases(repo_root, mission_slug))
    return _Probe(branch, tuple(f"{KITTY_SPECS_DIR}/{alias}/{_STATUS_LOG}" for alias in aliases))


def check_mission_branches(
    repo_root: Path,
    mission_slug: str,
    *,
    lane_branches: Sequence[str],
    owned: OwnedCheckout | None = None,
) -> MissionFreshness:
    """Freshness of the status evidence branch (path-scoped) and *lane_branches* (unscoped).

    One ``ls-remote`` and one ``fetch`` per resolved remote for the evidence
    branch and the lanes together (NFR-001). A coordination evidence branch
    that exists only remotely yields ``local_missing``; callers pass that
    through to the existing ``COORDINATION_WORKTREE_UNMATERIALIZED`` path
    rather than refusing here.
    """
    probes = [_evidence_probe(repo_root, mission_slug, owned), *(_Probe(branch) for branch in lane_branches)]
    verdicts = _check_probes(repo_root, probes)
    return MissionFreshness(evidence=verdicts[0], lanes=verdicts[1:])


_CANCELED_LANE = "canceled"


def _canceled_wp_ids(repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> frozenset[str]:
    """WP ids whose reduced lane is ``canceled``, read only; unreadable status yields none (over-select, never under)."""
    try:
        status_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.STATUS_STATE)
        snapshot = reduce(read_events(status_dir))
    except (OSError, StoreError, ValueError, CoordinationBranchDeleted, CoordinationWorktreeUnmaterialized):
        return frozenset()
    return frozenset(wp for wp, state in snapshot.work_packages.items() if isinstance(state, dict) and state.get("lane") == _CANCELED_LANE)


def approved_lane_branches(
    repo_root: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest,
    *,
    completed_wps: frozenset[str] = frozenset(),
    owned: OwnedCheckout | None = None,
) -> list[str]:
    """Branches of the code lanes the freshness check covers; the one selection consolidate and orchestrator-api share.

    Selects code lanes (planning lanes resolve to the target branch, the status
    evidence) that are not fully canceled and, on a resume, not already
    consolidated. This is "code lanes that are not fully canceled", not
    "approved lanes": it reads status only through the read-only seam and does
    not reuse the claim's ``excluded_canceled_wp_ids``, so it may over-select
    (an unreadable status log selects every code lane) and never under-selects.
    """
    canceled = _canceled_wp_ids(repo_root, mission_slug, owned)
    selected: list[str] = []
    for lane in lanes_manifest.lanes:
        if is_planning_lane(lane) or lane_fully_canceled(lane, canceled):
            continue
        if lane.wp_ids and all(wp in completed_wps for wp in lane.wp_ids):
            continue
        selected.append(lane_created_branch(lanes_manifest, lane.lane_id))
    return selected


# --------------------------------------------------------------------------- merge gate policy (T017)

_STALE_STATES = frozenset({FreshnessState.BEHIND, FreshnessState.DIVERGED, FreshnessState.LOCAL_MISSING})
_OPT_OUT_LINE = f"Opt out (not recommended): --origin-check warn, or {ORIGIN_CHECK_ENV}=warn."
_REVIEW_OPT_OUT_LINE = f"Opt out (not recommended): {ORIGIN_CHECK_ENV}=warn."
_RERUN_LINE = "  Then re-run."
_NO_ANSWER = "the remote did not answer"


class OriginFreshnessRefused(RuntimeError):
    """An evidence gate refused because origin freshness could not be established or was stale.

    ``error_code`` is the first code, ``error_codes`` every distinct code in
    refusal order (evidence first), ``verdicts`` the failing verdicts, and
    ``str(exc)`` the full operator text.
    """

    def __init__(self, error_code: str, error_codes: list[str], verdicts: list[FreshnessVerdict], message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_codes = error_codes
        self.verdicts = verdicts


@dataclass(frozen=True)
class _Violation:
    code: str
    verdict: FreshnessVerdict
    is_evidence: bool


def _code_for(verdict: FreshnessVerdict, *, is_evidence: bool) -> str | None:
    """The plan's policy table: the refusal code a verdict earns at a merge-path gate, or ``None``."""
    if verdict.state is FreshnessState.UNREACHABLE:
        return ORIGIN_UNREACHABLE
    if verdict.state in _STALE_STATES:
        return ORIGIN_STATUS_STALE if is_evidence else ORIGIN_LANE_STALE
    return None


def _headline(code: str, verdict: FreshnessVerdict) -> str:
    """First line of a refusal: ``<CODE>: <branch> is <state> (<n> behind / <m> ahead of <remote>/<branch>)``."""
    where = f"{verdict.remote}/{verdict.branch}"
    if verdict.state is FreshnessState.UNREACHABLE:
        return f"{code}: {verdict.branch} is unreachable ({verdict.detail or _NO_ANSWER})"
    if verdict.state is FreshnessState.LOCAL_MISSING:
        return f"{code}: {verdict.branch} is missing locally (it exists as {where})"
    return f"{code}: {verdict.branch} is {verdict.state.value} ({verdict.behind} behind / {verdict.ahead} ahead of {where})"


def _status_update_steps(verdict: FreshnessVerdict, checkout: Path | None) -> list[str]:
    """The commands that bring the evidence branch level with the remote, by state and holder.

    A strictly behind branch fast-forwards: ``pull`` in a holding checkout, else
    ``fetch <remote> <b>:<b>`` (a bare ``git pull`` would merge the branch into
    whatever the repository root has checked out). A diverged branch cannot
    fast-forward (the fetch refspec is rejected as non-fast-forward) and a plain
    ``pull`` aborts on git >= 2.33 without ``pull.rebase``, so it is merged
    explicitly with ``pull --no-rebase`` in a checkout that holds it.
    """
    remote, branch = verdict.remote, verdict.branch
    if verdict.state is not FreshnessState.DIVERGED:
        return [f"git fetch {remote} {branch}:{branch}" if checkout is None else f"git -C {checkout} pull {remote} {branch}"]
    if checkout is not None:
        return [f"git -C {checkout} pull --no-rebase {remote} {branch}"]
    return [f"git worktree add <path> {branch}    (or: git switch {branch})", f"git pull --no-rebase {remote} {branch}    (in that checkout)"]


def _status_remedy(verdict: FreshnessVerdict, checkout: Path | None, *, merge_record_exists: bool) -> list[str]:
    """Update the evidence branch where it lives; with a merge record, abort first."""
    steps = _status_update_steps(verdict, checkout)
    if merge_record_exists:
        return [
            "  A consolidation record exists. Recover with:",
            "    spec-kitty consolidate --abort",
            *(f"    {step}" for step in steps),
            "    spec-kitty consolidate",
        ]
    if len(steps) == 1:
        return [f"  Update it with: {steps[0]}", _RERUN_LINE]
    return ["  Update it with:", *(f"    {step}" for step in steps), _RERUN_LINE]


def _diverged_lane_remedy(remote: str | None, lane: str) -> list[str]:
    """The one remedy text for a diverged lane: integrate the remote lane, or push the local one."""
    return [
        f"  Inspect: git log {lane}...{remote}/{lane}",
        f"  If the remote lane has work you need: git -C <lane worktree> merge {remote}/{lane}",
        f"  If the local lane is the truth: git push {remote} {lane}",
        _RERUN_LINE,
    ]


def lane_diverged_text(headline: str, remote: str | None, lane: str) -> str:
    """A ``review`` refusal for a diverged lane: *headline*, the remedy, and the environment-only opt-out."""
    return "\n".join([headline, *_diverged_lane_remedy(remote, lane), _REVIEW_OPT_OUT_LINE])


def review_warning_text(headline: str, setting: OriginCheckSetting) -> str:
    """*headline* as a warning, naming the resolved setting (``review`` has no flag, so source is ``environment``)."""
    return f"{headline} (origin check is {setting.mode.value}, source: {setting.source})"


def _lane_remedy(verdict: FreshnessVerdict) -> list[str]:
    remote, lane = verdict.remote, verdict.branch
    if verdict.state is FreshnessState.DIVERGED:
        return _diverged_lane_remedy(remote, lane)
    if verdict.state is FreshnessState.LOCAL_MISSING:
        return [f"  Create it with: git branch {lane} {remote}/{lane}", _RERUN_LINE]
    return [
        f"  Update it with: git fetch {remote} {lane}",
        f"    then git branch -f {lane} {remote}/{lane}",
        f"    (or, when the lane is checked out: git -C <lane worktree> merge --ff-only {remote}/{lane})",
        _RERUN_LINE,
    ]


def _remedy(violation: _Violation, checkout: Path | None, *, merge_record_exists: bool) -> list[str]:
    verdict = violation.verdict
    if verdict.state is FreshnessState.UNREACHABLE:
        return [f"  Check network access and credentials for remote {verdict.remote}.", _RERUN_LINE]
    if violation.is_evidence and verdict.state is not FreshnessState.LOCAL_MISSING:
        return _status_remedy(verdict, checkout, merge_record_exists=merge_record_exists)
    return _lane_remedy(verdict)


def _violations(evidence: FreshnessVerdict | None, lanes: Iterable[FreshnessVerdict]) -> list[_Violation]:
    pairs = [(evidence, True)] if evidence is not None else []
    pairs.extend((lane, False) for lane in lanes)
    found: list[_Violation] = []
    for verdict, is_evidence in pairs:
        code = _code_for(verdict, is_evidence=is_evidence)
        if code is not None:
            found.append(_Violation(code, verdict, is_evidence))
    return found


def _warn_text(violation: _Violation, setting: OriginCheckSetting) -> str:
    return f"{_headline(violation.code, violation.verdict)} (origin check is {setting.mode.value}, source: {setting.source}; continuing)"


def enforce_merge_gate(
    *,
    evidence: FreshnessVerdict | None,
    lanes: Sequence[FreshnessVerdict],
    setting: OriginCheckSetting,
    merge_record_exists: bool,
    evidence_checkout: Path | None,
) -> list[str]:
    """Apply the merge-path policy: return warnings, or raise :class:`OriginFreshnessRefused`.

    Evidence ``local_missing`` refuses ``ORIGIN_STATUS_STALE``; a caller whose
    evidence branch is a coordination branch handles that case before calling.
    In ``warn`` mode every would-be refusal becomes a warning naming the verdict
    and ``setting.source``.
    """
    warnings = [setting.warning] if setting.warning else []
    violations = _violations(evidence, lanes)
    if not violations:
        return warnings
    if setting.mode is OriginCheckMode.WARN:
        return [*warnings, *(_warn_text(violation, setting) for violation in violations)]
    lines: list[str] = []
    for violation in violations:
        lines.append(_headline(violation.code, violation.verdict))
        lines.extend(_remedy(violation, evidence_checkout, merge_record_exists=merge_record_exists))
    lines.append(_OPT_OUT_LINE)
    codes = list(dict.fromkeys(violation.code for violation in violations))
    raise OriginFreshnessRefused(codes[0], codes, [violation.verdict for violation in violations], "\n".join(lines))


# --------------------------------------------------------------------------- review lane plan (T018)


class ReviewLaneKind(StrEnum):
    """What review preparation should do with a lane branch."""

    KEEP = "keep"
    FAST_FORWARD = "fast_forward"
    CREATE_FROM = "create_from"
    REFUSE = "refuse"
    WARN = "warn"


@dataclass(frozen=True)
class ReviewLaneAction:
    """Review-prep decision for one lane; the caller owns checkout cleanliness, locks and the actual move."""

    kind: ReviewLaneKind
    verdict: FreshnessVerdict
    remote_sha: str | None = None
    remote_ref: str | None = None
    code: str | None = None
    message: str | None = None


def plan_review_lane(repo_root: Path, lane_branch: str, setting: OriginCheckSetting | None = None) -> ReviewLaneAction:
    """Map a lane's freshness verdict to a review-prep action (plan policy table, review row).

    *setting* defaults to the environment-resolved one (``review`` has no flag); in
    ``warn`` mode a diverged lane is kept as it is with a warning instead of refused.
    """
    setting = setting or resolve_origin_check_mode(None)
    verdict = _only_verdict(check_branches(repo_root, [lane_branch]))
    ref = tracking_ref(verdict.remote, lane_branch) if verdict.remote else None
    if verdict.state is FreshnessState.BEHIND:
        return ReviewLaneAction(ReviewLaneKind.FAST_FORWARD, verdict, remote_sha=verdict.remote_sha, remote_ref=ref)
    if verdict.state is FreshnessState.LOCAL_MISSING:
        return ReviewLaneAction(ReviewLaneKind.CREATE_FROM, verdict, remote_sha=verdict.remote_sha, remote_ref=ref)
    if verdict.state is FreshnessState.DIVERGED:
        headline = _headline(ORIGIN_LANE_DIVERGED, verdict)
        if setting.mode is OriginCheckMode.WARN:
            return ReviewLaneAction(ReviewLaneKind.WARN, verdict, code=ORIGIN_LANE_DIVERGED, message=review_warning_text(headline, setting))
        message = lane_diverged_text(headline, verdict.remote, lane_branch)
        return ReviewLaneAction(ReviewLaneKind.REFUSE, verdict, remote_ref=ref, code=ORIGIN_LANE_DIVERGED, message=message)
    if verdict.state is FreshnessState.UNREACHABLE:
        return ReviewLaneAction(ReviewLaneKind.WARN, verdict, code=ORIGIN_UNREACHABLE, message=_headline(ORIGIN_UNREACHABLE, verdict))
    return ReviewLaneAction(ReviewLaneKind.KEEP, verdict)


def _only_verdict(verdicts: list[FreshnessVerdict]) -> FreshnessVerdict:
    (verdict,) = verdicts
    return verdict
