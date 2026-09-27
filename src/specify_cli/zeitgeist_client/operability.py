"""O1-C: Spec Kitty client operability (program-graph handle O1-C, parent
O1, "Spec Kitty client operability").

The bundled Zeitgeist client (Z1/Z4-C/Z7-C/Z8-C, already landed in this
package) reports its OWN liveness/connection/subscription/outbox status
here — not a second data store, not a payload log, and never fabricated:
a caller that supplies no live client/snapshot gets an honest "stale"/
"inactive" report rather than a made-up live value (O1-C's own "honest
reported-live/stale" criterion).

Seven named signals, one dataclass each, matching O1-C's node criterion
verbatim ("offer/drop/latency/revoke/lease/MCP/repair"):

* :class:`OfferSignal` / :class:`DropSignal` — both derived from one
  ``transport.OfferResult`` (:meth:`OfferSignal.from_result` /
  :meth:`DropSignal.from_result`). ``OfferSignal.budget_s`` is the hard
  750ms denominator (``budget.OFFER_BUDGET_S``) every ``within_budget``
  reading is measured against — never a bare ratio with no stated bound.
* :class:`LeaseSignal` — the current-focus lease. ``ttl_s`` is always
  ``transport.FOCUS_TTL_S`` (90), present even when ``active`` is
  ``False``: O1-C's own "hard ... <=90s current-focus bounds have
  denominators" criterion means the denominator is reported whether or not
  a lease happens to be active right now, not only on a live hit.
* :class:`RevokeSignal` — outbox counts only (``outbox_approval.
  status_counts``), never content. ``model_reachable`` is a documented
  structural constant, not a per-call probe: Z8-C's own test suite
  (``test_mcp_server_exposes_no_outbox_approval_tool``) and this module's
  own :func:`mcp_signal` both independently confirm the stdio MCP adapter
  never gains an approve/reject/revoke tool.
* :class:`McpSignal` — builds a fresh, in-process ``FastMCP`` server
  (``mcp_stdio.build_server()``, same technique ``test_mcp_stdio.py``
  uses — no subprocess, no real stdio pipe) and lists its tools, reporting
  the exact tool-name surface. A model talking over MCP structurally has
  no tool that reaches ``outbox_approval`` — this signal is one of the two
  places that guarantee is independently exercised (the other is Z8-C's
  own test file).
* :class:`RepairSignal` — a pure projection of ``live_frame.TeamSnapshot.
  reset_count``/``.last_reset_reason`` (Z4-C's own "observability without
  ever retaining what was cleared" fields). ``observed=False`` when no
  snapshot is supplied — never a fabricated "no resets" reading standing
  in for "no live subscription was checked".

:func:`collect_report` combines all of the above into one
:class:`OperabilityReport`. Payload-free: every field is a signal-level
enum/count/duration/boolean, never a relay URL, bearer token, or prose
payload. ``test_operability.py``'s own
``test_collect_report_never_carries_a_forbidden_sensitive_field`` proves
this the same way the rest of the client proves it — by running the report
through ``sanitizer.assert_clean`` against both of ``sanitizer.py``'s own
forbidden-key sets, not a bespoke check invented here.

Local failure drills — O1-C's own node criterion names exactly three
("local timeout/rotation/rollback drills"), each network-free and
deterministic:

* :func:`timeout_drill` — "relay unreachable": one real ``offer()`` call
  against a loopback address nothing listens on. ``transport.
  ZeitgeistClient.offer()`` already handles this correctly (that is
  Z1-T1's own N5 contract); this drill exists to prove it stays true and
  to surface the resulting signal, not to add new drop-handling logic.
* :func:`rotation_drill` — "auth expiry": reads ``credentials.py``'s
  already-stored ``token_issued_at`` (never the token value) and reports
  whether it has crossed :data:`ROTATION_WINDOW_S`. A purely local
  staleness check — there is no server-side auth-expiry endpoint yet
  (Z2a/Z2b territory), so this can only ever report the client's own
  honest read of its own stored metadata.
* :func:`rollback_drill` — "rollback": submits a throwaway pending outbox
  item, then immediately calls ``outbox_approval.revoke()`` on it. That
  call fails closed with ``InvalidTransition`` (a still-pending item is
  not ``"approved"`` — revoke only ever pulls back an *already-approved*
  decision) BEFORE ``outbox_approval._decide`` ever reaches its human-
  gesture seam, so this drill never opens ``/dev/tty`` and needs no human
  — it proves the fail-closed guard, not a full approve-then-revoke round
  trip (which Z8-C's own hard-trust requirement makes structurally
  impossible to script in the first place; see ``outbox_approval.py``'s
  module docstring). Content-addressed submission means a re-run of this
  drill for the same repo more than ``_ROLLBACK_DRILL_TTL_S`` after a prior
  run collides with that prior run's now-expired row, so ``revoke()`` can
  also fail closed with ``Expired`` instead of ``InvalidTransition`` — both
  are handled and both report ``outcome="pass"`` (see
  :func:`rollback_drill`'s own docstring).

No second data store: every signal reads state an existing module
(``transport``, ``credentials``, ``outbox_approval``, ``mcp_stdio``)
already owns. ``rollback_drill`` writes into the SAME
``zeitgeist-outbox.json`` file ``outbox_approval.py`` already owns (marked
with a dedicated ``operability_drill`` audience so it stays identifiable),
never a second file.
"""

