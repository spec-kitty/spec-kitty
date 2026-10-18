"""CLI command group: spec-kitty profile-invocation.

``spec-kitty dispatch`` opens standalone Ops. This module owns the companion
``profile-invocation complete`` close path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import typer
from rich.markup import escape
from specify_cli.cli.console import console

from specify_cli.cli.commands.dispatch import _build_executor
from specify_cli.invocation.errors import (
    AlreadyClosedError,
    ContextUnavailableError,  # noqa: F401 — re-exported for callers/tests
    InvalidModeForEvidenceError,
)
from specify_cli.invocation.executor import OpCommitOutcome
from specify_cli.invocation.writer import EVENTS_DIR, normalise_ref
from specify_cli.task_utils import find_repo_root

# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------



def _get_repo_root() -> Path:
    """Resolve the repository root using the project's canonical utility."""
    result: Path = find_repo_root()
    return result


# The opener lives at the top level (``spec-kitty dispatch``) while the closer
# lives here, so operators who find the closer first assume a sibling
# ``profile-invocation dispatch`` exists (#2984). The pointer goes in the Typer
# *epilog*, never in ``help=``: the shell-completion manifest schema is
# ``{help, hidden, deprecated, commands}``, so an epilog carries the guidance
# without regenerating ``_completion_manifest.json``.
_OPENER_EPILOG = (
    'Open:  spec-kitty dispatch "<request>"\n\n'
    "Close: spec-kitty profile-invocation complete --invocation-id <id> --outcome <outcome>"
)

profile_invocation_app = typer.Typer(
    name="profile-invocation",
    help="Manage invocation records.",
    epilog=_OPENER_EPILOG,
)


def _handle_complete_already_closed(
    invocation_id: str,
    *,
    json_output: bool,
) -> None:
    msg: dict[str, str] = {"error": "already_closed", "invocation_id": invocation_id}
    if json_output:
        typer.echo(json.dumps(msg), err=True)
    else:
        console.print(f"[red]Error:[/red] Invocation {invocation_id} is already closed.")
    raise typer.Exit(1) from None


def _print_uncommitted_note(outcome: OpCommitOutcome, invocation_id: str) -> None:
    """Say where the Op record went when its auto-commit did not happen (#6410).

    A skip is deliberate and quiet; a refusal is a warning. Neither advises
    overriding the protected-branch guard. The record stays on disk as an
    uncommitted file.
    """
    record = f"{EVENTS_DIR}/{invocation_id}.jsonl"
    if outcome.skipped:
        console.print(f"[dim]Op record kept on disk at {record}, not committed: {escape(outcome.skipped)}.[/dim]")
        return
    console.print(
        f"[yellow]Warning:[/yellow] Op record auto-commit was refused "
        f"({escape(outcome.refusal or 'unknown refusal')}). The completed event is on disk "
        f"at {record} but uncommitted. Commit the Op record yourself on the branch "
        "where it belongs."
    )


def _render_complete_response(
    *,
    invocation_id: str,
    outcome: str | None,
    evidence_ref: str | None,
    artifact: list[str] | None,
    commit: str | None,
    repo_root: Path,
    json_output: bool,
) -> None:
    if json_output:
        response = {
            "result": "success",
            "invocation_id": invocation_id,
            "outcome": outcome,
            "evidence_ref": evidence_ref,
            "artifact_links": [normalise_ref(a, repo_root) for a in (artifact or [])],
            "commit_link": commit,
        }
        typer.echo(json.dumps(response, indent=2))
        return

    console.print(f"[green]✓[/green] Invocation [bold]{invocation_id}[/bold] closed.")
    if outcome:
        console.print(f"  Outcome: {outcome}")
    if artifact:
        for item in artifact:
            console.print(f"  Artifact: {normalise_ref(item, repo_root)}")
    if commit:
        console.print(f"  Commit: {commit}")


@profile_invocation_app.command("complete")
def complete_invocation(
    invocation_id: str = typer.Option(..., "--invocation-id", "-i", help="Invocation ULID to close"),
    outcome: str = typer.Option(..., "--outcome", help="done | failed | abandoned"),
    evidence: str | None = typer.Option(None, "--evidence", help="Path to a UTF-8 text evidence file (Tier 2 promotion); checked before the Op closes"),
    artifact: list[str] = typer.Option(
        None,
        "--artifact",
        help="Path (repo-relative or absolute) or URL of an artifact produced by this invocation. Repeatable.",
    ),
    commit: str | None = typer.Option(
        None,
        "--commit",
        help="Git commit SHA most directly produced by this invocation. Singular.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON payload"),
) -> None:
    """Close an open invocation record. --invocation-id and --outcome are required.

    Use --artifact (repeatable) to link output artifacts to this invocation.
    Use --commit (singular) to link the primary git commit produced.
    Use --evidence to promote a file to a Tier 2 evidence artifact.
    Note: --evidence is rejected for records that are not execution records.
    """
    # Explicit-outcome guard (schema v2): a missing or invalid outcome is a
    # usage error at the CLI boundary — never silently coerced to "done".
    valid_outcomes: dict[str, Literal["done", "failed", "abandoned"]] = {
        "done": "done",
        "failed": "failed",
        "abandoned": "abandoned",
    }
    checked_outcome = valid_outcomes.get(outcome)
    if checked_outcome is None:
        raise typer.BadParameter(
            f"invalid outcome {outcome!r}: must be one of done, failed, abandoned",
            param_hint="--outcome",
        )

    repo_root = _get_repo_root()
    executor = _build_executor(repo_root)
    try:
        completed = executor.complete_invocation(
            invocation_id=invocation_id,
            outcome=checked_outcome,
            evidence_ref=evidence,
            artifact_refs=artifact or [],
            commit_sha=commit,
            # The CLI surface is the manual/agent close path; the doctor sweep
            # (the only other closer) calls the executor directly (FR-003).
            closed_by="agent",
        )
    except InvalidModeForEvidenceError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(2) from e
    except AlreadyClosedError:
        _handle_complete_already_closed(invocation_id, json_output=json_output)
    except Exception as e:
        typer.echo(json.dumps({"error": "complete_failed", "message": str(e)}), err=True)
        raise typer.Exit(1) from e

    # #4397 / #6410: a best-effort auto-commit that was skipped (untracked or
    # ignored kitty-ops/) or refused (e.g. a protected-branch guard) is visible
    # here, not just a logger.warning; the completed event is already on disk.
    # Human output only: the --json payload's shape is contract-frozen.
    commit_outcome = executor.last_op_commit
    if not json_output and commit_outcome is not None and not commit_outcome.committed:
        _print_uncommitted_note(commit_outcome, invocation_id)

    _render_complete_response(
        invocation_id=invocation_id,
        outcome=outcome,
        evidence_ref=completed.evidence_ref,
        artifact=artifact,
        commit=commit,
        repo_root=repo_root,
        json_output=json_output,
    )
