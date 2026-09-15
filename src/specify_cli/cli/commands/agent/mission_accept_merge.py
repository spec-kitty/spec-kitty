"""accept / merge command family for ``agent mission`` (#2056 WP06).

Hosts the two thin delegator commands ``accept_feature`` / ``merge_feature`` and
the worktree finders ``_find_latest_feature_worktree`` / ``_find_feature_worktree``
they share. ``accept``/``merge`` are deliberately thin wrappers over the
top-level ``accept``/``merge`` commands with agent-specific defaults; the
``top_level_accept`` / ``top_level_merge`` imports stay **function-local** so this
leaf does not pull the full accept/merge graph at module top level (A-3).

The commands are defined here as plain callables; ``mission`` registers them on
its Typer ``app`` and re-exports the names (tests import ``accept_feature`` /
``merge_feature`` from ``mission``). The relocated bodies resolve test-patched
cross-cutting symbols (``locate_project_root`` / ``resolve_mission_handle`` /
``get_feature_target_branch`` / ``_get_current_branch`` / ``_find_feature_worktree``)
through the ``mission`` module at call time so the historical ``mission.<name>``
patch seams keep working without an import cycle.

One-way leaf (INV-8): imports lower layers only at module scope; the ``mission``
lookup inside the commands is a deferred, call-time import. Behavior is preserved
byte-for-byte from the pre-decomposition ``mission.py``; the WP01 golden harness
is the regression net.
"""

from __future__ import annotations

import json
import os
from kernel._safe_re import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated, cast

from specify_cli.cli.console import console
import typer

from specify_cli.merge.config import MergeStrategy
from specify_cli.workspace.context import resolve_feature_worktree


PROJECT_ROOT_NOT_FOUND = "Could not locate project root"


def _find_latest_feature_worktree(repo_root: Path) -> Path | None:
    """Find the latest feature worktree by number.

    Migrated from find_latest_feature_worktree() in common.sh

    Args:
        repo_root: Repository root directory

    Returns:
        Path to latest worktree, or None if no worktrees exist
    """
    worktrees_dir = repo_root / ".worktrees"
    if not worktrees_dir.exists():
        return None

    latest_num = 0
    latest_worktree = None

    for worktree_dir in worktrees_dir.iterdir():
        if not worktree_dir.is_dir():
            continue

        # Match pattern: 001-feature-name
        match = re.match(r"^(\d{3})-", worktree_dir.name)
        if match:
            num = int(match.group(1))
            if num > latest_num:
                latest_num = num
                latest_worktree = worktree_dir

    return latest_worktree


def _find_feature_worktree(repo_root: Path, mission_slug: str) -> Path | None:
    """Find a deterministic worktree for a feature slug."""
    return resolve_feature_worktree(repo_root, mission_slug)


def accept_feature(
    feature: Annotated[str | None, typer.Option("--mission", help="Mission slug (required in multi-mission repos)")] = None,
    mode: Annotated[str, typer.Option("--mode", help="Acceptance mode: auto, pr, local, checklist")] = "auto",
    json_output: Annotated[bool, typer.Option("--json", help="Output results as JSON for agent parsing")] = False,
    lenient: Annotated[bool, typer.Option("--lenient", help="Skip strict metadata validation")] = False,
    no_commit: Annotated[bool, typer.Option("--no-commit", help="Skip auto-commit (report only)")] = False,
    diagnose: Annotated[bool, typer.Option("--diagnose", help="Diagnose acceptance blockers without mutation")] = False,
    merge_commit: Annotated[
        str | None,
        typer.Option(
            "--merge-commit",
            metavar="SHA",
            help="With --mode pr: record this PR merge commit as the mission's post-merge review baseline (#4231).",
        ),
    ] = None,
    target_branch: Annotated[
        str | None,
        typer.Option(
            "--target-branch",
            help="With --merge-commit: the branch the PR merged into. Defaults to the mission's declared target_branch, else the repository's primary branch.",
        ),
    ] = None,
    attest_first_landing: Annotated[
        bool,
        typer.Option(
            "--attest-first-landing-commit",
            help=("With --merge-commit: attest the supplied commit's first parent is the pre-landing target tip (#4231). Required for every landing shape."),
        ),
    ] = False,
) -> None:
    """Perform mission acceptance workflow.

    This command:
    1. Validates all tasks are in 'done' lane
    2. Runs acceptance checks from checklist files
    3. Creates acceptance report
    4. Marks mission as ready for merge

    Wrapper for top-level accept command with agent-specific defaults.

    Examples:
        # Run acceptance workflow
        spec-kitty agent mission accept --mission 077-my-mission

        # With JSON output for agents
        spec-kitty agent mission accept --mission 077-my-mission --json

        # Lenient mode (skip strict validation)
        spec-kitty agent mission accept --mission 077-my-mission --lenient --json
    """
    # A-3: resolve the heavyweight accept delegator via the ``mission`` module so
    # this leaf never imports the accept graph at module scope, while preserving
    # the ``mission.top_level_accept`` patch seam (tests patch it there).
    from specify_cli.cli.commands.agent import mission as _mission

    # Delegate to top-level accept command
    try:
        # Call top-level accept with mapped parameters
        _mission.top_level_accept(
            mission=feature,
            mode=mode,
            actor=None,  # Agent commands don't use --actor
            test=[],  # Agent commands don't use --test
            json_output=json_output,
            lenient=lenient,
            no_commit=no_commit,
            diagnose=diagnose,
            allow_fail=False,  # Agent commands use strict validation
            merge_commit=merge_commit,  # #4231: PR-merge evidence passthrough
            target_branch=target_branch,  # #4231: PR base branch passthrough
            attest_first_landing=attest_first_landing,  # #4231: anchor attestation passthrough
        )
    except typer.Exit:
        # Propagate typer.Exit cleanly
        raise
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e), "success": False}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None


