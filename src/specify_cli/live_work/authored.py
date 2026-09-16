"""#4269's authored-message service — CLI/MCP send, reply, read, inbox.

One shared application service behind the ``spec-kitty zeitgeist
send/reply/read/inbox`` commands and the MCP ``zeitgeist_send``/
``zeitgeist_reply``/``zeitgeist_read``/``zeitgeist_inbox`` tools: neither
adapter re-derives publishing, parent lookup, or bounded retrieval — "share
Z1 service" is the same criterion the subscription surface
(:mod:`specify_cli.zeitgeist_client.subscription`) already holds.

Scope (the 2026-09-14 ruling, ``HIC-ZEITGEIST-NOW-GIT-DONE-2026-09-14.md``):
authored messages are **live relay frames only**. There is no durable queue,
no journal, no offline outbox and no conversation archive — a message that
never reached the relay is failed, not parked, and a message that reached it
ages out with the ring. A decision's permanent record is the Git ledger
(``spec-kitty decision``); the ``decision`` kind here is the live frame that
accompanies it, never the record itself. That is why
:data:`DELIVERY_SCOPE_NOTE` rides every send result: the outcome vocabulary
(``accepted``/``offered``/``failed``) describes the *live* offer, never
retained delivery.

Authored vs captured (:mod:`live_work.kinds`'s split): these frames are
published only through this explicit call surface — a human or agent naming
its kind and body — never by a capture hook, because model private reasoning
is never narrative (content-safety rule,
``decisions/HIC-LIVE-WORK-DURABLE-ZEITGEIST-2026-09-13.md``). The closed
vocabulary is the shared contract's nine ``narrative.*`` kinds plus
``message.peer_sent``; the glossary's wider list ("review finding",
"retrospective learning") has no contract kind, and a "finding" is refused as
:attr:`AuthoredMessageError` code ``unsupported_kind`` rather than inventing
one the contract does not define.

Body discipline: the wire carries at most :data:`MAX_BODY_CHARS` (the relay's
own attr-value bound). An oversize body fails with ``oversize_body`` unless
the caller explicitly asked for truncation — an accidental whole-frame drop
is exactly what an explicit ``--truncate`` avoids, and an explicit cut is
reported as ``truncated`` rather than presented as complete content. A body
whose *content* is secret material is refused outright
(:func:`live_work.redaction.secret_material_reason`) — publishing
``[redacted]`` as someone's authored words would be a false message, not a
safe one.

Send/reply publish through the existing live path
(:func:`live_work.publisher.project_args` →
:meth:`specify_cli.zeitgeist_client.transport.ZeitgeistClient.offer`), with
one #4269 addition: a **stable contribution id**. The message id (a canonical
ULID event id) rides ``attrs["event_id"]`` AND the ControlEnvelope's
``request_id``, so the relay's replay cache dedupes a bounded retry
server-side — a re-offer of the same id returns the original answer and never
re-executes. Retries are bounded (:data:`MAX_SEND_ATTEMPTS`) and never claim
retained delivery; an offline relay is reported ``failed`` after them, per
the issue's acceptance criteria.

Read discipline: ``read_conversation``/``inbox`` read only the relay's recent
ring (:func:`specify_cli.zeitgeist_client.history.read_history`), bounded in
window, pages and message count. Message bodies are third-party content —
they reach an agent only inside :func:`subscription.render_event`'s
nonce-framed untrusted block, and reading a message grants no authority to
execute it. ``inbox`` reuses the #4216 novelty/receipt machinery
(:class:`specify_cli.zeitgeist_client.agent_delivery.AgentDelivery`) — same
consumer identity, same receipts, same rate cap — narrowed to authored
messages addressed to this consumer (team-wide or ``peer:<this logical
session>``); a peer thread is never broadened to team scope, and own
messages are suppressed by the relay's verified own-session filtering.
"""

from __future__ import annotations

import re
import time
import urllib.error
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kernel.clock import now_utc
from spec_kitty_events.models import normalize_event_id
from ulid import ULID

from .bindings import ResolvedBindings
from .kinds import WorkEmissionKind, payload_id
from .models import ActorBinding, Observation, Provenance, SessionBinding
from .publisher import MAX_ATTRS, project_args
from .redaction import MAX_SUMMARY_CHARS, secret_material_reason

