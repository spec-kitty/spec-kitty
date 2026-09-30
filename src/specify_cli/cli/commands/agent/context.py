"""Agent context management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NoReturn, cast

import typer
from specify_cli.cli.console import console
from typing_extensions import Annotated

from specify_cli.cli.commands._owned_checkout import (
    OwnedCheckoutOption,
    echo_stale_copy_warning,
    emit_owned_refusal,
    resolve_owned_or_adopt,
    stale_copy_payload,
    success_false_envelope,
)
from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,
    MissionNotFoundError,
    resolve_mission,
)
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES
from specify_cli.core.paths import locate_project_root
from mission_runtime import (
    ACTION_NAMES,
    ActionName,
    ActionContextError,
    MissionExecutionContext,
    OwnedCheckout,
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


def _validate_resolve_inputs(action: str, mission: str | None) -> tuple[Path, str]:
    """Resolve the project root and required ``--mission`` handle, or refuse.

    Campsite extraction (T042, behaviour-preserving): covers the original
    ``:126-141``.
    """
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
    return repo_root, raw_handle


def _resolve_context_mission(repo_root: Path, raw_handle: str) -> str:
    """Resolve ``raw_handle`` against the repository root for a **non-owned** run.

    WP08/T040: replaces the deleted ``operation_context`` probe. An owned run
    never reaches this function -- its mission identity comes straight from
    the validated :class:`mission_runtime.OwnedCheckout` fact instead (see
    ``resolve_context`` below).
    """
    try:
        mission_resolved = resolve_mission(raw_handle, repo_root)
    except AmbiguousHandleError as exc:
        raise ActionContextError("MISSION_AMBIGUOUS_SELECTOR", str(exc)) from exc
    except MissionNotFoundError as exc:
        raise ActionContextError("MISSION_NOT_FOUND", str(exc)) from exc
    # ``resolve_mission``'s return resolves as ``Any`` under the narrow-file
    # ``specify_cli.*`` follow_imports=skip override (pyproject.toml); str()
    # pins this function's own declared ``-> str`` without touching that
    # cross-cutting mypy config.
    return str(mission_resolved.mission_slug)


def _reanchor_planning_feature_dir(
    payload: dict[str, object],
    action: str,
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> None:
    """Re-anchor ``payload["feature_dir"]`` to the repository root checkout's PRIMARY-partition dir, for planning/authoring actions.

    Campsite extraction (T042) of the original ``:180-193``, with one WP08/T040
    addition: for an **owned** run the re-anchor target is ``owned.mission_dir``
    directly, never ``_primary_anchored_feature_dir`` -- that helper reads the
    repository-root checkout's own copy of the mission, which is exactly the
    stale-copy path this WP fixes (O4). ``owned=None`` preserves today's
    non-owned behaviour unchanged.
    """
    if action not in _PLANNING_AUTHORING_ACTIONS:
        return
    if owned is not None:
        payload["feature_dir"] = str(owned.mission_dir)
        return
    from specify_cli.cli.commands.agent.mission_feature_resolution import (
        _primary_anchored_feature_dir,
    )

    primary_feature_dir = _primary_anchored_feature_dir(repo_root, mission_slug)
    if primary_feature_dir is not None:
        payload["feature_dir"] = str(primary_feature_dir)


def _render_context_human(context: MissionExecutionContext, payload: dict[str, object]) -> None:
    """Print the human-mode summary lines on stdout.

    Campsite extraction (T042, behaviour-preserving): covers the original
    ``:198-207``.
    """
    console.print(f"[green]✓[/green] Resolved {context.action} context")
    console.print(f"  Mission: {context.mission_slug} ({context.detection_method})")
    console.print(f"  Feature dir: {payload['feature_dir']}")
    console.print(f"  Target branch: {context.target_branch}")
    if context.wp_id:
        console.print(f"  Work package: {context.wp_id} ({context.lane})")
    if context.workspace_path:
        console.print(f"  Workspace: {context.workspace_path}")
    for name, command in context.commands.items():
        console.print(f"  {name}: {command}")


def _emit_context_error(exc: ActionContextError, json_output: bool) -> NoReturn:
    """Render an ``ActionContextError`` through the command's own envelope and exit(1).

    Campsite extraction (T042) of the original ``:208-213``. Deliberately
    NOT routed through :func:`emit_owned_refusal`: this command's non-owned
    resolution path (``_validate_resolve_inputs``, ``_resolve_context_mission``,
    the WP-bearing ``resolve_action_context`` call) raises action-context
    errors that are not part of the owned-checkout registry
    (``MISSION_NOT_FOUND``, ``MISSION_AMBIGUOUS_SELECTOR``, ``INVALID_ACTION``,
    ``PROJECT_ROOT_UNRESOLVED``, ``MISSING_MISSION``), and
    :func:`emit_owned_refusal`'s registry assertion would reject every one of
    them. The envelope SHAPE still lives in one place
    (:func:`success_false_envelope`, the same builder the owned path uses);
    only the registry validation is owned-refusal-specific and lives solely
    on the :func:`resolve_owned_or_adopt` call site below.
    """
    payload = success_false_envelope(exc.code, str(exc))
    if json_output:
        print(json.dumps(payload, indent=2))
    else:
        console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(1)


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
    owned_checkout: OwnedCheckoutOption = None,
) -> None:
    """Resolve canonical feature/work-package/action context for prompt execution."""
    try:
        repo_root, raw_handle = _validate_resolve_inputs(action, mission)

        # WP08/FR-006/FR-021: the ONE ownership validation for this invocation
        # (NFR-002) -- an explicit ``--owned-checkout`` or a validated flagless
        # adoption. ``owned`` is threaded down instead of ever falling back to
        # a bare Path. A refusal here is always a registered
        # owned-checkout code (a claim primitive, an ``OWNED_*`` code,
        # ``WORKTREE_REGISTRY_UNAVAILABLE``, ``FEATURE_CONTEXT_UNRESOLVED`` or
        # ``MISSION_CONTEXT_CONFLICT``), so it is the one call site routed
        # through the registry-validating :func:`emit_owned_refusal`.
        try:
            owned = resolve_owned_or_adopt(
                repo_root,
                owned_checkout,
                raw_handle,
                cwd=Path.cwd(),
                allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            )
        except ActionContextError as exc:
            emit_owned_refusal(exc, json_output=json_output, envelope=success_false_envelope)

        if owned is not None:
            mission_slug = owned.mission_slug
            context = resolve_action_context(
                repo_root,
                action=cast(ActionName, action),
                feature=mission_slug,
                wp_id=wp_id,
                agent=agent,
                cwd=Path.cwd(),
                owned=owned,
            )
        else:
            mission_slug = _resolve_context_mission(repo_root, raw_handle)
            context = resolve_action_context(
                repo_root,
                action=cast(ActionName, action),
                feature=mission_slug,
                wp_id=wp_id,
                agent=agent,
                cwd=Path.cwd(),
            )

        # #5160 friction 3: re-anchor the reported feature_dir to the PRIMARY
        # partition for planning/authoring actions so this command agrees with
        # ``check-prerequisites`` / ``finalize-tasks`` (which anchor to primary).
        payload = context.to_dict()
        _reanchor_planning_feature_dir(payload, action, repo_root, mission_slug, owned=owned)

        # #5206: emit the canonical ``mission_dir`` key alongside the legacy
        # ``feature_dir`` alias so agent-facing prompts (which document
        # ``mission_dir`` as canonical) get a value that matches. Both keys
        # always agree; ``feature_dir`` remains for backward compatibility.
        payload["mission_dir"] = payload["feature_dir"]

        # WP08/FR-007: additive-only stale-copy channel, emitted ONLY for an
        # owned run (explicit or adopted); the non-owned payload above is
        # untouched, so it stays byte-identical to the pre-WP08 shape.
        if owned is not None:
            payload.update(stale_copy_payload(owned, warnings=cast("list[str]", payload["warnings"])))

        if json_output:
            print(json.dumps({"success": True, **payload}, indent=2))
        else:
            _render_context_human(context, payload)
            if owned is not None:
                echo_stale_copy_warning(owned)
    except ActionContextError as exc:
        _emit_context_error(exc, json_output)


# update-context command removed — agent_context.py was deleted in WP10.
# Agent command files are now thin shims generated by shims/generator.py.