from __future__ import annotations

import asyncio
import dataclasses

from kernel.clock import datetime, now_utc, parse_iso

from . import budget, credentials, outbox_approval, transport
from .live_frame import TeamSnapshot

# Operability uses the existing presence canary instead of inventing a relay
# op. The report remains free of event/user-authored payloads.
# Scheduling-jitter allowance for "did this land inside its hard budget"
# readings — mirrors test_transport.py's own generous bound for the same
# measurement-noise reason (see that file's test_n3 comment). Never widens
# the actual 750ms bound offer() enforces; only the *reported* within_budget
# reading tolerates sub-50ms wall-clock noise around it.
_BUDGET_TOLERANCE_S = 0.05

# A loopback address nothing listens on by default (unprivileged connect to
# a low port is refused immediately on every POSIX target this client
# supports — no bind/listen privilege is needed to *connect*). Callers that
# want a dynamically-guaranteed-free port (tests) pass their own explicit
# relay_url instead.
DEFAULT_UNREACHABLE_URL = "http://127.0.0.1:1"

# A purely local, client-side staleness signal — NOT a server-enforced
# token lifetime (no such endpoint exists yet; see the module docstring).
# 24h is deliberately the same order of magnitude as
# outbox_approval.MAX_TTL_S, not imported from it: two independently-owned
# constants that happen to agree, not one module reaching into another's
# internals.
ROTATION_WINDOW_S: float = 24 * 60 * 60.0

_DROPPED_OUTCOMES: frozenset[transport.OfferOutcome] = frozenset(
    {
        transport.OfferOutcome.DROPPED_BUDGET,
        transport.OfferOutcome.DROPPED_UNREACHABLE,
        transport.OfferOutcome.REFUSED_LOCAL,
        # #180: a 429 on the single attempt — the frame is gone (loudly, via
        # THROTTLE_NOTICE on stderr, but gone), which is exactly what this
        # signal reports. A bare REJECTED stays out: that is the relay's
        # answer about the frame, not a lost frame.
        transport.OfferOutcome.THROTTLED,
        # DRAIN_DISABLED is deliberately NOT here (D8, WP02): drain-off is a
        # clean, expected skip -- never a lost frame -- so DropSignal.from_result
        # must never report a drain refusal as a drop, and `operability report`
        # must never show it as one.
    }
)


# --- offer / drop / latency -------------------------------------------------


