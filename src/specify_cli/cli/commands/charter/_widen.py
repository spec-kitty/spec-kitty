"""Local Decision-Moment interview helpers for the ``charter interview`` subcommand.

These helpers drive the local Decision-Moment loop: per-question prompting,
local resolution, deferral, cancellation, and the terminal Decision-Moment
transition. They are public-by-convention (the legacy
``_schedule_inactivity_reminder``, ``_run_blocked_prompt_loop`` etc. are
imported by other modules and by tests) and are re-exported from the package
``__init__`` for backward compatibility.

The hosted "Widen Mode" dispatch (audience-widening of a Decision Moment via
the SaaS discussion) was removed with the frozen hosted surfaces (issue #6164);
only the local interview loop remains.
"""
from __future__ import annotations

import contextlib
import threading
from pathlib import Path
from typing import Any, NamedTuple

import typer
from mission_runtime import MissionArtifactKind, placement_seam
from rich.console import Console
from rich.panel import Panel

from specify_cli.decisions import service as _dm_service
from specify_cli.decisions.service import DecisionError as _DecisionError
from specify_cli.mission_metadata import load_meta_or_empty


class _AbsentPrereqState(NamedTuple):
    """Local stand-in for the removed ``widen.models.PrereqState`` sentinel.

    Hosted Widen Mode is gone (issue #6164), so widen prerequisites are now
    always absent. Callers only read ``all_satisfied``; the remaining fields
    mirror the retired dataclass so any residual attribute access stays False.
    """

    all_satisfied: bool = False
    teamspace_ok: bool = False
    slack_ok: bool = False
    saas_reachable: bool = False


#: Sentinel prereq-state used when widen prereqs are unavailable (always, now).
_WIDEN_PREREQS_ABSENT_CACHE: Any = _AbsentPrereqState()


def _get_widen_prereqs_absent() -> Any:
    """Return a fully-absent prereq-state sentinel."""
    return _WIDEN_PREREQS_ABSENT_CACHE


def _get_mission_id(repo_root: Path, mission_slug: str) -> str | None:
    """Read mission_id (ULID) from kitty-specs/<slug>/meta.json.

    Returns ``None`` if the file is absent or malformed.
    """
    # #3140: a malformed meta.json doesn't only trip load_meta_or_empty's own
    # (silent, non-raising) read below -- placement_seam(...).read_dir(...)
    # resolves the mission's lifecycle phase along the way
    # (mission_runtime.lifecycle_phase.resolve_lifecycle_phase ->
    # _read_baseline_merge_commit), which reads meta.json under the raise-on-
    # malformed contract (mission_metadata.load_meta's default). That
    # ValueError previously propagated out of this function, contradicting
    # its own docstring's "malformed -> None" promise. Absorb it locally
    # rather than relaxing the shared load_meta contract, which other
    # callers (e.g. the fail-closed corrupt-meta test) deliberately rely on
    # raising.
    try:
        feature_dir = placement_seam(repo_root, mission_slug).read_dir(
            MissionArtifactKind.PRIMARY_METADATA
        )
        # load_meta_or_empty (post-#2091 silent contract) absorbs a missing or
        # malformed meta.json to {}, matching the prior contextlib.suppress
        # absorption.
        data = load_meta_or_empty(feature_dir)
    except ValueError:
        return None
    return data.get("mission_id") or None


def _is_already_widened(widen_store: Any, decision_id: str) -> bool:
    """Return True if *decision_id* already has a pending widen entry.

    With hosted Widen Mode removed (issue #6164), ``widen_store`` is always
    ``None`` at every call site, so this short-circuits to ``False``; the
    helper is retained for API compatibility.
    """
    if widen_store is None:
        return False
    with contextlib.suppress(Exception):
        return any(e.decision_id == decision_id for e in widen_store.list_pending())
    return False


def _schedule_inactivity_reminder(
    console: Console,
    delay_seconds: int = 3600,
) -> threading.Timer:
    """Schedule an inactivity reminder for the blocked prompt (NFR-004).

    The timer fires once after *delay_seconds* (default 60 min).  It is a
    daemon thread so it will not prevent process exit.
    """

    def _remind() -> None:
        console.print(
            "\n[yellow]Still waiting on a decision.[/yellow] "
            "Type a local answer, or press d to defer.\n"
            "Waiting > ",
            end="",
        )

    timer = threading.Timer(delay_seconds, _remind)
    timer.daemon = True
    timer.start()
    return timer


def _render_waiting_panel(
    console: Console,
    question_text: str,
    invited: list[str] | None,
    slack_thread_url: str | None = None,
) -> None:
    """Render the waiting-for-decision panel (contracts/cli-contracts.md §4)."""
    participants_line = ", ".join(invited) if invited else "(none)"
    thread_line = f"Thread: {slack_thread_url}" if slack_thread_url else "Thread: (pending)"
    console.print(
        Panel(
            f"Question: {question_text}\n"
            f"Participants: {participants_line}\n"
            f"{thread_line}",
            title="Waiting for decision",
        )
    )
    console.print(
        "\nOptions:\n"
        "  <type an answer>   — resolve locally right now\n"
        "  [d]efer            — defer this question for later\n"
    )


