"""Mission and work-package filesystem fixtures for workflow regressions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specify_cli.frontmatter import write_frontmatter
from specify_cli.status.models import Lane, ReviewResult, StatusEvent, StatusSnapshot
from specify_cli.status.reducer import materialize
from tests._support.status_seed import seed_status_event

DEFAULT_CREATED_AT = "2026-05-02T08:31:36.083678+00:00"
DEFAULT_EVENT_AT = "2026-05-02T08:45:00+00:00"
DEFAULT_MISSION_ID = "01KQKV85RELIABILITY000000000"


@dataclass(frozen=True)
class BranchContext:
    """Canonical branch/worktree metadata for a mission lane."""

    mission_branch: str
    lane_branch: str
    base_ref: str
    lane_worktree: Path

    def to_json_dict(self) -> dict[str, str]:
        return {
            "mission_branch": self.mission_branch,
            "lane_branch": self.lane_branch,
            "base_ref": self.base_ref,
            "lane_worktree": str(self.lane_worktree),
        }


@dataclass(frozen=True)
class MissionFixture:
    """Paths and identity for a temporary Spec Kitty mission."""

    repo_root: Path
    mission_slug: str
    mission_id: str
    mission_dir: Path
    tasks_dir: Path
    branch_context: BranchContext | None = None

    @property
    def status_events_path(self) -> Path:
        return self.mission_dir / "status.events.jsonl"

    @property
    def status_snapshot_path(self) -> Path:
        return self.mission_dir / "status.json"


@dataclass(frozen=True)
class WorkPackageSpec:
    """Frontmatter fields needed by reliability workflow tests."""

    work_package_id: str = "WP01"
    title: str = "Regression Harness"
    dependencies: tuple[str, ...] = ()
    owned_files: tuple[str, ...] = ("tests/reliability/**",)
    authoritative_surface: str = "tests/reliability/"
    execution_mode: str = "code_change"
    requirement_refs: tuple[str, ...] = ("FR-001", "NFR-001")
    subtasks: tuple[str, ...] = ("T001",)
    lane: str | None = None

    @property
    def slug(self) -> str:
        return self.title.lower().replace(" ", "-")

    @property
    def file_stem(self) -> str:
        return f"{self.work_package_id}-{self.slug}"


@dataclass(frozen=True)
class ReviewArtifactSpec:
    """Minimal review-cycle artifact shape used by release gates."""

    work_package_id: str = "WP01"
    work_package_slug: str = "WP01-regression-harness"
    cycle: int = 1
    verdict: str = "rejected"
    reviewer: str = "reviewer-renata"
    created_at: str = DEFAULT_CREATED_AT

    @property
    def file_name(self) -> str:
        return f"review-cycle-{self.cycle}.md"

    @property
    def relative_path(self) -> Path:
        return Path("tasks") / self.work_package_slug / self.file_name

    def review_ref(self, mission_slug: str) -> str:
        return f"review-cycle://{mission_slug}/{self.work_package_slug}/{self.file_name}"


@dataclass(frozen=True)
class SharedLaneContext:
    """Active-work-package ownership context for shared-lane guards."""

    lane_id: str
    active_work_package_id: str
    lane_work_package_ids: tuple[str, ...]
    owned_files_by_work_package: dict[str, tuple[str, ...]] = field(default_factory=dict)
    lane_worktree: Path | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "active_work_package_id": self.active_work_package_id,
            "lane_work_package_ids": list(self.lane_work_package_ids),
            "owned_files_by_work_package": {
                key: list(value) for key, value in self.owned_files_by_work_package.items()
            },
            "lane_worktree": str(self.lane_worktree) if self.lane_worktree is not None else None,
        }


def create_mission_fixture(
    tmp_path: Path,
    *,
    repo_name: str = "repo",
    mission_slug: str = "release-320-workflow-reliability-01KQKV85",
    mission_id: str = DEFAULT_MISSION_ID,
    title: str = "3.2.0 Workflow Reliability Blockers",
    branch_context: BranchContext | None = None,
) -> MissionFixture:
    """Create a temporary repo root, mission directory, tasks dir, and meta.json."""

    repo_root = tmp_path / repo_name
    mission_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "title": title,
        "mission_type": "software-dev",
        "created_at": DEFAULT_CREATED_AT,
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if branch_context is not None:
        (mission_dir / "workspace-context.json").write_text(
            json.dumps(branch_context.to_json_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return MissionFixture(
        repo_root=repo_root,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mission_dir=mission_dir,
        tasks_dir=tasks_dir,
        branch_context=branch_context,
    )


def write_work_package(mission: MissionFixture, spec: WorkPackageSpec) -> Path:
    """Write a realistic flat ``tasks/WP*.md`` file with YAML frontmatter."""

    frontmatter: dict[str, Any] = {
        "work_package_id": spec.work_package_id,
        "title": spec.title,
        "dependencies": list(spec.dependencies),
        "requirement_refs": list(spec.requirement_refs),
        "planning_base_branch": "main",
        "merge_target_branch": "main",
        "branch_strategy": "Planning artifacts were generated on main; completed changes merge back to main.",
        "base_branch": "kitty/mission-release-320-workflow-reliability-01KQKV85",
        "base_commit": "35a2f79ee4aa3ed1737fff8996f64bf820f107bf",
        "created_at": DEFAULT_CREATED_AT,
        "subtasks": list(spec.subtasks),
        "phase": "Phase 1 - Regression Foundation",
        "assignee": "",
        "agent": "codex",
        "shell_pid": "0",
        "history": [
            {
                "at": "2026-05-02T08:10:17Z",
                "actor": "system",
                "action": "Fixture work package created.",
            }
        ],
        "authoritative_surface": spec.authoritative_surface,
        "execution_mode": spec.execution_mode,
        "owned_files": list(spec.owned_files),
    }
    if spec.lane is not None:
        frontmatter["lane"] = spec.lane

    body = f"\n# Work Package Prompt: {spec.work_package_id} - {spec.title}\n\nFixture body.\n"
    path = mission.tasks_dir / f"{spec.file_stem}.md"
    write_frontmatter(path, frontmatter, body)
    return path


def append_status_event(
    mission: MissionFixture,
    *,
    work_package_id: str = "WP01",
    from_lane: Lane = Lane.PLANNED,
    to_lane: Lane = Lane.IN_PROGRESS,
    event_id: str = "01KQKV85STATUS00000000001",
    at: str = DEFAULT_EVENT_AT,
    actor: str = "codex",
    execution_mode: str = "worktree",
    reason: str | None = "fixture transition",
    review_result: ReviewResult | None = None,
) -> StatusEvent:
    """Append a canonical status event using the production event store.

    ``review_result`` (WP05, verdict-seam-write-unification-01KZ9Q35,
    additive/backward-compatible): every verdict reader now resolves the
    event authority (``event_sourced_review_result``), never
    ``review-cycle-N.md`` frontmatter -- callers that need a fixture WP's
    CURRENT verdict to be visible to a repointed reader/gate must pass this,
    not merely write the on-disk artifact. Defaults to ``None`` so every
    pre-existing call site is unaffected.
    """

    event = StatusEvent(
        event_id=event_id,
        mission_slug=mission.mission_slug,
        mission_id=mission.mission_id,
        wp_id=work_package_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor=actor,
        force=False,
        execution_mode=execution_mode,
        reason=reason,
        review_result=review_result,
    )
    seed_status_event(mission.mission_dir, event)
    return event


def materialize_status(mission: MissionFixture) -> StatusSnapshot:
    """Materialize ``status.json`` through the production reducer."""

    return materialize(mission.mission_dir)


def write_review_artifact(mission: MissionFixture, spec: ReviewArtifactSpec) -> Path:
    """Write a review-cycle artifact with verdict frontmatter."""

    frontmatter = {
        "work_package_id": spec.work_package_id,
        "review_ref": spec.review_ref(mission.mission_slug),
        "cycle": spec.cycle,
        "verdict": spec.verdict,
        "reviewer": spec.reviewer,
        "created_at": spec.created_at,
    }
    body = f"\n# Review Cycle {spec.cycle}: {spec.work_package_id}\n\nVerdict: {spec.verdict}\n"
    path = mission.mission_dir / spec.relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(path, frontmatter, body)
    return path


def write_shared_lane_context(mission: MissionFixture, context: SharedLaneContext) -> Path:
    """Persist active shared-lane ownership context as deterministic JSON."""

    path = mission.mission_dir / "shared-lane-context.json"
    path.write_text(json.dumps(context.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
