"""Inline Feedback Survey offers after human trigger commands (WP06).

Host commands call :func:`offer_after_trigger` (or :func:`offer_after_op_close`)
exactly once after their own work has finished. The hook never raises to the
caller: any failure — including Ctrl-C during the optional survey — is
swallowed so a successful command cannot turn into a failure.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.cli.console import console as default_console
from specify_cli.compat.planner import is_ci_env
from specify_cli.core.env import is_interactive
from specify_cli.feedback import wording
from specify_cli.feedback.agent_protocol import normalize_mission_type
from specify_cli.feedback.eligibility import claim_offer
from specify_cli.feedback.endpoint import resolve_feedback_endpoint
from specify_cli.feedback.models import CLI_HARNESS, SurveyTrigger
from specify_cli.feedback.payload import collect_context
from specify_cli.feedback.preferences import Unreadable, load_preferences, set_automatic_prompts
from specify_cli.feedback.sender import build_and_hand_off
from specify_cli.feedback.terminal_form import run_form

if TYPE_CHECKING:
    from rich.console import Console

__all__ = [
    "mission_type_for",
    "offer_after_op_close",
    "offer_after_trigger",
]

_LOG = logging.getLogger(__name__)

_FIRST_QUESTION_TIMEOUT_S = 30.0
_SEPARATOR = "[dim]── feedback ──[/dim]"
_OP_CLOSE_OUTCOMES = frozenset({"done", "failed"})


def mission_type_for(repo_root: Path, mission_slug: str) -> str | None:
    """Read ``mission_type`` from the mission's ``meta.json`` and normalize it.

    Never raises. Unknown / free-form values become ``\"other\"`` via
    :func:`normalize_mission_type`; a typeless or unreadable mission yields
    ``None``.
    """
    try:
        from specify_cli.core.constants import KITTY_SPECS_DIR
        from specify_cli.mission import get_mission_type

        feature_dir = repo_root / KITTY_SPECS_DIR / mission_slug
        raw = get_mission_type(feature_dir)
        return normalize_mission_type(raw or None)
    except Exception:
        _LOG.debug("feedback mission_type_for failed", exc_info=False)
        return None


def offer_after_op_close(
    outcome: str,
    *,
    json_output: bool,
    console: Console | None = None,
) -> None:
    """Offer after Op close when *outcome* is ``done`` or ``failed`` only."""
    if outcome not in _OP_CLOSE_OUTCOMES:
        return
    offer_after_trigger(SurveyTrigger.OP_CLOSE, json_output=json_output, console=console)


def offer_after_trigger(
    trigger: SurveyTrigger,
    *,
    json_output: bool,
    mission_type: str | None = None,
    console: Console | None = None,
) -> None:
    """Offer the Feedback Survey after a host command has finished.

    Catches :class:`BaseException` (including ``KeyboardInterrupt``) because
    the host command has already completed: Ctrl-C during this optional survey
    must not turn a successful command into a failure. ``SystemExit`` is also
    swallowed — the survey path never calls ``exit``, and any stray exit must
    not rewrite the host's recorded outcome.
    """
    try:
        _offer_body(
            trigger,
            json_output=json_output,
            mission_type=mission_type,
            console=console if console is not None else default_console,
        )
    except BaseException:
        _LOG.debug("feedback offer_after_trigger failed", exc_info=False)
        return


def _endpoint_override() -> str | None:
    prefs = load_preferences()
    if isinstance(prefs, Unreadable):
        return None
    return prefs.endpoint_override


def _offer_body(
    trigger: SurveyTrigger,
    *,
    json_output: bool,
    mission_type: str | None,
    console: Console,
) -> None:
    if json_output:
        return
    if not is_interactive():
        return
    if is_ci_env():
        return
    if not trigger.is_automatic:
        return

    resolved = resolve_feedback_endpoint(override=_endpoint_override())
    decision = claim_offer(
        trigger,
        endpoint_available=resolved.url is not None,
        interactive=True,
        ci=False,
    )
    if decision.action != "prompt":
        return

    console.print()
    console.print(_SEPARATOR)

    result = run_form(allow_never=True, first_question_timeout_s=_FIRST_QUESTION_TIMEOUT_S)
    if result.outcome in ("skipped", "declined", "aborted"):
        return
    if result.outcome == "never":
        set_automatic_prompts(False)
        console.print(wording.PROMPTS_OFF_MESSAGE)
        return
    if result.outcome != "submitted" or result.answers is None:
        return

    context = collect_context(
        trigger,
        CLI_HARNESS,
        normalize_mission_type(mission_type),
    )
    build_and_hand_off(result.answers, context, resolved, consent=True)
    console.print(wording.THANK_YOU)