def _resolve_locally(
    decision_id: str,
    mission_slug: str,
    repo_root: Path,
    final_answer: str,
    actor: str,
    console: Console,
) -> bool:
    """FR-018: resolve with source=manual at the blocked prompt."""
    try:
        _dm_service.resolve_decision(
            repo_root=repo_root,
            mission_slug=mission_slug,
            decision_id=decision_id,
            final_answer=final_answer,
            actor=actor,
        )
    except _DecisionError as exc:
        console.print(
            f"[red]Write-back failed: {exc}. Your answer was NOT saved.[/red]"
        )
        return False
    console.print("[green]Resolved locally.[/green]")
    return True


def _defer_from_blocked_prompt(
    decision_id: str,
    mission_slug: str,
    repo_root: Path,
    actor: str,
    console: Console,
) -> bool:
    """T032: defer the decision from the blocked prompt."""
    try:
        rationale = console.input("Rationale for deferral (press Enter to skip): ").strip()
    except (KeyboardInterrupt, EOFError):
        rationale = ""

    try:
        _dm_service.defer_decision(
            repo_root=repo_root,
            mission_slug=mission_slug,
            decision_id=decision_id,
            rationale=rationale or "deferred from blocked prompt",
            actor=actor,
        )
    except _DecisionError as exc:
        console.print(
            f"[red]Write-back failed: {exc}. Your deferral was NOT saved.[/red]"
        )
        return False
    console.print("[yellow]Decision deferred.[/yellow]")
    return True


def _resolve_dm_terminal(
    *,
    repo_root: Path,
    mission_slug: str,
    decision_id: str,
    actual_answer: str,
    actor: str,
) -> None:
    """Apply the correct Decision Moment terminal transition after a question answer.

    Rules (FR-012):
    - ``!cancel`` → cancel (question not applicable)
    - non-empty → resolve
    - empty → defer
    """
    if actual_answer.strip().lower() == "!cancel":
        with contextlib.suppress(_DecisionError):
            _dm_service.cancel_decision(
                repo_root=repo_root,
                mission_slug=mission_slug,
                decision_id=decision_id,
                rationale="owner canceled during charter interview (question not applicable)",
                actor=actor,
            )
    elif actual_answer.strip():
        with contextlib.suppress(_DecisionError):
            _dm_service.resolve_decision(
                repo_root=repo_root,
                mission_slug=mission_slug,
                decision_id=decision_id,
                final_answer=actual_answer,
                actor=actor,
            )
    else:
        with contextlib.suppress(_DecisionError):
            _dm_service.defer_decision(
                repo_root=repo_root,
                mission_slug=mission_slug,
                decision_id=decision_id,
                rationale="owner deferred during charter interview",
                actor=actor,
            )


def _prompt_one_question(
    *,
    question_id: str,
    prompt_text: str,
    default_value: str,
    hint_line: str,
    console: Console,
    answers_override: dict[str, str],
) -> str:
    """Prompt the user for a single interview question.

    Returns the final answer string (may be empty for defer paths).
    """
    console.print(f"[dim]{hint_line}[/dim]")

    user_answer = typer.prompt(prompt_text, default=default_value)

    if question_id not in answers_override:
        answers_override[question_id] = user_answer

    return answers_override[question_id]


def _run_blocked_prompt_loop(
    decision_id: str,
    question_text: str,
    invited: list[str] | None,
    mission_slug: str,
    repo_root: Path,
    console: Console,
    actor: str,
    slack_thread_url: str | None = None,
) -> None:
    """Block the interview at a question until resolved locally.

    Renders the waiting panel and loops on input until the decision is
    resolved via one of:
    - plain text answer → decision.resolve(manual)
    - [d]efer → decision.defer()
    """
    _render_waiting_panel(console, question_text, invited, slack_thread_url)

    # NFR-004: inactivity reminder after 60 minutes
    _inactivity_timer = _schedule_inactivity_reminder(console)

    while True:
        try:
            raw = console.input("Waiting > ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Type d to defer or a local answer to resolve.[/dim]")
            continue

        cmd = raw.strip()

        if not cmd:
            # Blank line — re-show options summary
            console.print(
                "[dim]<local answer> | [d]efer | [!cancel][/dim]"
            )
            continue
        elif cmd.lower() == "d":
            _inactivity_timer.cancel()
            deferred = _defer_from_blocked_prompt(
                decision_id=decision_id,
                mission_slug=mission_slug,
                repo_root=repo_root,
                actor=actor,
                console=console,
            )
            if deferred:
                break
            _inactivity_timer = _schedule_inactivity_reminder(console)
        elif cmd.lower() == "!cancel":
            _inactivity_timer.cancel()
            console.print("[dim]Interview canceled.[/dim]")
            raise typer.Exit()
        else:
            # Plain text → local answer (FR-018)
            _inactivity_timer.cancel()
            resolved = _resolve_locally(
                decision_id=decision_id,
                mission_slug=mission_slug,
                repo_root=repo_root,
                final_answer=cmd,
                actor=actor,
                console=console,
            )
            if resolved:
                break
            _inactivity_timer = _schedule_inactivity_reminder(console)
