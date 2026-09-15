"""Live Work hook adapters — harness payloads → observations (spec-kitty#4268).

A :class:`HookAdapter` owns one harness's hook payload grammar: it parses
the JSON a harness pipes to a registered hook command, maps the externally
observable actions onto canonical :class:`~live_work.models.Observation`
records, and declares its own capability surface (what this harness's
supported hooks can and cannot observe, with honest limitations — the
machine-readable half of the capability matrix).

Adapters never raise on a malformed or unknown payload: a hook that fails
takes the harness invocation down with it, so every defect resolves to a
dropped observation (plus, where honest, a recorded coverage gap), never an
error exit. Private reasoning, raw terminal output, and secret-bearing
content never enter an adapter's output — see :mod:`live_work.redaction`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from ..models import Observation

__all__ = ["HookAdapter", "HARNESSES_WITH_ADAPTERS"]


class HookAdapter(Protocol):
    """The canonical hook-adapter API every harness adapter implements."""

    harness: str
    """The harness key (``claude``/``codex``) — the writers-registry key."""

    def parse(self, payload: Mapping[str, Any], *, repo_root: Path) -> list[Observation]:
        """Map one hook payload to zero or more observations.

        ``repo_root`` is the repository the observation binds to (from the
        payload's own ``cwd`` when present, else the process cwd); bindings
        are resolved by :func:`live_work.bindings.resolve_bindings` — a
        mission is bound only when determinable, never guessed.
        """
        ...

    def capability_notes(self) -> Mapping[str, str]:
        """Honest per-surface limitations, keyed by the capability row id."""
        ...


HARNESSES_WITH_ADAPTERS: tuple[str, ...] = ("claude", "codex")
"""Harnesses with a Live Work hook adapter in this package (the versions
Team Kitty and the factory actually use). Every other production harness
is enumerated by the capability matrix as not-yet-instrumented — claiming
coverage for a harness with no adapter is exactly the silent green this
package exists to prevent."""


def get_adapter(harness: str) -> HookAdapter | None:
    """Return the adapter for *harness*, or ``None`` when none ships."""
    from .claude_code import ClaudeCodeHookAdapter
    from .codex import CodexNotifyAdapter

    adapters: dict[str, HookAdapter] = {
        "claude": ClaudeCodeHookAdapter(),
        "codex": CodexNotifyAdapter(),
    }
    return adapters.get(harness)
