"""The executable Live Work capability matrix (spec-kitty#4268).

One row per (harness, observable surface): what is captured exactly, what
is only sampleable through the labeled watcher fallback, what is not
observable at all, and what is never captured by policy. Rows are data —
``spec-kitty live-work matrix`` prints them, tests pin them, and the
"no silent green" rule is enforced twice:

* :func:`CapabilityMatrix.degraded_harnesses` — a harness configured in
  ``.kittify/config.yaml`` whose capture hooks are *not* installed is
  degraded, and the CLI command exits non-zero on that state;
* every not-observable / never-captured surface is a row in the matrix
  itself, so a consumer cannot mistake silence for coverage.

The matrix is the machine-readable home of LIVE-WORK.md §5's
source-to-producer coverage table, restricted to this capture layer's
producers (hook adapters + watcher fallback); lifecycle-capture rows owned
by other seams (#4214, #3929, #4231, #4269, planning#2270) are named, not
duplicated — except the whole-mission lifecycle family below, which MAPS
those seams (contract kind → concrete producer → live consumer) without
owning them, per #4268's 2026-09-14 whole-mission coverage clarification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .codec import codec_state

__all__ = [
    "CapabilityMatrix",
    "CapabilityRow",
    "CapabilityStatus",
    "LIVE_WORK_HOOK_COMMAND_MARKER",
    "matrix_for_harness",
]


LIVE_WORK_HOOK_COMMAND_MARKER: Final[str] = "live-work hook"
"""The substring that identifies a Live Work capture hook command."""


class CapabilityStatus(StrEnum):
    """The capture status of one (harness, surface) cell."""

    EXACT = "exact"
    SAMPLED = "sampled_fallback"
    NOT_OBSERVABLE = "not_observable"
    NEVER_CAPTURED = "never_captured"
    NOT_INSTRUMENTED = "not_instrumented"


@dataclass(frozen=True)
class CapabilityRow:
    """One cell of the matrix."""

    harness: str
    surface: str
    status: CapabilityStatus
    mechanism: str
    limitation: str | None = None

    def as_dict(self) -> dict[str, str]:
        row = {
            "harness": self.harness,
            "surface": self.surface,
            "status": self.status.value,
            "mechanism": self.mechanism,
        }
        if self.limitation is not None:
            row["limitation"] = self.limitation
        return row


# ── Claude Code rows ─────────────────────────────────────────────────────────

_CLAUDE_ROWS: tuple[CapabilityRow, ...] = (
    CapabilityRow("claude", "session_start", CapabilityStatus.EXACT, "SessionStart hook"),
    CapabilityRow("claude", "session_end", CapabilityStatus.EXACT, "SessionEnd hook"),
    CapabilityRow(
        "claude",
        "session_end_abrupt_exit",
        CapabilityStatus.NOT_OBSERVABLE,
        "none",
        "no hook fires on abrupt process exit; the relay's <=90s presence expiry is the honest signal",
    ),
    CapabilityRow(
        "claude",
        "tool_invocations",
        CapabilityStatus.EXACT,
        "PreToolUse/PostToolUse hooks",
        "start and result are separate invocations with no shared tool-use id; each frame carries its own activity id",
    ),
    CapabilityRow("claude", "file_read", CapabilityStatus.EXACT, "PostToolUse(Read) hook"),
    CapabilityRow(
        "claude",
        "file_edit",
        CapabilityStatus.EXACT,
        "PostToolUse(Edit/MultiEdit/Write) hook",
        "Write maps to edit (create-vs-edit is not payload-distinguishable); Write deltas are full-content length",
    ),
    CapabilityRow(
        "claude",
        "file_delete_rename",
        CapabilityStatus.SAMPLED,
        "watcher fallback (changed-file observation)",
        "no delete/rename tool event; Bash mv/rm changes surface only through the labeled watcher fallback (sampled, no attribution)",
    ),
    CapabilityRow(
        "claude",
        "test_runs",
        CapabilityStatus.EXACT,
        "PostToolUse(Bash/BashOutput) hook, counts parsed locally",
        "only runs driven through the Bash tool; counts/outcomes only, raw output never captured",
    ),
    CapabilityRow(
        "claude",
        "delegation",
        CapabilityStatus.EXACT,
        "Pre/PostToolUse(Task) hook",
        "the counterpart is the subagent type; the child session id is not exposed to the parent's hooks",
    ),
    CapabilityRow("claude", "private_reasoning", CapabilityStatus.NEVER_CAPTURED, "policy", "prompts, notifications, and tool response bodies are never captured"),
)

# ── Codex rows ───────────────────────────────────────────────────────────────

_CODEX_ROWS: tuple[CapabilityRow, ...] = (
    CapabilityRow(
        "codex",
        "session_liveness_turns",
        CapabilityStatus.EXACT,
        "config.toml notify program (agent-turn-complete)",
        "a completed turn is published as the tool action 'codex.turn'; no finer granularity exists",
    ),
    CapabilityRow("codex", "tool_invocations", CapabilityStatus.NOT_OBSERVABLE, "none", "codex notify exposes turn-level events only"),
    CapabilityRow(
        "codex",
        "file_changes",
        CapabilityStatus.SAMPLED,
        "watcher fallback (changed-file observation)",
        "changed files only, explicitly labeled sampled: no attribution to an agent, and file reads are never claimed",
    ),
    CapabilityRow("codex", "test_runs", CapabilityStatus.NOT_OBSERVABLE, "none", "test outcomes surface only when the change reaches Git"),
    CapabilityRow("codex", "delegation", CapabilityStatus.NOT_OBSERVABLE, "none", "factory job/attempt binding is planning#2270's seam"),
    CapabilityRow(
        "codex", "private_reasoning", CapabilityStatus.NEVER_CAPTURED, "policy", "input_messages and last_assistant_message are prose and are never captured"
    ),
)

# ── Cross-harness policy rows ────────────────────────────────────────────────

_POLICY_ROWS: tuple[CapabilityRow, ...] = (
    CapabilityRow(
        "all",
        "secrets_credentials_env",
        CapabilityStatus.NEVER_CAPTURED,
        "policy",
        "secret files, token-bearing arguments, and environment values are excluded by live_work.redaction",
    ),
    CapabilityRow(
        "all", "raw_terminal_output", CapabilityStatus.NEVER_CAPTURED, "policy", "raw output never enters a frame; bounded sanitized summaries and counts only"
    ),
    CapabilityRow(
        "all",
        "mission_review_outcomes",
        CapabilityStatus.NOT_INSTRUMENTED,
        "none",
        "no mission-review lifecycle seam exists yet (review outcomes are not lifecycle events); #4231's lane",
    ),
    CapabilityRow(
        "all",
        "authored_messages",
        CapabilityStatus.NOT_INSTRUMENTED,
        "none",
        "authored communication is spec-kitty#4269's surface; model private reasoning is never narrative",
    ),
)

# Other production harnesses, enumerated per the issue's "enumerate exact
# other production harnesses before claiming coverage" — the repo's full
# harness roster (core.config.AI_CHOICES) with no adapter and no watcher
# wiring beyond the shared fallback.
_OTHER_HARNESSES: tuple[str, ...] = (
    "cursor",
    "copilot",
    "gemini",
    "qwen",
    "opencode",
    "windsurf",
    "kilocode",
    "auggie",
    "q",
    "kiro",
    "antigravity",
    "vibe",
    "pi",
    "letta",
    "llxprt",
)

_OTHER_ROWS: tuple[CapabilityRow, ...] = tuple(
    CapabilityRow(
        harness,
        "live_work_capture",
        CapabilityStatus.NOT_INSTRUMENTED,
        "none",
        "no Live Work hook adapter ships for this harness; changed files may still surface through the labeled watcher fallback",
    )
    for harness in _OTHER_HARNESSES
)

# ── Whole-mission lifecycle rows (#4268's 2026-09-14 clarification) ─────────
#
# The clarification demands a coverage matrix for the WHOLE mission — first
# specify, plan, task generation, implementation, review/rework,
# acceptance/merge and retrospective — each mapped to the existing event
# contract, the concrete seam that produces it, and the live consumer, with
# unsupported capture explicit. These rows carry harness ``"all"`` because
# the mission lifecycle is harness-independent (CLI-owned seams, not hook
# adapters) and they MAP seams this package does not own — contract kind,
# producer, consumer — never duplicate their producers. Continuity, stated
# once here instead of per row: repository and mission continuity come from
# the checkout's own binding (the same credential scope and canonical
# ``mission_id`` every seam resolves); session identity is honestly
# per-seam — a hook session is harness-scoped, a CLI moment is
# process-scoped, and a retry is a new linked invocation, never a forged
# continuation.

_MISSION_LIFECYCLE_ROWS: tuple[CapabilityRow, ...] = (
    CapabilityRow(
        "all",
        "mission_first_specify",
        CapabilityStatus.EXACT,
        "SpecifyStarted/SpecifyCompleted (spec_kitty_events.project_lifecycle) via emit_artifact_phase "
        "-> lifecycle_moment_handler (status/zeitgeist_bridge.py) -> live relay event.publish",
        "existing seam named, not duplicated (#4214's lane); retries dedupe on (event_type, mission, artifact)",
    ),
    CapabilityRow(
        "all",
        "mission_plan",
        CapabilityStatus.EXACT,
        "PlanStarted/PlanCompleted (spec_kitty_events.project_lifecycle) via emit_artifact_phase "
        "-> lifecycle_moment_handler (status/zeitgeist_bridge.py) -> live relay event.publish",
        "existing seam named, not duplicated (#4214's lane)",
    ),
    CapabilityRow(
        "all",
        "mission_task_generation",
        CapabilityStatus.EXACT,
        "TasksStarted/TasksCompleted with wp_count (spec_kitty_events.project_lifecycle) via emit_artifact_phase "
        "-> lifecycle_moment_handler (status/zeitgeist_bridge.py) -> live relay event.publish",
        "WPCreated is local+hosted only (outside the volatile vocabulary): work-package creation itself is not a live frame",
    ),
    CapabilityRow(
        "all",
        "mission_implementation",
        CapabilityStatus.EXACT,
        "WPStatusChanged (StatusTransitionPayload) via saas_moment_handler (status/zeitgeist_bridge.py) -> live relay event.publish",
        "existing seam named, not duplicated (#4327's WPStatusChanged fix); WP lane transitions (doing/for_review/done) only",
    ),
    CapabilityRow(
        "all",
        "mission_review_rework",
        CapabilityStatus.NOT_OBSERVABLE,
        "ReviewerSelfApproval (status/lifecycle_events.py) is local+hosted only",
        "no live producer: review outcomes are not in the volatile vocabulary; #4231's lane",
    ),
    CapabilityRow(
        "all",
        "mission_acceptance_merge",
        CapabilityStatus.NOT_OBSERVABLE,
        "none",
        "no producer: MissionClosed exists in the shared volatile vocabulary with no emitter in this repo, and the merge executor records no lifecycle event",
    ),
    CapabilityRow(
        "all",
        "mission_retrospective",
        CapabilityStatus.EXACT,
        "RetrospectiveCaptured/RetrospectiveCaptureFailed/RetrospectiveSkipped (retrospective/lifecycle_events.py) "
        "-> this package's live-work fanout -> work.lifecycle.retrospective_*.v1",
        "one frame per outcome after the local append; fire-and-forget with no retry (#4311 owns the shared wake-up window)",
    ),
)


def matrix_for_harness(harness: str) -> tuple[CapabilityRow, ...]:
    """The matrix rows for one harness (empty for an unknown harness)."""
    if harness == "claude":
        return _CLAUDE_ROWS
    if harness == "codex":
        return _CODEX_ROWS
    return tuple(row for row in _OTHER_ROWS if row.harness == harness)


@dataclass(frozen=True)
class HarnessHealth:
    """The runtime health of one harness's capture wiring."""

    harness: str
    hooks_installed: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "harness": self.harness,
            "hooks_installed": self.hooks_installed,
            "detail": self.detail,
        }


