"""``spec-kitty feedback`` — on-demand Feedback Survey and settings.

Submissions are anonymous unless an email is typed, and are sent only after
the consent prompt ``Send feedback?``. Hidden ``--agent-*`` flags delegate to
the agent protocol service (WP04); they never appear in ``--help``.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import click
import typer

from specify_cli.cli.console import console
from specify_cli.core.env import is_interactive
from specify_cli.feedback import wording
from specify_cli.feedback.agent_protocol import agent_check, agent_choice, agent_submit
from specify_cli.feedback.endpoint import ResolvedEndpoint, describe_endpoint, resolve_feedback_endpoint
from specify_cli.feedback.models import CLI_HARNESS, SurveyTrigger
from specify_cli.feedback.payload import ALLOWED_KEYS, collect_context
from specify_cli.feedback.preferences import Unreadable, load_preferences, set_automatic_prompts
from specify_cli.feedback.sender import build_and_hand_off
from specify_cli.feedback.terminal_form import run_form

__all__ = ["feedback"]

_NON_INTERACTIVE_HINT = "Run this from a terminal, or ask your agent to collect feedback."
_TRIGGER_CHOICES = click.Choice(
    [t.value for t in SurveyTrigger],
    case_sensitive=True,
)
_PROMPTS_CHOICES = click.Choice(["on", "off"], case_sensitive=False)
_AGENT_CHOICE_CHOICES = click.Choice(["skip", "never"], case_sensitive=True)
_AgentChoice = Literal["skip", "never"]


def _redact_url_userinfo(url: str) -> str:
    """Strip URL userinfo so credentials never appear in ``--status`` output."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if parts.username is None and parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def _endpoint_override() -> str | None:
    prefs = load_preferences()
    if isinstance(prefs, Unreadable):
        return None
    return prefs.endpoint_override


def _status_payload() -> dict[str, Any]:
    prefs = load_preferences()
    override = None if isinstance(prefs, Unreadable) else prefs.endpoint_override
    resolved = resolve_feedback_endpoint(override=override)
    display_url = _redact_url_userinfo(resolved.url) if resolved.url is not None else None
    display = ResolvedEndpoint(
        url=display_url,
        source=resolved.source,
        rejected_reason=resolved.rejected_reason,
    )
    fields = sorted(ALLOWED_KEYS)
    if isinstance(prefs, Unreadable):
        return {
            "endpoint": describe_endpoint(display),
            "endpoint_source": resolved.source,
            "fields": fields,
            "last_shown_at": None,
            "automatic_prompts": None,
            "preferences_unreadable": prefs.reason,
        }
    last = prefs.last_shown_at.isoformat() if prefs.last_shown_at is not None else None
    return {
        "endpoint": describe_endpoint(display),
        "endpoint_source": resolved.source,
        "fields": fields,
        "last_shown_at": last,
        "automatic_prompts": prefs.automatic_prompts,
        "preferences_unreadable": None,
    }


def _print_status(*, as_json: bool) -> None:
    payload = _status_payload()
    if as_json:
        sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
        return
    console.print(f"Destination: {payload['endpoint']}")
    console.print(f"Fields: {', '.join(payload['fields'])}")
    last = payload["last_shown_at"]
    console.print(f"Last shown: {last if last is not None else 'never'}")
    prompts = payload["automatic_prompts"]
    if prompts is None:
        console.print("Automatic prompts: unknown")
    else:
        console.print(f"Automatic prompts: {'on' if prompts else 'off'}")
    note = payload["preferences_unreadable"]
    if note:
        console.print(f"Preferences note: {note}")


def _parse_trigger(raw: str | None) -> SurveyTrigger:
    if raw is None:
        console.print("[red]Error:[/red] --trigger is required for agent mode.")
        raise typer.Exit(2)
    try:
        return SurveyTrigger(raw)
    except ValueError:
        console.print(f"[red]Error:[/red] invalid --trigger {raw!r}.")
        raise typer.Exit(2) from None


