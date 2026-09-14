"""``spec-kitty zeitgeist`` (Z7-C, program-graph handle Z7-C: "Spec Kitty
subscription CLI/MCP adapters").

A thin Typer shell over ``zeitgeist_client.subscription``'s shared
status()/watch() surface — the same functions ``mcp_stdio.py``'s stdio
MCP adapter calls, so a terminal user and an MCP client observe identical
bounded-read/bounded-watch behavior over one team's live presence/focus
stream (Z7-C's own "share Z1 service" criterion). This module owns no
network logic, no credential storage, and no snapshot/frame serialization
of its own — it only formats what ``subscription.py`` returns.

``repo`` — the credential-store key — is the one team context every command
below takes. Since spec-kitty#132 keys the store by ``resolution.store_key``'s
``host/owner/repo`` (e.g. ``github.com/acme/widget``), that is the form this
adapter accepts when a key is passed, and both commands also run with no key
at all, deriving it from the current checkout's origin remote exactly as
``status/zeitgeist_bridge.py`` does (:func:`resolution.store_key_for_checkout`)
— so ``spec-kitty zeitgeist status`` inside a checkout reads that checkout's
own auto-minted credential instead of failing on a user-typed name (#137).
Neither form ever accepts a bare repo NAME: after #132 nothing is stored
under one, and matching such an entry would serve a stale pre-#132 bearer.
Neither command takes a relay URL or a bearer/capability value — the
credential comes solely from ``credentials.py``'s existing store
(``subscription.resolve_stream``). A caller whose key has no stored checkout
gets :class:`subscription.NotCheckedOut`, reported here as a clean exit-1
message, never an auto-provisioned one — this module never calls
``credentials.store``/``credentials.revoke`` (no administration).

``mcp-serve`` is registered ``hidden=True`` (not a public CLI surface a
human is meant to invoke directly) — it is the process entry point an MCP
client's own launcher runs, matching
``docs/plans/zeitgeist-client-wp01-remaining.md`` item 4's "a status/watch
sub-group plus a hidden mcp-serve command".

Item 4's ``checkout``/``focus`` subcommands are NOT part of this pass — see
this module's own scope note in
``docs/plans/zeitgeist-client-wp01-remaining.md``: ``checkout`` writes a
credential (administration, Z7-C's own node criterion forbids it here) and
``focus`` belongs to ``transport.ZeitgeistClient``'s control-envelope surface,
not the ``FilteredStream`` subscription surface this node scopes
("watch/status/subscribe").

Z8-C adds the ``outbox`` sub-group: ``list``/``show``/``approve``/``reject``/
``revoke`` over ``outbox_approval.py``'s bundled, human-gesture-gated
approval surface for locally queued Zeitgeist prose (program-graph handle
Z8-C, "Bundled outside-model approval surface"). Unlike ``status``/``watch``,
this is deliberately NOT wired into ``mcp_stdio.py`` — see that module's own
docstring and ``outbox_approval.py``'s "hard trust requirement" section for
why a model talking over MCP must have no tool that reaches it.
``approve``/``reject``/``revoke`` below take no ``--yes``/``--force``/
``--non-interactive`` option; each is a thin pass-through to
``outbox_approval.approve``/``.reject``/``.revoke``, which raise
``HumanGestureRequired`` whenever no controlling terminal is available to
capture a real human gesture — that fault, not a CLI flag, is what a
non-interactive caller here hits.

O1-C adds the ``operability`` sub-group: ``report`` (one payload-free
snapshot of ``zeitgeist_client.operability``'s offer/drop/lease/revoke/mcp/
repair signals) plus ``drill-timeout``/``drill-rotation``/``drill-rollback``
(the three local, network-free failure drills O1-C's own node criterion
names). Same "no relay-url/token option, no second implementation"
discipline as ``status``/``watch``/``outbox`` above — every subcommand here
is a thin pass-through to ``operability.py``'s functions.
"""

from __future__ import annotations

from kernel.clock import now_epoch

import asyncio
import dataclasses
import getpass
import time
import sys
import urllib.error
from pathlib import Path
from typing import Any

import typer

from specify_cli.cli.console import console
from specify_cli.zeitgeist_client import credentials, moments, operability, outbox_approval, subscription, transport

