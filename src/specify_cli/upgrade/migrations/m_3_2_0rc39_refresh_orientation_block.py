"""Migration: refresh stale session-presence orientation blocks.

For projects that already have a ``<!-- spec-kitty:orientation -->`` block
installed, this migration detects when the block content is out-of-date
(e.g. after the orientation wording changed in 3.2.0rc39) and replaces it
with the current rendering.

``detect()`` returns ``True`` when *any* configured harness has a present
orientation block whose content differs from the freshly-rendered block.

``apply()`` calls ``writer.write()`` for each stale harness.  Because
``MarkdownRulesWriter.write()`` already performs an in-place replace of the
managed section, calling it on an already-current block is a safe no-op.

This migration purposefully does NOT install absent blocks — that is the
responsibility of the Phase 1/2 install migrations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

if TYPE_CHECKING:
    from specify_cli.session_presence.content import SessionPresenceContent

__all__ = ["RefreshOrientationBlockMigration"]


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions; no registry or config I/O)
# ---------------------------------------------------------------------------


def _extract_section(project_root: Path, rules_path: str) -> str | None:
    """Read and return the orientation section from *rules_path*, or ``None``.

    Extracts the content from ``SECTION_OPEN`` through ``SECTION_CLOSE``
    (inclusive), preserving any trailing newline, so the result can be
    compared directly against ``content.render()``.
    """
    from specify_cli.session_presence.content import SECTION_CLOSE, SECTION_OPEN

    target = project_root / rules_path
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return None
    start = text.find(SECTION_OPEN)
    if start == -1:
        return None
    end = text.find(SECTION_CLOSE, start)
    if end == -1:
        return None
    end += len(SECTION_CLOSE)
    if text[end : end + 1] == "\n":
        end += 1
    return text[start:end]


def _build_content(project_path: Path) -> SessionPresenceContent:
    """Construct a ``SessionPresenceContent`` for *project_path*."""
    from specify_cli.core.agent_config import load_agent_config
    from specify_cli.session_presence.content import SessionPresenceContent
    from specify_cli.session_presence.manager import SessionPresenceManager

    config = load_agent_config(project_path)
    manager = SessionPresenceManager(project_path, config)
    result = manager._build_content()
    assert isinstance(result, SessionPresenceContent)
    return result


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


@MigrationRegistry.register
class RefreshOrientationBlockMigration(BaseMigration):
    """Refresh stale session-presence orientation blocks in configured harnesses."""

    migration_id = "3_2_0rc39_refresh_orientation_block"
    description = (
        "Refresh stale orientation blocks in all configured harnesses — "
        "replaces any out-of-date <!-- spec-kitty:orientation --> section "
        "with the current wording (only touches installed blocks; "
        "absent blocks are left for the install migrations)"
    )
    target_version = "3.2.0rc39"
    runs_on_worktrees = False

    @staticmethod
    def _stale_keys(project_path: Path, rendered: str) -> list[str]:
        """Return configured harness keys whose orientation block is present but stale.

        Skips harnesses where ``has_presence()`` is ``False`` — those are the
        install migrations' responsibility.  Skips harnesses whose writer does
        not expose a ``rules_path`` (i.e. ``NullWriter``).
        """
        from specify_cli.core.agent_config import load_agent_config
        from specify_cli.session_presence.writers.markdown_rules import MarkdownRulesWriter
        from specify_cli.session_presence.writers.registry import get_writer

        config = load_agent_config(project_path)
        if not config:
            return []

        stale: list[str] = []
        for key in config.available:
            writer = get_writer(key)
            if not writer.has_presence(project_path):
                continue
            if not isinstance(writer, MarkdownRulesWriter):
                continue
            existing = _extract_section(project_path, writer.rules_path)
            if existing != rendered:
                stale.append(key)
        return stale

    # ------------------------------------------------------------------
    # BaseMigration interface
    # ------------------------------------------------------------------

    def detect(self, project_path: Path) -> bool:
        """Return ``True`` when any configured harness has a stale orientation block."""
        if not (project_path / ".kittify").is_dir():
            return False
        try:
            content = _build_content(project_path)
            return bool(self._stale_keys(project_path, content.render()))
        except Exception:
            return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not (project_path / ".kittify").is_dir():
            return False, ".kittify/ directory does not exist (not initialized)"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Replace each stale orientation block with freshly-rendered content."""
        content = _build_content(project_path)
        rendered = content.render()
        stale = self._stale_keys(project_path, rendered)

        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=[
                    f"Would refresh stale orientation block for harness: {key}"
                    for key in stale
                ],
            )

        if not stale:
            return MigrationResult(success=True, changes_made=[])

        from specify_cli.session_presence.writers.registry import get_writer

        applied: list[str] = []
        for key in stale:
            writer = get_writer(key)
            writer.write(project_path, content)
            applied.append(f"Refreshed orientation block for harness: {key}")

        return MigrationResult(success=True, changes_made=applied)
