"""SessionPresenceManager — orchestrates session presence across all configured agents.

Takes the committed ``SessionPresenceContent`` from the one content authority
(:mod:`specify_cli.session_presence.projection`, #5215), then delegates to
per-agent writers to install or update the orientation block in each agent's
configuration files. :meth:`SessionPresenceManager.live_content` adds live
health for the SessionStart hook only.

This module is the single entry point for all session presence write operations.
Writers are selected via ``projection.orientation_writer()`` and swallowed exceptions ensure callers
never need to guard against failures from this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NamedTuple

from specify_cli.core.version_compare import is_version_newer

from .content import SessionPresenceContent
from .projection import expected_orientation, orientation_writer, resolve_project_slug
from .upgrade_check import UpgradeChecker

if TYPE_CHECKING:
    from specify_cli.core.agent_config import AgentConfig

_logger = logging.getLogger(__name__)


class InstallResult(NamedTuple):
    """Result of a SessionPresenceManager install or update operation."""

    changes: list[str]
    warnings: list[str]


@dataclass
class SessionPresenceManager:
    """Orchestrate session presence installation across all configured agents.

    Attributes:
        project_root: Root directory of the spec-kitty project (parent of ``.kittify/``).
        agent_config: Loaded agent configuration (from ``specify_cli.core.agent_config``).
    """

    project_root: Path
    agent_config: AgentConfig

    def _build_content(self) -> SessionPresenceContent:
        """Return the committed orientation content (#5215).

        Deterministic: the identity project name and ``healthy``. The shipped
        session-presence migrations write through this method, so it must never
        carry live health. Delegates to the one content authority,
        :func:`specify_cli.session_presence.projection.expected_orientation`.
        """
        return expected_orientation(self.project_root)

    def live_content(self) -> SessionPresenceContent:
        """Return the orientation the SessionStart hook prints, with live health.

        Same version and project name as :meth:`_build_content`; health comes
        from pending migrations and the upgrade cache. Falls back to the cached
        upgrade state on any error so a session start is never blocked.
        """
        from importlib.metadata import version

        checker = UpgradeChecker()
        avail = checker.get_available_version()
        if avail is None:
            checker.check_in_background()
        current = version("spec-kitty-cli")
        slug = resolve_project_slug(self.project_root)

        health: Literal["healthy", "upgrade-available", "migration-required"]
        try:
            from specify_cli.compat import Decision, Invocation, plan as compat_plan

            inv = Invocation(
                command_path=("session-start",),
                raw_args=("session-start",),
                is_help=False,
                is_version=False,
                flag_no_nag=True,
                env_ci=False,
                stdout_is_tty=False,
            )
            _root = self.project_root

            def _resolver(_cwd: Path) -> Path | None:
                return _root

            result = compat_plan(inv, project_root_resolver=_resolver)
            if result.decision == Decision.BLOCK_PROJECT_MIGRATION:
                health = "migration-required"
            elif is_version_newer(avail, current):
                health = "upgrade-available"
            else:
                health = "healthy"
        except Exception:
            # Best-effort health check — never block session start
            health = "upgrade-available" if is_version_newer(avail, current) else "healthy"

        return SessionPresenceContent(current, slug, health, avail)

    def install(self) -> InstallResult:
        """Write presence for each configured agent that doesn't have it yet.

        Idempotent — safe to call multiple times.  Only writes to agents whose
        writer reports ``can_write()`` and not yet ``has_presence()``.

        Returns:
            ``InstallResult`` with lists of changes made and any warnings.
        """
        content = self._build_content()
        changes: list[str] = []
        warnings: list[str] = []
        for key in getattr(self.agent_config, "available", []):
            try:
                writer = orientation_writer(self.project_root, key, None)
                if writer is not None and not writer.has_presence(self.project_root):
                    writer.write(self.project_root, content)
                    changes.append(f"Wrote orientation for {key}")
                    warnings.extend(_writer_notices(writer, self.project_root))
            except Exception as exc:
                warnings.append(f"Failed to write orientation for {key}: {exc}")
                _logger.warning("SessionPresenceManager.install failed for %s: %s", key, exc)
        return InstallResult(changes=changes, warnings=warnings)

    def update(
        self,
        agents: set[str] | None = None,
        dry_run: bool = False,
    ) -> InstallResult:
        """Update (replace) presence for specified agents, whether or not already present.

        Unlike ``install()``, ``update()`` overwrites the orientation block even
        when it already exists — useful for upgrading the content after a version
        bump.

        Args:
            agents: Set of agent keys to update.  ``None`` means all configured agents.
            dry_run: If ``True``, return the list of changes without writing anything.

        Returns:
            ``InstallResult`` with lists of changes (or would-be changes) and warnings.
        """
        content = self._build_content()
        target_agents = agents if agents is not None else set(getattr(self.agent_config, "available", []))
        changes: list[str] = []
        warnings: list[str] = []
        for key in target_agents:
            try:
                writer = orientation_writer(self.project_root, key, None)
                if writer is not None:
                    if not dry_run:
                        writer.write(self.project_root, content)
                    changes.append(f"{'Would write' if dry_run else 'Wrote'} orientation for {key}")
                else:
                    _logger.debug("NullWriter or no harness dir for %s — skipping", key)
            except Exception as exc:
                warnings.append(f"Failed to update orientation for {key}: {exc}")
        return InstallResult(changes=changes, warnings=warnings)


def _writer_notices(writer: object, project_root: Path) -> list[str]:
    """Follow-up notices a writer leaves after a write (a committed file it would not edit)."""
    from .writers.claude_code import ClaudeCodeWriter, committed_settings_notice

    if not isinstance(writer, ClaudeCodeWriter):
        return []
    notice = committed_settings_notice(project_root)
    return [notice] if notice else []


__all__ = ["InstallResult", "SessionPresenceManager"]