app = typer.Typer(
    name="zeitgeist",
    help=(
        "Access to one team's live Zeitgeist presence/focus stream and status-moment "
        "events, authored peer messaging (#4269), a local human-gated prose approval "
        "surface, and operability drills."
    ),
)

_REPO_ARGUMENT = typer.Argument(
    None,
    help=(
        "Credential-store key this checkout's credential is stored under, as host/owner/repo "
        "(e.g. github.com/acme/widget). Omit to derive it from the current checkout's origin remote."
    ),
)
_JSON_OPTION = typer.Option(False, "--json", help="Emit plain JSON instead of a human-readable summary.")


def _resolve_store_key(repo: str | None) -> str:
    """The credential-store key the command reads: the caller-supplied
    ``host/owner/repo``, or the one derived from the current checkout when
    omitted (#137). A bare NAME exits 1 — after #132 nothing is stored
    under one, so accepting it could only ever serve an abandoned pre-#132
    bearer. The resolver import stays function-scoped like the bridge's own
    lazy ``resolve_credentials`` import: resolution drags in the SaaS auth
    context machinery, which a mere ``--help`` run must not."""
    from specify_cli.zeitgeist_client.resolution import StoreKeyError, parse_store_key, store_key_for_checkout  # noqa: PLC0415

    if repo is not None:
        try:
            return parse_store_key(repo)
        except StoreKeyError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1) from None
    derived = store_key_for_checkout(Path.cwd())
    if derived is None:
        console.print(
            "[red]Error:[/red] could not derive a Zeitgeist credential-store key from "
            f"{Path.cwd()} — not a git checkout with a hosted origin remote. "
            "Pass host/owner/repo (e.g. github.com/acme/widget) explicitly."
        )
        raise typer.Exit(1)
    return derived


def _report_not_checked_out(exc: subscription.NotCheckedOut) -> None:
    console.print(f"[red]Error:[/red] {exc}")
    console.print(
        "[yellow]Hint:[/yellow] no Zeitgeist checkout is stored for this repo in this logical session. "
        "Run the checkout flow (a publishing command) first, then retry. Readers reuse the same session as "
        "publishing commands by default; for a distinct concurrent agent, set "
        "SPEC_KITTY_ZEITGEIST_SESSION_ID to the same value in both processes."
    )
    raise typer.Exit(1)


def _report_connection_fault(exc: BaseException) -> None:
    console.print(f"[red]Error:[/red] could not reach the relay: {exc}")
    raise typer.Exit(1)


def _observation_age(entry: dict[str, Any], *, now: float) -> str:
    """An ``observed 40s ago`` suffix for an entry the relay timestamped, and
    an empty string otherwise — a "live now" line must never imply the
    observation was made at read time (spec-kitty#4215)."""
    observed_at = entry.get("observed_at")
    if not isinstance(observed_at, (int, float)) or isinstance(observed_at, bool):
        return ""
    return f"  observed {max(0, int(now - float(observed_at)))}s ago"


def _print_snapshot_summary(result: dict[str, Any]) -> None:
    presence: list[dict[str, Any]] = result.get("presence") or []
    focus: list[dict[str, Any]] = result.get("focus") or []
    from_snapshot = result.get("source") == "relay_snapshot"
    # kernel.clock is the single door for wall-clock reads (FR-012(b));
    # `time.monotonic()` below is a duration, not a clock read, and stays.
    now = now_epoch()
    console.print(f"[bold]{result.get('repo')}[/bold]  epoch={result.get('epoch')}")
    if from_snapshot:
        console.print("  source: the relay's own record of who is live now")
    else:
        listened = result.get("listened_s")
        reason = result.get("fallback_reason")
        console.print(f"  source: listened for {listened}s — this relay served no snapshot ({reason})")
    if not presence and not focus:
        if from_snapshot:
            console.print("  nobody is live on this relay right now. That is not proof nobody is working.")
        else:
            console.print("  (nothing was published while this command listened — not the same as nobody working)")
        return
    for p in presence:
        console.print(f"  presence  {p.get('session_ref')}  user={p.get('user')}  path={p.get('path')}{_observation_age(p, now=now)}")
    for f in focus:
        console.print(f"  focus     {f.get('session_ref')}  {f.get('focus_ref')}  state={f.get('state')}{_observation_age(f, now=now)}")


