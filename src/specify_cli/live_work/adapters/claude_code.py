"""Claude Code Live Work hook adapter (spec-kitty#4268).

Maps the Claude Code hook payloads (the JSON Claude Code pipes to a
registered hook command — one event per invocation) onto canonical
observations. The payload grammar mapped here is the documented common
shape: ``hook_event_name``, ``session_id``, ``transcript_path``, ``cwd``,
plus the per-event fields (``tool_name``/``tool_input``/``tool_response``
for tool events, ``source`` for SessionStart, ``reason`` for SessionEnd).
Unknown events and unknown fields are tolerated and reported through the
capability matrix, never raised.

Honest limitations this adapter declares (capability notes):

* **tool start/result correlation** — PreToolUse and PostToolUse are
  separate hook invocations and the payload carries no shared tool-use id,
  so a start and its result carry distinct activity ids (each frame still
  correlates through the session and tool name);
* **Write create-vs-edit** — the Write tool's payload does not distinguish
  creating a new file from editing an existing one; Write maps to
  ``edit`` and the delta is the full content length;
* **abrupt process exit** — no hook fires, so no ``session.ended`` frame
  is emitted; the relay's ≤90 s presence expiry is the honest signal
  (never a fabricated end);
* **prose surfaces** (UserPromptSubmit/Notification prompts, tool
  response bodies) are never captured — private reasoning and raw
  terminal output are excluded by :mod:`live_work.redaction`; test
  *counts* are parsed locally from a Bash result and published as counts
  only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final
from collections.abc import Mapping
from uuid import uuid4

from kernel.clock import now_utc

from ..bindings import ResolvedBindings, resolve_bindings
from ..kinds import WorkEmissionKind
from ..models import (
    ActivityBinding,
    ActorBinding,
    CoverageDetail,
    FileDetail,
    FileOperation,
    Observation,
    ObservationAction,
    Provenance,
    SessionBinding,
    TestRunDetail,
    ToolDetail,
    ToolOutcome,
    ToolState,
)
from ..redaction import MAX_SUMMARY_CHARS, redact_command_summary, relativize_path

__all__ = ["ClaudeCodeHookAdapter", "CLAUDE_HOOK_COMMANDS"]


HARNESS_KEY: Final[str] = "claude"

CLAUDE_HOOK_COMMANDS: Final[dict[str, str | None]] = {
    # event key -> matcher (None for lifecycle events)
    "SessionStart": None,
    "SessionEnd": None,
    "PreToolUse": None,
    "PostToolUse": None,
    "SubagentStop": None,
}
"""The Claude Code hook events the Live Work capture registers, with the
tool matcher each event is scoped to (``None`` = all tools)."""

_FILE_TOOLS: Final[frozenset[str]] = frozenset({"Read", "Edit", "MultiEdit", "Write", "NotebookEdit"})
_SHELL_TOOLS: Final[frozenset[str]] = frozenset({"Bash", "BashOutput"})
_DELEGATION_TOOL: Final[str] = "Task"

_TEST_RUNNER_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|[/\\\s])(pytest|py\.test|make|npm|pnpm|yarn|uv-run-pytest|ruff|mypy)(?:$|[/\\\s])")
_SUMMARY_COUNT_RE: Final[re.Pattern[str]] = re.compile(
    r"(\d+)\s+(passed|failed|skipped|error(?:s)?|warnings?)",
    re.IGNORECASE,
)


class ClaudeCodeHookAdapter:
    """Maps Claude Code hook payloads to Live Work observations."""

    harness = HARNESS_KEY

    def parse(self, payload: Mapping[str, Any], *, repo_root: Path) -> list[Observation]:
        event = str(payload.get("hook_event_name", "") or "")
        session_id = str(payload.get("session_id", "") or "")
        if not session_id:
            # No session identity means no attributable observation: honest
            # nothing, never a fabricated session.
            return []
        cwd = Path(str(payload.get("cwd") or repo_root or Path.cwd()))
        bindings = resolve_bindings(cwd)
        if bindings.repository is None:
            # A repo no team admitted produces nothing anywhere: with no
            # repository binding there is no authorized scope to publish in.
            return []

        handler = {
            "SessionStart": self._session_started,
            "SessionEnd": self._session_ended,
            "PreToolUse": self._pre_tool_use,
            "PostToolUse": self._post_tool_use,
        }.get(event)
        if handler is None:
            return []
        return list(handler(payload, session_id, bindings))

    def capability_notes(self) -> Mapping[str, str]:
        return {
            "tool_start_result_correlation": (
                "PreToolUse/PostToolUse are separate invocations with no shared tool-use id; start and result frames carry distinct activity ids"
            ),
            "write_create_vs_edit": ("the Write tool payload does not distinguish create from edit; Write maps to edit with a full-content-length delta"),
            "abrupt_exit": ("no hook fires on abrupt process exit; no session.ended frame is emitted (the relay's <=90s presence expiry is the honest signal)"),
            "prose": ("prompts, notifications, and tool response bodies are never captured; test counts are parsed locally and published as counts only"),
            "subagent_stop": (
                "SubagentStop is not wired: delegation frames come from the Task tool's Pre/PostToolUse pair, which names the counterpart subagent type"
            ),
        }

    # ── event handlers ──────────────────────────────────────────────────

    def _session_started(self, payload: Mapping[str, Any], session_id: str, bindings: ResolvedBindings) -> list[Observation]:
        source = str(payload.get("source", "") or "startup")
        return [
            self._observation(
                kind=WorkEmissionKind.SESSION_STARTED,
                session_id=session_id,
                bindings=bindings,
                text=f"claude code session started ({source})"[:MAX_SUMMARY_CHARS],
                extensions={"x-source": source[:64]},
            )
        ]

    def _session_ended(self, payload: Mapping[str, Any], session_id: str, bindings: ResolvedBindings) -> list[Observation]:
        reason = str(payload.get("reason", "") or "unknown")
        return [
            self._observation(
                kind=WorkEmissionKind.SESSION_ENDED,
                session_id=session_id,
                bindings=bindings,
                text=f"claude code session ended ({reason})"[:MAX_SUMMARY_CHARS],
                extensions={"x-reason": reason[:64]},
            )
        ]

    def _pre_tool_use(self, payload: Mapping[str, Any], session_id: str, bindings: ResolvedBindings) -> list[Observation]:
        tool_name = str(payload.get("tool_name", "") or "")
        tool_input = payload.get("tool_input") or {}
        if not tool_name:
            return []
        if tool_name == _DELEGATION_TOOL:
            subagent_type = str((tool_input.get("subagent_type") if isinstance(tool_input, Mapping) else "") or "task")
            return [
                self._observation(
                    kind=WorkEmissionKind.DELEGATION_STARTED,
                    session_id=session_id,
                    bindings=bindings,
                    counterpart=subagent_type,
                    activity=ActivityBinding(activity_id=_mint_id()),
                    text=f"delegated to {subagent_type}"[:MAX_SUMMARY_CHARS],
                )
            ]
        extensions: dict[str, str | int | float | bool] | None = None
        if tool_name in _SHELL_TOOLS and isinstance(tool_input, Mapping):
            summary = redact_command_summary(str(tool_input.get("command", "") or ""))
            if summary.value:
                extensions = {"x-summary": summary.value}
        return [
            self._observation(
                kind=WorkEmissionKind.TOOL_INVOKED,
                session_id=session_id,
                bindings=bindings,
                activity=ActivityBinding(activity_id=_mint_id()),
                action=ToolDetail(tool=_safe_tool_name(tool_name), state=ToolState.STARTED),
                extensions=extensions,
            )
        ]

    def _post_tool_use(self, payload: Mapping[str, Any], session_id: str, bindings: ResolvedBindings) -> list[Observation]:
        tool_name = str(payload.get("tool_name", "") or "")
        tool_input = payload.get("tool_input") or {}
        tool_response = payload.get("tool_response") or {}
        if not tool_name:
            return []
        if tool_name == _DELEGATION_TOOL:
            subagent_type = str((tool_input.get("subagent_type") if isinstance(tool_input, Mapping) else "") or "task")
            return [
                self._observation(
                    kind=WorkEmissionKind.DELEGATION_ENDED,
                    session_id=session_id,
                    bindings=bindings,
                    counterpart=subagent_type,
                    activity=ActivityBinding(activity_id=_mint_id()),
                    text=f"delegation to {subagent_type} finished"[:MAX_SUMMARY_CHARS],
                )
            ]
        observations: list[Observation] = []
        if tool_name in _FILE_TOOLS:
            file_observation = self._file_observation(tool_name, tool_input, session_id, bindings)
            if file_observation is not None:
                observations.append(file_observation)
        state, outcome = _terminal_state(tool_response)
        extensions: dict[str, str | int | float | bool] | None = None
        if tool_name in _SHELL_TOOLS and isinstance(tool_input, Mapping):
            summary = redact_command_summary(str(tool_input.get("command", "") or ""))
            if summary.value:
                extensions = {"x-summary": summary.value}
        observations.append(
            self._observation(
                kind=WorkEmissionKind.TOOL_INVOKED,
                session_id=session_id,
                bindings=bindings,
                activity=ActivityBinding(activity_id=_mint_id()),
                action=ToolDetail(
                    tool=_safe_tool_name(tool_name),
                    state=state,
                    outcome=outcome,
                ),
                extensions=extensions,
            )
        )
        if tool_name in _SHELL_TOOLS:
            test_observation = self._test_observation(tool_input, tool_response, session_id, bindings)
            if test_observation is not None:
                observations.append(test_observation)
        return observations

    # ── detail builders ─────────────────────────────────────────────────

    def _file_observation(
        self,
        tool_name: str,
        tool_input: Any,
        session_id: str,
        bindings: ResolvedBindings,
    ) -> Observation | None:
        if not isinstance(tool_input, Mapping):
            return None
        raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not isinstance(raw_path, str) or not raw_path:
            return None
        repo_root = bindings.repo_root or Path.cwd()
        relative = relativize_path(raw_path, repo_root)
        if relative.excluded:
            # Secret/unsafe paths never enter a frame, a log, or a gap
            # record — excluded by policy, silently and by design.
            return None
        operation, added, removed = _file_delta(tool_name, tool_input)
        return self._observation(
            kind=WorkEmissionKind.FILE_EDITED,
            session_id=session_id,
            bindings=bindings,
            activity=ActivityBinding(activity_id=_mint_id()),
            action=FileDetail(
                operation=operation,
                path=relative.value or "",
                bytes_added=added,
                bytes_removed=removed,
            ),
        )

    def _test_observation(
        self,
        tool_input: Any,
        tool_response: Any,
        session_id: str,
        bindings: ResolvedBindings,
    ) -> Observation | None:
        if not isinstance(tool_input, Mapping):
            return None
        command = str(tool_input.get("command", "") or "")
        if not _TEST_RUNNER_RE.search(f" {command} "):
            return None
        counts = _parse_test_counts(tool_response)
        if counts is None:
            return None
        passed, failed, skipped = counts
        selector = _compact_selector(command)
        return self._observation(
            kind=WorkEmissionKind.TEST_EXECUTED,
            session_id=session_id,
            bindings=bindings,
            activity=ActivityBinding(activity_id=_mint_id()),
            action=TestRunDetail(
                selector=selector,
                state=ToolState.RESULT,
                passed=passed,
                failed=failed,
                skipped=skipped,
                outcome=ToolOutcome.SUCCESS if failed == 0 else ToolOutcome.FAILURE,
            ),
        )

    def _observation(
        self,
        *,
        kind: WorkEmissionKind,
        session_id: str,
        bindings: ResolvedBindings,
        activity: ActivityBinding | None = None,
        action: ObservationAction | None = None,
        counterpart: str | None = None,
        text: str | None = None,
        extensions: dict[str, str | int | float | bool] | None = None,
    ) -> Observation:
        repository = bindings.repository
        if repository is None:  # pragma: no cover - parse() refuses unbound repos
            msg = "observation requires a repository binding"
            raise ValueError(msg)
        return Observation(
            kind=kind,
            session=SessionBinding(session_id=_safe_session_id(session_id)),
            actor=ActorBinding(harness=HARNESS_KEY),
            repository=repository,
            mission=bindings.mission,
            activity=activity,
            action=action,
            counterpart=counterpart,
            coverage=CoverageDetail(area="claude-code-capture", reason=None) if kind == WorkEmissionKind.COVERAGE_GAP else None,
            text=text,
            extensions=extensions,
            provenance=Provenance(
                source="harness_hook",
                capability="live-work.claude-code.hooks",
            ),
            occurred_at=now_utc().isoformat(),
        )


def _mint_id() -> str:
    return uuid4().hex


def _safe_tool_name(tool_name: str) -> str:
    # Tool names ride the wire's ident grammar; a name outside it is
    # preserved as its bounded alphanumeric skeleton, never dropped.
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", tool_name)[:64]
    return safe or "tool"


def _safe_session_id(session_id: str) -> str:
    # The relay's session_id grammar is [A-Za-z0-9][A-Za-z0-9._:-]{0,127}.
    safe = re.sub(r"[^A-Za-z0-9._:-]", "-", session_id)[:128]
    return safe or "unknown-session"


def _terminal_state(tool_response: Any) -> tuple[ToolState, ToolOutcome | None]:
    """(state, outcome) for one concluded tool use, from the response only."""
    if not isinstance(tool_response, Mapping):
        return ToolState.RESULT, ToolOutcome.SUCCESS
    if tool_response.get("interrupted"):
        return ToolState.CANCELLED, None
    if tool_response.get("is_error") or tool_response.get("error"):
        return ToolState.RESULT, ToolOutcome.FAILURE
    return ToolState.RESULT, ToolOutcome.SUCCESS


def _file_delta(tool_name: str, tool_input: Mapping[str, Any]) -> tuple[FileOperation, int, int]:
    """(operation, bytes_added, bytes_removed) for one file tool use.

    Lengths only — content itself never enters an observation. The Write
    delta is the full content length (create-vs-edit is not distinguishable
    in the payload; declared in the capability notes).
    """
    if tool_name == "Read":
        return FileOperation.READ, 0, 0
    if tool_name in ("Edit", "MultiEdit"):
        edits = tool_input.get("edits")
        if isinstance(edits, list) and edits:
            added = sum(len(str(e.get("new_string", "") or "")) for e in edits if isinstance(e, Mapping))
            removed = sum(len(str(e.get("old_string", "") or "")) for e in edits if isinstance(e, Mapping))
            return FileOperation.EDIT, added, removed
        old = str(tool_input.get("old_string", "") or "")
        new = str(tool_input.get("new_string", "") or "")
        return FileOperation.EDIT, len(new), len(old)
    if tool_name == "Write":
        return FileOperation.EDIT, len(str(tool_input.get("content", "") or "")), 0
    return FileOperation.EDIT, 0, 0


def _parse_test_counts(tool_response: Any) -> tuple[int, int, int] | None:
    """(passed, failed, skipped) parsed from a shell tool's summary line.

    Raw output never enters an observation — counts are extracted here and
    only the counts are published. ``None`` when no recognizable summary.
    """
    if not isinstance(tool_response, Mapping):
        return None
    stdout = tool_response.get("stdout") or tool_response.get("output") or ""
    if not isinstance(stdout, str):
        return None
    tail = stdout[-2000:]
    counts: dict[str, int] = {}
    for match in _SUMMARY_COUNT_RE.finditer(tail):
        number = int(match.group(1))
        word = match.group(2).lower().rstrip("s")
        if word in ("passed", "failed", "skipped", "error"):
            counts[word] = counts.get(word, 0) + number
    if not counts:
        return None
    return counts.get("passed", 0), counts.get("failed", 0) + counts.get("error", 0), counts.get("skipped", 0)


def _compact_selector(command: str) -> str:
    """A bounded, space-free selector for a test-run observation.

    Derived from the *redacted* command summary, never the raw command —
    the selector rides the wire like the summary does, so a credential
    shape that the summary would lose must never survive here either.
    """
    sanitized = redact_command_summary(command)
    tokens = (sanitized.value or "").split()
    if not tokens:
        return "test-run"
    parts = [tokens[0]]
    for token in tokens[1:5]:
        if token.startswith("-"):
            continue
        parts.append(token)
        if len(parts) >= 3:
            break
    selector = "::".join(part.replace(" ", "-")[:80] for part in parts)
    return re.sub(r"[^A-Za-z0-9._@+/-]", "-", selector)[:240] or "test-run"