@dataclasses.dataclass(frozen=True)
class OfferSignal:
    """The hard 750ms bound, always reported WITH its denominator
    (``budget_s``) — never a bare "was it fast" boolean with the bound left
    implicit."""

    outcome: str
    elapsed_s: float
    budget_s: float
    within_budget: bool
    status_code: int | None
    response_detail: str | None

    @classmethod
    def from_result(cls, result: transport.OfferResult) -> OfferSignal:
        return cls(
            outcome=result.outcome.value,
            elapsed_s=result.elapsed_s,
            budget_s=budget.OFFER_BUDGET_S,
            within_budget=result.elapsed_s <= budget.OFFER_BUDGET_S + _BUDGET_TOLERANCE_S,
            status_code=result.status_code,
            response_detail=result.response_detail,
        )


@dataclasses.dataclass(frozen=True)
class DropSignal:
    dropped: bool
    reason: str | None

    @classmethod
    def from_result(cls, result: transport.OfferResult) -> DropSignal:
        if result.outcome in _DROPPED_OUTCOMES:
            return cls(dropped=True, reason=result.outcome.value)
        return cls(dropped=False, reason=None)


# --- lease -------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class LeaseSignal:
    """``ttl_s`` is always ``transport.FOCUS_TTL_S`` (90) — present even
    when ``active`` is ``False``, so the denominator is never implicit."""

    active: bool
    ttl_s: int
    remaining_s: float | None


def lease_signal(client: transport.ZeitgeistClient, *, at: datetime | None = None) -> LeaseSignal:
    """Read ``client``'s current focus lease. ``at`` lets a caller pin "now"
    (used by drills/tests for deterministic remaining_s readings); defaults
    to the real wall clock."""
    focus_ref, started_at = client.focus_lease()
    if focus_ref is None or started_at is None:
        return LeaseSignal(active=False, ttl_s=transport.FOCUS_TTL_S, remaining_s=None)
    now = at if at is not None else now_utc()
    elapsed_s = (now - started_at).total_seconds()
    # Clamped on BOTH ends against the ttl_s denominator: the lower bound
    # (0.0) covers the ordinary "already past TTL" case; the upper bound
    # (transport.FOCUS_TTL_S) covers a negative elapsed_s (a backward clock
    # adjustment, or a caller-supplied `at` earlier than the lease start) --
    # without it remaining_s could read ABOVE ttl_s, breaking the module
    # docstring's "<=90s current-focus bound" guarantee.
    remaining_s = max(0.0, min(float(transport.FOCUS_TTL_S), float(transport.FOCUS_TTL_S) - elapsed_s))
    return LeaseSignal(active=True, ttl_s=transport.FOCUS_TTL_S, remaining_s=remaining_s)


# --- revoke --------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RevokeSignal:
    repo: str
    revocable_count: int
    model_reachable: bool = False


def revoke_signal(repo: str) -> RevokeSignal:
    """``revocable_count`` is every item currently ``"approved"`` for
    ``repo`` (the only status :func:`outbox_approval.revoke` accepts a
    transition from) — a count, never the items themselves."""
    counts = outbox_approval.status_counts(repo=repo)
    return RevokeSignal(repo=repo, revocable_count=counts.get("approved", 0))


# --- MCP -------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class McpSignal:
    reachable: bool
    tool_names: tuple[str, ...]


def mcp_signal() -> McpSignal:
    """Build a fresh, in-process MCP server and list its tools — see the
    module docstring for why this, not a subprocess probe, is the right
    check here."""
    from . import mcp_stdio  # deferred: keeps the `mcp` SDK import optional at this module's own import time

    try:
        server = mcp_stdio.build_server()
    except mcp_stdio.moments.MomentsDisabled:
        return McpSignal(reachable=False, tool_names=())
    tools = asyncio.run(server.list_tools())
    return McpSignal(reachable=True, tool_names=tuple(sorted(tool.name for tool in tools)))


# --- repair --------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RepairSignal:
    """``observed=False`` means "no live subscription was checked", never
    "checked and found zero resets" — see the module docstring."""

    observed: bool
    reset_count: int
    last_reset_reason: str | None


def repair_signal(snapshot: TeamSnapshot | None) -> RepairSignal:
    if snapshot is None:
        return RepairSignal(observed=False, reset_count=0, last_reset_reason=None)
    return RepairSignal(observed=True, reset_count=snapshot.reset_count, last_reset_reason=snapshot.last_reset_reason)


