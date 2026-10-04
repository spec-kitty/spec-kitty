"""Data models for execution lanes.

An ExecutionLane groups work packages that must share a single
worktree and branch because they have overlapping write scopes.
Sequential dependencies are represented as lane-level dependencies.

A LanesManifest is the complete lane assignment for a feature,
persisted as lanes.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CollapseEvent:
    """A single union-find merge event during lane computation.

    Attributes:
        wp_a: First work package ID involved in the merge.
        wp_b: Second work package ID involved in the merge.
        rule: Rule that triggered the merge. One of:
            "write_scope_overlap", "surface_heuristic", or
            "frozen_lane_membership" (#5573: two started WPs recorded on the
            same lane are kept together on a re-finalize).
        evidence: Human-readable explanation of why the merge occurred.
    """

    wp_a: str
    wp_b: str
    rule: str
    evidence: str

    def to_dict(self) -> dict[str, str]:
        return {
            "wp_a": self.wp_a,
            "wp_b": self.wp_b,
            "rule": self.rule,
            "evidence": self.evidence,
        }


@dataclass
class CollapseReport:
    """Summary of all union-find merge events during lane computation.

    Attributes:
        events: All CollapseEvent instances recorded during computation.
        independent_wps_collapsed: Number of merge events where the two WPs
            have no direct or transitive dependency relationship.
    """

    events: list[CollapseEvent]
    independent_wps_collapsed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "total_merges": len(self.events),
            "independent_wps_collapsed": self.independent_wps_collapsed,
            "by_rule": self._count_by_rule(),
        }

    def _count_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.events:
            counts[e.rule] = counts.get(e.rule, 0) + 1
        return counts


@dataclass(frozen=True)
class ExecutionLane:
    """A group of WPs sharing one worktree and branch.

    Attributes:
        lane_id: Identifier like "lane-a", "lane-b".
        wp_ids: WP IDs ordered by execution sequence within the lane.
        write_scope: Union of owned_files globs from all WPs in the lane.
        predicted_surfaces: Surface tags from the surface taxonomy.
        depends_on_lanes: Lane IDs that must complete before this lane starts.
        parallel_group: Lanes with the same group number can run in parallel.
    """

    lane_id: str
    wp_ids: tuple[str, ...]
    write_scope: tuple[str, ...]
    predicted_surfaces: tuple[str, ...]
    depends_on_lanes: tuple[str, ...]
    parallel_group: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "wp_ids": list(self.wp_ids),
            "write_scope": list(self.write_scope),
            "predicted_surfaces": list(self.predicted_surfaces),
            "depends_on_lanes": list(self.depends_on_lanes),
            "parallel_group": self.parallel_group,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionLane:
        return cls(
            lane_id=data["lane_id"],
            wp_ids=tuple(data["wp_ids"]),
            write_scope=tuple(data.get("write_scope", [])),
            predicted_surfaces=tuple(data.get("predicted_surfaces", [])),
            depends_on_lanes=tuple(data.get("depends_on_lanes", [])),
            parallel_group=data.get("parallel_group", 0),
        )


@dataclass
class LanesManifest:
    """Complete lane assignment for a feature.

    Attributes:
        version: Schema version (currently 1).
        mission_slug: Human-readable slug used in branch names.
        mission_id: Canonical ULID from meta.json. Used for merge locks and
            runtime identity. None for legacy missions whose backfill hasn't run
            (WP04/FR-004: never the mission_slug).
        mission_branch: Integration branch name (kitty/mission-{mission_slug}).
        target_branch: Branch the mission merges into (e.g. "main").
        lanes: Ordered list of execution lanes.
        computed_at: ISO 8601 timestamp of computation.
        computed_from: Description of inputs used (e.g. "dependency_graph+ownership").
        planning_artifact_wps: **Derived view** — WP IDs whose ``execution_mode``
            is ``planning_artifact``.  Populated from the ``lane-planning`` lane's
            ``wp_ids`` for backward compatibility.  Do NOT use this field as an
            authoritative source; use ``lane_for_wp()`` instead.  As of 3.1.1
            planning-artifact WPs are first-class lane-owned entities assigned to
            the canonical ``"lane-planning"`` lane.
        planning_commit_sha: FR-009 / ADR ``2026-07-29-1``: the recorded
            finalize-tasks planning-artifact commit on ``target_branch``, captured
            ONCE by ``mission_finalize_lanes._compute_and_write_lanes`` and frozen —
            never re-derived live at lane-allocation time (the moving-tip trap the
            ADR closes). ``None`` for a ``lanes.json`` written before this field
            existed; the allocator's merge step is a no-op in that case,
            reproducing pre-fix behaviour exactly (backward compatible).
    """

    version: int
    mission_slug: str
    mission_id: str | None  # WP04/FR-004: ULID or None; never a slug
    mission_branch: str
    target_branch: str
    lanes: list[ExecutionLane]
    computed_at: str
    computed_from: str
    planning_artifact_wps: list[str] = field(default_factory=list)
    collapse_report: CollapseReport | None = field(default=None)
    planning_commit_sha: str | None = field(default=None)

    def lane_for_wp(self, wp_id: str) -> ExecutionLane | None:
        """Return the lane containing the given WP, or None."""
        for lane in self.lanes:
            if wp_id in lane.wp_ids:
                return lane
        return None

    def parallel_groups(self) -> dict[int, list[ExecutionLane]]:
        """Group lanes by their parallel_group number."""
        groups: dict[int, list[ExecutionLane]] = {}
        for lane in self.lanes:
            groups.setdefault(lane.parallel_group, []).append(lane)
        return groups

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "version": self.version,
            "mission_slug": self.mission_slug,
            "mission_id": self.mission_id,
            "mission_branch": self.mission_branch,
            "target_branch": self.target_branch,
            "lanes": [lane.to_dict() for lane in self.lanes],
            "computed_at": self.computed_at,
            "computed_from": self.computed_from,
            "planning_artifact_wps": self.planning_artifact_wps,
            "planning_commit_sha": self.planning_commit_sha,
        }
        if self.collapse_report and self.collapse_report.events:
            d["collapse_report"] = self.collapse_report.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LanesManifest:
        mission_slug = data["mission_slug"]
        collapse_report: CollapseReport | None = None
        if "collapse_report" in data:
            cr_data = data["collapse_report"]
            collapse_report = CollapseReport(
                events=[
                    CollapseEvent(
                        wp_a=e["wp_a"],
                        wp_b=e["wp_b"],
                        rule=e["rule"],
                        evidence=e["evidence"],
                    )
                    for e in cr_data.get("events", [])
                ],
                independent_wps_collapsed=cr_data.get("independent_wps_collapsed", 0),
            )
        return cls(
            version=data["version"],
            mission_slug=mission_slug,
            mission_id=data.get("mission_id"),  # WP04: None when absent (no slug fallback)
            mission_branch=data["mission_branch"],
            target_branch=data["target_branch"],
            lanes=[ExecutionLane.from_dict(lane) for lane in data["lanes"]],
            computed_at=data["computed_at"],
            computed_from=data["computed_from"],
            planning_artifact_wps=data.get("planning_artifact_wps", []),
            collapse_report=collapse_report,
            planning_commit_sha=data.get("planning_commit_sha"),
        )
