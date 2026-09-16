"""Shared preflight for explicitly selected, single-branch mission checkouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from mission_runtime import ActionContextError
from specify_cli.core.git_ops import get_current_branch
from specify_cli.core.paths import load_meta_fail_closed
from specify_cli.core.utils import ensure_within_directory
from specify_cli.git.commit_helpers import _staged_tree_is_empty
from specify_cli.git.protection_policy import ProtectionPolicy


@dataclass(frozen=True)
class OwnedMission:
    """Validated repository identity, working checkout and mission identity."""

    primary: Path
    root: Path
    directory: Path
    slug: str
    target: str

    def files(self, paths: list[Path]) -> list[Path]:
        """Validate the complete batch before any staging or file mutation."""
        resolved = []
        for path in paths:
            candidate = self.root / path if not path.is_absolute() else path
            if ".." in path.parts:
                raise ActionContextError("OWNED_MISSION_PATH_REFUSED", f"Path is outside the selected mission: {path}")
            try:
                resolved.append(ensure_within_directory(candidate, self.directory))
            except ValueError as exc:
                raise ActionContextError("OWNED_MISSION_PATH_REFUSED", f"Path is outside the selected mission: {path}") from exc
        return resolved


class _EffectiveRootKwargs(TypedDict, total=False):
    effective_root: Path


def effective_root_kwargs(root: Path | None) -> _EffectiveRootKwargs:
    """Preserve omitted-keyword call shapes while keeping ``**kwargs`` typed."""
    return {"effective_root": root} if root is not None else {}


def resolve_owned_mission(
    primary: Path,
    checkout: Path,
    handle: str | None,
    *,
    target_override: str | None = None,
) -> OwnedMission:
    """Validate ownership before reading mission data; never fall back to primary."""
    # Imported lazily: both mission_resolver (via the specify_cli.context package) and
    # checkout_ownership (via specify_cli.ownership.workspace_strategy) pull the status
    # orchestration + workspace packages at module scope. owned_mission is cold-imported
    # by task_utils.support (37 CLI command modules), so module-level imports here break
    # the status-free cold-import boundary (#1461). They are used only in this function.
    from specify_cli.context.mission_resolver import (
        AmbiguousHandleError,
        MissionNotFoundError,
        resolve_mission,
    )
    from specify_cli.core.checkout_ownership import error_for_claim, resolve_ownership_claim

    claim = resolve_ownership_claim(checkout, resolved_primary=primary)
    error = error_for_claim(claim)
    if error is not None:
        raise ActionContextError(error.error_code, str(error))
    if not handle or not handle.strip():
        raise ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "--owned-checkout requires an explicit --mission.")
    root = claim.claimed_checkout
    try:
        mission = resolve_mission(handle, root)
    except (MissionNotFoundError, AmbiguousHandleError) as exc:
        raise ActionContextError("FEATURE_CONTEXT_UNRESOLVED", str(exc)) from exc
    directory = mission.feature_dir.resolve()
    try:
        ensure_within_directory(directory, root / "kitty-specs")
    except ValueError as exc:
        raise ActionContextError("OWNED_MISSION_PATH_REFUSED", "Mission directory escapes the selected checkout.") from exc
    meta = load_meta_fail_closed(directory)
    if meta is None or meta.get("topology") != "single_branch" or meta.get("coordination_branch"):
        raise ActionContextError("OWNED_TOPOLOGY_UNSUPPORTED", "--owned-checkout currently requires single_branch.")
    current = get_current_branch(root)
    target = str(meta.get("target_branch") or "")
    if current is None or not target or current != target or (target_override is not None and target_override != target):
        raise ActionContextError("OWNED_BRANCH_REFUSED", "The current branch and mission target must match; detached HEAD is unsupported.")
    if ProtectionPolicy.resolve(primary).is_protected(target) or ProtectionPolicy.resolve(root).is_protected(target):
        raise ActionContextError("OWNED_BRANCH_REFUSED", f"Protected destination refused: {target}")
    result = OwnedMission(primary.resolve(), root, directory, mission.feature_dir.name, target)
    # #3866: the resolve-time validation is a bounded top-level tripwire, not a
    # full-tree scan. ``directory.rglob("*")`` stat'd every entry of the mission
    # tree on every resolve (~8 call sites, several calls per command) — an
    # O(tree) latency cliff whose only unique value was catching a symlink
    # escape before write time; ``OwnedMission.files`` re-validates the actual
    # written paths at write time anyway, so a nested symlink escape is still
    # refused there. Validating the top level keeps the boundary tripwire (a
    # symlinked mission-root entry escaping the checkout is refused at resolve,
    # before any effects) at O(top-level entries) instead of O(tree).
    result.files(list(directory.iterdir()))
    return result


def require_unstaged_index(context: OwnedMission) -> None:
    """Refuse pre-existing staged changes instead of temporarily stashing them."""
    # _staged_tree_is_empty is the canonical staged-tree authority (commit_helpers).
    if not _staged_tree_is_empty(context.root):
        raise ActionContextError("OWNED_INDEX_REFUSED", "The selected checkout must have no staged changes before this operation.")
