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
import urllib.parse
import urllib.request
from typing import Any, cast

from . import budget, credentials, subscription, own_filter
from .live_frame import parse_live_frame

_READ_SLOTS = threading.BoundedSemaphore(4)

MAX_HISTORY_BYTES = 8 * 1024 * 1024
MAX_HISTORY_FRAMES = 500
_CURSOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}:[0-9]{1,19}")


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
    if not _READ_SLOTS.acquire(blocking=False):
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
            _READ_SLOTS.release()

    outcome = budget.run_with_deadline(read, deadline_s=min(timeout_s, 90.0))
    if not outcome.completed:
        raise TimeoutError("History read exceeded whole-call deadline")
    if outcome.error is not None:
        raise outcome.error
    assert outcome.result is not None
    return cast(dict[str, Any], outcome.result)