if TYPE_CHECKING:
    # Import-graph only: the typed client stays a function-scoped import at
    # runtime (publisher.py's discipline), but the signatures below name it.
    from specify_cli.zeitgeist_client.transport import OfferResult, ZeitgeistClient

__all__ = [
    "AuthoredMessageError",
    "DELIVERY_SCOPE_NOTE",
    "MAX_BODY_CHARS",
    "MAX_SEND_ATTEMPTS",
    "SendOutcome",
    "SendResult",
    "acknowledge_inbox",
    "inbox",
    "read_conversation",
    "reply",
    "send",
]


DELIVERY_SCOPE_NOTE = "live relay ring only; delivery is never retained and ages out with the ring"
"""The one-line honesty note every send result carries (#4269's no-retention
ruling) — the outcome describes the live offer, never durable recording."""

MAX_BODY_CHARS = MAX_SUMMARY_CHARS
"""The authored-body bound: the relay's own attr-value ceiling (240). The
command summaries :mod:`live_work.redaction` builds already ride the same
bound; an authored body is not a summary but travels the same wire."""

MAX_SEND_ATTEMPTS = 3
"""Bounded retry: an authored send re-offers the SAME contribution id at most
this many times before reporting the outcome. The relay's replay cache makes
every re-offer idempotent, so a retry can never double-apply."""

_RETRY_PAUSE_S = 0.25
"""Per-attempt pause (scaled by attempt): short, because the send is an
interactive command, not a background drain."""

_EVENT_PUBLISH_OP = "event.publish"
_HARNESS_ID = "spec-kitty-cli"
_PROVENANCE_CAPABILITY = "live-work.authored"

# The relay's ControlEnvelope request_id grammar, restated for thread ids —
# a thread id travels as an attr VALUE (≤240), but keeping it ident-shaped
# means it is stable, comparable and never mistaken for free prose.
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}")

# The logical-session selector grammar (session_identity._SESSION_PATTERN),
# restated: a `peer:` audience names one logical agent by exactly the id a
# harness would set SPEC_KITTY_ZEITGEIST_SESSION_ID to.
_PEER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

_AUTHORED_TOKENS: dict[str, WorkEmissionKind] = {
    "intent": WorkEmissionKind.NARRATIVE_INTENT_DECLARED,
    "progress": WorkEmissionKind.NARRATIVE_PROGRESS_REPORTED,
    "question": WorkEmissionKind.NARRATIVE_QUESTION_ASKED,
    "answer": WorkEmissionKind.NARRATIVE_QUESTION_ANSWERED,
    "decision": WorkEmissionKind.NARRATIVE_DECISION_RECORDED,
    "handoff": WorkEmissionKind.NARRATIVE_HANDOFF_PERFORMED,
    "blocker": WorkEmissionKind.NARRATIVE_BLOCKER_RAISED,
    "resolution": WorkEmissionKind.NARRATIVE_BLOCKER_RESOLVED,
    "next": WorkEmissionKind.NARRATIVE_NEXT_PROPOSED,
    "message": WorkEmissionKind.MESSAGE_PEER_SENT,
}
"""The CLI/MCP kind tokens → the closed emission vocabulary. The token set is
the issue's authored-intent list; the wire kind is always the shared
contract's ``work.<kind>.v<lineage>`` payload id."""

_TOKEN_BY_WIRE_ID: dict[str, str] = {payload_id(emission): token for token, emission in _AUTHORED_TOKENS.items()}
"""Reverse map for the read side: a frame is an authored message exactly when
its wire kind is one of this module's payload ids — anything else (a status
moment, a capture frame, a hostile string) is not ours to interpret."""

# Read-side bounds: same page ceiling and whole-call deadline shape
# subscription.agent_activity already holds (its 20-page / bounded-deadline
# loop is the proven idiom; these are the authored surface's own constants).
_MAX_HISTORY_PAGES = 20
_READ_DEADLINE_S = 10.0
_PARENT_LOOKUP_WINDOW_S = 900


