"""Lane worktree topology analysis.

Agents need a deterministic view of which work packages share a lane worktree,
which lane branch they are on, and what the diff base is. This module renders
that lane topology as structured JSON for prompt injection and as simple text
for diagnostics.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from specify_cli.core.dependency_graph import build_dependency_graph, topological_sort
from specify_cli.core.paths import get_main_repo_root, get_feature_target_branch
from specify_cli.mission_metadata import mission_identity_fields, resolve_mission_identity
from specify_cli.status import CanonicalStatusNotFoundError, Lane, get_wp_lane
from specify_cli.workspace.context import get_normalized_wp, resolve_workspace_for_wp


@dataclass
class WPTopologyEntry:
    """Per-WP lane topology information."""

    wp_id: str
    execution_mode: str = "code_change"
    resolution_kind: str = "lane_workspace"
    lane_id: str | None = None
    lane_wp_ids: list[str] = field(default_factory=list)
    branch_name: str | None = None
    base_branch: str | None = None
    review_paths: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    lane: str = "planned"
    worktree_exists: bool = False
    commits_ahead_of_base: int = 0


@dataclass
class FeatureTopology:
    """Lane topology for a feature."""

    mission_slug: str
    target_branch: str
    mission_branch: str
    mission_number: str = ""
    mission_type: str = "software-dev"
    entries: list[WPTopologyEntry] = field(default_factory=list)

    @property
    def has_stacking(self) -> bool:
        """Compatibility shim: true when the lane topology is worth injecting."""
        lane_ids = {entry.lane_id for entry in self.entries if entry.lane_id}
        resolution_kinds = {entry.resolution_kind for entry in self.entries}
        return len(lane_ids) > 1 or any(len(entry.lane_wp_ids) > 1 for entry in self.entries) or len(resolution_kinds) > 1

    def get_entry(self, wp_id: str) -> WPTopologyEntry | None:
        for entry in self.entries:
            if entry.wp_id == wp_id:
                return entry
        return None

    def get_actual_base_for_wp(self, wp_id: str) -> str | None:
        entry = self.get_entry(wp_id)
        if entry is not None and entry.resolution_kind == "repo_root":
            return entry.base_branch
        if entry is not None and entry.base_branch:
            return entry.base_branch
        return self.target_branch


def _read_canonical_lane_or_default(feature_dir: Path, wp_id: str) -> str:
    try:
        lane = get_wp_lane(feature_dir, wp_id)
    except CanonicalStatusNotFoundError:
        return "planned"
    except Exception:
        return "planned"
    if lane == Lane.UNINITIALIZED:
        return "planned"
    return str(lane)


def _count_commits_ahead(worktree_path: Path, base_branch: str) -> int:
    result = subprocess.run(
        ["git", "rev-list", "--count", f"{base_branch}..HEAD"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            return int(result.stdout.strip())
        except ValueError:
            pass
    return 0


def _planning_claim_commit(repo_root: Path, wp_path: Path, wp_id: str) -> str | None:
    result = subprocess.run(
        [
            "git",
            "log",
            "--format=%H%x00%s",
            "--",
            str(wp_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        for raw in result.stdout.splitlines():
            commit_hash, _, subject = raw.partition("\x00")
            if not commit_hash:
                continue
            if f"Move {wp_id} to in_progress" in subject or f"{wp_id} claimed for implementation" in subject or f"Start {wp_id} implementation" in subject:
                return commit_hash.strip()
    return None


def materialize_worktree_topology(repo_root: Path, mission_slug: str) -> FeatureTopology:
    """Gather the full lane worktree topology for a feature."""
    from mission_runtime import (
        MissionArtifactKind,
        ReadDegradeStrategy,
        ReadDirDecision,
        placement_seam,
        resolve_read_dir_or_degrade,
    )
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.lanes.branch_naming import lane_branch_name
    from specify_cli.lanes.persistence import read_lanes_json

    main_repo_root = get_main_repo_root(repo_root)
    target_branch = get_feature_target_branch(main_repo_root, mission_slug)
    # FR-001 (#2185): a single PRIMARY read dir co-resolves all three legs — the
    # identity meta.json (PRIMARY_METADATA), lanes.json (LANE_STATE), and the
    # tasks/ dependency graph (WORK_PACKAGE_TASK) are all PRIMARY-partition kinds
    # that resolve topology-blind to the PRIMARY checkout. The coord-aware resolver
    # would land on the STATUS-only ``-coord`` husk (no meta/lanes/tasks), yielding
    # a sentinel identity and an empty topology.
    # read-side-placement-seam-migration WP07: routed through
    # ``placement_seam`` (fail-loud on a deleted-coord mismatch, NFR-002)
    # instead of the kind-blind ``resolve_planning_read_dir``.
    seam = placement_seam(main_repo_root, mission_slug)
    feature_dir = seam.read_dir(MissionArtifactKind.LANE_STATE)
    # FR-006 (#2698): the per-WP LANE rendered into the review handoff is a
    # STATUS_STATE/COORD-partition kind, NOT a PRIMARY-partition one. Reading it
    # off ``feature_dir`` (the PRIMARY dir above) renders every WP as stale
    # ``planned`` on a coord-topology mission, because status transitions land on
    # the coord husk, never the PRIMARY status log. Route the lane read through
    # the SAME seam's STATUS_STATE projection — the coord husk for a coord
    # mission, and identical to ``feature_dir`` for flat topologies (structural
    # no-op). Identity/lanes.json/tasks stay on ``feature_dir`` (C-002: only the
    # STATUS-partition read moves; PRIMARY reads are untouched). Per-leg pattern
    # mirrors ``tasks_dependency_graph._check_dependent_warnings``.
    #
    # Degrade (WP07 discriminating-negative contract, #2698): materializing the
    # topology is a read-only *rendering* concern, so a mission whose coord
    # branch was deleted/cleaned up must still render — not crash. When the
    # STATUS_STATE projection is unreachable (coord branch declared in meta.json
    # but absent from git) fall back to the PRIMARY ``feature_dir``: the per-WP
    # lane degrades to its lanes.json default, which is the honest value once the
    # live coord status is genuinely gone. Live coord → true lanes (the fix
    # above); deleted coord → graceful PRIMARY fallback. The seam's fail-loud
    # NFR-002 behavior stays scoped to coord-partition WRITE/lifecycle paths, not
    # read-only handoff rendering.
    status_decision: ReadDirDecision = resolve_read_dir_or_degrade(
        main_repo_root,
        mission_slug,
        MissionArtifactKind.STATUS_STATE,
        strategy=ReadDegradeStrategy.DEGRADE_TO_FEATURE_DIR,
        caught=(CoordinationBranchDeleted,),
        degrade_target=feature_dir,
    )
    status_feature_dir = status_decision.read_dir
    identity = resolve_mission_identity(feature_dir)
    lanes_manifest = read_lanes_json(feature_dir)
    graph = build_dependency_graph(feature_dir)

    try:
        topo_order = topological_sort(graph)
    except ValueError:
        topo_order = sorted(graph.keys())

    entries: list[WPTopologyEntry] = []
    for wp_id in topo_order:
        workspace = resolve_workspace_for_wp(main_repo_root, mission_slug, wp_id)
        normalized_wp = get_normalized_wp(main_repo_root, mission_slug, wp_id)
        lane_entry = lanes_manifest.lane_for_wp(wp_id) if lanes_manifest is not None else None
        if lane_entry is None and workspace.resolution_kind != "repo_root":
            raise ValueError(f"{wp_id} is not assigned to any lane in lanes.json")

        worktree_exists = workspace.exists
        commits_ahead = 0
        if workspace.resolution_kind == "repo_root":
            base_branch: str | None = _planning_claim_commit(main_repo_root, normalized_wp.path, wp_id)
        else:
            base_branch = lanes_manifest.mission_branch if lane_entry and lanes_manifest is not None else None
        if worktree_exists and base_branch:
            commits_ahead = _count_commits_ahead(workspace.worktree_path, base_branch)

        entries.append(
            WPTopologyEntry(
                wp_id=wp_id,
                execution_mode=workspace.execution_mode,
                resolution_kind=workspace.resolution_kind,
                lane_id=lane_entry.lane_id if lane_entry else workspace.lane_id,
                lane_wp_ids=list(lane_entry.wp_ids) if lane_entry else list(workspace.lane_wp_ids),
                branch_name=(
                    lane_branch_name(
                        mission_slug,
                        lane_entry.lane_id,
                        target_branch=target_branch,
                    )
                    if lane_entry
                    else workspace.branch_name
                ),
                base_branch=base_branch,
                review_paths=(
                    list(normalized_wp.metadata.owned_files)
                    + (
                        [
                            f":(exclude)kitty-specs/{mission_slug}/tasks/**",
                            f":(exclude)kitty-specs/{mission_slug}/tasks.md",
                            f":(exclude)kitty-specs/{mission_slug}/status.events.jsonl",
                            f":(exclude)kitty-specs/{mission_slug}/status.json",
                        ]
                        if any(path.startswith(f"kitty-specs/{mission_slug}/") for path in normalized_wp.metadata.owned_files)
                        else []
                    )
                ),
                dependencies=graph.get(wp_id, []),
                lane=_read_canonical_lane_or_default(status_feature_dir, wp_id),
                worktree_exists=worktree_exists,
                commits_ahead_of_base=commits_ahead,
            )
        )

    return FeatureTopology(
        mission_slug=identity.mission_slug,
        mission_number=str(identity.mission_number) if identity.mission_number is not None else "",
        mission_type=identity.mission_type,
        target_branch=target_branch,
        mission_branch=lanes_manifest.mission_branch if lanes_manifest is not None else target_branch,
        entries=entries,
    )


def render_topology_json(topology: FeatureTopology, current_wp_id: str) -> list[str]:
    """Render lane topology as structured JSON for prompt injection."""
    current_entry = topology.get_entry(current_wp_id)
    diff_base = topology.get_actual_base_for_wp(current_wp_id)
    identity = mission_identity_fields(
        topology.mission_slug,
        topology.mission_number,
        topology.mission_type,
    )
    diff_command = (
        f"git diff {diff_base}..HEAD -- {' '.join(current_entry.review_paths)}"
        if current_entry and current_entry.resolution_kind == "repo_root" and current_entry.review_paths and diff_base
        else f"git diff {diff_base}..HEAD"
    )
    if current_entry and current_entry.resolution_kind == "repo_root" and not diff_base:
        diff_command = "unavailable: no deterministic implementation claim commit found"

    entries_json = []
    for entry in topology.entries:
        entry_data: dict[str, object] = {
            "wp": entry.wp_id,
            "status": entry.lane,
            "execution_mode": entry.execution_mode,
            "workspace_kind": entry.resolution_kind,
            "lane_id": entry.lane_id,
            "lane_wp_ids": entry.lane_wp_ids,
            "branch": entry.branch_name,
            "base": entry.base_branch,
        }
        if entry.worktree_exists:
            entry_data["commits_ahead"] = entry.commits_ahead_of_base
        if entry.dependencies:
            entry_data["dependencies"] = entry.dependencies
        entries_json.append(entry_data)

    payload = {
        "mission_slug": identity["mission_slug"],
        "mission_number": identity["mission_number"],
        "mission_type": identity["mission_type"],
        "target_branch": topology.target_branch,
        "mission_branch": topology.mission_branch,
        "current_wp": current_wp_id,
        "diff_command": diff_command,
        "shared_lane": bool(current_entry and len(current_entry.lane_wp_ids) > 1),
        "note": (
            f"{current_wp_id} runs in the repository root planning workspace."
            if current_entry and current_entry.resolution_kind == "repo_root"
            else f"{current_wp_id} shares lane {current_entry.lane_id} with {', '.join(current_entry.lane_wp_ids)}. "
            "Sequential WPs in the same lane reuse one worktree."
            if current_entry and len(current_entry.lane_wp_ids) > 1
            else f"{current_wp_id} owns lane {current_entry.lane_id} alone."
            if current_entry
            else f"{current_wp_id} is not in the computed topology."
        ),
        "entries": entries_json,
    }

    return [
        "<!-- WORKTREE_TOPOLOGY -->",
        json.dumps(payload, indent=2),
        "<!-- /WORKTREE_TOPOLOGY -->",
    ]


def render_topology_text(topology: FeatureTopology, current_wp_id: str) -> list[str]:
    """Render lane topology as human-readable text."""
    lines = []
    lines.append("╔" + "═" * 78 + "╗")
    lines.append("║  LANE WORKTREE TOPOLOGY" + " " * 54 + "║")
    lines.append("╠" + "═" * 78 + "╣")
    lines.append(f"║  Feature: {topology.mission_slug:<66} ║")
    lines.append(f"║  Target:  {topology.target_branch:<66} ║")
    lines.append(f"║  Mission: {topology.mission_branch:<66} ║")
    lines.append("║" + " " * 78 + "║")

    for entry in topology.entries:
        marker = "→" if entry.wp_id == current_wp_id else " "
        if entry.resolution_kind == "repo_root":
            line_text = f"{marker} {entry.wp_id} [{entry.lane}] workspace=repo-root mode={entry.execution_mode}"
        else:
            lane_members = ",".join(entry.lane_wp_ids)
            line_text = f"{marker} {entry.wp_id} [{entry.lane}] lane={entry.lane_id} members={lane_members} branch={entry.branch_name}"
        if entry.worktree_exists and entry.commits_ahead_of_base > 0:
            line_text += f" (+{entry.commits_ahead_of_base})"
        padded = line_text[:76].ljust(76)
        lines.append(f"║  {padded}║")

    lines.append("╚" + "═" * 78 + "╝")
    return lines


__all__ = [
    "WPTopologyEntry",
    "FeatureTopology",
    "materialize_worktree_topology",
    "render_topology_json",
    "render_topology_text",
]