# --- the combined report ----------------------------------------------------


@dataclasses.dataclass(frozen=True)
class OperabilityReport:
    repo: str
    checked_at: str
    credential_checked_out: bool
    offer: OfferSignal | None
    drop: DropSignal | None
    lease: LeaseSignal
    revoke: RevokeSignal
    mcp: McpSignal
    repair: RepairSignal


def collect_report(
    *,
    repo: str,
    client: transport.ZeitgeistClient | None = None,
    snapshot: TeamSnapshot | None = None,
) -> OperabilityReport:
    """One payload-free snapshot of every signal this module knows how to
    produce. ``client``/``snapshot`` are optional and independent: a caller
    with neither gets an honestly stale/inactive report (``offer``/``drop``
    stay ``None``, ``lease.active`` stays ``False``, ``repair.observed``
    stays ``False``) rather than this function fabricating a live value
    from nothing. Passing a live ``client`` runs exactly ONE
    supported ``presence.publish`` canary as the offer/drop/latency probe — never more
    than one network attempt, matching ``offer()``'s own drop-no-retry
    contract. ``repo`` is the credential-store key the caller resolved (the
    CLI derives it from the checkout, #137); it is echoed in the report,
    never re-derived here."""
    offer_sig: OfferSignal | None = None
    drop_sig: DropSignal | None = None
    lease = LeaseSignal(active=False, ttl_s=transport.FOCUS_TTL_S, remaining_s=None)
    if client is not None:
        result = client.presence("command")
        offer_sig = OfferSignal.from_result(result)
        drop_sig = DropSignal.from_result(result)
        lease = lease_signal(client)

    return OperabilityReport(
        repo=repo,
        checked_at=now_utc().isoformat(),
        credential_checked_out=credentials.load(repo=repo) is not None,
        offer=offer_sig,
        drop=drop_sig,
        lease=lease,
        revoke=revoke_signal(repo),
        mcp=mcp_signal(),
        repair=repair_signal(snapshot),
    )


# --- drills ------------------------------------------------------------------


def _drill_config(relay_url: str) -> transport.ClientConfig:
    """A throwaway client identity for a drill — never a real stored
    credential, never the caller's own session/agent identity."""
    return transport.ClientConfig(
        relay_url=relay_url,
        token="operability-drill",  # noqa: S106 - a placeholder identity string, never a real credential
        harness="operability",
        session_id="operability-drill",
        agent_id=None,
        repo="operability-drill",
        branch="operability-drill",
    )


@dataclasses.dataclass(frozen=True)
class TimeoutDrillResult:
    outcome: str  # "pass" | "fail" | "skipped: drain off" (WP02)
    offer: OfferSignal
    drop: DropSignal


def timeout_drill(relay_url: str = DEFAULT_UNREACHABLE_URL) -> TimeoutDrillResult:
    """Relay unreachable drill: one real ``offer()`` against ``relay_url``
    (a loopback address nothing listens on by default). Passes when the
    offer was dropped AND its elapsed time stayed within the 750ms
    denominator — proving the drop-no-retry contract holds under an
    unreachable target, not merely that *some* result came back.

    With drain off, ``offer()`` returns ``OfferOutcome.DRAIN_DISABLED``
    instead of a real drop -- no unreachable target was ever exercised, so
    reporting ``"pass"`` here would misreport "the drop-no-retry contract
    holds" for a check that never ran, and ``"fail"`` would misreport a
    clean, expected skip as a drill failure. ``outcome`` is instead the
    distinct string ``"skipped: drain off"`` -- neither ``"pass"`` nor
    ``"fail"`` (WP02/T009)."""
    client = transport.ZeitgeistClient(_drill_config(relay_url))
    result = client.presence("command")
    offer_sig = OfferSignal.from_result(result)
    drop_sig = DropSignal.from_result(result)
    if result.outcome is transport.OfferOutcome.DRAIN_DISABLED:
        return TimeoutDrillResult(outcome="skipped: drain off", offer=offer_sig, drop=drop_sig)
    passed = drop_sig.dropped and offer_sig.within_budget
    return TimeoutDrillResult(outcome="pass" if passed else "fail", offer=offer_sig, drop=drop_sig)


