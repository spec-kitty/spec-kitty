"""Z4-C: the network half of the filtered live-stream client — one SSE
connection per team-bound subscription against F3's
``GET /managed/stream`` (``zeitgeist/managed.py``, Z3's managed-runtime
routes; requires the ``managed.live`` capability enabled on the relay).

``live_frame`` (pure logic: parsing + ``StreamState``) does the actual
gap/epoch/revoke/<=90s-clear work; this module is the thin loop that reads
SSE ``data:`` lines off the wire, hands each one to
``live_frame.parse_live_frame``, and applies the result.

Team-bound selector, structurally: a subscription names exactly one team by
holding exactly one ``capability_credential`` — the opaque
``X-Zeitgeist-Capability`` token F3's ``managed_auth.py`` verifies and scopes
every reply to (``identity.team``/``deployment``/``repo``, derived from the
token's own signed claims, never from anything this client sends).
``TeamStreamConfig`` deliberately carries no ``team``/``deployment``/``repo``
field of its own — those names are members of
``sanitizer.FORBIDDEN_CONTROL_KEYS``, and a client-supplied filter would be
theatre anyway: the relay does not look at one. "No implicit multi-team
aggregate" follows the same way — this module offers no function that reads
from more than one ``FilteredStream``'s state; covering several teams means
holding several instances side by side in caller code, never widening this
one's shape (see ``test_two_subscriptions_never_share_state``).

Known, honestly-recorded scope reduction: no CLI or MCP surface. Z4-C's own
node criterion is the client *library* surfaces ("watch/check/current-focus
surfaces over Z1 service"); wiring a ``spec-kitty zeitgeist watch`` command
or an MCP tool onto them remains item 4 of
``docs/plans/zeitgeist-client-wp01-remaining.md``, untouched by this pass —
exactly the same "landed the primitive, not yet the adapter" split Z1-T1
itself recorded for ``offer()``/``credentials.py``.

FIX-M2-13: the same header-omission class ``transport.py``'s FIX-M2-10 note
fixed for ``offer()``'s ``POST /managed/control`` — confirmed against the
live ``zeitgeist`` source, not this module's own double: ``GET
/managed/stream`` sits behind the SAME outer, unconditional
``AuthenticationMiddleware`` gate every route but ``/health`` sits behind
(``zeitgeist/auth.py`` — checked first, ahead of ``managed.py``'s own
handler), in addition to ``managed.py``'s own ``X-Zeitgeist-Capability``
capability check (``managed_auth.py``, verified against a *different*
secret, ``ZEITGEIST_CAPABILITY_KEY``, than ``AuthenticationMiddleware``'s
shared ``ZEITGEIST_TOKEN``). Sending only ``X-Zeitgeist-Capability`` — this
module's pre-fix behaviour — never got past the outer gate at all: a real
relay answered every ``watch()`` connection attempt 401, regardless of
whether the capability credential itself was valid.

FIX-M2-15 (supersedes the "one stored credential, two headers" sentence
this replaces): against a real SaaS-provisioned per-team relay
(``apps.live_capability.provisioning_docker.DockerProvisioningDriver.
provision`` — ``ZEITGEIST_TOKEN``/``ZEITGEIST_CAPABILITY_KEY`` minted as
two INDEPENDENT, unrelated secrets), the SAME stored value can no longer
satisfy both gates — DQA-M2-05's own real-container walkthrough
reproduced this by hand. ``TeamStreamConfig`` therefore carries a SECOND,
optional field: ``relay_token`` (``Authorization: Bearer <relay_token>``)
alongside the original, still-required ``capability_credential``
(``X-Zeitgeist-Capability: <capability_credential>``). Precedence: when
``relay_token`` is configured (non-``None``), each header carries its OWN
value; when it is ``None`` (the default — every config built before this
fix), ``watch()`` falls back to ``capability_credential`` for BOTH
headers, exactly this module's original FIX-M2-13 behaviour, unchanged.
``subscription.resolve_stream`` threads ``credentials.py``'s own
identically-shaped, identically-optional ``StoredCredential.
capability_credential`` field through this same fallback (see that
module's docstring).
"""

from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from . import budget, own_filter
from .live_frame import FocusView, LiveFrame, StreamState, TeamSnapshot, parse_live_frame

_STREAM_PATH = "/managed/stream"


@dataclass(frozen=True)
class TeamStreamConfig:
    """One subscription's connection facts. See the module docstring for
    why there is no team/deployment/repo field here — the credential alone
    is the selector.

    ``relay_token`` (FIX-M2-15) is the SEPARATE ``Authorization`` credential
    — see the module docstring's FIX-M2-15 note. ``None`` (the default)
    falls back to ``capability_credential`` for both headers, exactly the
    original FIX-M2-13 single-credential behaviour."""

    relay_url: str
    capability_credential: str
    relay_token: str | None = None
    # Raw cached issuer references, never relay-derived opaque references.
    # None explicitly selects the complete diagnostic feed.
    own_sessions: str | None = None


