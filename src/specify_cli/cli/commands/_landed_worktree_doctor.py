"""Landed-worktree section of ``doctor workspaces`` (#7173, WP04).

Renders the verdicts of :func:`specify_cli.workspace.landed_worktrees.assess_worktrees`
after the unchanged husk report and, with ``--prune``, runs
:func:`~specify_cli.workspace.landed_worktrees.prune_landed` and prints each
outcome with its recreate command (``contracts/doctor-workspaces-cli.md``).
The decision logic lives in the workspace module; this module only renders.

Import discipline (one-way, I-2): imports shared infra from
:mod:`._doctor_shared`; never imports the CLI ``doctor`` module. The workspace
imports stay function-local, like the husk cluster's ``specify_cli.status``
imports.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from rich.markup import escape

from ._doctor_shared import console

if TYPE_CHECKING:
    from specify_cli.workspace.landed_worktrees import (
        PruneOutcome,
        WorktreeAssessment,
        WorktreeVerdict,
    )

__all__ = [
    "run_worktree_section",
]

PRUNE_COMMAND = "spec-kitty doctor workspaces --prune"
HUSK_FIX_COMMAND = "spec-kitty doctor workspaces --fix"
_SHORT_SHA = 12
_INDENT = "  "
_REMOTES_PREFIX = "refs/remotes/"
_DEFAULT_PRIMARY = "origin/<primary>"

_VERDICT_STYLE = {
    "landed": "green",
    "not_landed": "yellow",
    "unproven": "yellow",
    "mission_owned": "cyan",
}


def _prune_command(remote: str | None) -> str:
    """The prune command that repeats the remote in force, so a printed remedy stays runnable."""
    from specify_cli.workspace.landed_worktrees import DEFAULT_REMOTE

    if remote is None or remote == DEFAULT_REMOTE:
        return PRUNE_COMMAND
    return f"{PRUNE_COMMAND} --remote {remote}"


def _shown_path(path: Path, repo_root: Path) -> str:
    """*path* relative to the repository root when inside it, absolute otherwise."""
    resolved = path.resolve(strict=False)
    try:
        return str(resolved.relative_to(repo_root.resolve(strict=False)))
    except ValueError:
        return str(resolved)


def _short(tip: str | None) -> str:
    return (tip or "")[:_SHORT_SHA]


def _branch_label(branch: str | None, tip: str | None) -> str:
    if branch is not None:
        return branch
    return f"detached @{_short(tip)}" if tip else "detached"


def _primary_label(primary_ref: str | None) -> str:
    """``origin/main`` for ``refs/remotes/origin/main``."""
    if primary_ref is None:
        return _DEFAULT_PRIMARY
    return primary_ref.removeprefix(_REMOTES_PREFIX)


def _print(text: str) -> None:
    """One line, never wrapped: paths and recreate commands must stay copyable."""
    console.print(text, soft_wrap=True)


def _shown_verdicts(assessment: WorktreeAssessment) -> list[WorktreeVerdict]:
    """The text report's verdicts, grouped; ``excluded`` is shown only in JSON."""
    from specify_cli.workspace.landed_worktrees import Verdict

    order = (Verdict.LANDED, Verdict.NOT_LANDED, Verdict.UNPROVEN, Verdict.MISSION_OWNED)
    shown = [verdict for verdict in assessment.verdicts if verdict.verdict in order]
    return sorted(shown, key=lambda verdict: order.index(verdict.verdict))


def _ignored_line(verdict: WorktreeVerdict) -> str | None:
    """``will also delete ignored: .venv/, .env (+N more)``; ``None`` when nothing ignored is there."""
    if verdict.ignored_count == 0:
        return None
    more = verdict.ignored_count - len(verdict.ignored_paths)
    suffix = f" (+{more} more)" if more > 0 else ""
    return f"will also delete ignored: {', '.join(verdict.ignored_paths)}{suffix}"


