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

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout
    from runtime.next._internal_runtime.workflow_schema import WorkflowSequence
    from specify_cli.status.wp_metadata import WPMetadata
    from specify_cli.workspace.context import ResolvedWorkspace

from pydantic import ValidationError
from charter.activation.context import build_charter_context
from charter.activation.pack_context import CharterPackConfigError
from charter.activation.scope import CharterScopeConflict, CharterScopeNotFound
from charter.activation.scope_router import build_with_scope
from charter.activation.mission_type_profiles import (
    UnknownMissionTypeError,
    resolve_mission_type_context,
)
from charter.activation.resolver import GovernanceResolutionError, resolve_project_governance
from mission_runtime import ActionContextError, ClaimCommitUnresolved, OwnedRefusalCode, claim_commit_for_wp
from runtime.next._tmp_namespace import prompt_tmp_dir, write_prompt_file
from specify_cli.core.paths import get_feature_target_branch
from specify_cli.runtime.resolver import resolve_command
from specify_cli.review.antipattern_checklist import render_wp_review_antipattern_checklist
from specify_cli.status import FrontmatterError, read_authored_wp_frontmatter
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
    *,
    owned: OwnedCheckout | None = None,
) -> tuple[str, Path]:
    """Build a prompt for the given action.

    Returns ``(prompt_text, prompt_file_path)``.

    For planning actions (specify, plan, tasks, research, accept) the prompt is
    the command template with a mission context header prepended.

    For implement/review actions the prompt includes workspace paths, isolation
    rules, WP content, and completion instructions.

    ``owned`` (owned-checkout-lifecycle-authority WP12, FR-008/FR-009/FR-010):
    when set, the WP file, workspace, governance, mission-type context and the
    prompt's own temp file all come from the owned checkout the fact validated,
    never from the repository root checkout ``repo_root`` names; a review whose
    base cannot be proven raises ``ActionContextError`` carrying
    ``OWNED_REVIEW_BASE_UNAVAILABLE``.
    """
    governance_root = owned.owned_root if owned is not None else repo_root
    if action in ("implement", "review") and wp_id:
        prompt_text = _build_wp_prompt(action, feature_dir, mission_slug, wp_id, agent, repo_root, mission_type, owned=owned)
    else:
        prompt_text = _build_template_prompt(action, feature_dir, mission_slug, agent, governance_root, mission_type)

    prompt_file = _write_to_temp(action, wp_id, prompt_text, agent=agent, mission_slug=mission_slug, repo_root=governance_root)
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
    *,
    owned: OwnedCheckout | None = None,
) -> str:
    """Build prompt for implement or review actions with WP context."""
    governance_root = owned.owned_root if owned is not None else repo_root
    wp_file, wp_meta, wp_content = read_wp_task(_task_board_dir(repo_root, mission_slug, owned) / "tasks", wp_id, mission_slug)

    workspace = resolve_workspace_for_wp(repo_root, mission_slug, wp_id, owned=owned)
    workspace_path = workspace.worktree_path
    subtask_ids = [str(item) for item in wp_meta.subtasks if isinstance(item, str)]
    # WP06 (FR-004) — forward the WP frontmatter ``agent_profile`` to the
    # governance resolver so the profile's directive_references and
    # tactic_references are rendered into the prompt the agent will read.
    agent_profile_id = wp_meta.agent_profile

    lines: list[str] = []
    lines.extend(_workspace_header_lines(action, wp_id, agent, mission_slug, mission_type, workspace, owned))
    lines.extend(_mission_type_governance_lines(governance_root, feature_dir))
    lines.append(_governance_context(governance_root, action=action, feature_dir=feature_dir, profile=agent_profile_id))
    lines.append("Authority references: project glossary `docs/context/`; architecture ADRs `docs/adr/`.")
    lines.append("")
    lines.extend(_isolation_rule_lines(wp_id, action))

    # Working directory
    lines.append("WORKING DIRECTORY:")
    lines.append(f"  cd {workspace_path}")
    if owned is not None:
        lines.append("  # Work for this WP happens in the owned checkout")
    elif not workspace.lane_id:
        lines.append("  # Planning-artifact work for this WP happens in the repository root")
    lines.append("")

    if action == "review":
        lines.extend(_review_command_lines(repo_root, feature_dir, mission_slug, wp_id, wp_meta, workspace, owned))

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

    lines.extend(_completion_lines(action, wp_id, mission_slug, subtask_ids, owned))
    return "\n".join(lines)