class AuthoredMessageError(Exception):
    """A typed authored-message refusal — never a traceback, never a silent
    drop. ``code`` names the failure class; the message never echoes message
    content (an unsafe body's category is reported, not the body)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class SendOutcome(StrEnum):
    """The honest three-way send outcome — never "sent", never "recorded"."""

    ACCEPTED = "accepted"  # relay returned 2xx for this exact contribution id
    OFFERED = "offered"  # relay answered without confirming application (throttle); the stable id makes a re-offer idempotent
    FAILED = "failed"  # bounded attempts exhausted, or the relay definitively refused


@dataclass(frozen=True)
class SendResult:
    """One authored send's outcome — what was offered, never what was kept."""

    outcome: SendOutcome
    kind: str  # the CLI/MCP token, not the wire payload id
    message_id: str  # the stable contribution id (canonical ULID event id)
    thread: str
    audience: str
    reply_to: str | None = None
    truncated: bool = False
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """The JSON-safe projection both adapters return; always carries the
        delivery-scope note so no consumer can read "accepted" as "stored"."""
        return {
            "outcome": self.outcome.value,
            "kind": self.kind,
            "message_id": self.message_id,
            "thread": self.thread,
            "audience": self.audience,
            "reply_to": self.reply_to,
            "truncated": self.truncated,
            "reason": self.reason,
            "delivery_scope": DELIVERY_SCOPE_NOTE,
        }


# --- validation ---------------------------------------------------------------


def _require_moments_enabled() -> None:
    """The explicit opt-out is honored on the authored surface too: a
    developer who switched moments off did not opt into peer messaging.
    Raises the same :class:`moments.MomentsDisabled` the read surfaces raise,
    so every adapter reports it as one line, never a traceback."""
    from specify_cli.zeitgeist_client import moments  # noqa: PLC0415

    settings = moments.load_settings()
    if settings.agents is moments.MomentsMode.OFF:
        raise moments.MomentsDisabled(settings)


def _resolve_kind(kind: str) -> WorkEmissionKind:
    emission = _AUTHORED_TOKENS.get(kind.strip().lower())
    if emission is None:
        raise AuthoredMessageError(
            "unsupported_kind",
            f"{kind.strip()!r} is not authored vocabulary; supported kinds: {', '.join(sorted(_AUTHORED_TOKENS))} "
            "(a 'finding' has no contract kind — file it, do not narrate it)",
        )
    return emission


def _bounded_body(body: str, *, allow_truncate: bool) -> tuple[str, bool]:
    """The body that will be published, and whether it was explicitly cut.

    Both the full input and the published text must pass the secret gate: a
    credential that starts inside the first 240 characters is refused before
    truncation could launder its tail into the wire."""
    if not isinstance(body, str) or not body.strip():
        raise AuthoredMessageError("invalid_body", "an authored message needs body text — the prose is the observation")
    reason = secret_material_reason(body)
    if reason is not None:
        raise AuthoredMessageError(
            "unsafe_body",
            f"the body looks like a {reason}; authored messages never publish secret material (category reported, never the content)",
        )
    if len(body) <= MAX_BODY_CHARS:
        return body, False
    if not allow_truncate:
        raise AuthoredMessageError(
            "oversize_body",
            f"body is {len(body)} chars; the live wire carries at most {MAX_BODY_CHARS} — pass --truncate/allow_truncate to cut it explicitly",
        )
    truncated = body[:MAX_BODY_CHARS]
    tail_reason = secret_material_reason(truncated)
    if tail_reason is not None:
        raise AuthoredMessageError("unsafe_body", f"the truncated body still looks like a {tail_reason}; cut the secret out yourself or do not send it")
    return truncated, True


def _resolve_audience(audience: str | None, *, default: str = "team") -> str:
    if audience is None:
        return default
    if audience == "team":
        return audience
    peer = audience.removeprefix("peer:")
    if peer != audience and _PEER_RE.fullmatch(peer):
        return audience
    raise AuthoredMessageError("invalid_audience", "audience is 'team' or 'peer:<logical-session-id>' — an authored message never addresses anything else")


def _validated_id(value: str, *, code: str, what: str) -> str:
    if not _ID_RE.fullmatch(value):
        raise AuthoredMessageError(code, f"{what} must be a 1-64 char identifier of letters, digits, '.', '_', '@', '+', '-' (the relay envelope's own id grammar)")
    return value


