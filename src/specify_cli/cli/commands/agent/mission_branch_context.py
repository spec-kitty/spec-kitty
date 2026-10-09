"""Branch-context command family for ``agent mission`` (#2056 WP05, Seam B).

Hosts the ``branch-context`` command plus the deterministic branch-resolution
helpers it shares with the planning lifecycle commands
(``setup-plan``/``finalize-tasks``): the branch-contract injector, the
primary-branch recommender, the local/remote ref probe, the start-branch
switcher, the planning-branch resolver, and the branch-context banner.

Several of these helpers (``_inject_branch_contract``, ``_show_branch_context``,
``_resolve_planning_branch``, ``_resolve_feature_target_branch``,
``_get_current_branch``, ``_resolve_primary_branch_for_recommendation``) are
*shared* with the not-yet-relocated ``setup_plan``/``finalize_tasks``/lifecycle
commands in ``mission.py``. They are defined here and re-imported into
``mission.py`` as module globals so every historical ``mission.<name>`` patch
target keeps resolving (WP09 finalizes the comprehensive shim sweep), and the
in-``mission`` callers see ``mission.<name>`` monkeypatches (they reference the
re-imported globals).

The ``branch_context`` command is defined here as a plain callable; ``mission``
registers it on its Typer ``app``. So the CLI surface is unchanged (WP01 golden
harness is the regression net). To honor the established
``mission._resolve_primary_branch_for_recommendation`` monkeypatch target, the
command resolves that helper through the ``mission`` module at call time.

One-way leaf (INV-8): imports lower layers + sibling Seam C/D leaves only, never
back into ``mission`` at module scope (the ``mission`` lookup inside the command
is a deferred, call-time import to preserve the patch seam without an import
cycle). Behavior is preserved byte-for-byte from the pre-decomposition
``mission.py``.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Annotated

from specify_cli.cli.console import console
import typer

from specify_cli.core.git_ops import get_current_branch
from specify_cli.core.paths import (
    MissionMetaReadError,
    get_main_repo_root,
    get_status_read_root,
    load_meta_fail_closed,
    read_target_branch_from_meta,
)
from specify_cli.missions._resolve_planning_branch import (
    load_mission_target_branch,
)

from specify_cli.cli.commands.agent.mission_parsing import (
    _emit_json,
    _utc_now_iso,
)


PROJECT_ROOT_NOT_FOUND = "Could not locate project root"
PROJECT_ROOT_NOT_FOUND_MESSAGE = f"{PROJECT_ROOT_NOT_FOUND}. Run from within spec-kitty repository."


def _resolve_feature_target_branch(feature_dir: Path, repo_root: Path) -> str:
    """Resolve canonical target/base branch from metadata with branch fallback.

    FR-008 / #2139: delegates the meta.json field read to the single
    read_target_branch_from_meta authority instead of re-embedding a local
    ``""`` default; the current-branch fallback chain below is this call
    site's own deliberate degradation and is unrelated to the meta.json
    field-read contract, so it is preserved as-is.
    """
    target = read_target_branch_from_meta(feature_dir)
    if target:
        # str(...) narrows the cross-module Any mypy sees under this repo's
        # `follow_imports = "skip"` override for specify_cli.* (pyproject.toml);
        # target is already a str here (read_target_branch_from_meta's real
        # contract), mirroring the same cast in core/paths.py:723.
        return str(target)
    return get_current_branch(repo_root) or "main"


def read_minted_mission_branch(feature_dir: Path) -> str | None:
    """The protected-target ``mission_branch`` recorded in ``meta.json``, else ``None``.

    #5100 FR-007: a protected single_branch mission's planning and write
    checkout is the minted ``meta.mission_branch``; ``meta.target_branch``
    stays the protected merge target. Callers that ask "is HEAD on the branch
    this mission expects?" must prefer this over the merge target, or every
    such mission reports a spurious mismatch. An unreadable ``meta.json`` or an
    absent/blank field yields ``None`` (the caller keeps its merge-target
    operand), never an error.
    """
    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError:
        return None
    minted = (meta or {}).get("mission_branch")
    return minted if isinstance(minted, str) and minted else None


def _inject_branch_contract(
    payload: dict[str, object],
    *,
    target_branch: str,
    current_branch: str | None = None,
    primary_branch: str | None = None,
    match_target_branch: str | None = None,
    expected_checkout_branch: str | None = None,
) -> dict[str, object]:
    """Attach deterministic branch/runtime aliases for templates and agents.

    When ``primary_branch`` is supplied the contract is additionally enriched
    with a primary-branch recommendation payload (issue #765):
    ``primary_branch``, ``current_is_primary``, ``recommended_strategy`` and a
    human-readable ``reason``. Callers that do not resolve the primary branch
    omit it, and the emitted payload is byte-identical to the legacy contract
    so existing snapshots and consumers are unaffected.

    ``match_target_branch`` (FR-006 / #3124) decouples the honesty of the
    ``branch_matches_target`` verdict from the *display* ``target_branch``. When
    supplied, the match is computed against it (``resolved_current_branch ==
    match_target_branch``) instead of the primary-anchored ``target_branch`` used
    for every display/planning field. ``setup-plan`` passes the mission's
    ``meta.json`` target here while feeding ``current_branch`` the invoking
    checkout's HEAD, so a lane on a divergent branch reports honest disagreement
    without disturbing the deliberate primary-anchored target resolution. Callers
    that omit it (e.g. ``branch-context``) keep the legacy match byte-for-byte.

    ``expected_checkout_branch`` names the branch the operator's checkout is
    *supposed* to be on when that differs from the merge ``target_branch`` --
    the protected-target mission branch minted at create time (#5100 FR-007),
    which is checked out while ``target_branch`` stays the protected merge
    target. It feeds ``branch_context.expected_checkout_branch`` and, unless
    ``match_target_branch`` overrides it, the ``branch_matches_target`` verdict,
    so the contract never describes the protected target as the checkout.
    """
    enriched = dict(payload)
    raw_runtime_vars = enriched.get("runtime_vars", {})
    runtime_vars = dict(raw_runtime_vars) if isinstance(raw_runtime_vars, dict) else {}
    now_utc_iso = str(runtime_vars.get("now_utc_iso", _utc_now_iso()))
    resolved_current_branch = str(current_branch or target_branch).strip() or target_branch
    planning_base_branch = target_branch
    merge_target_branch = target_branch
    expected_checkout = expected_checkout_branch or target_branch
    match_reference = match_target_branch if match_target_branch is not None else expected_checkout
    branch_matches_target = resolved_current_branch == match_reference
    branch_strategy_summary = (
        f"Current branch at workflow start: {resolved_current_branch}. "
        f"Planning/base branch for this mission: {planning_base_branch}. "
        f"Completed changes must merge into {merge_target_branch}."
    )
    runtime_vars["now_utc_iso"] = now_utc_iso
    runtime_vars["current_branch"] = resolved_current_branch
    runtime_vars["target_branch"] = target_branch
    runtime_vars["base_branch"] = target_branch
    runtime_vars["planning_base_branch"] = planning_base_branch
    runtime_vars["merge_target_branch"] = merge_target_branch
    runtime_vars["branch_matches_target"] = branch_matches_target
    runtime_vars["branch_strategy_summary"] = branch_strategy_summary

    branch_context_block = {
        "current_branch": resolved_current_branch,
        "target_branch": target_branch,
        "base_branch": target_branch,
        "planning_base_branch": planning_base_branch,
        "merge_target_branch": merge_target_branch,
        "expected_checkout_branch": expected_checkout,
        "matches_target": branch_matches_target,
        "branch_strategy_summary": branch_strategy_summary,
    }

    enriched["current_branch"] = resolved_current_branch
    enriched["CURRENT_BRANCH"] = resolved_current_branch
    enriched["target_branch"] = target_branch
    enriched["base_branch"] = target_branch
    enriched["TARGET_BRANCH"] = target_branch
    enriched["BASE_BRANCH"] = target_branch
    enriched["planning_base_branch"] = planning_base_branch
    enriched["PLANNING_BASE_BRANCH"] = planning_base_branch
    enriched["merge_target_branch"] = merge_target_branch
    enriched["MERGE_TARGET_BRANCH"] = merge_target_branch
    enriched["EXPECTED_TARGET_BRANCH"] = target_branch
    enriched["EXPECTED_BASE_BRANCH"] = target_branch
    enriched["branch_matches_target"] = branch_matches_target
    enriched["BRANCH_MATCHES_TARGET"] = branch_matches_target
    enriched["branch_strategy_summary"] = branch_strategy_summary
    enriched["runtime_vars"] = runtime_vars
    enriched["NOW_UTC_ISO"] = now_utc_iso
    enriched["branch_context"] = branch_context_block

    # Primary-branch recommendation (issue #765). Only emitted when the caller
    # resolved the repo's primary branch, so payloads from callers that do not
    # pass ``primary_branch`` remain byte-identical to the legacy contract.
    if primary_branch:
        current_is_primary = resolved_current_branch == primary_branch
        if current_is_primary:
            recommended_strategy = "feature-branch"
            recommendation_reason = (
                f"You are on the primary branch '{primary_branch}'. PR-bound "
                "missions should start on a dedicated feature branch so planning "
                f"artifacts are not committed to '{primary_branch}'."
            )
        else:
            recommended_strategy = "stay"
            recommendation_reason = f"You are on '{resolved_current_branch}', which is not the primary branch '{primary_branch}'; staying on it is fine."
        # ``branch_context_block`` is the same object stored in ``enriched`` above,
        # so updating it here also updates ``enriched['branch_context']``.
        branch_context_block["primary_branch"] = primary_branch
        branch_context_block["current_is_primary"] = current_is_primary
        branch_context_block["recommended_strategy"] = recommended_strategy
        branch_context_block["reason"] = recommendation_reason
        runtime_vars["primary_branch"] = primary_branch
        runtime_vars["current_is_primary"] = current_is_primary
        runtime_vars["recommended_strategy"] = recommended_strategy
        enriched["primary_branch"] = primary_branch
        enriched["PRIMARY_BRANCH"] = primary_branch
        enriched["current_is_primary"] = current_is_primary
        enriched["CURRENT_IS_PRIMARY"] = current_is_primary
        enriched["recommended_strategy"] = recommended_strategy
        enriched["RECOMMENDED_STRATEGY"] = recommended_strategy
        enriched["branch_recommendation_reason"] = recommendation_reason

    return enriched


def _git_local_or_remote_branch_exists(repo_root: Path, branch_name: str) -> bool:
    """Return true when a local or origin branch ref exists."""
    for ref in (f"refs/heads/{branch_name}", f"refs/remotes/origin/{branch_name}"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return True
    return False


def _resolve_primary_branch_for_recommendation(
    repo_root: Path,
    current_branch: str | None,
) -> str:
    """Resolve the primary branch for recommendations without feature-branch bias.

    FR-007 (mission ``primary-merge-vocabulary``): folded onto the canonical
    :func:`specify_cli.core.git_ops.resolve_primary_branch` via its ``bias``
    flag — this is now a thin, named delegating wrapper rather than a parallel
    re-implementation of the origin/HEAD cascade. ``bias=False`` preserves the
    deliberate no-feature-bias behavior (a ticket branch is never mistaken for
    the primary branch). The name is retained so the historical
    ``mission._resolve_primary_branch_for_recommendation`` monkeypatch target
    and re-export stay intact.
    """
    from specify_cli.core.git_ops import resolve_primary_branch

    return str(resolve_primary_branch(repo_root, current_branch=current_branch, bias=False))


def _switch_to_start_branch(repo_root: Path | None, start_branch: str) -> str:
    """Create or switch to a mission start branch before scaffold writes."""
    branch = start_branch.strip()
    if not branch:
        raise ValueError("--start-branch requires a non-empty branch name.")
    if repo_root is None:
        raise ValueError(PROJECT_ROOT_NOT_FOUND_MESSAGE)

    check_ref = subprocess.run(
        ["git", "check-ref-format", "--branch", branch],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=5,
    )
    if check_ref.returncode != 0:
        detail = check_ref.stderr.strip() or check_ref.stdout.strip() or "invalid branch name"
        raise ValueError(f"Invalid --start-branch '{branch}': {detail}")

    current_branch = get_current_branch(repo_root)
    if current_branch == branch:
        return branch

    branch_exists = _git_local_or_remote_branch_exists(repo_root, branch)
    switch_cmd = ["git", "switch", branch] if branch_exists else ["git", "switch", "-c", branch]
    switch = subprocess.run(
        switch_cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if switch.returncode != 0:
        detail = switch.stderr.strip() or switch.stdout.strip() or "unknown git error"
        raise RuntimeError(f"Failed to switch to --start-branch '{branch}': {detail}")
    return branch


def _show_branch_context(
    repo_root: Path,
    mission_slug: str,
    json_output: bool = False,
) -> tuple[Path, str]:
    """Show branch context banner. Returns (main_repo_root, current_branch).

    Uses the canonical resolve_target_branch() from core.git_ops.
    Shows a consistent, visible banner at the start of every command.
    """
    from specify_cli.core.git_ops import resolve_target_branch

    # Route ``get_main_repo_root`` / ``get_current_branch`` through the ``mission``
    # module so the historical ``mission.<name>`` patch seams (exercised by
    # callers still living in ``mission.py``) keep working after relocation.
    from specify_cli.cli.commands.agent import mission as _mission

    main_repo_root = _mission.get_main_repo_root(repo_root)
    current_branch = _mission.get_current_branch(main_repo_root)
    if current_branch is None:
        raise RuntimeError("Detached HEAD — checkout a branch before continuing")

    resolution = resolve_target_branch(mission_slug, main_repo_root, current_branch, respect_current=True)

    if not json_output:
        if not resolution.should_notify:
            console.print(f"[bold cyan]Branch:[/bold cyan] {current_branch} (target for this mission)")
        else:
            console.print(f"[bold yellow]Branch:[/bold yellow] on '{resolution.current}', mission targets '{resolution.target}'")

    return main_repo_root, resolution.current


def _resolve_planning_branch(
    repo_root: Path,
    feature_dir: Path,
    *,
    target_branch_override: str | None = None,
) -> str:
    """Resolve the canonical merge target branch for a mission directory.

    WP07 / FR-012 / SC-04 (issue #1348 "prep-branch leak" fix):

    Pre-WP07 this helper returned ``git branch --show-current`` via
    :func:`_show_branch_context`. When an operator ran ``finalize-tasks``
    from a ``prep/...`` branch (a documented workaround for the legacy
    main-pin guard) the prep branch name got baked into WP frontmatter
    as ``merge_target_branch``. The prep branch was deleted later and
    lane allocation crashed because its parent ref was gone.

    Post-WP07 the resolver reads the canonical target from
    ``meta.json`` (the value ``mission create`` persisted when the
    operator was definitively on the right base). The current checkout
    branch is intentionally **never** consulted. The
    ``target_branch_override`` parameter exists for legacy missions that
    pre-date branch-context persistence and for explicit operator
    override via the ``--target-branch`` CLI flag.

    Args:
        repo_root: Repository root (unused now; kept for callers that
            patch the symbol — preserving the API shape avoids a
            cross-WP rename storm).
        feature_dir: Path to the mission's ``kitty-specs/<slug>/`` dir.
        target_branch_override: Explicit override (e.g. CLI ``--target-branch``).
            Wins over ``meta.json`` when truthy. Whitespace-only values
            are treated as absent.

    Returns:
        The canonical merge target branch name.

    Raises:
        PlanningBranchResolutionFailed: ``meta.json`` is missing /
            corrupt and no override is supplied.
    """
    del repo_root  # No longer used; kept in signature for API stability.
    if target_branch_override is not None and target_branch_override.strip():
        return target_branch_override.strip()
    resolved: str = load_mission_target_branch(feature_dir)
    return resolved


def _get_current_branch(repo_root: Path) -> str:
    """Get current git branch name.

    Args:
        repo_root: Repository root directory

    Returns:
        Current branch name, or detected primary branch if not in a git repo
    """
    from specify_cli.core.git_ops import resolve_primary_branch

    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else resolve_primary_branch(repo_root)


def branch_context(
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
    target_branch: Annotated[
        str | None,
        typer.Option(
            "--target-branch",
            help="Planned landing branch (defaults to current branch)",
        ),
    ] = None,
) -> None:
    """Return deterministic branch contract for planning-stage prompts."""
    # Deferred import keeps this leaf module free of an import cycle while still
    # honoring the historical ``mission.<name>`` monkeypatch targets (tests patch
    # ``locate_project_root`` / ``is_git_repo`` / ``get_current_branch`` /
    # ``_resolve_primary_branch_for_recommendation`` on the ``mission`` module).
    from specify_cli.cli.commands.agent import mission as _mission

    try:
        repo_root = _mission.locate_project_root()
        if repo_root is None:
            error_msg = PROJECT_ROOT_NOT_FOUND_MESSAGE
            if json_output:
                _emit_json({"error": error_msg})
            else:
                console.print(f"[red]Error:[/red] {error_msg}")
            raise typer.Exit(1)

        if not _mission.is_git_repo(repo_root):
            error_msg = "Not in a git repository. Branch context requires git."
            if json_output:
                _emit_json({"error": error_msg})
            else:
                console.print(f"[red]Error:[/red] {error_msg}")
            raise typer.Exit(1)

        # ``locate_project_root`` deliberately re-anchors linked worktrees to
        # the primary checkout for shared metadata reads. Branch identity is
        # invocation-owned state, but only within the repository being queried.
        caller_root = get_status_read_root(Path.cwd())
        if get_main_repo_root(caller_root).resolve() != get_main_repo_root(repo_root).resolve():
            caller_root = repo_root
        current_branch = _mission.get_current_branch(caller_root)
        if not current_branch or current_branch == "HEAD":
            error_msg = "Must be on a branch to resolve branch context (detached HEAD detected)."
            if json_output:
                _emit_json({"error": error_msg})
            else:
                console.print(f"[red]Error:[/red] {error_msg}")
            raise typer.Exit(1)

        primary_branch = _mission._resolve_primary_branch_for_recommendation(repo_root, current_branch)
        resolved_target_branch = str(target_branch).strip() if target_branch and str(target_branch).strip() else current_branch
        payload: dict[str, object] = {
            "result": "success",
            "repo_root": str(repo_root.resolve()),
            "target_branch_source": "cli_arg" if target_branch else "current_branch",
            "next_step": ("Use this deterministic branch contract during specify/plan prompts; do not rediscover branch state inside the LLM."),
        }
        enriched = _inject_branch_contract(
            payload,
            target_branch=resolved_target_branch,
            current_branch=current_branch,
            primary_branch=primary_branch,
        )

        if json_output:
            _emit_json(enriched)
        else:
            console.print(f"[bold cyan]Current branch:[/bold cyan] {enriched['current_branch']}")
            console.print(f"[bold cyan]Planning/base branch:[/bold cyan] {enriched['planning_base_branch']}")
            console.print(f"[bold cyan]Merge target:[/bold cyan] {enriched['merge_target_branch']}")
            console.print(f"[bold cyan]Matches target:[/bold cyan] {enriched['branch_matches_target']}")
            console.print(f"[bold cyan]Primary branch:[/bold cyan] {enriched['primary_branch']}")
            console.print(f"[bold cyan]On primary branch:[/bold cyan] {enriched['current_is_primary']}")
            console.print(f"[bold cyan]Recommended strategy:[/bold cyan] {enriched['recommended_strategy']}")
            console.print(f"[dim]{enriched['branch_recommendation_reason']}[/dim]")

    except typer.Exit:
        raise
    except Exception as e:
        if json_output:
            _emit_json({"error": str(e)})
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