def _workspace_header_lines(
    action: str,
    wp_id: str,
    agent: str,
    mission_slug: str,
    mission_type: str,
    workspace: ResolvedWorkspace,
    owned: OwnedCheckout | None,
) -> list[str]:
    """The banner plus the agent / mission / workspace identification block."""
    lines = [
        "=" * 80,
        f"{action.upper()}: {wp_id}",
        "=" * 80,
        "",
        f"Agent: {agent}",
        f"Mission: {mission_slug}",
        f"Mission Type: {mission_type}",
        f"Workspace: {workspace.worktree_path}",
    ]
    if workspace.lane_id:
        shared = ", ".join(workspace.lane_wp_ids or [wp_id])
        lines.append(f"Workspace contract: lane {workspace.lane_id} shared by {shared}")
    elif owned is not None:
        lines.append("Workspace contract: owned checkout")
    else:
        lines.append("Workspace contract: repository root planning workspace")
    lines.append("")
    return lines


def _isolation_rule_lines(wp_id: str, action: str) -> list[str]:
    """The WORK PACKAGE ISOLATION RULES box."""
    return [
        "=" * 78,
        "  CRITICAL: WORK PACKAGE ISOLATION RULES",
        "=" * 78,
        f"  YOU ARE {'IMPLEMENTING' if action == 'implement' else 'REVIEWING'}: {wp_id}",
        "",
        "  DO:",
        f"    - Only modify status of {wp_id}",
        "    - Ignore git commits and status changes from other agents",
        "",
        "  DO NOT:",
        f"    - Change status of any WP other than {wp_id}",
        "    - React to or investigate other WPs' status changes",
        "=" * 78,
        "",
    ]


def _review_pathspecs(mission_slug: str, wp_meta: WPMetadata) -> list[str]:
    """The WP's ``owned_files`` as git pathspecs (mission-dir bookkeeping excluded)."""
    pathspecs = list(wp_meta.owned_files)
    mission_root = f"kitty-specs/{mission_slug}/"
    if any(path.startswith(mission_root) for path in pathspecs):
        pathspecs.extend(
            [
                f":(exclude){mission_root}tasks/**",
                f":(exclude){mission_root}tasks.md",
                f":(exclude){mission_root}status.events.jsonl",
                f":(exclude){mission_root}status.json",
            ]
        )
    return pathspecs


def _review_base_unavailable(wp_id: str, why: str) -> ActionContextError:
    """The typed refusal for an owned review whose base cannot be proven (US3-AS5)."""
    return ActionContextError(
        OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE.value,
        f"cannot build a scoped review diff for {wp_id} in the owned checkout: {why}",
    )


def _claim_commit_or_none(status_dir: Path, wp_id: str) -> str | None:
    """The WP's claim commit, or ``None`` when it cannot be proven (fail closed)."""
    try:
        return claim_commit_for_wp(status_dir, wp_id)
    except ClaimCommitUnresolved:
        return None


def _lane_review_base(repo_root: Path, mission_slug: str, workspace: ResolvedWorkspace, owned: OwnedCheckout | None) -> str:
    """Base ref of a lane workspace review: the lane's own base, else the mission's target branch.

    An owned mission takes the target from the validated fact, never from the
    repository root checkout's ``meta.json``.
    """
    lane_base: str | None = workspace.context.base_branch if workspace.context else None
    if lane_base:
        return lane_base
    if owned is not None:
        return owned.write_branch
    return get_feature_target_branch(repo_root, mission_slug)


def _review_command_lines(
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    wp_meta: WPMetadata,
    workspace: ResolvedWorkspace,
    owned: OwnedCheckout | None,
) -> list[str]:
    """REVIEW COMMANDS block plus the anti-pattern checklist (review action only).

    Three cases: a lane workspace diffs against its lane base; an owned checkout
    and the repository root checkout both diff against the WP's claim commit
    (:func:`mission_runtime.claim_commit_for_wp`, FR-025). The owned case scopes
    the diff to the WP's ``owned_files`` and refuses (typed error) rather than
    ever emitting an unscoped whole-checkout diff (FR-010).
    """
    lines = ["REVIEW COMMANDS:"]
    if workspace.lane_id:
        base = _lane_review_base(repo_root, mission_slug, workspace, owned)
        lines.append(f"  git log {base}..HEAD --oneline")
        lines.append(f"  git diff {base}..HEAD --stat")
    else:
        pathspecs = _review_pathspecs(mission_slug, wp_meta)
        if owned is not None and not pathspecs:
            raise _review_base_unavailable(wp_id, "the work package declares no owned_files")
        claim = _claim_commit_or_none(owned.mission_dir if owned is not None else feature_dir, wp_id)
        if claim is None and owned is not None:
            raise _review_base_unavailable(wp_id, "no single claim commit was found on HEAD")
        review_paths = " -- " + " ".join(pathspecs) if pathspecs else ""
        if claim is None:
            lines.append("  unavailable: no deterministic implementation claim commit found for this WP")
        else:
            lines.append(f"  git log {claim}..HEAD --oneline{review_paths}")
            lines.append(f"  git diff {claim}..HEAD --stat{review_paths}")
    lines.append("")
    lines.append(render_wp_review_antipattern_checklist())
    lines.append("")
    return lines


