"""SessionPresenceManager — orchestrates session presence across all configured agents.

Builds ``SessionPresenceContent`` from the current CLI version and the upgrade
cache, then delegates to per-agent writers to install or update the orientation
block in each agent's configuration files.

This module is the single entry point for all session presence write operations.
Writers are looked up via ``get_writer()`` and swallowed exceptions ensure callers
never need to guard against failures from this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NamedTuple

from specify_cli.core.version_compare import is_version_newer

from .content import SessionPresenceContent
from .upgrade_check import UpgradeChecker
from .writers.registry import get_writer

if TYPE_CHECKING:
    from specify_cli.core.agent_config import AgentConfig

_logger = logging.getLogger(__name__)


def local_presence_content(project_slug: str) -> SessionPresenceContent:
    """Render installed-version orientation without consulting live health services."""
    from importlib.metadata import version, PackageNotFoundError

    try:
        current = version("spec-kitty-cli")
    except PackageNotFoundError as exc:
        raise ValueError("Installed session content version is unavailable") from exc
    if not current or not project_slug:
        raise ValueError("Missing required local session content")
    return SessionPresenceContent(current, project_slug, "healthy", None)


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

    def _project_slug(self) -> str:
        """Read the canonical project identity, independent of agent settings."""
        from specify_cli.identity.project import load_identity

        return load_identity(self.project_root / ".kittify" / "config.yaml").project_slug or "unknown"

    def _build_content(self) -> SessionPresenceContent:
        """Build ``SessionPresenceContent`` from current version and upgrade cache.

        Determines health status by checking for pending migrations and available
        upgrades.  Falls back to ``"healthy"`` on any error so callers are never
        blocked.
        """
        from importlib.metadata import version

        checker = UpgradeChecker()
        avail = checker.get_available_version()
        if avail is None:
            checker.check_in_background()
        current = version("spec-kitty-cli")
        slug = self._project_slug()

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
            writer = get_writer(key)
            try:
                if writer.can_write(self.project_root) and not writer.has_presence(self.project_root):
                    writer.write(self.project_root, content)
                    changes.append(f"Wrote orientation for {key}")
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
        content = local_presence_content(self._project_slug()) if dry_run else self._build_content()
        target_agents = agents if agents is not None else set(getattr(self.agent_config, "available", []))
        changes: list[str] = []
        warnings: list[str] = []
        for key in target_agents:
            writer = get_writer(key)
            try:
                if writer.can_write(self.project_root):
                    if not dry_run:
                        writer.write(self.project_root, content)
                    changes.append(f"{'Would write' if dry_run else 'Wrote'} orientation for {key}")
                else:
                    _logger.debug("NullWriter or no harness dir for %s — skipping", key)
            except Exception as exc:
                warnings.append(f"Failed to update orientation for {key}: {exc}")
        return InstallResult(changes=changes, warnings=warnings)


__all__ = ["InstallResult", "SessionPresenceManager"]