class FilteredStream:
    """A single team-bound live-stream subscription.

    ``watch()`` opens exactly one SSE connection, applies every accepted
    frame to local state, and yields it. ``check()``/``current_focus()``
    read that local state back with **no network call of their own** — Z4-C's
    "no missed-event reconstruction" criterion means there is structurally
    no request this class can make to ask the relay what a caller missed; a
    ``signal.kind in {"gap","epoch"}`` frame (or an ``epoch`` value change
    between frames) instead clears local state outright, so a caller who
    only ever calls ``check()`` sees an honestly empty view rather than a
    silently stale one.

    One instance is one team; state is never shared across instances (no
    module-level registry of any kind).

    ``frame_filter`` (#190) is this class's one client-side membership rule:
    a callable over an already-parsed :class:`LiveFrame`, applied before a
    frame is either applied to state or yielded. Own-session suppression is
    performed separately by the relay before its subscriber queue; this
    predicate applies the remaining reader preferences. A rejected frame leaves no trace at all (it
    never reaches ``StreamState``, which is lossless for that anyway: only
    presence/focus mutate it), so a caller holding a filtered stream sees an
    honest "this subscription does not carry that" rather than a frame it
    must remember to ignore itself. ``None`` (the default) admits every
    shape-valid frame — today's behaviour, unchanged.
    """

    def __init__(
        self,
        config: TeamStreamConfig,
        *,
        frame_filter: Callable[[LiveFrame], bool] | None = None,
    ) -> None:
        self._config = config
        self._state = StreamState()
        self._lock = threading.Lock()
        self._frame_filter = frame_filter

    def watch(self, *, idle_timeout_s: float | None = None) -> Iterator[LiveFrame]:
        """Yield each accepted ``LiveFrame`` as it arrives.

        Returns (does not raise) when the relay closes the connection, or
        when ``idle_timeout_s`` elapses across the whole call — including
        connect and non-data SSE heartbeat lines. ``idle_timeout_s=None``
        (the default) waits indefinitely.

        Connection failure (refused, DNS, a non-2xx response — e.g. an
        expired credential, or 503 when the relay's stream slots are
        saturated) raises ``urllib.error.URLError``/``HTTPError`` on the
        first ``next()``. This is a long-lived subscription, not a
        drop-no-retry offer — Z1's 750ms ``OFFER_BUDGET_S`` model does not
        apply here; whether/when to reconnect is the caller's decision, not
        this generator's.
        """
        url = self._config.relay_url.rstrip("/") + _STREAM_PATH
        headers = {
            # Two independent gates, each with its OWN credential — see the
            # module docstring's FIX-M2-15 note. `relay_token` falls back to
            # `capability_credential` when unset, so a single-credential
            # config still presents the same value to both gates.
            "Authorization": f"Bearer {self._config.relay_token or self._config.capability_credential}",
            "X-Zeitgeist-Capability": self._config.capability_credential,
        }
        if self._config.own_sessions is not None:
            url += "?filterOwn=true"
            headers["X-Zeitgeist-Own-Sessions"] = self._config.own_sessions
        else:
            url += "?filterOwn=false"
        req = urllib.request.Request(url, headers=headers, method="GET")
        opener = budget.NoRedirects.build()
        deadline = None if idle_timeout_s is None else time.monotonic() + idle_timeout_s
        with opener.open(req, timeout=idle_timeout_s) as resp:
            if self._config.own_sessions is not None:
                own_filter.require_ack(resp.headers)
            if deadline is None:
                yield from self._read_frames(resp)
                return

            items: queue.Queue[bytes | BaseException] = queue.Queue()
            stop = threading.Event()

            def _reader() -> None:
                try:
                    while not stop.is_set():
                        raw_line = resp.readline()
                        items.put(raw_line)
                        if not raw_line:
                            return
                except BaseException as exc:  # noqa: BLE001 - forwarded to caller thread
                    items.put(exc)

            reader = threading.Thread(target=_reader, name="zeitgeist-sse-read", daemon=True)
            reader.start()
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return
                    try:
                        item = items.get(timeout=remaining)
                    except queue.Empty:
                        return
                    if isinstance(item, BaseException):
                        if isinstance(item, TimeoutError):
                            return
                        raise item
                    if not item:
                        return
                    live_frame_obj = self._apply_line(item)
                    if live_frame_obj is not None:
                        yield live_frame_obj
            finally:
                stop.set()
                resp.close()
                reader.join(timeout=0.1)

    def _read_frames(self, resp: object) -> Iterator[LiveFrame]:
        """Unbounded read path used only when no deadline was requested."""
        while True:
            raw_line = resp.readline()  # type: ignore[attr-defined]
            if not raw_line:
                return
            live_frame_obj = self._apply_line(raw_line)
            if live_frame_obj is not None:
                yield live_frame_obj

    def _apply_line(self, raw_line: bytes) -> LiveFrame | None:
        """Parse, filter, and apply one line; return an accepted frame."""
        live_frame_obj = self._accept_line(raw_line)
        if live_frame_obj is None:
            return None
        if self._frame_filter is not None and not self._frame_filter(live_frame_obj):
            return None
        with self._lock:
            self._state.apply(live_frame_obj)
        return live_frame_obj

    @staticmethod
    def _accept_line(raw_line: bytes) -> LiveFrame | None:
        """Decode one SSE wire line into a :class:`LiveFrame`, or ``None``
        for anything that is not a well-formed ``data:`` line carrying a
        shape-valid frame — never raises, so one hostile/malformed line
        cannot end the watch loop for every frame after it."""
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line.startswith("data:"):
            return None
        text = line[len("data:") :].strip()
        if not text:
            return None
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parse_live_frame(raw)

    def check(self, *, now: float | None = None) -> TeamSnapshot:
        """The current, honestly-known, TTL-clamped view — whatever
        ``watch()`` has accumulated so far. No network call."""
        with self._lock:
            return self._state.snapshot(now=now)

    def current_focus(self, *, now: float | None = None) -> tuple[FocusView, ...]:
        """Convenience accessor for the opt-in current-focus view alone."""
        return self.check(now=now).focus