def _emit_json(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def _dispatch_hidden(
    *,
    agent_check_flag: bool,
    agent_submit_flag: bool,
    agent_choice_raw: str | None,
    trigger_raw: str | None,
    agent: str | None,
    rating: str | None,
    comment: str | None,
    email: str | None,
    consent: str | None,
    as_json: bool,
) -> None:
    """Handle mutually exclusive hidden agent modes; return only when idle."""
    modes = sum(
        (
            int(agent_check_flag),
            int(agent_submit_flag),
            int(agent_choice_raw is not None),
        )
    )
    if modes == 0:
        return
    if modes > 1:
        console.print("[red]Error:[/red] --agent-check, --agent-submit, and --agent-choice are mutually exclusive.")
        raise typer.Exit(2)

    trigger = _parse_trigger(trigger_raw)

    if agent_check_flag:
        payload = agent_check(trigger, agent)
        _emit_json(payload) if as_json else console.print(json.dumps(payload, sort_keys=True))
        raise typer.Exit(0)

    if agent_submit_flag:
        payload = agent_submit(
            trigger,
            agent,
            rating=rating,
            comment=comment,
            email=email,
            consent=consent,
        )
        _emit_json(payload) if as_json else console.print(json.dumps(payload, sort_keys=True))
        raise typer.Exit(0)

    assert agent_choice_raw is not None
    # click.Choice already restricted to skip|never before dispatch reaches here.
    choice: _AgentChoice = "skip" if agent_choice_raw == "skip" else "never"
    payload = agent_choice(choice, trigger)
    _emit_json(payload) if as_json else console.print(json.dumps(payload, sort_keys=True))
    raise typer.Exit(0)


def _run_bare_form() -> None:
    resolved = resolve_feedback_endpoint(override=_endpoint_override())
    if resolved.url is None:
        console.print(wording.NO_ENDPOINT_MESSAGE)
        raise typer.Exit(0)
    if not is_interactive():
        console.print(_NON_INTERACTIVE_HINT)
        raise typer.Exit(0)

    result = run_form(allow_never=False)
    if result.outcome != "submitted" or result.answers is None:
        if result.outcome == "declined":
            console.print(wording.NOT_SENT_MESSAGE)
        raise typer.Exit(0)

    context = collect_context(SurveyTrigger.ON_DEMAND, CLI_HARNESS, None)
    build_and_hand_off(result.answers, context, resolved, consent=True)
    console.print(wording.THANK_YOU)
    raise typer.Exit(0)


def feedback(
    status: bool = typer.Option(
        False,
        "--status",
        help="Show the effective destination, fields sent, last-shown date, and automatic prompts.",
    ),
    prompts: str | None = typer.Option(
        None,
        "--prompts",
        help="Turn automatic feedback prompts on or off.",
        click_type=_PROMPTS_CHOICES,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON for --status or hidden agent modes.",
    ),
    agent_check_flag: bool = typer.Option(
        False,
        "--agent-check",
        help="Agent: decide whether to present the survey.",
        hidden=True,
    ),
    agent_submit_flag: bool = typer.Option(
        False,
        "--agent-submit",
        help="Agent: submit validated survey answers.",
        hidden=True,
    ),
    agent_choice_raw: str | None = typer.Option(
        None,
        "--agent-choice",
        help="Agent: record skip or never.",
        hidden=True,
        click_type=_AGENT_CHOICE_CHOICES,
    ),
    trigger_raw: str | None = typer.Option(
        None,
        "--trigger",
        help="Survey trigger for hidden agent modes.",
        hidden=True,
        click_type=_TRIGGER_CHOICES,
    ),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="Harness / agent key for hidden agent modes.",
        hidden=True,
    ),
    rating: str | None = typer.Option(
        None,
        "--rating",
        help="Rating 1-5 for --agent-submit.",
        hidden=True,
    ),
    comment: str | None = typer.Option(
        None,
        "--comment",
        help="Optional comment for --agent-submit.",
        hidden=True,
    ),
    email: str | None = typer.Option(
        None,
        "--email",
        help="Optional email for --agent-submit.",
        hidden=True,
    ),
    consent: str | None = typer.Option(
        None,
        "--consent",
        help="Must be the exact string 'yes' for --agent-submit.",
        hidden=True,
    ),
) -> None:
    """Offer the Feedback Survey on demand, or inspect / toggle settings.

    Submissions are anonymous unless an email is typed, and are sent only after
    ``Send feedback?``. Automatic prompts ignore the weekly limit for this
    on-demand command. Prefer ``--status`` to see the destination; the consent
    step never prints a URL.
    """
    if status and prompts is not None:
        console.print("[red]Error:[/red] --status and --prompts are mutually exclusive.")
        raise typer.Exit(2)

    _dispatch_hidden(
        agent_check_flag=agent_check_flag,
        agent_submit_flag=agent_submit_flag,
        agent_choice_raw=agent_choice_raw,
        trigger_raw=trigger_raw,
        agent=agent,
        rating=rating,
        comment=comment,
        email=email,
        consent=consent,
        as_json=as_json,
    )

    if status:
        _print_status(as_json=as_json)
        raise typer.Exit(0)

    if prompts is not None:
        enabled = prompts.casefold() == "on"
        set_automatic_prompts(enabled)
        console.print(f"Automatic prompts: {'on' if enabled else 'off'}")
        raise typer.Exit(0)

    _run_bare_form()