def _maybe_auto_retry_in_worktree(
    repo_root: Path,
    resolved_feature: str | None,
    target: str,
    strategy: str,
    *,
    push: bool,
    dry_run: bool,
    keep_branch: bool | None,
    keep_worktree: bool | None,
) -> None:
    """Re-run merge inside the deterministic mission worktree, then exit.

    No-op (returns) when already on a mission branch or auto-retry is suppressed
    by the recursion-guard env var. When the current branch is not a mission
    branch, requires ``--mission`` to pick a worktree deterministically, then
    re-invokes the CLI there and exits with its return code. Routes
    ``_get_current_branch`` / ``_find_feature_worktree`` through the ``mission``
    module to preserve the historical patch seams.
    """
    if os.environ.get("SPEC_KITTY_AUTORETRY"):
        return

    from specify_cli.cli.commands.agent import mission as _mission

    current_branch = _mission._get_current_branch(repo_root)
    if re.match(r"^\d{3}-", current_branch):
        return

    if not resolved_feature:
        raise RuntimeError(f"Not on mission branch ({current_branch}). Auto-retry requires --mission to choose a deterministic worktree.")

    retry_worktree = _mission._find_feature_worktree(repo_root, resolved_feature)
    if not retry_worktree:
        raise RuntimeError(f"Could not find worktree for mission {resolved_feature} under {repo_root / '.worktrees'}.")

    console.print(f"[yellow]Auto-retry:[/yellow] Not on mission branch ({current_branch}). Running merge in {retry_worktree.name}")

    # Set env var to prevent infinite recursion
    env = os.environ.copy()
    env["SPEC_KITTY_AUTORETRY"] = "1"

    # Re-run command in worktree; pass canonical slug so retry is unambiguous.
    retry_cmd = ["spec-kitty", "agent", "mission", "merge"]
    retry_cmd.extend(["--mission", resolved_feature])
    retry_cmd.extend(["--target", target, "--strategy", strategy])
    if push:
        retry_cmd.append("--push")
    if dry_run:
        retry_cmd.append("--dry-run")
    if keep_branch is True:
        retry_cmd.append("--keep-branch")
    elif keep_branch is False:
        retry_cmd.append("--delete-branch")
    if keep_worktree is True:
        retry_cmd.append("--keep-worktree")
    elif keep_worktree is False:
        retry_cmd.append("--remove-worktree")
    retry_cmd.append("--no-auto-retry")

    result = subprocess.run(
        retry_cmd,
        cwd=retry_worktree,
        env=env,
    )
    sys.exit(result.returncode)


