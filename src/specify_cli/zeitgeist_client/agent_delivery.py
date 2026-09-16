"""One agent-facing policy for stream and retained-history delivery.

Canonical event identity, not local files or semantic guesses, defines novelty.
Adapters acknowledge only a successfully delivered batch. In particular MCP
consumers echo the returned receipt on their next request, so a failed tool
response is never implicitly marked read.
"""

from __future__ import annotations

import hashlib
import json
from itertools import islice
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from spec_kitty_events.models import normalize_event_id

from . import credentials, history, moments, session_identity
from .live_frame import LiveFrame
from .receipts import ReceiptStore

# The hostile-relay scan bound, derived rather than restated: one catch-up
# reads at most ``history.MAX_HISTORY_PAGES`` pages of ``history.
# MAX_HISTORY_FRAMES`` retained frames each, so a single ``select()`` scan
# never sees more frames than that product (finding #5, PR #4224).
MAX_SCAN_FRAMES: int = history.MAX_HISTORY_PAGES * history.MAX_HISTORY_FRAMES


def consumer_identity(consumer: str | None = None) -> tuple[str, bool]:
    """Resolve a logical consumer across processes; never use a human identity."""
    if consumer is not None:
        if not consumer.strip() or len(consumer) > 256:
            raise ValueError("consumer must contain 1..256 characters")
        return consumer, True
    return session_identity.logical_session_id(), True


def _digest(value: Any) -> str:
    # Non-charter hashes isolate receipt contexts and event identities.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()  # noqa: TID251


def frame_identity(frame: Mapping[str, Any]) -> str:
    """Canonical source event ID, or relay epoch/sequence for transport frames."""
    payload = frame.get("payload")
    if frame.get("frame_type") == "event" and isinstance(payload, Mapping):
        attrs = payload.get("attrs")
        event_id = attrs.get("event_id") if isinstance(attrs, Mapping) else None
        if event_id is not None:
            # Do not turn a malformed domain identity into an apparently novel
            # transport identity: fail this read explicitly.
            try:
                canonical_id = normalize_event_id(event_id)
            except ValueError:
                # Contract diagnostics can echo malformed IDs. Event attrs
                # must never escape the untrusted-content rendering via errors.
                raise ValueError("Malformed canonical event identity in Zeitgeist activity") from None
            return _digest(["event", canonical_id])
    return _digest(["relay", frame["epoch"], frame["seq"]])


class AgentDelivery:
    """Settings snapshot and receipt context shared by CLI and MCP adapters."""

    def __init__(
        self,
        repo: str,
        *,
        settings: moments.MomentSettings | None = None,
        consumer: str | None = None,
        project_root: Path | None = None,
        receipts: ReceiptStore | None = None,
    ) -> None:
        self.repo = repo
        self.settings = settings if settings is not None else moments.load_settings(project_root=project_root)
        if self.settings.agents is moments.MomentsMode.OFF:
            raise moments.MomentsDisabled(self.settings)
        self.consumer, self.stable_consumer = consumer_identity(consumer)
        root = project_root if project_root is not None else moments.locate_repo_root()
        self.local_missions = moments.local_missions(root) if self.settings.agents is moments.MomentsMode.MINE else ()
        self.predicate = moments.frame_predicate(self.settings, local_missions=self.local_missions)
        self.receipts = receipts or ReceiptStore()
        stored = credentials.load(repo=repo)
        # Admission metadata is stable across token renewal (same scope rule as
        # credential lease preservation). Legacy entries lacking this metadata
        # conservatively isolate using their opaque capability fingerprint.
        scope = None
        if stored is not None:
            if stored.team and stored.host and stored.repo_slug:
                scope = [stored.relay_url, stored.team, stored.host, stored.repo_slug]
            else:
                scope = [stored.relay_url, stored.capability_credential or stored.token]
        filters = self.settings.as_dict()
        filters.pop("agents_source", None)
        filters.pop("kinds_unknown", None)
        filters.pop("rate_per_minute", None)
        for key in ("repos", "missions", "teammates", "kinds"):
            filters[key] = sorted(filters[key])
        self.context = _digest([self.consumer, repo, scope, filters, sorted(self.local_missions)])

    def acknowledge(self, receipt: str | None) -> None:
        """Acknowledge a previous successful delivery in this scope."""
        if receipt is not None:
            self.receipts.acknowledge(self.context, receipt)

    def select(
        self,
        frames: Iterable[dict[str, Any]],
        *,
        max_frames: int,
        replay: bool = False,
    ) -> dict[str, Any]:
        """Filter and deduplicate before budget; prepare, never commit, receipts."""
        if max_frames < 1:
            raise ValueError("max_frames must be >= 1")
        known = set() if replay else self.receipts.known(self.context)
        budget_ids = self.receipts.budget_event_ids(self.context)
        remaining = self.settings.rate_per_minute if replay else max(0, self.settings.rate_per_minute - len(budget_ids))
        surfaced: list[dict[str, Any]] = []
        event_count = 0
        identities: list[tuple[str, bool]] = []
        counts = {"filtered": 0, "duplicates": 0, "rate": 0, "budget": 0}
        iterator = iter(frames)
        for frame in islice(iterator, MAX_SCAN_FRAMES):
            live = LiveFrame(**frame)
            if not self.predicate(live):
                counts["filtered"] += 1
                continue
            signal = frame["frame_type"] == "signal"
            identity = frame_identity(frame)
            if not signal and identity in known:
                counts["duplicates"] += 1
                continue
            # Within-batch duplicates cannot spend any budget, including when
            # their first occurrence was withheld (but never persisted as read).
            known.add(identity)
            is_event = frame["frame_type"] == "event"
            reason = (
                "budget"
                if len(surfaced) >= max_frames
                else "rate"
                if is_event and (event_count >= self.settings.rate_per_minute or (identity not in budget_ids and remaining <= 0))
                else None
            )
            if reason is not None:
                counts[reason] += 1
                continue
            surfaced.append(frame)
            if is_event:
                event_count += 1
            if not signal and not replay:
                identities.append((identity, is_event))
            if is_event and identity not in budget_ids:
                remaining -= 1
        # A source that yields exactly MAX_SCAN_FRAMES frames and is exhausted
        # has not hit the scan limit; only a frame beyond the cap proves the
        # scan was cut short. The probe frame is discarded — surfacing it
        # would exceed the very bound being reported (finding #5, PR #4224).
        scan_limit_reached = next(iterator, None) is not None
        result: dict[str, Any] = {
            "repo": self.repo,
            "frames": surfaced,
            "withheld": counts,
            "scan_limit_reached": scan_limit_reached,
            "settings": self.settings.as_dict(),
            "consumer_continuity": "stable" if self.stable_consumer else "process_only",
            "own_filter": "not_requested",
            "replay": replay,
            "catch_up": {"operation": "activity", "within_retention_only": True},
        }
        # Validate serialization before even issuing a receipt. No content is
        # persisted; adapters still decide when delivery actually succeeded.
        json.dumps(result, allow_nan=False)
        result["receipt"] = self.receipts.prepare(self.context, identities, rate_limit=self.settings.rate_per_minute) if not replay else None
        if counts["rate"]:
            result["rate_note"] = (
                f"+{counts['rate']} more moments withheld (agent rate cap: {self.settings.rate_per_minute}/min); use activity to catch up within retention"
            )
        return result
