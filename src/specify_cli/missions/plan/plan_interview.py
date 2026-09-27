"""Plan interview flow with Widen Mode affordance (FR-002, WP08 T044).

Applies the same ``[w]iden`` pattern as the charter and specify interview
flows to the ``plan`` interview surface.  Each question opened here records
a Decision Moment with ``origin_flow=PLAN``.

Public API:
    run_plan_interview(questions, repo_root, mission_slug, console, actor)
        Drive a list of (question_id, question_text) through the widen-enabled
        interview loop and return a dict of answers.

This module is intentionally thin — it reuses helpers from
``specify_cli.widen.interview_helpers`` and the same WidenFlow/WidenPendingStore
infrastructure already used by charter.py and specify_interview.py.
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.core import hosted_posture
from specify_cli.core.env import is_interactive
from specify_cli.mission_metadata import load_meta_or_empty
import contextlib
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape

__all__ = ["run_plan_interview"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_actor() -> str:
    """Return the git user email or ``'cli'`` as fallback."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        email = result.stdout.strip()
        if email:
            return email
    except Exception:  # noqa: BLE001
        pass
    return "cli"


def _get_mission_id(repo_root: Path, mission_slug: str) -> str | None:
    """Read mission_id (ULID) from kitty-specs/<slug>/meta.json.

    Routed onto the kind-aware read seam (FR-001) for the feature-dir leg and
    the canonical meta.json reader (FR-005 / post-#2091) for the parse leg:
    ``load_meta_or_empty`` absorbs a missing/malformed meta.json to ``{}``,
    preserving the original broad ``contextlib.suppress(Exception)`` contract
    (silent ``None`` on any read/parse failure).

    read-side-placement-seam-migration WP07: the feature-dir leg is routed
    through ``placement_seam`` (fail-loud on a deleted-coord mismatch,
    NFR-002) instead of the kind-blind ``resolve_planning_read_dir`` —
    behavior-neutral since PRIMARY_METADATA is PRIMARY-partition.
    """
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )
    with contextlib.suppress(Exception):
        data = load_meta_or_empty(feature_dir)
        return data.get("mission_id") or None
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_plan_interview(  # noqa: C901
    questions: list[tuple[str, str]],
    repo_root: Path,
    mission_slug: str,
    console: Console,
    actor: str | None = None,
) -> dict[str, str]:
    """Drive a plan interview with the Widen Mode affordance.

    Args:
        questions:    List of ``(question_id, question_text)`` pairs in order.
        repo_root:    Absolute path to the repo root.
        mission_slug: Mission slug (e.g. ``'my-mission-01ABC'``).
        console:      Rich Console for output.
        actor:        Git user email; resolved automatically if None.

    Returns:
        A dict mapping ``question_id`` to the owner's answer.  Empty string
        for questions that were widened (pending-external-input) or deferred.

    Non-interactive contract (#2876): when :func:`is_interactive` is False —
    ``SPEC_KITTY_NON_INTERACTIVE`` set, or stdin is not a TTY, which is how
    agents and CI drive this tool — the interview never prompts (a blocking
    prompt hangs forever on an open-but-silent stdin pipe). Per the issue it
    *takes the defaults*: every Decision Moment is still opened and recorded
    (deferred / unanswered), so ``decisions/index.json`` is written exactly as
    in the interactive path — only the blocking ``typer.prompt`` (and the widen
    affordance, which needs a keystroke) is skipped.
    """
    import typer

    interactive = is_interactive()
    if not interactive:
        console.print(
            "[dim]Non-interactive: taking defaults for the plan interview "
            "(no prompts; questions recorded as deferred).[/dim]"
        )

    from specify_cli.decisions import service as _dm_service
    from specify_cli.decisions.models import OriginFlow as _DmOriginFlow
    from specify_cli.decisions.service import DecisionError as _DecisionError
    from specify_cli.widen.interview_helpers import (
        resolve_already_widened_prompt,
        run_end_of_interview_pending_pass,
    )

    if actor is None:
        actor = _resolve_actor()

    # ------------------------------------------------------------------
    # Prereq check + widen infrastructure setup (non-fatal)
    # ------------------------------------------------------------------
    prereq_state: Any = None
    widen_flow: Any = None
    widen_store: Any = None
    saas_client: Any = None

    # Widen needs a keystroke ([w]); it is only reachable interactively. Skipping
    # the setup non-interactively also avoids the SaaS prereq probe in CI (#2876).
    # FR-004: gate on drain BEFORE SaasClient.from_env/load_auth_context, not
    # just before check_prereqs -- those two calls already read the credential
    # store (and may refresh an expired OAuth session over the network).
    if interactive and hosted_posture.drain_posture().enabled:
        try:
            from specify_cli.saas_client import SaasClient
            from specify_cli.widen import check_prereqs
            from specify_cli.widen.flow import WidenFlow
            from specify_cli.widen.state import WidenPendingStore

            saas_client = SaasClient.from_env(repo_root)
            _team_slug: str = ""
            with contextlib.suppress(Exception):
                from specify_cli.saas_client.auth import load_auth_context

                _auth_ctx = load_auth_context(repo_root)
                _team_slug = _auth_ctx.team_slug or ""

            prereq_state = check_prereqs(saas_client, team_slug=_team_slug)
            if prereq_state.all_satisfied:
                widen_flow = WidenFlow(saas_client, repo_root, console)
                widen_store = WidenPendingStore(repo_root, mission_slug)
        except Exception:  # noqa: BLE001
            pass  # non-fatal; [w] will be suppressed

    mission_id = _get_mission_id(repo_root, mission_slug)

    answers: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Question loop
    # ------------------------------------------------------------------
    for question_id, question_text in questions:
        default_value = ""

        # Open a Decision Moment (non-fatal)
        current_decision_id: str | None = None
        with contextlib.suppress(_DecisionError, Exception):
            dm_response = _dm_service.open_decision(
                repo_root=repo_root,
                mission_slug=mission_slug,
                origin_flow=_DmOriginFlow.PLAN,
                step_id=f"plan.{question_id}",
                input_key=question_id,
                question=question_text,
                options=(),
                actor=actor,
            )
            current_decision_id = dm_response.decision_id

        # T045 — Already-widened question prompt (narrow-once seam, #2675 T061)
        _already_widened = resolve_already_widened_prompt(
            widen_store=widen_store,
            decision_id=current_decision_id,
            saas_client=saas_client,
            question_text=question_text,
            mission_slug=mission_slug,
            repo_root=repo_root,
            dm_service=_dm_service,
            actor=actor,
            console=console,
        )
        if _already_widened:
            answers[question_id] = ""
            continue  # next question

        # Build hint line
        widen_suffix = ""
        if (
            prereq_state is not None
            and prereq_state.all_satisfied
            and widen_flow is not None
            and widen_store is not None
            and current_decision_id is not None
            and not _already_widened
        ):
            widen_suffix = " | [w]iden"
        hint_line = (
            f"[enter]=accept default | [text]=type answer{widen_suffix}"
            " | [d]efer | [!cancel]"
        )
        # #2876: the hint's bracketed keys are literal text, not Rich markup.
        # Unescaped, Rich eats [enter]/[text]/[d]/[w] as style tags and the
        # operator sees "=accept default | =type answer | efer | [!cancel]".
        if interactive:
            console.print(f"[dim]{escape(hint_line)}[/dim]")

        # Prompt
        user_answer = ""
        while True:
            if not interactive:
                # #2876: non-interactive — take the default, never prompt (a
                # blocking read hangs on a silent stdin pipe). The Decision
                # Moment above is still recorded (deferred below).
                user_answer = default_value
                break
            try:
                raw = typer.prompt(question_text, default=default_value)
            except (KeyboardInterrupt, EOFError):
                raise typer.Exit() from None

            if (
                raw.strip().lower() == "w"
                and widen_flow is not None
                and current_decision_id is not None
                and mission_id is not None
            ):
                from kernel.clock import now_utc

                from specify_cli.widen.models import WidenAction, WidenPendingEntry

                result = widen_flow.run_widen_mode(
                    decision_id=current_decision_id,
                    mission_id=mission_id,
                    mission_slug=mission_slug,
                    question_text=question_text,
                    actor=actor,
                )

                if result.action == WidenAction.CANCEL:
                    console.print(f"[dim]{escape(hint_line)}[/dim]")
                    continue  # re-prompt

                if result.action == WidenAction.BLOCK:
                    from specify_cli.cli.commands.charter import _run_blocked_prompt_loop

                    _run_blocked_prompt_loop(
                        decision_id=result.decision_id or current_decision_id,
                        question_text=question_text,
                        invited=result.invited,
                        mission_slug=mission_slug,
                        repo_root=repo_root,
                        console=console,
                        saas_client=saas_client,
                        actor=actor,
                    )
                    user_answer = ""
                    break

                if result.action == WidenAction.CONTINUE:
                    if widen_store is not None:
                        try:
                            widen_store.add_pending(
                                WidenPendingEntry(
                                    decision_id=result.decision_id or current_decision_id,
                                    mission_slug=mission_slug,
                                    question_id=f"plan.{question_id}",
                                    question_text=question_text,
                                    entered_pending_at=now_utc(),
                                    widen_endpoint_response={},
                                )
                            )
                        except Exception as exc:  # noqa: BLE001
                            console.print(
                                "[red]Could not save pending widen marker: "
                                f"{exc}. Question was NOT parked.[/red]"
                            )
                            continue
                    user_answer = ""
                    break

                # Unknown action
                user_answer = raw
                break

            else:
                user_answer = raw
                break

        answers[question_id] = user_answer

        # Terminal DM event (non-fatal)
        if current_decision_id is not None:
            if user_answer.strip().lower() == "!cancel":
                with contextlib.suppress(Exception):
                    _dm_service.cancel_decision(
                        repo_root=repo_root,
                        mission_slug=mission_slug,
                        decision_id=current_decision_id,
                        rationale="owner canceled during plan interview",
                        actor=actor,
                    )
            elif user_answer.strip():
                with contextlib.suppress(Exception):
                    _dm_service.resolve_decision(
                        repo_root=repo_root,
                        mission_slug=mission_slug,
                        decision_id=current_decision_id,
                        final_answer=user_answer,
                        actor=actor,
                    )
            else:
                with contextlib.suppress(Exception):
                    _dm_service.defer_decision(
                        repo_root=repo_root,
                        mission_slug=mission_slug,
                        decision_id=current_decision_id,
                        rationale="owner deferred during plan interview",
                        actor=actor,
                    )

    # ------------------------------------------------------------------
    # T040 — End-of-interview pending pass (FR-010)
    # ------------------------------------------------------------------
    if widen_store is not None and saas_client is not None:
        run_end_of_interview_pending_pass(
            widen_store=widen_store,
            saas_client=saas_client,
            mission_slug=mission_slug,
            repo_root=repo_root,
            console=console,
            dm_service=_dm_service,
            actor=actor,
        )

    return answers