def _claude_hooks_installed(repo_root: Path) -> HarnessHealth:
    settings = repo_root / ".claude" / "settings.json"
    if not settings.exists():
        return HarnessHealth("claude", False, ".claude/settings.json not present")
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return HarnessHealth("claude", False, ".claude/settings.json unreadable")
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return HarnessHealth("claude", False, "no hooks section in .claude/settings.json")
    found: list[str] = []
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks", []) if isinstance(entry.get("hooks"), list) else []:
                if isinstance(hook, dict) and hook.get("type") == "command" and LIVE_WORK_HOOK_COMMAND_MARKER in str(hook.get("command", "")):
                    found.append(str(event))
    if found:
        return HarnessHealth("claude", True, f"live-work hooks on: {', '.join(sorted(set(found)))}")
    return HarnessHealth("claude", False, "no live-work hook command in .claude/settings.json")


def _codex_hooks_installed(repo_root: Path) -> HarnessHealth:
    import tomllib

    config = repo_root / ".codex" / "config.toml"
    if not config.exists():
        return HarnessHealth("codex", False, ".codex/config.toml not present")
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return HarnessHealth("codex", False, ".codex/config.toml unreadable")
    notify = data.get("notify")
    commands = notify if isinstance(notify, list) else [notify] if isinstance(notify, str) else []
    live = any(LIVE_WORK_HOOK_COMMAND_MARKER in str(command) for command in commands)
    if live:
        return HarnessHealth("codex", True, "live-work notify command configured")
    return HarnessHealth("codex", False, "no live-work notify command in .codex/config.toml")