@dataclasses.dataclass(frozen=True)
class RotationDrillResult:
    """``outcome`` is "pass" whenever the drill produced an honest signal —
    ``rotation_due=True`` is a legitimate, expected reading (a stale
    credential correctly detected), not a drill failure. Only an exception
    escaping this function would leave a caller without any result at all;
    there is no separate "fail" outcome for a rotation drill to report."""

    outcome: str
    checked_out: bool
    age_s: float | None
    rotation_window_s: float
    rotation_due: bool


def rotation_drill(repo: str) -> RotationDrillResult:
    """Auth expiry drill: reads ``repo``'s stored ``token_issued_at`` —
    never the token value itself — and reports whether it has crossed
    :data:`ROTATION_WINDOW_S`. ``repo`` is the credential-store key the
    caller resolved (the CLI derives it from the checkout, #137)."""
    stored = credentials.load(repo=repo)
    if stored is None:
        return RotationDrillResult(outcome="pass", checked_out=False, age_s=None, rotation_window_s=ROTATION_WINDOW_S, rotation_due=False)
    issued_at = parse_iso(stored.token_issued_at)
    age_s = (now_utc() - issued_at).total_seconds()
    return RotationDrillResult(
        outcome="pass",
        checked_out=True,
        age_s=age_s,
        rotation_window_s=ROTATION_WINDOW_S,
        rotation_due=age_s >= ROTATION_WINDOW_S,
    )


_ROLLBACK_DRILL_AUDIENCE = "operability_drill"
_ROLLBACK_DRILL_CONTENT = "operability rollback drill probe (never disclosed outside outbox show/approve; discarded on TTL expiry)"
_ROLLBACK_DRILL_TTL_S = 1.0


@dataclasses.dataclass(frozen=True)
class RollbackDrillResult:
    outcome: str  # "pass" | "fail"
    item_id: str
    blocked_reason: str


def rollback_drill(*, repo: str) -> RollbackDrillResult:
    """Rollback drill: submits a throwaway pending outbox item for
    ``repo``, then immediately calls ``revoke()`` on it. See the module
    docstring for why this proves the fail-closed guard (never a human
    gesture, never ``/dev/tty``) rather than a full approve-then-revoke
    round trip.

    ``outbox_approval.submit`` is content-addressed, so every call for the
    SAME ``repo`` hashes to the SAME ``item_id`` (fixed audience/content).
    The first call within :data:`_ROLLBACK_DRILL_TTL_S` of a prior call
    resubmits that same still-pending row and blocks on
    ``InvalidTransition`` as above; a call made AFTER that TTL has lapsed
    instead resubmits/returns that same row already flipped to
    ``"expired"`` by ``submit()``'s own sweep, so ``revoke()`` raises
    ``outbox_approval.Expired`` instead. An expired item is exactly as
    unrevoke-able as a never-approved one -- both are the fail-closed guard
    holding -- so this drill treats both as an equally valid ``"pass"``,
    distinguished only by ``blocked_reason``. Without this, a second
    invocation of the drill more than ~1s after the first (the ordinary
    "run it again" usage pattern) would raise an unhandled exception."""
    item = outbox_approval.submit(
        repo=repo,
        audience=_ROLLBACK_DRILL_AUDIENCE,
        content=_ROLLBACK_DRILL_CONTENT,
        ttl_s=_ROLLBACK_DRILL_TTL_S,
    )
    try:
        outbox_approval.revoke(item.item_id, actor="operability-drill")
    except outbox_approval.InvalidTransition:
        return RollbackDrillResult(outcome="pass", item_id=item.item_id, blocked_reason="not_yet_approved")
    except outbox_approval.Expired:
        return RollbackDrillResult(outcome="pass", item_id=item.item_id, blocked_reason="expired_before_disposition")
    return RollbackDrillResult(outcome="fail", item_id=item.item_id, blocked_reason="")