def _completion_lines(action: str, wp_id: str, mission_slug: str, subtask_ids: list[str], owned: OwnedCheckout | None = None) -> list[str]:
    """The WHEN DONE completion-command block.

    An owned mission's completion commands carry ``--owned-checkout <P>``: that
    is the supported owned lifecycle path, and a bare command would resolve the
    repository root checkout instead.
    """
    suffix = f" --owned-checkout {owned.owned_root}" if owned is not None else ""
    lines = ["WHEN DONE:"]
    if action == "implement":
        if subtask_ids:
            subtask_cmd = " ".join(subtask_ids)
            lines.append(f"  spec-kitty agent tasks mark-status {subtask_cmd} --status done --mission {mission_slug}{suffix}")
        else:
            lines.append("  No subtask completion command is needed; this work package declares no subtasks.")
        lines.append(f'  spec-kitty agent tasks move-task {wp_id} --to for_review --mission {mission_slug}{suffix} --note "Ready for review"')
    else:
        lines.append(f'  APPROVE: spec-kitty agent tasks move-task {wp_id} --to approved --mission {mission_slug}{suffix} --note "Review passed"')
        lines.append("           approved means review-passed; merge will later record done")
        lines.append(f"  REJECT:  spec-kitty agent tasks move-task {wp_id} --to planned --review-feedback-file <feedback-file> --mission {mission_slug}{suffix}")
    return lines


def _task_board_dir(repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> Path:
    """Where the WP task files live: the fact's mission directory when owned.

    The WP task board is a PRIMARY-partition artifact, which for an owned
    mission is the owned checkout itself, so the owned arm reads the fact
    directly and consults no resolver.
    """
    if owned is not None:
        return owned.mission_dir
    from mission_runtime import MissionArtifactKind, mission_context_for

    return mission_context_for(repo_root, mission_slug).artifact(MissionArtifactKind.WORK_PACKAGE_TASK).read_dir


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


def read_wp_task(tasks_dir: Path, wp_id: str, mission_slug: str) -> tuple[Path, WPMetadata, str]:
    """Load the exact WP file, authored metadata, and body from its task surface."""
    expected_file = tasks_dir / f"{wp_id}.md"
    recovery = (
        f"Restore or regenerate the primary task for {wp_id} at {expected_file} "
        f"(or a titled {wp_id} file under {tasks_dir}), then rerun `spec-kitty next --mission {mission_slug}`. "
        f"If {wp_id} was removed on purpose, move it to canceled instead: "
        f"`spec-kitty agent tasks move-task {wp_id} --to canceled --mission {mission_slug}`."
    )
    if not tasks_dir.is_dir():
        raise FileNotFoundError(f"Canonical WORK_PACKAGE_TASK directory for {wp_id} is missing at {tasks_dir}; expected {expected_file}. {recovery}")

    wp_file = next(
        (path for path in sorted(tasks_dir.glob("WP*.md")) if path.stem == wp_id or path.stem.startswith(f"{wp_id}-")),
        None,
    )
    if wp_file is None:
        raise FileNotFoundError(f"Canonical WORK_PACKAGE_TASK file for {wp_id} is missing at {expected_file}. {recovery}")

    try:
        wp_meta, _ = read_authored_wp_frontmatter(wp_file)
        if wp_meta.work_package_id != wp_id:
            raise ValueError(
                f"Canonical WORK_PACKAGE_TASK file {wp_file} declares work_package_id "
                f"{wp_meta.work_package_id}; expected {wp_id}, found {wp_meta.work_package_id}. {recovery}"
            )
        wp_content = wp_file.read_text(encoding="utf-8")
    except (FrontmatterError, OSError, UnicodeError, ValidationError) as exc:
        raise ValueError(f"Could not read canonical WORK_PACKAGE_TASK file {wp_file}: {exc}. {recovery}") from exc
    return wp_file, wp_meta, wp_content


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