def harness_health(harness: str, repo_root: Path) -> HarnessHealth | None:
    """Runtime hook-installation health for one harness (``None`` = no adapter)."""
    if harness == "claude":
        return _claude_hooks_installed(repo_root)
    if harness == "codex":
        return _codex_hooks_installed(repo_root)
    return None


class CapabilityMatrix:
    """The executable matrix: static rows plus runtime health states."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def rows(self) -> tuple[CapabilityRow, ...]:
        return _CLAUDE_ROWS + _CODEX_ROWS + _MISSION_LIFECYCLE_ROWS + _POLICY_ROWS + _OTHER_ROWS

    def health(self) -> dict[str, HarnessHealth]:
        return {harness: health for harness in ("claude", "codex") if (health := harness_health(harness, self._repo_root)) is not None}

    def degraded_harnesses(self, configured_harnesses: frozenset[str]) -> list[str]:
        """Configured harnesses whose capture hooks are missing.

        This is the "no silent green" enforcement: a harness the project
        actually uses (``.kittify/config.yaml`` available list) with no
        installed Live Work hooks is named here, and the ``live-work
        matrix`` command exits non-zero on it.
        """
        degraded: list[str] = []
        for harness in sorted(configured_harnesses):
            health = harness_health(harness, self._repo_root)
            if health is not None and not health.hooks_installed:
                degraded.append(harness)
            elif health is None and harness in _OTHER_HARNESSES:
                # No adapter ships for this harness — an explicit
                # not-instrumented row, not a degraded state, unless hooks
                # of its own exist that we cannot see.
                continue
        return degraded

    def as_dict(self) -> dict[str, object]:
        return {
            "codec": codec_state(),
            "rows": [row.as_dict() for row in self.rows()],
            "health": {h: health.as_dict() for h, health in self.health().items()},
        }
