"""Agent context management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, cast

import typer
from rich.console import Console
from specify_cli.cli.console import console
from typing_extensions import Annotated

from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,
    MissionNotFoundError,
    resolve_mission,
)
from specify_cli.core.paths import locate_project_root
from specify_cli.missions.operation_context import (
    MissionOperationContext,
    MissionSurfaceConflictError,
    resolve_mission_operation_context,
)
from mission_runtime import (
    ACTION_NAMES,
    ActionName,
    ActionContextError,
    resolve_action_context,
)

app = typer.Typer(name="context", help="Agent context management commands", no_args_is_help=True)

# #5160 friction 3 (#2017/#2101): planning/authoring actions author artifacts on
# the PRIMARY partition (spec/plan/tasks). ``resolve_action_context`` routes the
# reported ``feature_dir`` through the coord-aware read resolver (the correct
# surface for STATUS reads such as move-task, which the FR-010 guards pin on the
# coord husk), so this command MUST re-anchor to primary for planning actions —
# exactly as ``check-prerequisites`` does — or an agent authoring at the reported
# dir writes to coord while ``finalize-tasks`` reads an empty primary ``tasks/``.
_PLANNING_AUTHORING_ACTIONS: frozenset[str] = frozenset(
    {
        "specify",
        "plan",
        "tasks",
        "tasks_outline",
        "tasks_packages",
        "tasks_finalize",
    }
)


def _find_feature_directory(
    repo_root: Path,
    cwd: Path,  # noqa: ARG001 -- kept for signature compatibility
    explicit_mission: str | None = None,
) -> Path:
    """Find the mission directory from an explicit mission handle.

    Routes through the single read primitive
    (:func:`specify_cli.missions._read_path_resolver.resolve_mission_read_path`),
    so a ``--mission <mid8>`` handle resolves to the same directory as the full
    slug (F-001/F-003/F-004). There is **no silent fallback** to a
    wrong-but-plausible primary-checkout path: an unresolvable handle raises a
    structured :class:`ActionContextError` (``FEATURE_CONTEXT_UNRESOLVED``) and
    an ambiguous handle raises ``MISSION_AMBIGUOUS_SELECTOR`` (C-CTX-4 / C-009).

    Args:
        repo_root: Repository root path
        cwd: Current working directory (unused — kept for signature compatibility)
        explicit_mission: Mission handle provided explicitly (required)

    Returns:
        Path to mission directory

    Raises:
        ActionContextError: If no handle is provided, the handle is ambiguous, or
            it resolves to no existing mission directory (structured error).
    """
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
        resolve_handle_to_read_path,
    )

    raw_handle = explicit_mission.strip() if explicit_mission else None
    if not raw_handle:
        raise ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "--mission <slug> is required")
    # WP02/FR-002: the single guarded read-side seam (IC-01) collapses the former
    # raw-join → load_meta → resolve_mid8 bootstrap. It performs the primary-meta
    # probe, the sanctioned mid8 cascade, the fail-closed coord gate, and the
    # existence-gated topology routing internally — and adds the missing
    # assert_safe_path_segment guard (FR-004) the hand-rolled block lacked.
    try:
        feature_dir: Path = resolve_handle_to_read_path(
            repo_root,
            raw_handle,
            require_exists=True,
        )
    except MissionSelectorAmbiguous as exc:
        raise ActionContextError(exc.error_code, str(exc)) from exc
    except StatusReadPathNotFound as exc:
        raise ActionContextError(
            "FEATURE_CONTEXT_UNRESOLVED",
            f"Mission not found for handle {raw_handle!r}; checked the coordination worktree and the primary checkout. {exc}",
        ) from exc
    return feature_dir


@app.command(name="resolve")
def resolve_context(
    action: Annotated[
        str,
        typer.Option(
            "--action",
            help=(f"Action to resolve context for ({', '.join(ACTION_NAMES)})"),
        ),
    ],
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug (e.g., '020-my-mission')")] = None,
    wp_id: Annotated[str | None, typer.Option("--wp-id", help="Work package ID (e.g., WP01)")] = None,
    agent: Annotated[str | None, typer.Option("--agent", help="Agent name for exact command rendering")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output results as JSON")] = False,
) -> None:
    """Resolve canonical feature/work-package/action context for prompt execution."""
    try:
        repo_root = locate_project_root()
        if repo_root is None:
            raise ActionContextError(
                "PROJECT_ROOT_UNRESOLVED",
                "Could not locate project root.",
            )

        if action not in ACTION_NAMES:
            raise ActionContextError(
                "INVALID_ACTION",
                f"Invalid action '{action}'. Expected one of: {', '.join(ACTION_NAMES)}.",
            )

        raw_handle = mission.strip() if mission else None
        if not raw_handle:
            raise ActionContextError("MISSING_MISSION", "--mission <slug> is required")
        # Resolve through the mission-resolver directly (not
        # a resolver that prints to stderr and exits on failure) so an
        # unresolvable or ambiguous handle
        # flows through this command's own ``ActionContextError``/``--json``
        # envelope below instead of bypassing it (FR-003/FR-004, #160).
        try:
            operation: MissionOperationContext = resolve_mission_operation_context(
                repo_root,
                raw_handle,
                cwd=Path.cwd(),
            )
        except MissionSurfaceConflictError as exc:
            raise ActionContextError("MISSION_CONTEXT_CONFLICT", str(exc)) from exc

        try:
            mission_resolved = operation.identity if operation.identity is not None else resolve_mission(raw_handle, operation.mission_anchor_root)
        except AmbiguousHandleError as exc:
            raise ActionContextError("MISSION_AMBIGUOUS_SELECTOR", str(exc)) from exc
        except MissionNotFoundError as exc:
            raise ActionContextError("MISSION_NOT_FOUND", str(exc)) from exc
        mission_slug = mission_resolved.mission_slug

        context = resolve_action_context(
            repo_root,
            action=cast(ActionName, action),
            feature=mission_slug,
            wp_id=wp_id,
            agent=agent,
            cwd=Path.cwd(),
            effective_root=operation.mission_anchor_root,
        )

        # #5160 friction 3: re-anchor the reported feature_dir to the PRIMARY
        # partition for planning/authoring actions so this command agrees with
        # ``check-prerequisites`` / ``finalize-tasks`` (which anchor to primary).
        # Uses the SAME primary anchor ``check-prerequisites`` uses; falls back to
        # the resolver's coord-aware dir only when the mission has no primary dir.
        payload = context.to_dict()
        if action in _PLANNING_AUTHORING_ACTIONS:
            from specify_cli.cli.commands.agent.mission_feature_resolution import (
                _primary_anchored_feature_dir,
            )

            primary_feature_dir = _primary_anchored_feature_dir(repo_root, mission_slug)
            if primary_feature_dir is not None:
                payload["feature_dir"] = str(primary_feature_dir)

        # #5206: emit the canonical ``mission_dir`` key alongside the legacy
        # ``feature_dir`` alias so agent-facing prompts (which document
        # ``mission_dir`` as canonical) get a value that matches. Both keys
        # always agree; ``feature_dir`` remains for backward compatibility.
        payload["mission_dir"] = payload["feature_dir"]

        if json_output:
            print(json.dumps({"success": True, **payload}, indent=2))
        else:
            console.print(f"[green]✓[/green] Resolved {action} context")
            console.print(f"  Mission: {context.mission_slug} ({context.detection_method})")
            console.print(f"  Feature dir: {payload['feature_dir']}")
            console.print(f"  Target branch: {context.target_branch}")
            if context.wp_id:
                console.print(f"  Work package: {context.wp_id} ({context.lane})")
            if context.workspace_path:
                console.print(f"  Workspace: {context.workspace_path}")
            for name, command in context.commands.items():
                console.print(f"  {name}: {command}")
    except ActionContextError as exc:
        if json_output:
            print(json.dumps({"success": False, "error_code": exc.code, "error": str(exc)}, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)


# update-context command removed — agent_context.py was deleted in WP10.
# Agent command files are now thin shims generated by shims/generator.py.