def _manual_commands(verdict: WorktreeVerdict, repo_root: Path, primary: str) -> list[str]:
    """The hand removal for a worktree unproven only because running processes cannot be checked (else ``[]``).

    Like the prune (``LANDED_INTENT``), the branch tip is kept under
    ``refs/spec-kitty/discarded/<branch>`` before the branch is deleted; the
    printed write is the guard's own create-only bookkeeping write.
    """
    from specify_cli.git.destructive_guard import discarded_ref
    from specify_cli.git.ref_advance import bookkeeping_ref_write_args
    from specify_cli.workspace.landed_worktrees import Reason, shell_command

    if verdict.reason is not Reason.PROCESS_PROOF_UNAVAILABLE:
        return []
    lines = [
        f"only after checking nothing runs in it; content is on {primary}:",
        f"{_INDENT}{shell_command('git', 'worktree', 'remove', str(verdict.path.resolve(strict=False)))}",
    ]
    if verdict.branch is not None:
        if verdict.tip is not None:
            keep = bookkeeping_ref_write_args(discarded_ref(repo_root, verdict.branch, verdict.tip), verdict.tip, create_only=True)
            lines.append(f"{_INDENT}{shell_command('git', *keep)}")
        lines.append(f"{_INDENT}{shell_command('git', 'branch', '-D', verdict.branch)}")
    return lines


def _render_verdict(
    verdict: WorktreeVerdict,
    repo_root: Path,
    primary: str,
    *,
    prune: bool,
    prune_command: str = PRUNE_COMMAND,
) -> None:
    value = verdict.verdict.value
    label = escape(_branch_label(verdict.branch, verdict.tip))
    line = (
        f"{_INDENT}{escape(_shown_path(verdict.path, repo_root))} ({label}): "
        f"[{_VERDICT_STYLE[value]}]{value}[/{_VERDICT_STYLE[value]}] — "
        f"{verdict.reason.value}: {escape(verdict.detail)}"
    )
    _print(line)
    extra = _ignored_line(verdict)
    if extra is not None:
        _print(f"{_INDENT * 2}{escape(extra)}")
    for manual in _manual_commands(verdict, repo_root, primary):
        _print(f"{_INDENT * 2}{escape(manual)}")
    if verdict.removable and not prune:
        _print(f"{_INDENT * 2}remove with: {prune_command}")


def _render_assessment(assessment: WorktreeAssessment, repo_root: Path, *, prune: bool) -> None:
    console.print()
    if assessment.error is not None:
        _print(f"[red]Error:[/red] {escape(assessment.error)}")
        return
    primary = escape(assessment.primary_ref or _DEFAULT_PRIMARY)
    _print(f"[bold]Worktrees[/bold] (proven against the local {primary}; nothing is fetched)")
    shown = _shown_verdicts(assessment)
    if not shown:
        _print(f"{_INDENT}No linked worktrees to assess.")
    prune_command = _prune_command(assessment.remote)
    for verdict in shown:
        _render_verdict(
            verdict,
            repo_root,
            _primary_label(assessment.primary_ref),
            prune=prune,
            prune_command=prune_command,
        )
    landed = sum(1 for verdict in shown if verdict.removable)
    _print(f"{landed} landed, {len(shown) - landed} kept")
    if assessment.uninspected_processes > 0:
        _print(f"{assessment.uninspected_processes} process(es) could not be inspected for a working directory inside a worktree; they were skipped.")


def _refusal_hint(outcome: PruneOutcome, primary: str, prune_command: str = PRUNE_COMMAND) -> str | None:
    """What the operator does next for a prune refusal that is not the guard's own (``None`` for the guard's)."""
    from specify_cli.git.destructive_guard import WORKTREE_PARTIALLY_REMOVED
    from specify_cli.workspace.landed_worktrees import (
        BRANCH_DELETE_FAILED,
        BRANCH_MOVED,
        NOT_REGISTERED,
        TIP_MOVED,
        WORKTREE_REMOVE_FAILED,
        shell_command,
    )

    if outcome.refusal in (TIP_MOVED, NOT_REGISTERED):
        return f"the worktree changed after it was assessed; run `{prune_command}` again"
    if outcome.refusal == WORKTREE_REMOVE_FAILED:
        return f"the removal could not run; inspect it, then `{shell_command('git', 'worktree', 'remove', str(outcome.path))}` (no --force)"
    if outcome.refusal == WORKTREE_PARTIALLY_REMOVED:
        return f"git unregistered the worktree but could not delete all of it; the branch is kept; clear the leftover with `{HUSK_FIX_COMMAND}`"
    if outcome.branch is None:
        return None
    if outcome.refusal == BRANCH_MOVED:
        return f"the branch moved after it was assessed; inspect it with `{shell_command('git', 'log', outcome.branch)}`"
    if outcome.refusal == BRANCH_DELETE_FAILED:
        return f"the branch delete failed; content is on {primary}: `{shell_command('git', 'branch', '-D', outcome.branch)}`"
    return None