@app.command()
def status(
    repo: str | None = _REPO_ARGUMENT,
    timeout: float = typer.Option(
        subscription.DEFAULT_STATUS_TIMEOUT_S,
        "--timeout",
        min=0.001,
        help=(
            "Seconds to wait for the relay, and to listen for when it serves no snapshot "
            f"(clamped to <= {subscription.MAX_TIMEOUT_S}s, the honest reported-live ceiling)."
        ),
    ),
    as_json: bool = _JSON_OPTION,
    raw: bool = typer.Option(False, "--raw", help="Include own session in the diagnostic snapshot."),
) -> None:
    """Who is live on ``repo``'s relay right now, answered immediately from
    the relay's own presence/focus record; a relay without that route falls
    back to a bounded listen."""
    key = _resolve_store_key(repo)
    try:
        result = subscription.status(key, timeout_s=timeout, filter_own=not raw)
    except subscription.NotCheckedOut as exc:
        _report_not_checked_out(exc)
        return
    except ValueError as exc:
        # Own-filter contract failures (no cached publisher identity; a relay
        # that will not confirm filtering) are explicit, named faults — the
        # same ones ``watch``/``activity`` already map this way. Reporting
        # them as "could not reach the relay" misdiagnoses a contract-
        # mandated refusal as a network problem (finding #1, PR #4224).
        console.print(str(exc), markup=False)
        raise typer.Exit(1) from None
    except (urllib.error.URLError, TimeoutError) as exc:
        _report_connection_fault(exc)
        return

    if as_json:
        console.emit_json(result)
    else:
        _print_snapshot_summary(result)


@app.command()
def watch(
    repo: str | None = _REPO_ARGUMENT,
    timeout: float = typer.Option(
        subscription.DEFAULT_WATCH_TIMEOUT_S,
        "--timeout",
        min=0.001,
        help=f"Maximum seconds for the whole watch (clamped to <= {subscription.MAX_TIMEOUT_S}s, the honest reported-live ceiling).",
    ),
    max_frames: int = typer.Option(
        subscription.MAX_WATCH_FRAMES,
        "--max-frames",
        min=1,
        help="Maximum delivered frames; agent mode scans within the timeout to count withheld frames.",
    ),
    as_json: bool = _JSON_OPTION,
    raw: bool = typer.Option(False, "--raw", help="Diagnostic stream: include own session and bypass agent filters, receipts and rate limits."),
    consumer: str | None = typer.Option(
        None, "--consumer", help="Delivery receipt context override; publisher identity still uses SPEC_KITTY_ZEITGEIST_SESSION_ID."
    ),
) -> None:
    """Print live frames plus a final summary, bounded by whole-call
    ``--timeout`` and ``--max-frames`` count."""
    key = _resolve_store_key(repo)
    started = time.monotonic()
    count = 0
    result: dict[str, Any] = {}
    policy = None
    try:
        if raw:
            frame_iter = subscription.watch(key, timeout_s=timeout, max_frames=max_frames)
        else:
            from specify_cli.zeitgeist_client.agent_delivery import AgentDelivery

            policy = AgentDelivery(key, consumer=consumer)
            result = subscription.agent_watch(key, timeout_s=timeout, max_frames=max_frames, delivery=policy)
            frame_iter = iter(result["frames"])
        for frame in frame_iter:
            count += 1
            if as_json:
                # One compact JSON object per line (JSON Lines), never the
                # multi-line pretty form status() uses — a stream of frames
                # must stay line-delimited for a caller piping this output.
                console.emit_json(frame, indent=None)
            elif frame["frame_type"] == "event":
                # An event's attrs are another client's free prose (#10): the
                # human-readable branch renders it through the same shared,
                # nonce-framed untrusted-content block the MCP adapter uses —
                # never as this tool's own trusted output. Printed with rich
                # markup DISABLED: the block's own [markers] are literal text,
                # and so is whatever prose a teammate broadcast — letting the
                # console interpret bracketed tags would both strip the frame
                # and hand hostile bytes a markup interpreter.
                console.print(subscription.render_event(frame), markup=False, highlight=False)
            else:
                console.print(f"[bold]{frame['frame_type']}[/bold]  seq={frame['seq']}  {frame['payload']}")
    except moments.MomentsDisabled as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(0) from None
    except ValueError as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(1) from None
    except subscription.NotCheckedOut as exc:
        _report_not_checked_out(exc)
    except (urllib.error.URLError, TimeoutError) as exc:
        _report_connection_fault(exc)
    except KeyboardInterrupt:
        raise typer.Exit(130) from None
    else:
        elapsed_s = time.monotonic() - started
        effective_timeout = min(timeout, float(subscription.MAX_TIMEOUT_S))
        if count >= max_frames:
            reason = "max_frames"
        elif elapsed_s >= max(0.0, effective_timeout - 0.05):
            reason = "timeout"
        else:
            reason = "stream_closed"
        summary = {
            "type": "watch_summary",
            "repo": key,
            "frames": count,
            "reason": reason,
            "elapsed_s": round(elapsed_s, 3),
            **{k: v for k, v in result.items() if k not in {"frames", "repo", "receipt"}},
        }
        if as_json:
            console.emit_json(summary, indent=None)
        else:
            console.print(f"watch summary  frames={count}  reason={reason}  elapsed_s={elapsed_s:.3f}")
            console.print({k: v for k, v in summary.items() if k not in {"type", "repo", "frames", "reason", "elapsed_s"}})
        sys.stdout.flush()
        if policy is not None:
            policy.acknowledge(result.get("receipt"))


