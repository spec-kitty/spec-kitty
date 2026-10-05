"""Ordered phases of ``spec-kitty implement`` and the immutable values they pass along.

Each phase is built once, by exactly one phase function, and never changes afterwards
(data-model.md, "Phase results"). The command (``implement.py``) owns the tracker steps and their
exception handling; the phases raise and never render the tracker.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specify_cli.lanes.implement_support import LaneWorkspaceResult
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.workspace.context import ResolvedWorkspace


@dataclass(frozen=True)
class ImplementContext:
    """The ``detect`` phase result: where the mission lives and what the WP declares."""

    repo_root: Path
    auto_commit: bool | None
    mission_slug: str
    feature_dir: Path
    wp_file: Path
    declared_deps: list[str]


@dataclass(frozen=True)
class ClaimPreflight:
    """The claim-preflight result: the target branch and the two surfaces the claim reads."""

    planning_branch: str
    status_feature_dir: Path
    lanes_feature_dir: Path


@dataclass(frozen=True)
class WorkspaceSelection:
    """The workspace/lane selection result."""

    resolved_workspace: ResolvedWorkspace
    lanes_manifest: LanesManifest | None
    lane: ExecutionLane | None


@dataclass(frozen=True)
class AllocationResult:
    """The ``allocate`` phase result: the allocated workspace plus the effective ``--base``."""

    result: LaneWorkspaceResult
    effective_base: str | None
