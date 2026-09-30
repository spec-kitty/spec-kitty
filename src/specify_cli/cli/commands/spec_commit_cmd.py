"""Mission-aware ``spec-commit`` entrypoint (FR-001/002/003).

Closes the #1619 P0 specify-phase deadlock: unlike the generic ``safe-commit``
command (which is mission-blind), this command derives the mission slug from a
``kitty-specs/<slug>/`` path argument or ``--mission``, resolves the
:class:`~specify_cli.git.protection_policy.ProtectionPolicy` at the command
boundary, and routes the commit through
:func:`~specify_cli.coordination.commit_router.commit_for_mission`.

SPEC is a PRIMARY/planning artifact, so it lands on the mission's primary
target branch for every topology and NEVER routes through coordination
(write-surface-coherence WP02/WP03). On a PROTECTED primary the commit is
therefore refused — not silently transited to a coord worktree — with the two
real remedies: create/check out a non-protected feature branch, or set the
``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` operator hatch (#2739 B01).

Design basis: WP02 / IC-02 / ADR ``2026-06-21-1``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer
from specify_cli.cli.console import console

from mission_runtime import ActionContextError, MissionArtifactKind, OwnedCheckout
from specify_cli.cli.commands._owned_checkout import OwnedCheckoutOption, resolve_owned_or_refuse
from specify_cli.coordination.commit_router import CommitRouterResult, commit_for_mission
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES, require_unstaged_index
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.task_utils import find_repo_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_repo_root() -> Path:
    """Return the primary repo root (follows worktree links to main checkout)."""
    root: Path = find_repo_root()
    return root


def _derive_mission_slug(path_arg: str | None, mission_opt: str | None) -> str | None:
    """Derive the mission slug from a ``kitty-specs/<slug>/`` path or ``--mission``."""
    if mission_opt:
        return mission_opt.strip()
    if path_arg:
        # Accept either the slug directly or a ``kitty-specs/<slug>`` path.
        p = Path(path_arg)
        # If the path contains a ``kitty-specs`` component, take the part after it.
        parts = p.parts
        try:
            idx = next(i for i, part in enumerate(parts) if part == KITTY_SPECS_DIR)
            # slug is the component immediately after ``kitty-specs``
            if idx + 1 < len(parts):
                return parts[idx + 1]
        except StopIteration:
            pass
        # Otherwise treat the final component as the slug.
        return p.name or None
    return None


def _payload(
    *,
    success: bool,
    committed: bool = False,
    placement_ref: str | None = None,
    commit_hash: str | None = None,
    error: str | None = None,
    diagnostic: str | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "result": "success" if success else "error",
        "success": success,
        "committed": committed,
    }
    if placement_ref is not None:
        result["placement_ref"] = placement_ref
    if commit_hash is not None:
        result["commit_hash"] = commit_hash
    if error is not None:
        result["error"] = error
    if diagnostic is not None:
        result["diagnostic"] = diagnostic
    if reason is not None:
        result["reason"] = reason
    return result


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def _resolve_commit_inputs(
    repo_root: Path,
    files: list[Path],
    mission_slug: str | None,
    owned: OwnedCheckout | None,
) -> tuple[str | None, list[Path]]:
    """Resolve and validate the complete commit batch before any mutation.

    An owned run reads its slug and every path off the validated fact:
    ``owned.files`` (whose ``OwnedCheckoutPathRefused`` maps to
    ``OWNED_MISSION_PATH_REFUSED`` at the CLI edge) runs first, then
    ``require_unstaged_index``, so the whole batch is refused before staging.
    """
    if owned is not None:
        abs_files = owned.files(files)
        require_unstaged_index(owned)
        return owned.mission_slug, abs_files
    abs_files = [(repo_root / path).resolve() if not path.is_absolute() else path.resolve() for path in files]
    return mission_slug, abs_files


def _refusal_envelope(code: str, message: str) -> dict[str, object]:
    """This command's failure payload plus the owned refusal's ``error_code``."""
    return {**_payload(success=False, error=message), "error_code": code}


def _mission_slug_from_args(files: list[Path], mission: str | None) -> str | None:
    """The mission handle this invocation names: ``--mission``, else the first file's ``kitty-specs/<slug>/``."""
    return _derive_mission_slug(str(files[0]) if files else None, mission)


def _reject_directory_args(abs_files: list[Path], json_output: bool) -> None:
    """Fail fast on directory arguments with a clear, files-only message.

    #2739 B11: git stages a directory's files, but the safe-commit backstop
    compares literally against the requested path (the directory), so a directory
    arg would otherwise abort with the opaque "staging area contains unexpected
    paths" error. Reject early with actionable guidance instead.
    """
    directory_args = [f for f in abs_files if f.is_dir()]
    if not directory_args:
        return
    listed = ", ".join(str(d) for d in directory_args)
    _err(
        json_output,
        "spec-commit takes individual file paths, not directories. "
        f"Received director{'ies' if len(directory_args) > 1 else 'y'}: "
        f"{listed}. Pass the specific files to commit instead.",
    )
    raise typer.Exit(1)