@app.command()
def activity(
    repo: str | None = _REPO_ARGUMENT,
    window: int = typer.Option(900, "--window", min=0, help="Lookback seconds within the relay's configured retention."),
    timeout: float = typer.Option(subscription.DEFAULT_STATUS_TIMEOUT_S, "--timeout", min=0.001),
    max_frames: int = typer.Option(subscription.MAX_WATCH_FRAMES, "--max-frames", min=1),
    replay: bool = typer.Option(False, "--replay", help="Intentionally include previously acknowledged activity."),
    consumer: str | None = typer.Option(None, "--consumer", help="Stable logical agent ID shared with watch/MCP."),
    raw: bool = typer.Option(False, "--raw", help="Diagnostic read: include own session (skip relay own-session suppression)."),
    as_json: bool = _JSON_OPTION,
) -> None:
    """Catch up on retained activity using the same policy as agent watch."""
    from specify_cli.zeitgeist_client.agent_delivery import AgentDelivery

    key = _resolve_store_key(repo)
    try:
        policy = AgentDelivery(key, consumer=consumer)
        # ``--raw`` is the own-filter escape hatch parity with ``status``/
        # ``watch`` and the MCP tools' ``filter_own``: against a pre-#295
        # relay, or a session with no cached publisher identity, this is the
        # one CLI-side way to read retained activity unfiltered (finding #2,
        # PR #4224).
        result = subscription.agent_activity(key, window_s=window, timeout_s=timeout, max_frames=max_frames, replay=replay, delivery=policy, filter_own=not raw)
        if as_json:
            console.emit_json(result)
        else:
            for frame in result["frames"]:
                if frame["frame_type"] == "event":
                    console.print(subscription.render_event(frame), markup=False, highlight=False)
                else:
                    console.print(frame)
            console.print({k: v for k, v in result.items() if k not in {"frames", "receipt"}})
        sys.stdout.flush()
        policy.acknowledge(result.get("receipt"))
    except moments.MomentsDisabled as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(0) from None
    except subscription.NotCheckedOut as exc:
        _report_not_checked_out(exc)
    except (urllib.error.URLError, TimeoutError) as exc:
        _report_connection_fault(exc)
    except ValueError as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(1) from None


# --- #4269: authored peer messaging ------------------------------------------

