"""Bounded retained activity through the relay's existing /managed/events API.

History is a retained observation, never proof of current presence or complete
past activity. This transport requests relay own-session filtering when enabled and checks
its acknowledgment before decoding; receipt policy belongs to its caller.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any, cast

from . import budget, credentials, subscription, own_filter
from .live_frame import parse_live_frame

MAX_HISTORY_PAGES = 20
MAX_HISTORY_BYTES = 8 * 1024 * 1024
MAX_HISTORY_FRAMES = 500
_CURSOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}:[0-9]{1,19}")

# A permit held longer than the 90s socket-read cap belongs to a worker that
# ``budget.run_with_deadline`` already abandoned (its caller returned at the
# whole-call deadline); reaping it is bookkeeping only — the abandoned
# worker's socket is never touched.
_STALE_READ_HOLD_S = 95.0


class _ReadSlots:
    """A history-read permit ledger that reaps holds abandoned by timeouts.

    ``read_history`` runs its socket read under ``budget.run_with_deadline``,
    which abandons a timed-out worker thread still blocked in
    ``resp.read()``; that worker's ``finally`` releases its permit only when
    the socket dies on its own. A plain ``BoundedSemaphore`` therefore leaks
    the permit for the process lifetime, and four stuck reads disable
    history reads entirely. Each hold here instead carries its acquisition
    time, and ``acquire`` reaps holds older than ``stale_hold_s`` first — a
    stuck read costs one slot for a bounded window, never forever. Releasing
    a reaped token is a no-op, so the abandoned worker's own late ``finally``
    can never free a permit a later reader is holding."""

    def __init__(self, capacity: int = 4, *, stale_hold_s: float = _STALE_READ_HOLD_S, clock: Callable[[], float] = time.monotonic) -> None:
        self._capacity = capacity
        self._stale_hold_s = stale_hold_s
        self._clock = clock
        self._lock = threading.Lock()
        self._held: dict[int, float] = {}
        self._next_token = 0

    def acquire(self) -> int | None:
        """Take a permit token, or ``None`` when every slot is still held."""
        with self._lock:
            now = self._clock()
            for token, taken_at in list(self._held.items()):
                if now - taken_at > self._stale_hold_s:
                    del self._held[token]
            if len(self._held) >= self._capacity:
                return None
            self._next_token += 1
            self._held[self._next_token] = now
            return self._next_token

    def release(self, token: int) -> None:
        """Release a permit; a reaped token is a no-op, never a double release."""
        with self._lock:
            self._held.pop(token, None)


_READ_SLOTS = _ReadSlots()


class HistoryProtocolError(ValueError):
    """The relay did not supply a usable, bounded history response."""


def _unsigned(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _decode(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise HistoryProtocolError("Invalid history JSON") from exc
    if not isinstance(data, dict):
        raise HistoryProtocolError("Invalid history envelope")
    version, epoch = data.get("schema_version"), data.get("epoch")
    if (
        not isinstance(version, str)
        or not version.startswith("1.")
        or not isinstance(epoch, str)
        or not _CURSOR.fullmatch(f"{epoch}:0")
        or not _unsigned(data.get("seq"))
        or not isinstance(data.get("events"), list)
    ):
        raise HistoryProtocolError("Invalid history envelope")
    if "reset" in data and not isinstance(data["reset"], bool):
        raise HistoryProtocolError("Invalid history reset")
    gap = data.get("gap")
    if gap is not None and (not isinstance(gap, dict) or not _unsigned(gap.get("from_seq")) or not _unsigned(gap.get("to_seq")) or gap["from_seq"] > gap["to_seq"]):
        raise HistoryProtocolError("Invalid history gap")
    return data


def _project(data: dict[str, Any], *, repo: str, window_s: int) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    previous = 0
    for raw in data["events"]:
        frame = parse_live_frame(raw)
        if frame is None or frame.epoch != data["epoch"] or not math.isfinite(frame.emitted_at) or frame.seq <= previous or frame.seq > data["seq"]:
            raise HistoryProtocolError("Invalid or unordered history frame")
        previous = frame.seq
        if len(frames) < MAX_HISTORY_FRAMES:
            frames.append(subscription._serialize_frame(frame))
    withheld = len(data["events"]) - len(frames)
    continuation = f"{data['epoch']}:{frames[-1]['seq']}" if withheld and frames else None
    return {
        "repo": repo,
        "frames": frames,
        "coverage": {
            "source": "relay_retained_history",
            "epoch": data["epoch"],
            "seq": data["seq"],
            "requested_window_s": window_s,
            "retention_s": None,
            "complete": False,
            "reset": data.get("reset", False),
            "gap": data.get("gap"),
            "truncated": bool(withheld),
            "withheld_count": withheld,
            "continuation": continuation,
        },
    }


def read_history(
    repo: str,
    *,
    window_s: int = 900,
    timeout_s: float = 2.0,
    since: str | None = None,
    filter_own: bool = False,
) -> dict[str, Any]:
    """Read one credential-bound retained page, without acknowledging delivery.

    ``since`` is the relay's epoch/sequence cursor. A frame cap returns a
    continuation at the last returned frame, never the response's global tip.
    The relay rejects windows above its configured retention; this client does
    not guess that deployment setting. Unknown retention/completeness remains
    explicit even for empty responses. HTTP errors propagate without retries.
    """
    if not isinstance(filter_own, bool):
        raise ValueError("filter_own must be a boolean")
    if not _unsigned(window_s):
        raise ValueError("window_s must be a non-negative integer")
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be finite and > 0")
    if since is not None and not _CURSOR.fullmatch(since):
        raise ValueError("since must be <epoch>:<seq> with seq >= 0")
    stored = credentials.load(repo=repo)
    if stored is None:
        raise subscription.NotCheckedOut(repo)
    query = {"window_s": str(window_s), "filterOwn": "true" if filter_own else "false"}
    if since is not None:
        query["since"] = since
    url = stored.relay_url.rstrip("/") + "/managed/events?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {stored.token}",
            "X-Zeitgeist-Capability": stored.capability_credential or stored.token,
        },
        method="GET",
    )
    if filter_own:
        request.add_header("X-Zeitgeist-Own-Sessions", own_filter.identity_header(stored))
    slots = _READ_SLOTS
    token = slots.acquire()
    if token is None:
        raise HistoryProtocolError("History reader busy: previous timed-out reads have not finished")

    def read() -> dict[str, Any]:
        try:
            with budget.NoRedirects.build().open(request, timeout=min(timeout_s, 90.0)) as response:
                if filter_own:
                    own_filter.require_ack(response.headers)
                body = response.read(MAX_HISTORY_BYTES + 1)
            if len(body) > MAX_HISTORY_BYTES:
                raise HistoryProtocolError("History response exceeds byte limit")
            return _project(_decode(body), repo=repo, window_s=window_s)
        finally:
            # Release onto the ledger this read acquired from, never onto
            # whatever ``_READ_SLOTS`` names by the time an abandoned worker
            # finally exits — resolving the global at release time would let
            # a straggler from one ledger pop a token minted by another.
            slots.release(token)

    outcome = budget.run_with_deadline(read, deadline_s=min(timeout_s, 90.0))
    if not outcome.completed:
        raise TimeoutError("History read exceeded whole-call deadline")
    if outcome.error is not None:
        raise outcome.error
    assert outcome.result is not None
    return cast(dict[str, Any], outcome.result)