def _delegate_to_top_level_merge(
    resolved_feature: str | None,
    target: str,
    strategy: str,
    *,
    push: bool,
    dry_run: bool,
    keep_branch: bool | None,
    keep_worktree: bool | None,
) -> None:
    """Delegate to the top-level merge command with agent parameter mapping.

    Unset agent flags remain ``None`` so the top-level retention gate can
    require an explicit choice. Explicit keep choices invert to the top-level
    delete/remove flags.
    """
    from specify_cli.cli.commands.agent import mission as _mission

    try:
        _mission.top_level_merge(
            strategy=MergeStrategy(strategy),
            delete_branch=None if keep_branch is None else not keep_branch,
            remove_worktree=None if keep_worktree is None else not keep_worktree,
            push=push,
            target_branch=target,  # Note: parameter name differs
            dry_run=dry_run,
            json_output=False,
            mission=(resolved_feature or ""),
            resume=False,  # Agent commands don't support resume
            abort=False,  # Agent commands don't support abort
            context_token=cast(str, None),
            keep_workspace=False,
        )
    except typer.Exit:
        # Propagate typer.Exit cleanly
        raise
    except Exception as e:
        print(json.dumps({"error": str(e), "success": False}))
        raise typer.Exit(1) from None


def merge_feature(
    feature: Annotated[str | None, typer.Option("--mission", help="Mission slug (required in multi-mission repos)")] = None,
    target: Annotated[str | None, typer.Option("--target", help="Target branch for the branch-integration step (required in multi-mission repos)")] = None,
    strategy: Annotated[str, typer.Option("--strategy", help="Strategy for the branch-integration step: merge, squash, rebase")] = "merge",
    push: Annotated[bool, typer.Option("--push", help="Publish to origin after the local merge (the operator publish step)")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show actions without executing")] = False,
    keep_branch: Annotated[
        bool | None,
        typer.Option(
            "--keep-branch/--delete-branch",
            help="Keep or delete mission branch after merge (default: retain-gate choice)",
        ),
    ] = None,
    keep_worktree: Annotated[
        bool | None,
        typer.Option(
            "--keep-worktree/--remove-worktree",
            help="Keep or remove worktree after merge (default: retain-gate choice)",
        ),
    ] = None,
    auto_retry: Annotated[
        bool, typer.Option("--auto-retry/--no-auto-retry", help="Auto-navigate to a deterministic mission worktree if in the wrong location")
    ] = False,
) -> None:
    """Merge mission branch into target branch.

    This command:
    1. Validates the mission is accepted
    2. Merges the mission branch into target (usually 'main')
    3. Cleans up worktree
    4. Deletes the mission branch

    Auto-retry logic:
    If current branch doesn't match feature pattern and auto-retry is enabled,
    it retries only when --mission is provided so worktree selection is deterministic.

    Delegates to existing tasks_cli.py merge implementation.

    Examples:
        # Merge into main branch
        spec-kitty agent mission merge --mission 077-my-mission

        # Merge into specific branch with push
        spec-kitty agent mission merge --mission 077-my-mission --target develop --push

        # Dry-run mode
        spec-kitty agent mission merge --mission 077-my-mission --dry-run

        # Keep worktree and branch after merge
        spec-kitty agent mission merge --mission 077-my-mission --keep-worktree --keep-branch
    """
    # The ``mission`` lookup honors the historical ``mission.<name>`` patch seams
    # (``locate_project_root`` / ``resolve_mission_handle`` / ``get_feature_target_branch``).
    from specify_cli.cli.commands.agent import mission as _mission

    try:
        repo_root = _mission.locate_project_root()
        if repo_root is None:
            error = PROJECT_ROOT_NOT_FOUND
            print(json.dumps({"error": error, "success": False}))
            sys.exit(1)

        # Resolve the mission handle to a canonical slug before delegating.
        resolved_feature = feature
        if feature:
            try:
                _resolved = _mission.resolve_mission_handle(feature, repo_root)
            except (SystemExit, typer.Exit):
                # Preserve legacy wrapper behavior in tests and programmatic
                # callers that pass a raw slug/worktree hint without a real
                # mission directory. The delegated merge flow still performs
                # its own resolution when operating against a real repo.
                _resolved = None
            if _resolved is not None:
                resolved_feature = _resolved.mission_slug

        # Resolve target branch dynamically if not specified
        if target is None:
            if resolved_feature:
                target = _mission.get_feature_target_branch(repo_root, resolved_feature)
            else:
                from specify_cli.core.git_ops import resolve_primary_branch

                target = resolve_primary_branch(repo_root)

        if auto_retry:
            _maybe_auto_retry_in_worktree(
                repo_root,
                resolved_feature,
                target,
                strategy,
                push=push,
                dry_run=dry_run,
                keep_branch=keep_branch,
                keep_worktree=keep_worktree,
            )

        _delegate_to_top_level_merge(
            resolved_feature,
            target,
            strategy,
            push=push,
            dry_run=dry_run,
            keep_branch=keep_branch,
            keep_worktree=keep_worktree,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print(json.dumps({"error": str(e), "success": False}))
        raise typer.Exit(1) from None