_KIND_ARGUMENT = typer.Argument(
    ...,
    help=("Authored kind: intent, progress, question, answer, decision, handoff, blocker, resolution, next, or message (a peer reply)."),
)
_BODY_ARGUMENT = typer.Argument(..., help="Authored body text; the live wire carries at most 240 chars.")
_AUDIENCE_OPTION = typer.Option(
    None,
    "--audience",
    help="team (the default when a mission binding resolves it) or peer:<logical-session-id> to address one agent.",
)
_TRUNCATE_OPTION = typer.Option(False, "--truncate", help="Explicitly cut an oversize body to the 240-char wire bound instead of failing.")
_THREAD_OPTION = typer.Option(None, "--thread", help="Thread id; defaults to this message's own id (a new conversation's root).")


def _authored() -> Any:
    """Lazy import of the authored service — ``live_work.authored`` pulls
    ``spec_kitty_events.models`` and ``ulid``, which a bare ``--help`` or any
    unrelated command must not pay for at CLI startup."""
    from specify_cli.live_work import authored  # noqa: PLC0415

    return authored


def _print_send_result(result: Any, *, as_json: bool) -> None:
    from specify_cli.live_work.authored import DELIVERY_SCOPE_NOTE  # noqa: PLC0415

    if as_json:
        console.emit_json(result.as_dict())
        return
    outcome = result.outcome.value
    style = "green" if outcome == "accepted" else "yellow" if outcome == "offered" else "red"
    console.print(f"[{style}]{outcome}[/{style}]  message={result.message_id}  thread={result.thread}  audience={result.audience}")
    if result.reply_to:
        console.print(f"  reply_to={result.reply_to}")
    if result.truncated:
        console.print("  [yellow]body truncated to the 240-char wire bound (explicit --truncate)[/yellow]")
    if result.reason:
        console.print(f"  [yellow]{result.reason}[/yellow]", markup=False, highlight=False)
    console.print(f"  [dim]{DELIVERY_SCOPE_NOTE}[/dim]", markup=False, highlight=False)


@app.command()
def send(
    kind: str = _KIND_ARGUMENT,
    body: str = _BODY_ARGUMENT,
    audience: str | None = _AUDIENCE_OPTION,
    thread: str | None = _THREAD_OPTION,
    truncate: bool = _TRUNCATE_OPTION,
    as_json: bool = _JSON_OPTION,
) -> None:
    """Author and publish one live message (#4269) — accepted/offered/failed,
    never retained delivery."""
    from specify_cli.live_work.authored import AuthoredMessageError, SendOutcome  # noqa: PLC0415

    module = _authored()
    try:
        result = module.send(kind, body, cwd=Path.cwd(), audience=audience, thread=thread, allow_truncate=truncate)
    except moments.MomentsDisabled as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(0) from None
    except AuthoredMessageError as exc:
        console.print(f"[red]Error:[/red] {exc}", markup=False, highlight=False)
        raise typer.Exit(1) from None
    _print_send_result(result, as_json=as_json)
    if result.outcome is SendOutcome.FAILED:
        raise typer.Exit(1)


@app.command()
def reply(
    reply_to: str = typer.Argument(..., help="The message id being replied to; it must still be in the relay's recent window."),
    body: str = _BODY_ARGUMENT,
    audience: str | None = _AUDIENCE_OPTION,
    truncate: bool = _TRUNCATE_OPTION,
    as_json: bool = _JSON_OPTION,
) -> None:
    """Reply to one authored message — thread and audience come from the
    parent; a peer thread is never broadened to team scope."""
    from specify_cli.live_work.authored import AuthoredMessageError, SendOutcome  # noqa: PLC0415

    module = _authored()
    try:
        result = module.reply(reply_to, body, cwd=Path.cwd(), audience=audience, allow_truncate=truncate)
    except moments.MomentsDisabled as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(0) from None
    except AuthoredMessageError as exc:
        console.print(f"[red]Error:[/red] {exc}", markup=False, highlight=False)
        raise typer.Exit(1) from None
    _print_send_result(result, as_json=as_json)
    if result.outcome is SendOutcome.FAILED:
        raise typer.Exit(1)


