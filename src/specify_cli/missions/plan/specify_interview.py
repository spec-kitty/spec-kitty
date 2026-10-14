"""Specify interview flow (local Decision-Moment loop).

Each question opened here records a Decision Moment with
``origin_flow=SPECIFY``. Hosted Widen Mode was removed in issue #6164; only the
local interview loop remains.

Public API:
    run_specify_interview(questions, repo_root, mission_slug, console, actor)
        Drive a list of (question_id, question_text) through the local
        interview loop and return a dict of answers.
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.core.env import is_interactive
from specify_cli.mission_metadata import load_meta_or_empty
import contextlib
from pathlib import Path

from rich.console import Console
from rich.markup import escape

__all__ = ["run_specify_interview"]


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


def run_specify_interview(
    questions: list[tuple[str, str]],
    repo_root: Path,
    mission_slug: str,
    console: Console,
    actor: str | None = None,
) -> dict[str, str]:
    """Drive a specify interview (local Decision-Moment loop).

    Args:
        questions:    List of ``(question_id, question_text)`` pairs in order.
        repo_root:    Absolute path to the repo root.
        mission_slug: Mission slug (e.g. ``'my-mission-01ABC'``).
        console:      Rich Console for output.
        actor:        Git user email; resolved automatically if None.

    Returns:
        A dict mapping ``question_id`` to the owner's answer.  Empty string
        for questions that were deferred.

    Non-interactive contract (#2876): when :func:`is_interactive` is False --
    ``SPEC_KITTY_NON_INTERACTIVE`` set, or stdin is not a TTY, which is how
    agents and CI drive this tool -- the interview never prompts (a blocking
    prompt hangs forever on an open-but-silent stdin pipe). Per the issue it
    *takes the defaults*: every Decision Moment is still opened and recorded
    (deferred / unanswered), so ``decisions/index.json`` is written exactly as
    in the interactive path -- only the blocking ``typer.prompt`` is skipped.
    """
    import typer

    interactive = is_interactive()
    if not interactive:
        console.print(
            "[dim]Non-interactive: taking defaults for the specify interview "
            "(no prompts; questions recorded as deferred).[/dim]"
        )

    from specify_cli.decisions import service as _dm_service
    from specify_cli.decisions.models import OriginFlow as _DmOriginFlow
    from specify_cli.decisions.service import DecisionError as _DecisionError

    if actor is None:
        actor = _resolve_actor()

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
                origin_flow=_DmOriginFlow.SPECIFY,
                step_id=f"specify.{question_id}",
                input_key=question_id,
                question=question_text,
                options=(),
                actor=actor,
            )
            current_decision_id = dm_response.decision_id

        # Build hint line
        hint_line = (
            "[enter]=accept default | [text]=type answer"
            " | [d]efer | [!cancel]"
        )
        if interactive:
            console.print(f"[dim]{escape(hint_line)}[/dim]")

        # Prompt
        if not interactive:
            # #2876: non-interactive -- take the default, never prompt (a
            # blocking read hangs on a silent stdin pipe). The Decision
            # Moment above is still recorded (deferred below).
            user_answer = default_value
        else:
            try:
                user_answer = typer.prompt(question_text, default=default_value)
            except (KeyboardInterrupt, EOFError):
                raise typer.Exit() from None

        answers[question_id] = user_answer

        # Terminal DM event (non-fatal)
        if current_decision_id is not None:
            if user_answer.strip().lower() == "!cancel":
                with contextlib.suppress(Exception):
                    _dm_service.cancel_decision(
                        repo_root=repo_root,
                        mission_slug=mission_slug,
                        decision_id=current_decision_id,
                        rationale="owner canceled during specify interview",
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
                        rationale="owner deferred during specify interview",
                        actor=actor,
                    )

    return answers
