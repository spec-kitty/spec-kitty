"""SessionPresenceContent dataclass and render logic.

This is the single place where the orientation block text is generated.
All harness writers consume this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SECTION_OPEN = "<!-- spec-kitty:orientation -->"
SECTION_CLOSE = "<!-- /spec-kitty:orientation -->"

__all__ = [
    "SECTION_OPEN",
    "SECTION_CLOSE",
    "SessionPresenceContent",
]


@dataclass(frozen=True)
class SessionPresenceContent:
    """Immutable value object representing what to inject into an agent config file.

    Invariants (from data-model.md):
    - ``frozen=True`` — value object, never mutated after creation.
    - ``available_version`` is ``None`` only when no cache file exists yet.
    - When ``health == "upgrade-available"``, ``available_version`` is not ``None``
      and differs from ``version``.
    """

    version: str
    project_slug: str
    health: Literal["healthy", "upgrade-available", "migration-required"]
    available_version: str | None  # None when cache not yet populated
    #: How the harness starts a full Mission (``invocation.invocation_for_writer``);
    #: writers set it per harness, the default is the slash-command form.
    specify_invocation: str = "`/spec-kitty.specify`"

    def render(self) -> str:
        """Render the orientation block text.

        Returns a string that starts with ``SECTION_OPEN`` and ends with
        ``SECTION_CLOSE`` followed by a newline, suitable for injection into
        any text-based agent configuration file.
        """
        upgrade_line = f"\n⚠ Upgrade available: {self.available_version} — run `spec-kitty upgrade --cli` to update." if self.health == "upgrade-available" else ""
        migration_line = "\n⚠ Project migration required — run `spec-kitty upgrade` before using missions." if self.health == "migration-required" else ""
        return (
            f"{SECTION_OPEN}\n"
            f"**Spec Kitty v{self.version}** — "
            f"project: {self.project_slug} ({self.health})"
            f"{upgrade_line}{migration_line}\n\n"
            "Two usage patterns:\n"
            "- **Full mission** (spec → plan → tasks → implement → review → merge):\n"
            '  trigger: "spec out", "create a mission", "write a spec", "plan this"\n'
            f"  → run {self.specify_invocation}\n"
            "- **Lightweight dispatch** (ad-hoc fix, question, or advice — no mission created):\n"
            '  trigger: "hey spec kitty", "use spec kitty to", "spec kitty <anything>"\n'
            '  → **ALWAYS run `spec-kitty dispatch "<request verbatim>"` — do NOT answer directly.**\n'
            "  If you know the right profile, pass it to skip routing:\n"
            '  `spec-kitty dispatch "<request verbatim>" --profile <profile-id>`\n'
            "  Reason: `spec-kitty dispatch` loads governance context, routes the request,\n"
            "  and opens the Op. Skipping it produces ungoverned, untracked responses.\n"
            "  After finishing the work, close the Op with the command printed in the capsule\n"
            "  (`spec-kitty profile-invocation complete --invocation-id <id> "
            "--outcome <done|failed|abandoned>`).\n"
            f"{SECTION_CLOSE}\n"
        )