def _print_message_views(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        console.emit_json(result)
        return
    for message in result["messages"]:
        console.print(message["untrusted_text"], markup=False, highlight=False)
    summary = {k: v for k, v in result.items() if k not in {"messages", "settings"}}
    console.print(summary)


@app.command()
def read(
    thread: str | None = typer.Argument(None, help="Thread id; omit to read all recent authored messages."),
    repo: str | None = _REPO_ARGUMENT,
    window: int = typer.Option(900, "--window", min=0, help="Lookback seconds within the relay's configured retention."),
    max_messages: int = typer.Option(100, "--max-messages", min=1, help="Maximum messages delivered in one read."),
    as_json: bool = _JSON_OPTION,
) -> None:
    """Read a conversation thread (or recent authored messages) from the
    relay's recent ring; bodies render inside untrusted markers."""
    module = _authored()
    key = _resolve_store_key(repo)
    try:
        result = module.read_conversation(key, thread=thread, window_s=window, max_messages=max_messages)
    except subscription.NotCheckedOut as exc:
        _report_not_checked_out(exc)
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        _report_connection_fault(exc)
        return
    _print_message_views(result, as_json=as_json)


@app.command()
def inbox(
    repo: str | None = _REPO_ARGUMENT,
    consumer: str | None = typer.Option(None, "--consumer", help="Stable logical agent ID shared with watch/activity/MCP."),
    window: int = typer.Option(900, "--window", min=0, help="Lookback seconds within the relay's configured retention."),
    max_messages: int = typer.Option(50, "--max-messages", min=1, help="Maximum messages delivered in one scan."),
    acknowledge: str | None = typer.Option(None, "--acknowledge", help="The receipt returned by a previous successful inbox call."),
    replay: bool = typer.Option(False, "--replay", help="Intentionally include previously acknowledged messages."),
    as_json: bool = _JSON_OPTION,
) -> None:
    """Addressed inbox: novel authored messages for this consumer, over the
    same novelty/receipt policy as agent watch."""
    module = _authored()
    key = _resolve_store_key(repo)
    try:
        result = module.inbox(key, consumer=consumer, window_s=window, max_messages=max_messages, acknowledge=acknowledge, replay=replay)
        _print_message_views(result, as_json=as_json)
        sys.stdout.flush()
    except moments.MomentsDisabled as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(0) from None
    except subscription.NotCheckedOut as exc:
        _report_not_checked_out(exc)
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        _report_connection_fault(exc)
        return
    receipt = result.get("receipt")
    if receipt:
        from specify_cli.live_work.authored import acknowledge_inbox  # noqa: PLC0415

        # Delivery succeeded once the output above landed — commit the
        # receipt now, exactly like the activity command does.
        acknowledge_inbox(key, receipt, consumer=consumer)


@app.command(name="mcp-serve", hidden=True)
def mcp_serve() -> None:
    """Serve the Z7-C stdio MCP adapter (``mcp_stdio.run_stdio``) until the
    client disconnects. Process entry point for an MCP client's launcher —
    not meant for direct interactive use, hence hidden.

    #190: switched off (`spec-kitty moments off`), this prints one line to
    stderr and exits 0 — stdout stays clean for the MCP framing protocol —
    rather than starting a server that would only ever look broken."""
    from specify_cli.zeitgeist_client import mcp_stdio

    asyncio.run(mcp_stdio.run_stdio())


# --- Z8-C: outbox (bundled outside-model approval surface) -----------------

outbox_app = typer.Typer(
    name="outbox",
    help="Inspect/approve/reject/revoke locally queued Zeitgeist prose. Every "
    "decision requires a real human at a real terminal — there is no --yes/"
    "--force option and no reachability from MCP or a script.",
)
app.add_typer(outbox_app, name="outbox")

_ITEM_ID_ARGUMENT = typer.Argument(..., help="The content-addressed id of the pending/decided item.")
_ACTOR_OPTION = typer.Option(None, "--actor", help="Attribution recorded on the receipt. Defaults to the local OS user.")


def _resolve_actor(actor: str | None) -> str:
    return actor if actor else getpass.getuser()


@outbox_app.command("list")
def outbox_list(
    repo: str | None = typer.Option(None, "--repo", help="Only items queued for this repo."),
    as_json: bool = _JSON_OPTION,
) -> None:
    """Every item still awaiting a human disposition. Content is shown only
    as a bounded, redacted preview — never the exact prose (use ``show`` for
    that, by exact id)."""
    items = outbox_approval.list_pending(repo=repo)
    if as_json:
        console.emit_json(
            [
                {
                    "item_id": item.item_id,
                    "repo": item.repo,
                    "audience": item.audience,
                    "content_preview": outbox_approval.redacted_preview(item.content),
                    "created_at": item.created_at,
                    "expires_at": item.expires_at,
                }
                for item in items
            ]
        )
        return
    if not items:
        console.print("(no pending items)")
        return
    for item in items:
        preview = outbox_approval.redacted_preview(item.content)
        console.print(f"[bold]{item.item_id[:12]}[/bold]  repo={item.repo}  audience={item.audience}  expires={item.expires_at}  {preview!r}")


@outbox_app.command("show")
def outbox_show(item_id: str = _ITEM_ID_ARGUMENT, as_json: bool = _JSON_OPTION) -> None:
    """The exact full record for ``item_id`` — the one explicit, per-id
    disclosure action (see ``outbox_approval.py``'s module docstring)."""
    try:
        item = outbox_approval.show(item_id)
    except outbox_approval.NotFound as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    if as_json:
        console.emit_json(dataclasses.asdict(item))
        return
    console.print(f"[bold]{item.item_id}[/bold]  status={item.status}")
    console.print(f"  repo={item.repo}  audience={item.audience}")
    console.print(f"  context={item.context}")
    console.print(f"  created_at={item.created_at}  expires_at={item.expires_at}")
    console.print("  content (exact, verbatim):")
    console.print(f"    {item.content}")


def _run_decision(item_id: str, actor: str | None, decide: Any, verb: str) -> None:
    resolved_actor = _resolve_actor(actor)
    try:
        receipt = decide(item_id, actor=resolved_actor)
    except outbox_approval.HumanGestureRequired as exc:
        console.print(f"[red]Refused:[/red] {exc}")
        raise typer.Exit(1) from None
    except outbox_approval.OutboxError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    console.print(f"[green]{verb}[/green]  item={receipt.item_id[:12]}  receipt={receipt.receipt_id[:12]}  actor={receipt.actor}")


@outbox_app.command("approve")
def outbox_approve(item_id: str = _ITEM_ID_ARGUMENT, actor: str | None = _ACTOR_OPTION) -> None:
    """Approve ``item_id``. Requires typing back the item's own challenge at
    the controlling terminal when prompted — there is no flag to skip this."""
    _run_decision(item_id, actor, outbox_approval.approve, "approved")


@outbox_app.command("reject")
def outbox_reject(item_id: str = _ITEM_ID_ARGUMENT, actor: str | None = _ACTOR_OPTION) -> None:
    """Reject ``item_id``. Same human-gesture requirement as ``approve``."""
    _run_decision(item_id, actor, outbox_approval.reject, "rejected")


@outbox_app.command("revoke")
def outbox_revoke(item_id: str = _ITEM_ID_ARGUMENT, actor: str | None = _ACTOR_OPTION) -> None:
    """Pull back an already-approved ``item_id``. Same human-gesture
    requirement as ``approve``; only valid from ``approved``."""
    _run_decision(item_id, actor, outbox_approval.revoke, "revoked")


# --- O1-C: operability (payload-free self-report + local drills) -----------

operability_app = typer.Typer(
    name="operability",
    help="Payload-free self-report of this client's liveness/connection/subscription/outbox "
    "status, plus local failure drills (relay unreachable, auth expiry, revoke fail-closed). "
    "Every subcommand here reuses zeitgeist_client.operability's signals/drills — no second "
    "implementation, no relay-url/token option, no network beyond the one optional canary "
    "offer `report` makes when repo already has a stored checkout.",
)
app.add_typer(operability_app, name="operability")


def _report_client(repo: str) -> transport.ZeitgeistClient | None:
    """Build a throwaway probe client from repo's already-stored checkout,
    if any — never a second credential source, never a --relay-url/--token
    option on this command. ``repo`` is the resolved credential-store key."""
    stored = credentials.load(repo=repo)
    if stored is None:
        return None
    return transport.ZeitgeistClient(
        transport.ClientConfig(
            relay_url=stored.relay_url,
            token=stored.token,
            # FIX-M2-15: threads the stored two-credential shape through;
            # `None` falls back to `token` for both headers unchanged.
            capability_credential=stored.capability_credential,
            harness="operability",
            session_id="operability-report",
            agent_id=None,
            repo=repo,
            branch="operability",
        )
    )


def _print_operability_report(report: operability.OperabilityReport) -> None:
    console.print(f"[bold]{report.repo}[/bold]  checked_at={report.checked_at}")
    console.print(f"  credential_checked_out={report.credential_checked_out}")
    if report.offer is None or report.drop is None:
        console.print("  offer/drop/latency: (no stored checkout — no live probe attempted)")
    else:
        response = ""
        if report.offer.status_code is not None:
            response = f" ({report.offer.status_code}"
            if report.offer.response_detail:
                response += f": {report.offer.response_detail}"
            response += ")"
        console.print(
            f"  offer     outcome={report.offer.outcome}{response}  elapsed_s={report.offer.elapsed_s:.3f}  "
            f"budget_s={report.offer.budget_s}  within_budget={report.offer.within_budget}"
        )
        console.print(f"  drop      dropped={report.drop.dropped}  reason={report.drop.reason}")
    console.print(f"  lease     active={report.lease.active}  ttl_s={report.lease.ttl_s}  remaining_s={report.lease.remaining_s}")
    console.print(f"  revoke    revocable_count={report.revoke.revocable_count}  model_reachable={report.revoke.model_reachable}")
    console.print(f"  mcp       reachable={report.mcp.reachable}  tools={list(report.mcp.tool_names)}")
    console.print(f"  repair    observed={report.repair.observed}  reset_count={report.repair.reset_count}  last_reset_reason={report.repair.last_reset_reason}")


@operability_app.command("report")
def operability_report(repo: str | None = _REPO_ARGUMENT, as_json: bool = _JSON_OPTION) -> None:
    """One payload-free snapshot of ``repo``'s operability signals. Runs a
    single canary offer probe only if ``repo`` already has a stored
    checkout — otherwise reports honestly stale/inactive rather than
    fabricating a live reading."""
    key = _resolve_store_key(repo)
    report = operability.collect_report(repo=key, client=_report_client(key))
    if as_json:
        console.emit_json(dataclasses.asdict(report))
        return
    _print_operability_report(report)


@operability_app.command("drill-timeout")
def operability_drill_timeout(as_json: bool = _JSON_OPTION) -> None:
    """Local "relay unreachable" drill — one offer() against a loopback
    address nothing listens on. Network-free (loopback only) and needs no
    repo/checkout."""
    result = operability.timeout_drill()
    if as_json:
        console.emit_json(dataclasses.asdict(result))
        return
    color = "green" if result.outcome == "pass" else "red"
    console.print(f"[{color}]{result.outcome}[/{color}]  offer={result.offer.outcome}  elapsed_s={result.offer.elapsed_s:.3f}  budget_s={result.offer.budget_s}")


@operability_app.command("drill-rotation")
def operability_drill_rotation(repo: str | None = _REPO_ARGUMENT, as_json: bool = _JSON_OPTION) -> None:
    """Local "auth expiry" drill for ``repo``'s stored checkout — reads only
    the stored ``token_issued_at`` timestamp, never the token value."""
    result = operability.rotation_drill(_resolve_store_key(repo))
    if as_json:
        console.emit_json(dataclasses.asdict(result))
        return
    console.print(
        f"[green]{result.outcome}[/green]  checked_out={result.checked_out}  age_s={result.age_s}  "
        f"rotation_window_s={result.rotation_window_s}  rotation_due={result.rotation_due}"
    )


@operability_app.command("drill-rollback")
def operability_drill_rollback(repo: str | None = _REPO_ARGUMENT, as_json: bool = _JSON_OPTION) -> None:
    """Local "rollback" drill: proves ``outbox_approval.revoke()`` fails
    closed on a never-approved item — never touches the controlling
    terminal, never requires a human."""
    result = operability.rollback_drill(repo=_resolve_store_key(repo))
    if as_json:
        console.emit_json(dataclasses.asdict(result))
        return
    color = "green" if result.outcome == "pass" else "red"
    console.print(f"[{color}]{result.outcome}[/{color}]  item={result.item_id[:12]}  blocked_reason={result.blocked_reason}")