def _print_hint(outcome: PruneOutcome, primary: str, prune_command: str = PRUNE_COMMAND) -> None:
    hint = _refusal_hint(outcome, primary, prune_command)
    if hint is not None:
        _print(f"{_INDENT}{escape(hint)}")


def _render_outcome(
    outcome: PruneOutcome,
    repo_root: Path,
    primary: str,
    prune_command: str = PRUNE_COMMAND,
) -> None:
    from specify_cli.git.destructive_guard import WORKTREE_PARTIALLY_REMOVED

    path = escape(_shown_path(outcome.path, repo_root))
    where = f"branch {escape(outcome.branch)}" if outcome.branch is not None else "detached"
    head = f"{path} ({where} at {_short(outcome.tip)})"
    if not outcome.removed:
        _print(f"[yellow]Kept[/yellow] {head}: refused ({escape(outcome.refusal or 'unknown')})")
        _print_hint(outcome, primary, prune_command)
        return
    _print(f"[green]Removed[/green] {head}")
    _print(f"{_INDENT}recreate: {escape(outcome.recreate)}")
    if outcome.kept_ref is not None:
        _print(f"{_INDENT}tip kept at {escape(outcome.kept_ref)}")
    if outcome.refusal is not None:
        label = "partly removed" if outcome.refusal == WORKTREE_PARTIALLY_REMOVED else "branch kept"
        _print(f"{_INDENT}[yellow]{label}:[/yellow] {escape(outcome.refusal)}")
        _print_hint(outcome, primary, prune_command)


def _render_prune(
    outcomes: Sequence[PruneOutcome],
    repo_root: Path,
    primary: str,
    prune_command: str = PRUNE_COMMAND,
) -> None:
    if not outcomes:
        _print("No landed worktrees to prune.")
        return
    for outcome in outcomes:
        _render_outcome(outcome, repo_root, primary, prune_command)


def _payload(assessment: WorktreeAssessment, outcomes: Sequence[PruneOutcome], *, prune: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "remote": assessment.remote,
        "worktrees": [verdict.to_json() for verdict in assessment.verdicts],
        "uninspected_processes": assessment.uninspected_processes,
    }
    if assessment.error is not None:
        payload["worktrees_error"] = assessment.error
    if prune:
        payload["pruned"] = [outcome.to_json() for outcome in outcomes]
    return payload


def _exit_code(assessment: WorktreeAssessment, outcomes: Sequence[PruneOutcome]) -> int:
    """1 when the worktree list is unreadable or a removal was refused; landed worktrees alone never fail.

    Keeping the primary branch (``BRANCH_IS_PRIMARY``) is the rule, not a refusal.
    """
    from specify_cli.workspace.landed_worktrees import BRANCH_IS_PRIMARY

    refused = any(outcome.refusal not in (None, BRANCH_IS_PRIMARY) for outcome in outcomes)
    if assessment.error is not None or refused:
        return 1
    return 0


def run_worktree_section(
    repo_root: Path,
    *,
    current_dir: Path,
    prune: bool,
    json_output: bool,
    remote: str | None = None,
) -> tuple[dict[str, object], int]:
    """Assess (and with *prune* remove) landed worktrees; ``(json keys, exit code)``.

    In text mode the section is printed here; in JSON mode the caller merges
    the returned keys into the husk payload. *remote* is the remote whose
    primary ref proves a landing (``None`` = ``DEFAULT_REMOTE``).
    """
    from specify_cli.workspace import process_probe
    from specify_cli.workspace.landed_worktrees import DEFAULT_REMOTE, ProbeFn, assess_worktrees, prune_landed

    handled = DEFAULT_REMOTE if remote is None else remote
    probe: ProbeFn = process_probe.processes_with_cwd_under
    assessment = assess_worktrees(repo_root, current_dir=current_dir, probe=probe, remote=handled)
    outcomes: list[PruneOutcome] = []
    if prune:
        outcomes = prune_landed(
            repo_root, current_dir=current_dir, probe=probe, assessment=assessment, remote=handled
        )
    if not json_output:
        _render_assessment(assessment, repo_root, prune=prune)
        if prune and assessment.error is None:
            _render_prune(
                outcomes,
                repo_root,
                _primary_label(assessment.primary_ref),
                _prune_command(handled),
            )
    return _payload(assessment, outcomes, prune=prune), _exit_code(assessment, outcomes)
