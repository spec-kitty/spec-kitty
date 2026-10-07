"""Adapter the evidence gates share over :mod:`specify_cli.git.origin_freshness` (FR-003/FR-004).

``accept`` and the orchestrator-api ``accept-mission`` / ``consolidate-mission``
commands each need the same four steps: read the status evidence (and, for
consolidation, the approved lane branches) from one remote contact, set a
coordination-only ``local_missing`` evidence verdict aside for the existing
``COORDINATION_WORKTREE_UNMATERIALIZED`` handling, apply the merge-gate policy,
and render the verdicts as plain data. This module owns exactly that, so no gate
restates it. It never prints.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mission_runtime import OwnedCheckout, resolve_topology, routes_through_coordination
from specify_cli.git.origin_freshness import (
    FreshnessState,
    FreshnessVerdict,
    OriginCheckMode,
    OriginCheckSetting,
    check_mission_branches,
    enforce_merge_gate,
    origin_not_checked_warning,
)
from specify_cli.git.ref_advance import RefAdvanceError, worktrees_with_branch_checked_out

__all__ = ["run_origin_gate", "verdict_payloads"]


def verdict_payload(verdict: FreshnessVerdict) -> dict[str, object]:
    """One verdict as the additive ``origin_freshness`` row (branch, remote, state, behind, ahead, scope, detail)."""
    return {
        "branch": verdict.branch,
        "remote": verdict.remote,
        "state": verdict.state.value,
        "behind": verdict.behind,
        "ahead": verdict.ahead,
        "scope": verdict.scope,
        "detail": verdict.detail,
    }


def verdict_payloads(verdicts: Sequence[FreshnessVerdict]) -> list[dict[str, object]]:
    """Every verdict as an ``origin_freshness`` row, order preserved."""
    return [verdict_payload(verdict) for verdict in verdicts]


def _evidence_checkout(repo_root: Path, branch: str) -> Path | None:
    """The worktree that holds the evidence branch, so the pull remedy runs where the branch lives."""
    try:
        holders = worktrees_with_branch_checked_out(repo_root, branch)
    except RefAdvanceError:
        return None
    return holders[0] if holders else None


def _coordination_unmaterialized(repo_root: Path, mission_slug: str, evidence: FreshnessVerdict) -> bool:
    """A coordination evidence branch that exists only on the remote: not a stale-evidence refusal (WP03 carry-forward)."""
    if evidence.state is not FreshnessState.LOCAL_MISSING:
        return False
    return routes_through_coordination(resolve_topology(repo_root, mission_slug))


def run_origin_gate(
    repo_root: Path,
    mission_slug: str,
    *,
    setting: OriginCheckSetting,
    lane_branches: Sequence[str] = (),
    owned: OwnedCheckout | None = None,
    merge_record_exists: bool = False,
) -> list[str]:
    """Check status evidence and *lane_branches* against origin and apply the policy.

    Returns the warnings to surface (warn mode, read-only commands, a diagnostic
    on the opt-out input); in ``off`` mode it contacts nothing and returns the
    one not-checked warning; raises :class:`~specify_cli.git.origin_freshness.OriginFreshnessRefused`
    in enforce mode. A coordination evidence branch missing locally is not judged
    here: the caller's existing ``COORDINATION_WORKTREE_UNMATERIALIZED`` path owns it,
    and neither is an evidence branch the placement seam refuses to name (the
    caller's status-directory resolver renders that refusal).
    """
    if setting.mode is OriginCheckMode.OFF:
        return [origin_not_checked_warning(setting)]
    fresh = check_mission_branches(repo_root, mission_slug, lane_branches=lane_branches, owned=owned)
    evidence = fresh.evidence
    if evidence is not None and _coordination_unmaterialized(repo_root, mission_slug, evidence):
        evidence = None
    warnings: list[str] = enforce_merge_gate(
        evidence=evidence,
        lanes=fresh.lanes,
        setting=setting,
        merge_record_exists=merge_record_exists,
        evidence_checkout=None if evidence is None else _evidence_checkout(repo_root, evidence.branch),
    )
    return warnings
