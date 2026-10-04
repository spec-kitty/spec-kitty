"""Merge support package for lane-based Spec Kitty merges."""

from __future__ import annotations

from specify_cli.consolidation.baseline import (
    BaselineMergeCommitError,
    assert_baseline_merge_commit_on_target,
    record_baseline_merge_commit,
)
from specify_cli.consolidation.config import (
    ConfigError,
    MergeConfig,
    MergeStrategy,
    load_merge_config,
)
from specify_cli.consolidation.conflict_resolver import (
    ConflictType,
    ResolutionResult,
    classify_conflict,
    resolve_owned_conflicts,
)
from specify_cli.consolidation.mission_number.bake import assign_next_mission_number
from specify_cli.consolidation.ordering import (
    MergeOrderError,
    get_merge_order,
    has_dependency_info,
)
from specify_cli.consolidation.state import (
    ConsolidationState,
    acquire_merge_lock,
    clear_state,
    has_active_consolidation,
    is_merge_locked,
    load_state,
    needs_number_assignment,
    release_merge_lock,
    save_state,
)
from specify_cli.consolidation.workspace import (
    cleanup_merge_workspace,
    create_merge_workspace,
    get_merge_workspace,
    get_merge_workspace_path,
)

__all__ = [
    # Baseline merge commit
    "BaselineMergeCommitError",
    "record_baseline_merge_commit",
    "assert_baseline_merge_commit_on_target",
    # Merge config
    "MergeStrategy",
    "MergeConfig",
    "ConfigError",
    "load_merge_config",
    # Conflict resolution
    "ConflictType",
    "ResolutionResult",
    "classify_conflict",
    "resolve_owned_conflicts",
    # Ordering
    "get_merge_order",
    "MergeOrderError",
    "has_dependency_info",
    "assign_next_mission_number",
    # State persistence
    "ConsolidationState",
    "save_state",
    "load_state",
    "clear_state",
    "has_active_consolidation",
    "acquire_merge_lock",
    "release_merge_lock",
    "is_merge_locked",
    "needs_number_assignment",
    # Workspace
    "create_merge_workspace",
    "cleanup_merge_workspace",
    "get_merge_workspace",
    "get_merge_workspace_path",
]