def _mint_message_id() -> str:
    """A canonical ULID event id — the stable contribution id. It rides the
    envelope's ``request_id`` (idempotent replay) and ``attrs['event_id']``
    (the novelty machinery's canonical identity), so both dedupe on the same
    value; ``normalize_event_id`` asserts the mint is canonical."""
    return normalize_event_id(str(ULID()))


def _logical_session() -> str:
    from specify_cli.zeitgeist_client import session_identity  # noqa: PLC0415

    try:
        session_id: str = session_identity.logical_session_id()
    except ValueError as exc:
        raise AuthoredMessageError("invalid_session", str(exc)) from None
    return session_id


# --- publishing ---------------------------------------------------------------


def _observation(emission: WorkEmissionKind, text: str, bindings: ResolvedBindings) -> Observation:
    """The capture-record-shaped authored observation. ``source="manual"`` is
    the honest provenance: an explicit human/agent call site, never a capture
    hook; the authenticated principal stays server-derived, so no actor claim
    rides the frame."""
    if bindings.repository is None:
        raise AuthoredMessageError(
            "unbound_context",
            "no repository binding for this checkout — an authored message is always repo/mission bound, never free-floating",
        )
    return Observation(
        kind=emission,
        session=SessionBinding(session_id=_logical_session()),
        actor=ActorBinding(harness=_HARNESS_ID),
        repository=bindings.repository,
        mission=bindings.mission,
        text=text,
        provenance=Provenance(source="manual", capability=_PROVENANCE_CAPABILITY),
        occurred_at=now_utc().isoformat(),
    )


def _inject_authored_attrs(args: dict[str, Any], *, message_id: str, thread: str, audience: str, reply_to: str | None) -> None:
    """Add the authored-message wire metadata to a projected arg set.

    ``event_id`` is deliberately NOT x-namespaced: it is the canonical event
    identity the novelty/receipt machinery already dedupes on. The rest ride
    the x-namespaced attr surface alongside the publisher's own ``x-text``.
    """
    attrs: dict[str, Any] = dict(args["attrs"])
    attrs["event_id"] = message_id
    attrs["x-thread"] = thread
    attrs["x-audience"] = audience
    if reply_to is not None:
        attrs["x-reply-to"] = reply_to
    if len(attrs) > MAX_ATTRS:
        raise AuthoredMessageError("attrs_budget", f"the projected frame carries {len(attrs)} attrs; the relay wire bound is {MAX_ATTRS}")
    args["attrs"] = attrs


def _offer_with_bounded_retry(client: ZeitgeistClient, args: dict[str, Any], message_id: str) -> tuple[SendOutcome, str | None]:
    """Offer until sent, definitively refused, or attempts exhausted.

    A definitive refusal (relay 4xx/5xx, local sanitizer) never retries —
    retrying an unauthorized audience or a revoked thread would only hammer
    the door the relay just closed. Throttle and transport drops retry on the
    SAME contribution id, which the relay's replay cache makes idempotent.
    """
    from specify_cli.zeitgeist_client.transport import OfferOutcome  # noqa: PLC0415

    last: OfferResult | None = None
    for attempt in range(MAX_SEND_ATTEMPTS):
        result = client.offer(_EVENT_PUBLISH_OP, args, request_id=message_id)
        if result.outcome is OfferOutcome.SENT:
            return SendOutcome.ACCEPTED, None
        if result.outcome in (OfferOutcome.REJECTED, OfferOutcome.REFUSED_LOCAL):
            return SendOutcome.FAILED, _failure_reason(result)
        last = result
        if attempt + 1 < MAX_SEND_ATTEMPTS:
            time.sleep(_RETRY_PAUSE_S * (attempt + 1))
    if last is not None and last.outcome is OfferOutcome.THROTTLED:
        return (
            SendOutcome.OFFERED,
            "relay throttled the offer without confirming application; re-offering the same message id is idempotent within the live window",
        )
    assert last is not None  # MAX_SEND_ATTEMPTS >= 1, so one offer always ran
    return SendOutcome.FAILED, _failure_reason(last)


def _failure_reason(result: OfferResult) -> str:
    detail = f"; relay said: {result.response_detail}" if result.response_detail else ""
    return f"offer {result.outcome.value} (request_id {result.request_id}) after {MAX_SEND_ATTEMPTS} bounded attempt(s){detail}"


