"""Prompt generation for ``spec-kitty next``.

Independent from ``workflow.py``.  Generates prompt text for each action type,
writes it to a temp file, and returns ``(prompt_text, prompt_file_path)``.

WP11 addition: ``_workflow_for``
-----------------------------------------
Slice F WP11 adds a workflow lookup helper. This satisfies the NFR-001
byte-stability contract: missions without ``workflow_id`` in
``meta.json`` always get the ``software-dev-default`` workflow (permanent
default per NEW-2 resolution).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from specify_cli.core.owned_mission import effective_root_kwargs
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.next._internal_runtime.workflow_schema import WorkflowSequence

from charter.activation.context import build_charter_context
from charter.activation.pack_context import CharterPackConfigError
from charter.activation.scope import CharterScopeConflict, CharterScopeNotFound
from charter.activation.scope_router import build_with_scope
from charter.activation.mission_type_profiles import (
    UnknownMissionTypeError,
    resolve_mission_type_context,
)
from charter.activation.resolver import GovernanceResolutionError, resolve_project_governance
from runtime.next._tmp_namespace import prompt_tmp_dir, write_prompt_file
from specify_cli.core.paths import get_feature_target_branch
from specify_cli.runtime.resolver import resolve_command
from specify_cli.review.antipattern_checklist import render_wp_review_antipattern_checklist
from specify_cli.status import read_wp_frontmatter
from specify_cli.workspace.context import resolve_workspace_for_wp


# ---------------------------------------------------------------------------
# Workflow lookup (Slice F WP11, FR-013 / NFR-001)
# ---------------------------------------------------------------------------


def _workflow_for(mission_dir_str: str) -> WorkflowSequence:
    """Return the ``WorkflowSequence`` for *mission_dir_str*.

    Routes through ``runtime_bridge_engine.resolve_workflow_for_mission`` (the
    FR-013 sole home of the ``_internal_runtime`` engine/planner private
    surface) so the resolver logic is co-located with the DAG-based runtime
    engine and not duplicated. Project-authored workflow files are mutable,
    so this helper intentionally performs a fresh load.
    """
    from runtime.next.runtime_bridge_engine import resolve_workflow_for_mission

    return resolve_workflow_for_mission(Path(mission_dir_str))


def build_prompt(
    action: str,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str | None,
    agent: str,
    repo_root: Path,
    mission_type: str,
    effective_root: Path | None = None,
) -> tuple[str, Path]:
    """Build a prompt for the given action.

    Returns ``(prompt_text, prompt_file_path)``.

    For planning actions (specify, plan, tasks, research, accept) the prompt is
    the command template with a feature context header prepended.

    For implement/review actions the prompt includes workspace paths, isolation
    rules, WP content, and completion instructions.
    """
    if action in ("implement", "review") and wp_id:
        prompt_text = _build_wp_prompt(action, feature_dir, mission_slug, wp_id, agent, repo_root, mission_type, **effective_root_kwargs(effective_root))
    else:
        prompt_text = _build_template_prompt(action, feature_dir, mission_slug, agent, effective_root or repo_root, mission_type)

    prompt_file = _write_to_temp(action, wp_id, prompt_text, agent=agent, mission_slug=mission_slug, repo_root=repo_root)
    return prompt_text, prompt_file


def build_decision_prompt(
    question: str,
    options: list[str] | None,
    decision_id: str,
    mission_slug: str,
    agent: str,
    repo_root: Path,
) -> tuple[str, Path]:
    """Build a prompt for a decision_required response.

    Returns ``(prompt_text, prompt_file_path)``.
    """
    lines: list[str] = [
        "=" * 80,
        "DECISION REQUIRED",
        "=" * 80,
        "",
        f"Mission: {mission_slug}",
        f"Agent: {agent}",
        f"Decision ID: {decision_id}",
        "",
        f"Question: {question}",
        "",
    ]

    if options:
        lines.append("Options:")
        for i, opt in enumerate(options, 1):
            lines.append(f"  {i}. {opt}")
        lines.append("")

    lines.append("To answer:")
    lines.append(f'  spec-kitty next --agent {agent} --mission {mission_slug} --answer "<your answer>" --decision-id "{decision_id}"')

    prompt_text = "\n".join(lines)
    prompt_file = _write_to_temp(
        "decision",
        None,
        prompt_text,
        agent=agent,
        mission_slug=mission_slug,
        repo_root=repo_root,
    )
    return prompt_text, prompt_file


def _build_template_prompt(
    action: str,
    feature_dir: Path,
    mission_slug: str,
    agent: str,
    repo_root: Path,
    mission_type: str,
) -> str:
    """Build prompt from a command template file."""
    result = resolve_command(f"{action}.md", repo_root, mission=mission_type)
    template_content = result.path.read_text(encoding="utf-8")

    header = _mission_context_header(mission_slug, feature_dir, agent)
    governance = _governance_context(repo_root, action=action, feature_dir=feature_dir)
    return f"{header}\n\n{governance}\n\n{template_content}"


def _build_wp_prompt(
    action: str,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    agent: str,
    repo_root: Path,
    mission_type: str,
    effective_root: Path | None = None,
) -> str:
    """Build prompt for implement or review actions with WP context."""
    workspace = resolve_workspace_for_wp(repo_root, mission_slug, wp_id, **effective_root_kwargs(effective_root))
    workspace_path = workspace.worktree_path
    wp_files = sorted((feature_dir / "tasks").glob(f"{wp_id}*.md"))
    wp_meta = None
    if wp_files:
        wp_meta, _ = read_wp_frontmatter(wp_files[0])
    subtask_ids = [str(item) for item in (wp_meta.subtasks if wp_meta is not None else []) if isinstance(item, str)]
    subtask_cmd = " ".join(subtask_ids) if subtask_ids else "<subtask-ids>"
    # WP06 (FR-004) — forward the WP frontmatter ``agent_profile`` to the
    # governance resolver so the profile's directive_references and
    # tactic_references are rendered into the prompt the agent will read.
    agent_profile_id = wp_meta.agent_profile if wp_meta is not None else None

    # Read WP file content
    wp_content = _read_wp_content(feature_dir, wp_id)

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"{action.upper()}: {wp_id}")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Agent: {agent}")
    lines.append(f"Mission: {mission_slug}")
    lines.append(f"Mission Type: {mission_type}")
    lines.append(f"Workspace: {workspace_path}")
    if workspace.lane_id:
        shared = ", ".join(workspace.lane_wp_ids or [wp_id])
        lines.append(f"Workspace contract: lane {workspace.lane_id} shared by {shared}")
    else:
        lines.append("Workspace contract: repository root planning workspace")
    lines.append("")
    lines.extend(_mission_type_governance_lines(effective_root or repo_root, feature_dir))
    lines.append(_governance_context(effective_root or repo_root, action=action, feature_dir=feature_dir, profile=agent_profile_id))
    lines.append("Authority references: project glossary `docs/context/`; architecture ADRs `docs/adr/`.")
    lines.append("")

    # WP isolation rules
    lines.append("=" * 78)
    lines.append("  CRITICAL: WORK PACKAGE ISOLATION RULES")
    lines.append("=" * 78)
    lines.append(f"  YOU ARE {'IMPLEMENTING' if action == 'implement' else 'REVIEWING'}: {wp_id}")
    lines.append("")
    lines.append("  DO:")
    lines.append(f"    - Only modify status of {wp_id}")
    lines.append("    - Ignore git commits and status changes from other agents")
    lines.append("")
    lines.append("  DO NOT:")
    lines.append(f"    - Change status of any WP other than {wp_id}")
    lines.append("    - React to or investigate other WPs' status changes")
    lines.append("=" * 78)
    lines.append("")

    # Working directory
    lines.append("WORKING DIRECTORY:")
    lines.append(f"  cd {workspace_path}")
    if not workspace.lane_id:
        lines.append("  # Planning-artifact work for this WP happens in the repository root")
    lines.append("")

    if action == "review":
        review_paths = ""
        if not workspace.lane_id or effective_root is not None:
            if wp_files:
                wp_meta, _ = read_wp_frontmatter(wp_files[0])
                if wp_meta.owned_files:
                    review_pathspecs = list(wp_meta.owned_files)
                    mission_root = f"kitty-specs/{mission_slug}/"
                    if any(path.startswith(mission_root) for path in review_pathspecs):
                        review_pathspecs.extend(
                            [
                                f":(exclude){mission_root}tasks/**",
                                f":(exclude){mission_root}tasks.md",
                                f":(exclude){mission_root}status.events.jsonl",
                                f":(exclude){mission_root}status.json",
                            ]
                        )
                    review_paths = " -- " + " ".join(review_pathspecs)
            claim = subprocess.run(
                [
                    "git",
                    "log",
                    "--format=%H%x00%s",
                    "--",
                    *(str(path) for path in wp_files),
                ],
                cwd=effective_root or repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            review_base = None
            for raw in claim.stdout.splitlines():
                commit_hash, _, subject = raw.partition("\x00")
                if not commit_hash:
                    continue
                if f"Move {wp_id} to in_progress" in subject or f"{wp_id} claimed for implementation" in subject or f"Start {wp_id} implementation" in subject:
                    review_base = commit_hash.strip()
                    break
        lines.append("REVIEW COMMANDS:")
        if workspace.lane_id and effective_root is None:
            review_base = (
                workspace.context.base_branch if workspace.context and workspace.context.base_branch else get_feature_target_branch(repo_root, mission_slug)
            )
            lines.append(f"  git log {review_base}..HEAD --oneline")
            lines.append(f"  git diff {review_base}..HEAD --stat")
        elif review_base is None:
            lines.append("  unavailable: no deterministic implementation claim commit found for this WP")
        else:
            lines.append(f"  git log {review_base}..HEAD --oneline{review_paths}")
            lines.append(f"  git diff {review_base}..HEAD --stat{review_paths}")
        lines.append("")
        lines.append(render_wp_review_antipattern_checklist())
        lines.append("")

    # WP content
    lines.append("=" * 78)
    lines.append("  WORK PACKAGE PROMPT BEGINS")
    lines.append("=" * 78)
    lines.append("")
    lines.append(wp_content)
    lines.append("")
    lines.append("=" * 78)
    lines.append("  WORK PACKAGE PROMPT ENDS")
    lines.append("=" * 78)
    lines.append("")

    # Completion instructions
    lines.append("WHEN DONE:")
    if action == "implement":
        lines.append(f"  spec-kitty agent tasks mark-status {subtask_cmd} --status done --mission {mission_slug}")
        lines.append(f'  spec-kitty agent tasks move-task {wp_id} --to for_review --mission {mission_slug} --note "Ready for review"')
    else:
        lines.append(f'  APPROVE: spec-kitty agent tasks move-task {wp_id} --to approved --mission {mission_slug} --note "Review passed"')
        lines.append("           approved means review-passed; merge will later record done")
        lines.append(f"  REJECT:  spec-kitty agent tasks move-task {wp_id} --to planned --review-feedback-file <feedback-file> --mission {mission_slug}")

    return "\n".join(lines)


def _mission_context_header(mission_slug: str, feature_dir: Path, agent: str) -> str:
    """Build a mission context header for template prompts."""
    lines = [
        "=" * 80,
        f"Mission: {mission_slug}",
        f"Agent: {agent}",
        f"Mission directory: {feature_dir}",
        "=" * 80,
    ]
    return "\n".join(lines)


def _mission_type_governance_lines(repo_root: Path, feature_dir: Path) -> list[str]:
    """Return the mission-type governance lines to splice into a WP prompt.

    Returns an empty list when no payload is rendered.  Wrapping the
    optionality here (instead of in the caller) keeps
    :func:`_build_wp_prompt` under the C901 complexity ceiling.
    """
    payload = _mission_type_governance_payload(repo_root, feature_dir)
    if payload is None:
        return []
    return [payload, ""]


def _mission_type_governance_payload(repo_root: Path, feature_dir: Path) -> str | None:
    """Resolve mission-type-scoped governance for a WP prompt (WP08, FR-011).

    The mission-type resolver (``charter.activation.mission_type_profiles.resolve_mission_type_context``)
    runs FIRST so the documentation / research / plan default selections
    fill any gaps the project + org layers leave empty.  The hard-fail
    contract (:class:`UnknownMissionTypeError`) is intentionally NOT
    swallowed: a mission whose ``meta.json`` declares an unknown
    ``mission_type`` and whose project has no ``selected_*`` overrides
    MUST fail loudly rather than silently routing to
    ``software-dev-default``.

    Real missions write ``meta.json`` at ``finalize-tasks`` time; older
    fixtures that predate WP08 wiring legitimately have no ``meta.json``,
    so we return ``None`` in that case to preserve backward
    compatibility.  Parse / I/O failures also collapse to ``None`` so the
    project + org resolver downstream can still surface its own
    diagnostics.
    """
    if not (feature_dir / "meta.json").exists():
        return None
    try:
        bundle = resolve_mission_type_context(repo_root, feature_dir=feature_dir)
    except UnknownMissionTypeError:
        # FR-011 hard-fail surface: propagate so the operator sees the
        # missing-profile diagnostic instead of a silent fallback.
        raise
    except Exception:
        return None
    text = bundle.governance_text.rstrip()
    return text or None


def _governance_context(
    repo_root: Path,
    action: str | None = None,
    *,
    feature_dir: Path | None = None,
    profile: str | None = None,
) -> str:
    """Render governance context for prompt preamble.

    For bootstrap actions, charter context is injected on first load.
    Falls back to compact governance rendering if charter artifacts are missing.

    When *feature_dir* is supplied, charter resolution is monorepo-aware:
    :func:`charter.activation.scope_router.build_with_scope` resolves the nearest
    enclosing charter for *feature_dir* before building context.  For
    single-project repos (no ``charter_scopes:`` configured) this is a
    pass-through — the resolved scope root equals *repo_root* and the
    output is byte-identical to the previous behaviour (NFR-001 binding).
    When *feature_dir* is ``None``, the call falls back to
    :func:`charter.activation.context.build_charter_context` with *repo_root* directly,
    preserving backward compat with callers that do not yet supply the arg.

    When *profile* is supplied (typically the WP frontmatter
    ``agent_profile`` field forwarded by :func:`_build_wp_prompt`), it is
    passed through so the resolver renders the profile's directive- and
    tactic-references into the prompt the agent will read.  ``profile=None``
    preserves the prior byte-identical output (NFR-005 contract from WP03).

    HIGH-1 (post-merge remediation cycle 1): routes through
    :func:`charter.activation.scope_router.build_with_scope` when *feature_dir* is
    provided so monorepo operators get the nearest-enclosing charter, not
    always the root-project charter.
    """
    if action:
        try:
            if feature_dir is not None:
                # Monorepo-aware path: resolve the nearest enclosing charter
                # for feature_dir, then build the context from that scope root.
                context = build_with_scope(
                    repo_root,
                    feature_dir,
                    action=action,
                    mark_loaded=True,
                    profile=profile,
                )
            else:
                # Single-project / legacy path: call build_charter_context
                # directly with repo_root (byte-identical to pre-HIGH-1 for
                # callers that do not supply feature_dir).
                context = build_charter_context(
                    repo_root,
                    action=action,
                    mark_loaded=True,
                    profile=profile,
                )
            if context.mode != "missing":
                return context.text
        except (CharterScopeConflict, CharterScopeNotFound):
            # Scope routing failures mean the operator-authored monorepo
            # governance config does not cover this feature path. Falling back
            # to root governance would silently cross a trust boundary.
            raise
        except CharterPackConfigError:
            # WP07/T040 (FR-012 error half / NFR-006): activation-resolution
            # failures are fail-closed. A malformed charter pack / dangling
            # 'charter:' pointer MUST surface to the operator, never degrade
            # into a silent legacy render. Mirrors the CharterScope* re-raise
            # immediately above.
            raise
        except Exception:
            # Non-fatal: fall back to compact governance rendering.
            pass

    return _legacy_governance_context(repo_root)


def _legacy_governance_context(repo_root: Path) -> str:
    """Render compact governance context via resolver."""
    try:
        resolution = resolve_project_governance(repo_root)
    except GovernanceResolutionError as exc:
        return f"Governance: unresolved ({exc})"
    except Exception as exc:
        return f"Governance: unavailable ({exc})"

    paradigms = ", ".join(resolution.paradigms) if resolution.paradigms else "(none)"
    directives = ", ".join(resolution.directives) if resolution.directives else "(none)"
    tools = ", ".join(resolution.tools) if resolution.tools else "(none)"

    lines = [
        "Governance:",
        f"  - Template set: {resolution.template_set}",
        f"  - Paradigms: {paradigms}",
        f"  - Directives: {directives}",
        f"  - Tools: {tools}",
    ]
    if resolution.diagnostics:
        lines.append(f"  - Diagnostics: {' | '.join(resolution.diagnostics)}")
    return "\n".join(lines)


def _read_wp_content(feature_dir: Path, wp_id: str) -> str:
    """Read WP file content from the tasks directory."""
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return f"[WP file not found: tasks directory missing at {tasks_dir}]"

    # Find matching WP file
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        if wp_file.stem.startswith(wp_id):
            try:
                return wp_file.read_text(encoding="utf-8")
            except OSError:
                return f"[Error reading {wp_file}]"

    return f"[WP file not found for {wp_id} in {tasks_dir}]"


def _write_to_temp(
    action: str,
    wp_id: str | None,
    content: str,
    *,
    agent: str = "unknown",
    mission_slug: str = "unknown",
    repo_root: Path,
) -> Path:
    """Write prompt content to a temp file.

    Filenames include agent and feature to avoid collisions when multiple
    agents or features run concurrently. The file is rooted under the
    shared, per-repo, sweepable namespace (WP02 / FR-003) rather than the
    flat ``tempfile.gettempdir()`` root, so WP01's session reaper can find
    and remove it.
    """
    wp_suffix = f"-{wp_id}" if wp_id else ""
    filename = f"spec-kitty-next-{agent}-{mission_slug}-{action}{wp_suffix}.md"
    prompt_path = prompt_tmp_dir(repo_root) / filename
    write_prompt_file(prompt_path, content)
    return prompt_path