def spec_commit_command(
    files: list[Path] = typer.Argument(
        ...,
        help=("Spec artifacts to commit (absolute or relative paths). Must belong to the mission resolved via --mission or the kitty-specs/<slug>/ path."),
    ),
    message: str = typer.Option(..., "--message", "-m", help="Commit message."),
    mission: str | None = typer.Option(
        None,
        "--mission",
        help=("Mission slug (e.g. '001-my-mission'). When omitted, the slug is derived from the first file argument's kitty-specs/<slug>/ path."),
    ),
    target_branch: str | None = typer.Option(
        None,
        "--target-branch",
        help=("Short primary branch name used for the post-commit ff-advance (WP09 / FR-010). Optional."),
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON."),
    owned_checkout: OwnedCheckoutOption = None,
) -> None:
    """Commit spec artifacts to the mission's resolved placement.

    SPEC is a primary/planning artifact: it lands on the mission's primary target
    branch for every topology. On an unprotected or flattened primary the commit
    is direct. On a PROTECTED primary the commit is refused (there is no fallback
    surface); recover by either creating/checking out a non-protected feature
    branch ('spec-kitty agent mission create --start-branch <feature-branch>') or
    setting SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1 to commit on the current
    branch.

    Pass individual FILES, not directories.
    """
    try:
        repo_root = _current_repo_root()
        derived_slug = _mission_slug_from_args(files, mission)
        # Validate --owned-checkout (or adopt the caller's checkout) exactly once. A
        # refusal renders through emit_owned_refusal with this command's failure
        # envelope; the raw option value goes straight into the shared helper.
        owned = resolve_owned_or_refuse(
            repo_root,
            owned_checkout,
            derived_slug,
            cwd=Path.cwd(),
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            json_output=json_output,
            envelope=_refusal_envelope,
            target_override=target_branch,
        )
        mission_slug, abs_files = _resolve_commit_inputs(repo_root, files, derived_slug, owned)
        _reject_directory_args(abs_files, json_output)
        if not mission_slug:
            _err(
                json_output,
                "Cannot resolve mission slug. Pass --mission <slug> or provide a kitty-specs/<slug>/ path as the first argument.",
            )
            raise typer.Exit(1)

        # Boundary-resolve the protection policy (FR-007, NFR-003).
        policy = ProtectionPolicy.resolve(repo_root)

        result: CommitRouterResult = commit_for_mission(
            repo_root=repo_root,
            mission_slug=mission_slug,
            files=tuple(abs_files),
            message=message,
            policy=policy,
            # The operator-facing ``spec-commit`` entry point commits the SPEC
            # planning artifact (write-surface-coherence WP02 / T007). SPEC is a
            # primary kind, so it lands on the primary target branch for every
            # topology — no planning→coord transit.
            kind=MissionArtifactKind.SPEC,
            target_branch=target_branch,
            owned=owned,
        )

        if result.status == "committed":
            payload = _payload(
                success=True,
                committed=True,
                placement_ref=result.placement_ref,
                commit_hash=result.commit_hash,
            )
            if json_output:
                print(json.dumps(payload, indent=2))
            else:
                console.print(f"[green]✓[/green] Spec artifact(s) committed to {result.placement_ref}")
                if result.commit_hash:
                    console.print(f"[dim]Commit: {result.commit_hash[:7]}[/dim]")

        elif result.status == "unchanged":
            # #2739 B03: a committed:false success must carry a machine-readable
            # reason so a caller can tell "nothing to do" from "silently wrong".
            payload = _payload(
                success=True,
                committed=False,
                placement_ref=result.placement_ref,
                reason=result.reason or "no_op",
            )
            if json_output:
                print(json.dumps(payload, indent=2))
            else:
                console.print("[dim]Spec artifact(s) unchanged, no commit needed[/dim]")

        elif result.status == "no_op_wrong_surface":
            # T008: actionable refusal — the router's own diagnostic already
            # names the concrete remedy (e.g. move the mission onto a
            # non-protected feature branch); no coordination-worktree retry
            # hint is added here since that transit no longer exists.
            actionable = result.diagnostic or "Artifact absent at resolved placement."
            payload = _payload(
                success=False,
                error=actionable,
                placement_ref=result.placement_ref,
                diagnostic=result.diagnostic,
            )
            if json_output:
                print(json.dumps(payload, indent=2))
            else:
                console.print(f"[red]Error:[/red] {actionable}")
            raise typer.Exit(1)

        else:  # "error"
            payload = _payload(
                success=False,
                error=result.diagnostic or "Commit failed.",
                placement_ref=result.placement_ref,
            )
            if json_output:
                print(json.dumps(payload, indent=2))
            else:
                console.print(f"[red]Error:[/red] {result.diagnostic or 'Commit failed.'}")
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except ActionContextError as exc:
        payload = {**_payload(success=False, error=str(exc)), "error_code": exc.code}
        if json_output:
            print(json.dumps(payload))
        else:
            console.print(f"[red]{exc.code}:[/red] {exc}")
        raise typer.Exit(1) from exc
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        payload = _payload(success=False, error=str(exc))
        if json_output:
            print(json.dumps(payload, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


def _err(json_output: bool, message: str) -> None:
    if json_output:
        print(json.dumps(_payload(success=False, error=message), indent=2))
    else:
        console.print(f"[red]Error:[/red] {message}")