def _publish(
    observation: Observation,
    *,
    cwd: Path,
    message_id: str,
    thread: str,
    audience: str,
    reply_to: str | None,
) -> tuple[SendOutcome, str | None]:
    """One observation onto the existing relay path, with the stable id.

    Credential resolution is the publisher's own: an unresolvable checkout
    (no team, not admitted, no network to Team Kitty) is a typed refusal
    here — unlike capture hooks, an authored send has a caller waiting for
    an honest answer, so "silently drop" is not an option.
    """
    from specify_cli.zeitgeist_client import repo_identity, resolution  # noqa: PLC0415
    from specify_cli.zeitgeist_client.transport import ClientConfig, ZeitgeistClient  # noqa: PLC0415

    deadline = repo_identity.Deadline()
    credential = resolution.resolve_credentials(cwd, deadline=deadline)
    if credential is None:
        raise AuthoredMessageError(
            "not_admitted",
            "no relay credentials for this checkout (repo not admitted or nothing configured) — an authored message produces nothing anywhere until it is",
        )
    args = project_args(observation)
    _inject_authored_attrs(args, message_id=message_id, thread=thread, audience=audience, reply_to=reply_to)
    client = ZeitgeistClient(
        ClientConfig(
            relay_url=credential.relay_url,
            token=credential.token,
            harness=_HARNESS_ID,
            session_id=observation.session.session_id,
            agent_id=None,
            repo="",
            branch="",
            capability_credential=credential.capability_credential,
        )
    )
    return _offer_with_bounded_retry(client, args, message_id)


def _send_prepared(
    emission: WorkEmissionKind,
    token: str,
    text: str,
    *,
    cwd: Path,
    audience: str | None,
    thread: str | None,
    reply_to: str | None,
    truncated: bool,
) -> SendResult:
    # Call-time attribute lookup, deliberately: the shared binding resolver is
    # the seam tests (and future callers) patch without reaching into here.
    from . import bindings  # noqa: PLC0415

    resolved = bindings.resolve_bindings(cwd)
    message_id = _mint_message_id()
    resolved_thread = _validated_id(thread, code="invalid_thread", what="thread id") if thread is not None else message_id
    resolved_audience = _resolve_audience(audience)
    observation = _observation(emission, text, resolved)
    outcome, reason = _publish(
        observation,
        cwd=cwd,
        message_id=message_id,
        thread=resolved_thread,
        audience=resolved_audience,
        reply_to=reply_to,
    )
    return SendResult(
        outcome=outcome,
        kind=token,
        message_id=message_id,
        thread=resolved_thread,
        audience=resolved_audience,
        reply_to=reply_to,
        truncated=truncated,
        reason=reason,
    )


def send(
    kind: str,
    body: str,
    *,
    cwd: Path,
    audience: str | None = None,
    thread: str | None = None,
    allow_truncate: bool = False,
) -> SendResult:
    """Author and publish one live message (#4269). The thread defaults to
    the message's own id — a new conversation's root."""
    _require_moments_enabled()
    emission = _resolve_kind(kind)
    text, truncated = _bounded_body(body, allow_truncate=allow_truncate)
    return _send_prepared(
        emission,
        kind.strip().lower(),
        text,
        cwd=cwd,
        audience=audience,
        thread=thread,
        reply_to=None,
        truncated=truncated,
    )


def reply(
    reply_to: str,
    body: str,
    *,
    cwd: Path,
    audience: str | None = None,
    allow_truncate: bool = False,
) -> SendResult:
    """Reply to one authored message by its id.

    Thread and audience come from the parent: a peer thread is never
    broadened to team scope, and an explicitly passed audience must be the
    parent's own. The parent must still be in the relay's recent window —
    there is no durable history to reply from, and saying so is the typed
    ``unknown_parent`` failure.
    """
    _require_moments_enabled()
    parent_id = _validated_id(reply_to, code="invalid_reply_to", what="reply_to message id")
    text, truncated = _bounded_body(body, allow_truncate=allow_truncate)
    parent = _lookup_parent(cwd, parent_id)
    # A parent frame that carries no audience attr reads as team-scope on
    # every surface (the sender's own default); the reply inherits that same
    # effective audience, never a broader one.
    inherited_audience = parent["audience"] or "team"
    if audience is not None and audience != inherited_audience:
        raise AuthoredMessageError(
            "invalid_audience",
            "a reply inherits its audience from the parent message — pass no audience to keep it, never a different one (a peer thread is never broadened)",
        )
    return _send_prepared(
        WorkEmissionKind.MESSAGE_PEER_SENT,
        "message",
        text,
        cwd=cwd,
        audience=inherited_audience,
        thread=parent["thread"],
        reply_to=parent_id,
        truncated=truncated,
    )


