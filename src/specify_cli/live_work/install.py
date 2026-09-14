"""Live Work hook installation (spec-kitty#4268).

Registers the capture hook commands in each harness's native configuration,
reusing the canonical registrars — never a second settings writer:

* Claude Code — ``spec-kitty live-work hook claude`` on the four mapped
  events (SessionStart/SessionEnd/PreToolUse/PostToolUse) via
  :class:`specify_cli.session_presence.hooks.ClaudeCodeHookRegistrar`,
  the same atomic merge/preserve/unregister path the lint and presence
  hooks already use;
* Codex — a ``notify`` entry in ``config.toml``. The notify key is merged
  *textually* (append-only): parsing and re-serializing a user's TOML
  would destroy their comments, and an existing non-spec-kitty ``notify``
  is never clobbered — the install reports refusal instead.

Both directions are idempotent, and uninstall removes exactly the
spec-kitty entries, never sibling hooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .adapters.claude_code import CLAUDE_HOOK_COMMANDS

__all__ = [
    "CLAUDE_LIVE_WORK_COMMAND",
    "CODEX_LIVE_WORK_COMMAND",
    "CODEX_NOTIFY_LINE",
    "InstallOutcome",
    "install_hooks",
    "uninstall_hooks",
]


CLAUDE_LIVE_WORK_COMMAND: Final[str] = "spec-kitty live-work hook claude"
CODEX_LIVE_WORK_COMMAND: Final[str] = "spec-kitty live-work hook codex"
CODEX_NOTIFY_LINE: Final[str] = f'notify = ["{CODEX_LIVE_WORK_COMMAND}"]'

_CLAUDE_SETTINGS_PATH: Final[Path] = Path(".claude") / "settings.json"
_CODEX_CONFIG_PATH: Final[Path] = Path(".codex") / "config.toml"


@dataclass(frozen=True)
class InstallOutcome:
    """What one install/uninstall actually did — never a silent no-op."""

    harness: str
    installed: bool
    detail: str


def install_hooks(harness: str, project_root: Path) -> InstallOutcome:
    """Idempotently install the Live Work capture hooks for one harness."""
    if harness == "claude":
        return _install_claude(project_root)
    if harness == "codex":
        return _install_codex(project_root)
    return InstallOutcome(harness, False, "no Live Work adapter ships for this harness")


def uninstall_hooks(harness: str, project_root: Path) -> InstallOutcome:
    """Idempotently remove the Live Work capture hooks for one harness."""
    if harness == "claude":
        return _uninstall_claude(project_root)
    if harness == "codex":
        return _uninstall_codex(project_root)
    return InstallOutcome(harness, False, "no Live Work adapter ships for this harness")


# ── Claude Code ──────────────────────────────────────────────────────────────


def _install_claude(project_root: Path) -> InstallOutcome:
    from specify_cli.session_presence.hooks import ClaudeCodeHookRegistrar

    settings = project_root / _CLAUDE_SETTINGS_PATH
    if not settings.exists():
        # Respect deletions: never create a settings.json the project chose
        # not to have. The capability matrix reports the not-installed state.
        return InstallOutcome("claude", False, ".claude/settings.json not present (install skipped)")
    changed: list[str] = []
    for event, matcher in CLAUDE_HOOK_COMMANDS.items():
        registrar = ClaudeCodeHookRegistrar(event_key=event)
        if not registrar.is_registered(project_root, CLAUDE_LIVE_WORK_COMMAND):
            registrar.register(project_root, CLAUDE_LIVE_WORK_COMMAND, matcher=matcher)
            changed.append(event)
    if changed:
        return InstallOutcome("claude", True, f"registered live-work hooks on: {', '.join(changed)}")
    return InstallOutcome("claude", True, "live-work hooks already registered")


def _uninstall_claude(project_root: Path) -> InstallOutcome:
    from specify_cli.session_presence.hooks import ClaudeCodeHookRegistrar

    removed: list[str] = []
    for event in CLAUDE_HOOK_COMMANDS:
        registrar = ClaudeCodeHookRegistrar(event_key=event)
        if registrar.is_registered(project_root, CLAUDE_LIVE_WORK_COMMAND):
            registrar.unregister(project_root, CLAUDE_LIVE_WORK_COMMAND)
            removed.append(event)
    if removed:
        return InstallOutcome("claude", True, f"removed live-work hooks from: {', '.join(removed)}")
    return InstallOutcome("claude", True, "no live-work hooks were registered")


# ── Codex ────────────────────────────────────────────────────────────────────


def _install_codex(project_root: Path) -> InstallOutcome:
    config = project_root / _CODEX_CONFIG_PATH
    if not config.parent.exists():
        return InstallOutcome("codex", False, ".codex/ not present (install skipped)")
    if not config.exists():
        config.write_text(f"{CODEX_NOTIFY_LINE}\n", encoding="utf-8")
        return InstallOutcome("codex", True, "created .codex/config.toml with the live-work notify entry")
    text = config.read_text(encoding="utf-8")
    if CODEX_NOTIFY_LINE in text:
        return InstallOutcome("codex", True, "live-work notify entry already present")
    if _has_notify_key(text):
        return InstallOutcome(
            "codex",
            False,
            "an existing notify key is configured; refusing to clobber it (add the spec-kitty live-work command to the existing list by hand)",
        )
    config.write_text(text.rstrip("\n") + f"\n{CODEX_NOTIFY_LINE}\n", encoding="utf-8")
    return InstallOutcome("codex", True, "appended the live-work notify entry")


def _uninstall_codex(project_root: Path) -> InstallOutcome:
    config = project_root / _CODEX_CONFIG_PATH
    if not config.exists():
        return InstallOutcome("codex", True, "no .codex/config.toml present")
    text = config.read_text(encoding="utf-8")
    if CODEX_NOTIFY_LINE not in text:
        return InstallOutcome("codex", True, "no live-work notify entry present")
    lines = [line for line in text.splitlines() if line.strip() != CODEX_NOTIFY_LINE]
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return InstallOutcome("codex", True, "removed the live-work notify entry")


def _has_notify_key(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("notify") and ("=" in stripped):
            return True
    return False
