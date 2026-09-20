"""Evidence-based merge gate evaluation engine.

Three gates that must pass before a merge proceeds:
1. Evidence gate — all WPs have reviewer approval in the event log.
2. Risk gate — parallelization risk score is below threshold.
3. Dependency gate — all WP dependencies are in done lane.

Gates are configurable via MergeGateConfig. Each gate returns
pass/fail/skip. The overall evaluation passes if no blocking
failures exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from kernel.clock import now_utc_iso
from specify_cli.mission_metadata import mission_identity_fields, resolve_mission_identity
from specify_cli.policy.config import MergeGateConfig
from specify_cli.status_lanes import has_operator_provenance, is_acceptable_ending


class GateVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True)
class GateResult:
    """Result of a single gate evaluation."""

    gate_name: str
    verdict: GateVerdict
    details: str
    blocking: bool  # True if mode=="block" and verdict=="fail"


@dataclass
class MergeGateEvaluation:
    """Combined result of all gate evaluations."""

    mission_slug: str
    evaluated_at: str
    gates: list[GateResult] = field(default_factory=list)
    mission_number: str | None = None
    mission_type: str | None = None

    @property
    def overall_pass(self) -> bool:
        return not any(g.blocking for g in self.gates)

    @property
    def warnings(self) -> list[str]:
        return [
            f"{g.gate_name}: {g.details}"
            for g in self.gates
            if g.verdict == GateVerdict.FAIL and not g.blocking
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            **mission_identity_fields(
                self.mission_slug,
                self.mission_number,
                self.mission_type,
            ),
            "evaluated_at": self.evaluated_at,
            "overall_pass": self.overall_pass,
            "gates": [
                {
                    "gate_name": g.gate_name,
                    "verdict": g.verdict,
                    "details": g.details,
                    "blocking": g.blocking,
                }
                for g in self.gates
            ],
            "warnings": self.warnings,
        }


def evaluate_merge_gates(
    feature_dir: Path,
    mission_slug: str,
    wp_ids: list[str],
    policy: MergeGateConfig,
    repo_root: Path,
) -> MergeGateEvaluation:
    """Evaluate all merge gates for a feature.

    Args:
        feature_dir: Path to kitty-specs/{mission_slug}/.
        mission_slug: Feature identifier.
        wp_ids: WP IDs being merged.
        policy: Merge gate configuration.
        repo_root: Repository root.

    Returns:
        MergeGateEvaluation with per-gate results.
    """
    evaluation = MergeGateEvaluation(
        mission_slug=mission_slug,
        evaluated_at=now_utc_iso(),
    )
    identity = resolve_mission_identity(feature_dir)
    evaluation.mission_slug = identity.mission_slug
    evaluation.mission_number = (
        str(identity.mission_number)
        if identity.mission_number is not None
        else None
    )
    evaluation.mission_type = identity.mission_type

    if not policy.enabled or policy.mode == "off":
        return evaluation

    is_blocking = policy.mode == "block"

    if policy.require_review_approval:
        evaluation.gates.append(
            _evaluate_evidence_gate(feature_dir, wp_ids, is_blocking)
        )

    if policy.require_risk_check:
        evaluation.gates.append(
            _evaluate_risk_gate(feature_dir, is_blocking, repo_root, mission_slug)
        )

    if policy.require_deps_complete:
        evaluation.gates.append(
            _evaluate_dependency_gate(
                feature_dir, wp_ids, is_blocking, repo_root, mission_slug
            )
        )

    evaluation.gates.append(
        _evaluate_issue_matrix_completeness_gate(feature_dir, is_blocking)
    )

    return evaluation


def _evaluate_evidence_gate(
    feature_dir: Path, wp_ids: list[str], is_blocking: bool,
) -> GateResult:
    """Report (informationally) whether every WP is at an acceptable mission ending.

    FR-009 merge face: routed through the single shared aggregate
    :func:`~specify_cli.status_lanes.mission_terminal_acceptability` (dedup
    fold, #4764 — this gate previously re-inlined its own per-WP
    acceptable-ending loop despite this very docstring already claiming to
    use "the same shared aggregate"; it now genuinely does). That aggregate
    itself consults :func:`~specify_cli.status_lanes.is_acceptable_ending`
    and :func:`~specify_cli.status_lanes.has_operator_provenance` — a
    ``canceled`` WP carrying operator-authored provenance is an acceptable
    ending, so a legitimately-canceled WP is not reported as missing
    approval; a synthetic (non-provenance) cancellation, an active lane, or a
    WP declared in ``wp_ids`` but absent from the snapshot entirely (the
    aggregate's ``expected_wp_ids`` fail-closed rule) still fails here.

    T006 (terminus-safety-invariant, FR-002/FR-003, #4764): this "missing
    approval" finding is NEVER blocking, regardless of ``policy.merge_gates.mode``
    — the terminal-lane invariant this used to gate (softened to a warning under
    ``mode: warn``, the #4764 fail-open) is now enforced UNCONDITIONALLY, before
    any mutation, by ``merge.executor._assert_mission_terminal_ready`` (built on
    the same shared aggregate, ``status_lanes.mission_terminal_acceptability``).
    This gate stays purely informational so the operator still sees which WPs
    are missing review approval in the printed gate summary; a ``mode: block``
    config no longer needs this gate to enforce the invariant since the
    executor precondition already refuses unconditionally. Only genuine
    evidence-QUALITY concerns (review verdict / risk / hollow-review) remain
    mode-softened (FR-003) — this de-conflates the terminal-lane invariant out
    of that softenable path.
    """
    try:
        from specify_cli.status import read_events, reduce
        from specify_cli.status_lanes import mission_terminal_acceptability

        snapshot = reduce(read_events(feature_dir))
        work_packages = snapshot.work_packages if hasattr(snapshot, "work_packages") else {}
        relevant = {wp_id: work_packages[wp_id] for wp_id in wp_ids if wp_id in work_packages}

        _ok, missing = mission_terminal_acceptability(relevant, expected_wp_ids=wp_ids)
        if missing:
            return GateResult(
                gate_name="evidence",
                verdict=GateVerdict.FAIL,
                details=(
                    f"WPs missing review approval: {', '.join(missing)} "
                    "(informational — the terminal-lane invariant is enforced "
                    "unconditionally before any mutation, regardless of gate "
                    "mode; see merge.executor._assert_mission_terminal_ready)"
                ),
                # T006: never blocking here — see the docstring above. The
                # unconditional executor precondition owns the hard refuse.
                blocking=False,
            )
        return GateResult(
            gate_name="evidence",
            verdict=GateVerdict.PASS,
            details=f"All {len(wp_ids)} WPs have review approval",
            blocking=False,
        )
    except Exception as exc:
        return GateResult(
            gate_name="evidence",
            verdict=GateVerdict.FAIL,
            details=f"Could not read event log: {exc}",
            blocking=is_blocking,
        )


def _evaluate_risk_gate(
    feature_dir: Path, is_blocking: bool, repo_root: Path, mission_slug: str,
) -> GateResult:
    """Check that parallelization risk score is below threshold.

    #3439 / FR-003 / C-001: LANE_STATE is a PRIMARY-partition kind. On a
    coord-topology mission the ``feature_dir`` handed in by the merge flow is
    the STATUS-only ``-coord`` husk, which carries no ``lanes.json`` — so a
    direct ``read_lanes_json(feature_dir)`` returned ``None`` and the gate
    silently SKIPped. Route the LANE_STATE read through the canonical placement
    seam (the existing SSOT — no predicate fork) so the gate evaluates real
    lane data on every topology. STATUS-partition reads are untouched (C-002).
    """
    try:
        from mission_runtime import MissionArtifactKind, placement_seam

        from specify_cli.lanes.persistence import read_lanes_json
        from specify_cli.policy.config import load_policy_config
        from specify_cli.policy.risk_scorer import compute_risk_report

        lane_state_dir = placement_seam(repo_root, mission_slug).read_dir(
            MissionArtifactKind.LANE_STATE
        )
        lanes_manifest = read_lanes_json(lane_state_dir)
        if lanes_manifest is None:
            return GateResult(
                gate_name="risk",
                verdict=GateVerdict.SKIP,
                details="No lanes.json — risk gate skipped",
                blocking=False,
            )

        # Load risk policy from the threaded repo root (never re-derived from
        # feature_dir, which is the coord husk on a coord-topology mission).
        policy = load_policy_config(repo_root)
        report = compute_risk_report(lanes_manifest, policy=policy.risk)

        if report.exceeds_threshold:
            return GateResult(
                gate_name="risk",
                verdict=GateVerdict.FAIL,
                details=(
                    f"Risk score {report.overall_score:.2f} exceeds "
                    f"threshold {report.threshold:.2f}"
                ),
                blocking=is_blocking,
            )
        return GateResult(
            gate_name="risk",
            verdict=GateVerdict.PASS,
            details=f"Risk score {report.overall_score:.2f} within threshold",
            blocking=False,
        )
    except Exception as exc:
        return GateResult(
            gate_name="risk",
            verdict=GateVerdict.SKIP,
            details=f"Risk assessment unavailable: {exc}",
            blocking=False,
        )


def _evaluate_dependency_gate(
    feature_dir: Path, wp_ids: list[str], is_blocking: bool,
    repo_root: Path, mission_slug: str,
) -> GateResult:
    """Check that all WP dependencies are in done lane.

    #3439 / FR-003 / C-001/C-002 per-leg split. The dependency GRAPH is built
    from WORK_PACKAGE_TASK (``tasks/``) — a PRIMARY-partition kind absent on the
    coord husk, so a direct ``build_dependency_graph(feature_dir)`` saw an EMPTY
    graph and treated every dependency as satisfied. Route that read through the
    placement seam (PRIMARY). The per-WP LANE snapshot stays on the coord-aware
    STATUS_STATE surface: ``read_events`` keeps reading the handed-in
    ``feature_dir`` (the coord husk on a coord mission) — do NOT over-correct the
    STATUS read to PRIMARY (C-002).
    """
    try:
        from mission_runtime import MissionArtifactKind, placement_seam

        from specify_cli.core.dependency_graph import build_dependency_graph
        from specify_cli.status import reduce
        from specify_cli.status import read_events

        work_package_task_dir = placement_seam(repo_root, mission_slug).read_dir(
            MissionArtifactKind.WORK_PACKAGE_TASK
        )
        graph = build_dependency_graph(work_package_task_dir)
        # Merge gate evaluation must remain read-only. Writing status.json here
        # dirties the repo and can block repeated merge attempts. STATUS_STATE
        # stays on the coord-aware feature_dir (C-002).
        snapshot = reduce(read_events(feature_dir))

        wp_lanes: dict[str, str] = {}
        wp_provenance: dict[str, bool] = {}
        if snapshot and hasattr(snapshot, "work_packages"):
            for wp_id_key, wp_data in snapshot.work_packages.items():
                if isinstance(wp_data, dict):
                    lane_val = wp_data.get("lane")
                    wp_provenance[wp_id_key] = has_operator_provenance(wp_data)
                else:
                    lane_val = getattr(wp_data, "lane", None)
                    wp_provenance[wp_id_key] = False
                if lane_val:
                    wp_lanes[wp_id_key] = str(lane_val)

        # FR-009 merge face: a dependency counts as resolved when it is an
        # acceptable ending — ``approved``/``done``, OR a ``canceled`` dependency
        # with operator-authored provenance. Routed through the single
        # ``is_acceptable_ending`` authority so a canceled-with-provenance
        # dependency does not strand a surviving dependent at merge (the claim
        # face is owned by the dependency-readiness gate).
        incomplete_deps: list[str] = []
        for wp_id in wp_ids:
            for dep_id in graph.get(wp_id, []):
                dep_lane = wp_lanes.get(dep_id, "unknown")
                if not is_acceptable_ending(
                    dep_lane, has_provenance=wp_provenance.get(dep_id, False)
                ):
                    incomplete_deps.append(f"{dep_id} (lane={dep_lane})")

        if incomplete_deps:
            return GateResult(
                gate_name="dependency",
                verdict=GateVerdict.FAIL,
                details=f"Incomplete dependencies: {', '.join(incomplete_deps)}",
                blocking=is_blocking,
            )
        return GateResult(
            gate_name="dependency",
            verdict=GateVerdict.PASS,
            details="All dependencies complete",
            blocking=False,
        )
    except Exception as exc:
        return GateResult(
            gate_name="dependency",
            verdict=GateVerdict.SKIP,
            details=f"Dependency check unavailable: {exc}",
            blocking=False,
        )


def _evaluate_issue_matrix_completeness_gate(
    feature_dir: Path, is_blocking: bool,
) -> GateResult:
    """Check that every discovered issue reference has an issue-matrix row.

    T030 (WP08, FR-004, #1738): a net-new reader for ``merge_gates`` — this
    module is not a WP05 migration target, it gains its first issue-matrix
    read here. Uses the SAME two canonical definitions the finalization/
    approval path uses (no third/fourth definition): WP08's multi-file
    :func:`~specify_cli.tasks.issue_reference_discovery.
    discover_issue_references` for "what is referenced", and WP05's
    dir-based :func:`~specify_cli.tasks.issue_matrix_migration.
    load_issue_matrix` for "what the matrix says".

    Fail-closed only when references exist: zero discovered references is a
    PASS (nothing to enforce). WP09 owns the formal ``not_applicable``
    Gate-4 verdict for the post-merge review surface; this merge gate's
    zero-reference branch is intentionally the simpler "nothing to check"
    case, not a re-definition of ``not_applicable``.
    """
    try:
        from specify_cli.tasks.issue_matrix_migration import load_issue_matrix
        from specify_cli.tasks.issue_reference_discovery import discover_issue_references

        refs = discover_issue_references(feature_dir)
        if not refs:
            return GateResult(
                gate_name="issue_matrix_completeness",
                verdict=GateVerdict.PASS,
                details="No issue references discovered — nothing to enforce",
                blocking=False,
            )

        referenced_issues = {f"#{ref.number}" for ref in refs}
        matrix_issues = {row.issue for row in load_issue_matrix(feature_dir)}
        missing_issues = sorted(referenced_issues - matrix_issues)

        if missing_issues:
            return GateResult(
                gate_name="issue_matrix_completeness",
                verdict=GateVerdict.FAIL,
                details=(
                    "Issue-matrix is missing rows for referenced issue(s): "
                    f"{', '.join(missing_issues)}"
                ),
                blocking=is_blocking,
            )
        return GateResult(
            gate_name="issue_matrix_completeness",
            verdict=GateVerdict.PASS,
            details=f"All {len(referenced_issues)} referenced issue(s) have matrix rows",
            blocking=False,
        )
    except Exception as exc:
        return GateResult(
            gate_name="issue_matrix_completeness",
            verdict=GateVerdict.FAIL,
            details=f"Could not evaluate issue-matrix completeness: {exc}",
            blocking=is_blocking,
        )