def _lookup_parent(cwd: Path, parent_id: str) -> dict[str, Any]:
    """Find the parent message in the relay's recent ring, or refuse typed.

    The read is the read surfaces' own: this checkout's credential-store key
    → :func:`history.read_history` under the same bounded window. Every
    environmental failure (no stored credential, relay fault, protocol
    damage) is a typed authored failure — the reply command has no other
    error channel.
    """
    from specify_cli.zeitgeist_client import subscription  # noqa: PLC0415
    from specify_cli.zeitgeist_client.resolution import store_key_for_checkout  # noqa: PLC0415

    key = store_key_for_checkout(cwd)
    if key is None:
        raise AuthoredMessageError(
            "unbound_context",
            "could not derive a Zeitgeist credential-store key from this checkout — not a git checkout with a hosted origin remote",
        )
    try:
        frames, _coverage = _authored_history(key, window_s=_PARENT_LOOKUP_WINDOW_S, filter_own=False)
    except subscription.NotCheckedOut as exc:
        raise AuthoredMessageError("not_checked_out", str(exc)) from None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AuthoredMessageError("unretrievable_parent", f"could not read the relay's recent ring to find the parent message: {exc}") from None
    for frame in frames:
        message = _message_from_frame(frame)
        if message is not None and message["message_id"] == parent_id:
            return message
    raise AuthoredMessageError("unknown_parent", f"message {parent_id} is not in the relay's recent window — there is no durable history to reply from")


# --- reading ------------------------------------------------------------------


