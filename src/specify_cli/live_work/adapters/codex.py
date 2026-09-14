"""Codex Live Work notify adapter (spec-kitty#4268).

Codex CLI's supported hook surface is the ``notify`` program (configured in
``config.toml``): it receives one JSON event per program run, currently the
turn-level ``agent-turn-complete`` notification. That is the *whole*
observable surface — there is no per-tool, per-file, or per-test hook in
the Codex versions Team Kitty and the factory use, and this adapter says
so in its capability notes rather than laundering a turn into tool or file
activity:

* a completed turn publishes **nothing as an action** — a turn is not a
  tool invocation, and inventing one would misattribute;
* what a turn notification honestly carries is session-level liveness and
  identity: the observation records that the session produced a turn
  completion in this repository (the message bodies, ``input_messages``
  and ``last_assistant_message``, are prose and are never captured);
* tool/file/test activity in a Codex session is **not observable** — the
  capability matrix carries those rows as ``not_observable`` with the
  watcher fallback (sampled changed-file observation, explicitly labeled,
  no attribution, no reads) as the only partial coverage.

When Codex grows richer hook events, this adapter maps them here and the
matrix rows move — the vocabulary and publisher need no change.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final
from collections.abc import Mapping

from kernel.clock import now_utc

from ..bindings import resolve_bindings
from ..kinds import WorkEmissionKind
from ..models import (
    ActivityBinding,
    ActorBinding,
    Observation,
    Provenance,
    SessionBinding,
    ToolDetail,
    ToolOutcome,
    ToolState,
)

__all__ = ["CodexNotifyAdapter", "CODEX_NOTIFY_EVENTS"]


HARNESS_KEY: Final[str] = "codex"

CODEX_NOTIFY_EVENTS: Final[frozenset[str]] = frozenset({"agent-turn-complete"})
"""The Codex notify event types this adapter maps (the observed surface)."""

_TURN_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class CodexNotifyAdapter:
    """Maps Codex ``notify`` payloads to Live Work observations."""

    harness = HARNESS_KEY

    def parse(self, payload: Mapping[str, Any], *, repo_root: Path) -> list[Observation]:
        event_type = str(payload.get("type", "") or "")
        if event_type not in CODEX_NOTIFY_EVENTS:
            # Unknown/unmapped notify events are tolerated and recorded in
            # the capability matrix, never raised into the harness.
            return []
        session_id = self._session_id(payload)
        if session_id is None:
            return []
        cwd = Path(str(payload.get("cwd") or repo_root or Path.cwd()))
        bindings = resolve_bindings(cwd)
        if bindings.repository is None:
            return []
        return [
            Observation(
                kind=WorkEmissionKind.TOOL_INVOKED,
                session=SessionBinding(session_id=session_id),
                actor=ActorBinding(harness=HARNESS_KEY),
                repository=bindings.repository,
                mission=bindings.mission,
                activity=ActivityBinding(activity_id=self._activity_id(payload)),
                action=ToolDetail(
                    tool="codex.turn",
                    state=ToolState.RESULT,
                    outcome=ToolOutcome.SUCCESS,
                ),
                extensions={"x-codex-event": event_type[:64]},
                provenance=Provenance(
                    source="harness_hook",
                    capability="live-work.codex.notify",
                    limitation=(
                        "codex notify exposes turn-level events only; a "
                        "completed turn is published as the tool action "
                        "'codex.turn' — the harness's own unit of observable "
                        "work; tool, file, and test activity is not "
                        "observable"
                    ),
                ),
                occurred_at=now_utc().isoformat(),
            )
        ]

    def capability_notes(self) -> Mapping[str, str]:
        return {
            "notify_surface": ("the supported hook surface is the config.toml notify program; only agent-turn-complete events are delivered"),
            "tools": "tool invocations are not observable in codex notify events",
            "files": (
                "file operations are not hook-attributable; changed files are covered only by the labeled watcher fallback (sampled, no attribution, no reads)"
            ),
            "tests": ("test runs are not observable; outcomes surface only when the change reaches Git"),
            "prose": ("input_messages and last_assistant_message are prose and are never captured"),
        }

    def _session_id(self, payload: Mapping[str, Any]) -> str | None:
        for key in ("session_id", "thread_id", "conversation_id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                safe = re.sub(r"[^A-Za-z0-9._:-]", "-", value)[:128]
                if safe:
                    return safe
        turn_id = payload.get("turn_id")
        if isinstance(turn_id, str) and _TURN_ID_RE.match(turn_id):
            return f"codex-turn-{turn_id}"
        return None

    def _activity_id(self, payload: Mapping[str, Any]) -> str:
        turn_id = payload.get("turn_id")
        if isinstance(turn_id, str) and turn_id:
            safe = re.sub(r"[^A-Za-z0-9._-]", "-", turn_id)[:128]
            if safe:
                return f"codex-{safe}"
        return f"codex-turn-{now_utc().strftime('%Y%m%dT%H%M%S%f')}"
