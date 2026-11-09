"""Shared kernel of the terminus reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP10).

The symbols every verification check shares: lane branch and dependency resolution, the closed-world
anchors, the mission-owned bookkeeping classifier, the lazily-read status event log, the planning
prefix and the lane walk record. Moved verbatim out of ``reconciliation.py``; that module re-exports
every name, so no caller changes (C-005).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.consolidation.git_probes import GitProbeError, commits_in_range, first_parent_commits_in_range
from specify_cli.consolidation.wp_attribution import Unattributable, UnattributableReason
from specify_cli.core.constants import KITTIFY_DIR, KITTY_SPECS_DIR
from specify_cli.lanes.compute import is_planning_lane, lane_created_branch, lane_fully_canceled
from specify_cli.lanes.models import ExecutionLane, LanesManifest


# Lanes that count as "approved" (an acceptable, merge-ready ending) for claim
# membership. ``done`` is included so a resume that already baked ``done`` for a
# WP still recognizes it as claimed (never re-derived here — the strings mirror
# ``status.models.Lane`` values, the single lane vocabulary).
_APPROVED_MEMBERSHIP_LANES: frozenset[str] = frozenset({"approved", "done"})


# A repo-ROOT ``kitty-ops/<ULID>.jsonl`` Op-record orphan (#2251) — anchored to the
# repo root (``^``), never anywhere-in-tree, so a product-source path that merely
# CONTAINS a ``kitty-ops/`` segment deeper in the tree is not mistaken for the
# toolchain's own Op-record ledger. Mirrors the ULID shape
# ``coordination/coherence.py`` uses for its (deliberately broader, whole-tree)
# dirty-state-gate classifier.
_KITTY_OPS_ROOT_RECORD = re.compile(r"^kitty-ops/[0-9A-HJKMNP-TV-Z]{26}\.jsonl$")


def _is_bookkeeping(path: str, mission_slug: str | None, planning_prefix: str | None) -> bool:
    """True when *path* is the MISSION's OWN planning/toolchain surface.

    Anchored to three mission/toolchain-owned roots — never a global
    basename match — closing a silent-data-loss defect (Epic #5001 landing
    remediation): this used to delegate to
    :func:`~specify_cli.coordination.coherence.is_toolchain_generated_churn`,
    a DIRTY-STATE-gate classifier that, at the time, matched by bare
    basename anywhere in the repository (``PurePosixPath(path).name ==
    "meta.json"`` matched ``src/config/meta.json`` just as readily as the
    mission's own ``kitty-specs/<slug>/meta.json``). In the squash content
    axis a path that classifier called bookkeeping was skipped BEFORE
    authored-blob attribution, so a removed/canceled WP's commit touching an
    ordinary product-source file merely NAMED like a toolchain artifact rode
    a carrier lane onto the target and shipped at exit 0. #4933 has
    since made ``coherence.py``'s ``meta.json`` leg depth-exact
    (``kitty-specs/<mission>/meta.json`` at any monorepo prefix, plus the
    legacy ``.kittify/meta.json``), but it is still not anchored to THIS
    claim's slug — it exempts ANY mission's ``meta.json`` — and it remains a
    dirty-state-gate predicate with its own consumers. This axis therefore
    keeps its own, narrower classification rather than delegating to it.

    A path counts as bookkeeping only when it is anchored to:

    * a ``kitty-specs/<slug>/`` segment sequence where ``<slug>`` is THIS
      claim's own *mission_slug* — covers the mission's own ``meta.json``,
      ``status.events.jsonl``, issue-matrix, ``traces/``, ``decisions/``,
      retrospective, tasks, and plan artifacts, wherever that segment
      sequence occurs in the path (the repo-root ``kitty-specs/<slug>/…`` a
      merge commit lands directly, AND a coordination-topology worktree's
      nested copy alike);
    * *planning_prefix* as an exact prefix (belt-and-suspenders for a
      hand-built claim that sets the prefix without a ``mission_slug``);
    * a repo-ROOT ``.kittify/`` prefix — encoding-provenance,
      mission-state-audit, and other toolchain-owned state;
    * a repo-ROOT ``kitty-ops/<ULID>.jsonl`` Op-record orphan
      (:data:`_KITTY_OPS_ROOT_RECORD`);
    * for a bare-slug coordination claim only (a NESTED *planning_prefix*), the
      coordination-kind files (status pair, traces, matrices, decision log, review
      cycles) anywhere under the composed directory ``kitty-specs/<alias>/``
      *planning_prefix* ends in
      (:func:`_is_nested_alias_coordination_file`, #5651).

    Any other path — including one that merely shares a bookkeeping
    basename — is real content, subject to the closed-world attribution
    check.

    Extracted to module level (mixed-lane-authorship-soundness / #5046 WP05)
    so :func:`build_approved_wp_set` can bind it via ``functools.partial`` and
    hand it to ``wp_attribution.resolve_canceled_wp`` as the SAME denylist the
    verifier itself uses — the claim (:class:`ApprovedWpCommitSet`) does not
    exist yet at that call site, so the *claim*-taking overload
    (:meth:`MergeOutcomeVerifier._is_bookkeeping_path`) cannot be called there.
    """
    normalized = path.rstrip("/")
    if mission_slug:
        parts = normalized.split("/")
        try:
            specs_index = parts.index(KITTY_SPECS_DIR)
        except ValueError:
            specs_index = -1
        # ``kitty-specs`` segment immediately followed by THIS mission's own
        # slug, wherever it occurs in the path (not just at a literal prefix
        # match). Mission-scoped, never a bare basename: a product path can
        # never satisfy this unless it is literally nested under the
        # mission's own planning directory. Anchoring on the SEGMENT SEQUENCE
        # (not *planning_prefix* alone) closes a real mismatch: under
        # coordination topology *planning_prefix* is derived from the
        # STATUS_STATE placement's ``feature_dir`` (the coord WORKTREE's
        # nested copy, e.g. ``.worktrees/<slug>-<mid8>-coord/kitty-specs/
        # <slug>``), while the commits this axis scans land the mission's
        # bookkeeping directly at the repo-root ``kitty-specs/<slug>/`` — the
        # two paths never share a common prefix, so relying on
        # *planning_prefix* alone silently stopped recognizing the
        # mission's own ``status.json`` / ``status.events.jsonl`` / etc. as
        # bookkeeping once the whole-tree churn classifier was dropped.
        if specs_index != -1 and specs_index + 1 < len(parts) and parts[specs_index + 1] == mission_slug:
            return True
    if planning_prefix and (normalized == planning_prefix or normalized.startswith(planning_prefix + "/")):
        return True
    if normalized == KITTIFY_DIR or normalized.startswith(KITTIFY_DIR + "/"):
        return True
    if _is_nested_alias_coordination_file(normalized, mission_slug, planning_prefix):
        return True
    return bool(_KITTY_OPS_ROOT_RECORD.match(normalized))


def _is_nested_alias_coordination_file(path: str, mission_slug: str | None, planning_prefix: str | None) -> bool:
    """True when *path* is a coordination-kind file of the composed directory a bare-slug coordination claim names.

    A bare-slug coordination Mission keeps its primary directory at
    ``kitty-specs/<slug>`` while the coordination seed writes its coordination
    records (the status pair, traces, matrices, the decision log, review cycles)
    under the composed ``kitty-specs/<slug>-<mid8>`` directory (#5651). The claim's
    *planning_prefix* is then the NESTED coordination-worktree path whose last
    segment is that composed name, and the name is read from it, never rebuilt from
    the slug. Only a root-anchored path ``kitty-specs/<alias>/<file>``, at any depth
    below the directory, whose file is a coordination kind
    (:func:`~specify_cli.coordination.coherence.is_coordination_kind_file`, the predicate
    the seed itself uses to decide what to carry) qualifies; a planning file, source, an
    unclassified file and any other directory stay content. A root-form or absent prefix,
    or one that already names the primary directory, never applies this rule.
    """
    if not planning_prefix:
        return False
    prefix_parts = planning_prefix.rstrip("/").split("/")
    # <something>/kitty-specs/<alias>: nested, so the older exact-prefix rule cannot see it.
    if len(prefix_parts) < 3 or prefix_parts[-2] != KITTY_SPECS_DIR or not all(prefix_parts[:-2]):
        return False
    alias = prefix_parts[-1]
    parts = path.split("/")
    if alias == mission_slug or len(parts) < 3 or parts[0] != KITTY_SPECS_DIR or parts[1] != alias:
        return False
    # Function-local: this module imports nothing from the coordination package at its top.
    from specify_cli.coordination.coherence import is_coordination_kind_file

    is_coordination_kind: bool = is_coordination_kind_file("/".join(parts[2:]))
    return is_coordination_kind


class _ClaimEventLog:
    """The mission's status events for ONE claim build: read lazily, and at most once.

    The canceled-dependency resolution and the mixed-lane resolution both need
    the log, each only for some missions; whichever asks first pays the read and
    the other reuses it. A ``StoreError`` is remembered the same way, so both
    report the same unreadable log (NFR-002; never overridable — the attestation
    lives in that same log).
    """

    def __init__(self, feature_dir: Path) -> None:
        self._feature_dir = feature_dir
        self._events: Sequence[Any] | None = None
        self._error: Exception | None = None

    def read(self) -> Sequence[Any] | None:
        """The events in append order, or ``None`` when the log cannot be read (then use :meth:`unreadable`)."""
        if self._events is None and self._error is None:
            # Lazy import: keeps this module import-light, as in ``build_approved_wp_set``.
            from specify_cli.status import StoreError, read_events

            try:
                self._events = read_events(self._feature_dir)
            except StoreError as exc:
                self._error = exc
        return self._events

    def unreadable(self, lane_id: str, wp_id: str) -> Unattributable:
        """The ``events_unreadable`` outcome naming *lane_id* / *wp_id* and the store error."""
        outcome = Unattributable.for_reason(UnattributableReason.EVENTS_UNREADABLE, lane_id, wp_id)
        return Unattributable(outcome.reason, f"{outcome.detail} ({self._error})")


def _dependency_lane_ids(lanes_manifest: LanesManifest, lane: ExecutionLane) -> list[str]:
    """Every lane *lane* depends on, transitively (``lanes.json`` ``depends_on_lanes``)."""
    by_id = {candidate.lane_id: candidate for candidate in lanes_manifest.lanes}
    seen: list[str] = []
    pending = list(lane.depends_on_lanes)
    while pending:
        lane_id = pending.pop()
        if lane_id in seen or lane_id not in by_id:
            continue
        seen.append(lane_id)
        pending.extend(by_id[lane_id].depends_on_lanes)
    return sorted(seen)


def _closed_world_anchors(
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    target_base: str | None,
    *,
    excluded_canceled_wp_ids: frozenset[str],
    frozen_tips: Mapping[str, str] | None,
) -> list[str]:
    """FR-013 anchors for *lane*: dependency-lane tips (the allocator merges them in
    without ``--no-ff``, also on its reuse path after work began) and the target's
    pre-consolidation tip (commits already on the target ship nothing new).

    *frozen_tips* (FR-015) is a ``--resume``'s ONE frozen anchor set: created dependency-lane
    branch -> the tip the interrupted run froze before its first mutation
    (``ConsolidationState.pre_interrupt_lane_tips``, through ``ClaimInputs.dependency_anchors``).
    A dependency lane it names is anchored on that SHA, so a commit the lane gained after the
    interruption is exempt nowhere. A dependency lane it does not name keeps the live branch name
    (a *degraded anchor*: a record without that tip, see ADR
    ``2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition``). ``None`` (a fresh
    run, the forecast, every other caller) is the live read for every lane. The exclusions below
    are unchanged by it.

    A FULLY-canceled dependency lane is not an anchor (#5569): its tip carries
    canceled content, which must never be exempt as history that predates *lane*.
    Its commits before its own base are still covered by the anchors that reach
    them (the approved dependencies it was cut from, the target tip).

    A PLANNING dependency lane is not an anchor either: its branch name is the LIVE
    target branch, which on a ``--resume`` after the interrupted run advanced the target
    already reaches every merged lane commit and would exempt a late one. What a planning
    lane legitimately contributes is on the target's pre-consolidation tip, *target_base*.
    """
    by_id = {candidate.lane_id: candidate for candidate in lanes_manifest.lanes}
    frozen = frozen_tips or {}
    branches = [
        _lane_branch_for(lanes_manifest, dep)
        for dep in _dependency_lane_ids(lanes_manifest, lane)
        if not is_planning_lane(by_id[dep]) and not lane_fully_canceled(by_id[dep], excluded_canceled_wp_ids)
    ]
    anchors = [frozen.get(branch, branch) for branch in branches]
    if target_base:
        anchors.append(target_base)
    return anchors


def _planning_prefix(repo_root: Path, feature_dir: Path) -> str | None:
    """Repo-relative posix path of the mission planning dir (``kitty-specs/<slug>``).

    Returns ``None`` when *feature_dir* is not under *repo_root* — the closed-world
    content check then falls back to the toolchain-churn denylist alone.
    """
    try:
        relative = feature_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    return relative.as_posix()


def _lane_branch_for(lanes_manifest: LanesManifest, lane_id: str) -> str:
    """Resolve a lane's **created** branch name from the creation input (slug + lane id).

    Thin alias over the shared :func:`~specify_cli.lanes.compute.lane_created_branch`
    (single canonical home — see its docstring for the I-1/I-3 rationale this
    module and ``merge.executor`` previously duplicated under different names).
    """
    # Local annotation re-narrows to ``str``: the narrow-file mypy override
    # (``specify_cli.*`` follow_imports = "skip") erases the callee's own
    # ``-> str`` to ``Any`` here (same pattern as executor.py's
    # ``_created_lane_branch`` re-wrap it replaces).
    branch: str = lane_created_branch(lanes_manifest, lane_id)
    return branch


def _lane_tip_commits(repo_root: Path, coord_base_ref: str, branch: str) -> list[str]:
    """Commits on a lane tip, TOLERATING an unresolvable range at claim-build time.

    Claim building has always tolerated a lane branch (or coord base) that does not
    resolve — a fully-canceled lane has no branch, and some topologies cut the
    branch after this read — yielding no commits for that lane rather than aborting
    the whole merge. The #5001 FOLD-3 fail-closed window-error signal
    (:class:`GitProbeError`) is scoped to the VERIFIER's window scan
    (:meth:`MergeOutcomeVerifier._reachable_excluded` /
    ``_unattributable_content``), where an unevaluable window must refuse; the claim
    BUILDER keeps its pre-existing tolerant behavior here so a legitimate merge
    (e.g. a canceled-lane survivor merge) is never turned into a spurious refusal.
    """
    try:
        commits: list[str] = commits_in_range(repo_root, coord_base_ref, branch)
    except GitProbeError:
        return []
    return commits


def _lane_is_approved(lane: object, work_packages: Mapping[str, Mapping[str, object]]) -> bool:
    """True when at least one of *lane*'s WPs is in an approved membership lane."""
    wp_ids = getattr(lane, "wp_ids", ())
    return any(str((work_packages.get(wp) or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES for wp in wp_ids)


def _lane_first_parent_spine(repo_root: Path, coord_base_ref: str, branch: str) -> list[str]:
    """First-parent SHAs (newest-first) for a lane, TOLERATING an unresolvable range.

    Mirrors :func:`_lane_tip_commits`' claim-build tolerance: an unresolvable lane
    branch / coord base (a fully-canceled lane has no branch; some topologies cut it
    after this read) yields no authorship rather than turning a legitimate merge into
    a spurious refusal. The #5013 F7 fail-closed ``GitProbeError`` signal is scoped to
    the VERIFIER's window scan, not the claim BUILDER.
    """
    try:
        spine: list[str] = first_parent_commits_in_range(repo_root, coord_base_ref, branch)
        return spine
    except GitProbeError:
        return []


@dataclass(frozen=True)
class _LaneWalk:
    """One lane's authorship walk: its range base and branch, first-parent spine and FINAL blobs / deletions."""

    base: str
    branch: str
    spine: list[str]
    blobs: set[tuple[str, str]]
    deletions: set[str]


__all__ = [
    "_APPROVED_MEMBERSHIP_LANES",
    "_ClaimEventLog",
    "_KITTY_OPS_ROOT_RECORD",
    "_LaneWalk",
    "_closed_world_anchors",
    "_dependency_lane_ids",
    "_is_bookkeeping",
    "_is_nested_alias_coordination_file",
    "_lane_branch_for",
    "_lane_first_parent_spine",
    "_lane_is_approved",
    "_lane_tip_commits",
    "_planning_prefix",
]