def _authored_history(repo: str, *, window_s: int, filter_own: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bounded retained pages from the relay's recent ring.

    Same shape as ``subscription.agent_activity``'s retained-reader loop: a
    whole-call deadline, a page ceiling, honest continuation handling, and
    coverage that says what the ring itself said (gaps, truncation, reset)
    rather than claiming completeness.
    """
    from specify_cli.zeitgeist_client import history  # noqa: PLC0415

    coverage: dict[str, Any] = {}
    frames: list[dict[str, Any]] = []
    since: str | None = None
    deadline = time.monotonic() + _READ_DEADLINE_S
    for _ in range(_MAX_HISTORY_PAGES):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            coverage["scan_limit_reached"] = True
            break
        page = history.read_history(repo, window_s=window_s, timeout_s=remaining, since=since, filter_own=filter_own)
        previous_gap = coverage.get("gap")
        previous_reset = coverage.get("reset", False)
        coverage.update(page["coverage"])
        coverage["gap"] = coverage.get("gap") or previous_gap
        coverage["reset"] = coverage.get("reset", False) or previous_reset
        frames.extend(page["frames"])
        continuation = coverage.get("continuation")
        if continuation is None:
            break
        if continuation == since:
            raise ValueError("History continuation made no progress")
        since = continuation
    else:
        coverage["scan_limit_reached"] = True
    return frames, coverage


def _bounded_attr(value: Any) -> str | None:
    """One attr value as a bounded string, or ``None`` — a hostile frame's
    attr is data (clamped like ``render_event`` clamps it), never trusted."""
    if not isinstance(value, str) or not value:
        return None
    return value[:MAX_SUMMARY_CHARS]


def _message_from_frame(frame: Mapping[str, Any]) -> dict[str, Any] | None:
    """One authored message projected from a serialized event frame, or
    ``None`` when the frame is not ours to interpret.

    The structured fields are bounded/clamped data; the body prose travels
    ONLY inside ``untrusted_text`` — :func:`subscription.render_event`'s
    nonce-framed block, the same rendering every other agent-facing event
    surface uses, never re-derived here.
    """
    from specify_cli.zeitgeist_client import subscription  # noqa: PLC0415

    if frame.get("frame_type") != "event":
        return None
    payload = frame.get("payload")
    if not isinstance(payload, Mapping):
        return None
    wire_kind = payload.get("kind")
    token = _TOKEN_BY_WIRE_ID.get(wire_kind) if isinstance(wire_kind, str) else None
    if token is None:
        return None
    attrs = payload.get("attrs")
    if not isinstance(attrs, Mapping):
        attrs = {}
    message_id = _bounded_attr(attrs.get("event_id"))
    cleaned = subscription.sanitized_event_payload(payload)
    return {
        "message_id": message_id,
        "thread": _bounded_attr(attrs.get("x-thread")) or message_id,
        "reply_to": _bounded_attr(attrs.get("x-reply-to")),
        "kind": token,
        "audience": _bounded_attr(attrs.get("x-audience")),
        "actor": cleaned.get("actor"),
        "emitted_at": frame.get("emitted_at"),
        "seq": frame.get("seq"),
        "untrusted_text": subscription.render_event(frame),
    }


def read_conversation(
    repo: str,
    *,
    thread: str | None = None,
    window_s: int = 900,
    max_messages: int = 100,
) -> dict[str, Any]:
    """Read one conversation thread (or all recent authored messages) from
    the relay's recent ring. Own messages are included — a conversation shows
    both sides; the addressed :func:`inbox` is the novelty-filtered view.

    Raises :class:`subscription.NotCheckedOut` when ``repo`` has no stored
    credential, and propagates relay faults unchanged — the same contract the
    read surfaces already hold.
    """
    if max_messages < 1:
        raise ValueError("max_messages must be >= 1")
    frames, coverage = _authored_history(repo, window_s=window_s, filter_own=False)
    messages: list[dict[str, Any]] = []
    withheld = {"not_authored": 0, "thread": 0, "budget": 0}
    for frame in frames:
        message = _message_from_frame(frame)
        if message is None:
            withheld["not_authored"] += 1
            continue
        if thread is not None and message["thread"] != thread:
            withheld["thread"] += 1
            continue
        if len(messages) >= max_messages:
            withheld["budget"] += 1
            continue
        messages.append(message)
    return {"repo": repo, "thread": thread, "messages": messages, "withheld": withheld, "coverage": coverage}


def inbox(
    repo: str,
    *,
    consumer: str | None = None,
    window_s: int = 900,
    max_messages: int = 50,
    acknowledge: str | None = None,
    replay: bool = False,
) -> dict[str, Any]:
    """Addressed inbox: novel authored messages for this consumer —
    team-wide messages and ``peer:<this logical session>`` messages, own
    messages suppressed by the relay's verified own-session filtering — over
    the same novelty/receipt policy as agent watch (:class:`AgentDelivery`).

    The returned receipt is PREPARED, not committed: acknowledge it (the CLI
    does so once its output has actually landed; an MCP client echoes it on
    the next call) and the batch stops repeating.
    """
    from specify_cli.zeitgeist_client.agent_delivery import AgentDelivery  # noqa: PLC0415

    if max_messages < 1:
        raise ValueError("max_messages must be >= 1")
    policy = AgentDelivery(repo, consumer=consumer)
    policy.acknowledge(acknowledge)
    frames, coverage = _authored_history(repo, window_s=window_s, filter_own=True)
    addressed: list[dict[str, Any]] = []
    unaddressed = 0
    for frame in frames:
        message = _message_from_frame(frame)
        if message is None:
            continue
        audience = message["audience"]
        if audience is None or audience == "team" or audience == f"peer:{policy.consumer}":
            addressed.append(dict(frame))
        else:
            unaddressed += 1
    result: dict[str, Any] = policy.select(addressed, max_frames=max_messages, replay=replay)
    result["messages"] = [_message_from_frame(frame) for frame in result.pop("frames")]
    result["withheld"]["unaddressed"] = unaddressed
    result["catch_up"] = {"operation": "inbox", "within_retention_only": True}
    result["coverage"] = coverage
    return result


def acknowledge_inbox(repo: str, receipt: str, *, consumer: str | None = None) -> None:
    """Commit a previously returned inbox receipt — only after the batch it
    covers was actually delivered. Selection is never acknowledgement."""
    from specify_cli.zeitgeist_client.agent_delivery import AgentDelivery  # noqa: PLC0415

    AgentDelivery(repo, consumer=consumer).acknowledge(receipt)
