"""Project-aware template resolution through the 6-tier override chain.

Composes MissionTemplateRepository (doctrine-level, package-default tier) with the
charter factory's tier chain. Charter is the
concretization of doctrine into local context-aware legislation.

FR-003 (charter-sole-door-bypass-closure-01KZ3WAA WP05) — **this module is
now a thin delegate.** :class:`CharterTemplateResolver` used to import
``charter.offering.resolver``'s tier functions itself, making it a *second*
charter-layer door onto that chain alongside
:class:`charter.activation.resolver.ActiveCharterService` (the factory) — the C-001
"two doors within charter" seam FR-003 closes. Every tier-chain call now
routes through the factory's ``resolve_command_asset`` /
``resolve_content_asset`` methods, and this module no longer imports
``charter.offering.resolver`` at all (only the ``ResolutionTier`` *type*, via the
sanctioned ``charter.resolution`` facade, which is a pure re-export
preserving object identity).

The class is retained rather than retired because it is part of the public
``charter`` package surface (``charter/__init__.py`` exports it), and this
mission's own precedent for the identical situation is delegation, not
deletion: WP01 turned
``specify_cli.doctrine_service_factory.build_activation_aware_doctrine_service``
into a thin re-export of the unified charter builder instead of removing it.
Its one production caller (``specify_cli/runtime/resolver.py``) no longer
uses this class at all — it calls the factory directly — so the production
path has exactly one door.

Scope note: the ``resolve_*_path`` methods below are **not** part of the
FR-003 seam and are intentionally left reaching
:class:`MissionTemplateRepository` directly. They are package-default
repository lookups, not ``charter.offering.resolver`` tier-chain calls — the same
doctrine surface ``doctrine/resolver.py``'s own package-default tier consumes. There is
therefore no second *authority* to consolidate: both these methods and the
factory's ``resolve_package_default_*`` methods delegate to that one
repository. Routing them through the factory as well would need
``missions_root`` plumbing this class does not carry (its ``__init__``
accepts an arbitrary repository object), growing the diff without removing
an authority.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from charter.resolution import ResolutionTier
from charter.activation.resolver import ActiveCharterService
from charter.offering.missions.repository import MissionTemplateRepository, TemplateResult

__all__ = [
    "CharterTemplateResolver",
]


class CharterTemplateResolver:
    """6-tier project-aware template resolution.

    Resolution order: OVERRIDE > LEGACY > ORG > GLOBAL_MISSION > GLOBAL > PACKAGE_DEFAULT.

    A thin delegate onto :class:`charter.activation.resolver.ActiveCharterService` for the
    tier chain (FR-003) — see the module docstring.
    """

    def __init__(self, repo: MissionTemplateRepository | None = None) -> None:
        self._repo = repo or MissionTemplateRepository.default()

    @classmethod
    def from_missions_root(cls, missions_root: Path) -> CharterTemplateResolver:
        """Create a resolver backed by a specific missions root."""
        return cls(MissionTemplateRepository(missions_root))

    def resolve_command_template_path(self, mission: str, name: str) -> Path | None:
        """Resolve a package-default command template path through charter."""
        return self._repo._command_template_path(mission, name)

    def resolve_content_template_path(self, mission: str, name: str) -> Path | None:
        """Resolve a package-default content template path through charter."""
        return self._repo._content_template_path(mission, name)

    def resolve_mission_config_path(self, mission: str) -> Path | None:
        """Resolve a package-default mission config path through charter."""
        return self._repo._mission_config_path(mission)

    def resolve_command_template(
        self,
        mission: str,
        name: str,
        project_dir: Path | None = None,
    ) -> TemplateResult:
        """Resolve a command template through the 6-tier override chain.

        Args:
            mission: Mission name.
            name: Template name without ``.md`` extension.
            project_dir: Project root for override/legacy lookups.
                If ``None``, falls back to doctrine-level lookup only.

        Returns:
            TemplateResult with content, origin, and tier.

        Raises:
            FileNotFoundError: If template not found at any tier.
        """
        if project_dir is not None:
            # FR-003: tier chain reached through the factory, never through a
            # direct ``charter.offering.resolver`` import of our own.
            result = ActiveCharterService.resolve_command_asset(f"{name}.md", project_dir, mission=mission)
            content = result.path.read_text(encoding="utf-8")
            origin = self._tier_to_origin(result.tier, mission, "command-templates", f"{name}.md")
            return TemplateResult(content=content, origin=origin, tier=result.tier)

        # No project context — doctrine-only lookup
        template = self._repo.get_command_template(mission, name)
        if template is None:
            raise FileNotFoundError(
                f"Command template '{name}.md' not found for mission '{mission}'"
            )
        return TemplateResult(
            content=template.content,
            origin=template.origin,
            tier=ResolutionTier.PACKAGE_DEFAULT,
        )

    def resolve_content_template(
        self,
        mission: str,
        name: str,
        project_dir: Path | None = None,
    ) -> TemplateResult:
        """Resolve a content template through the 6-tier override chain.

        Args:
            mission: Mission name.
            name: Template filename with extension.
            project_dir: Project root for override/legacy lookups.
                If ``None``, falls back to doctrine-level lookup only.

        Returns:
            TemplateResult with content, origin, and tier.

        Raises:
            FileNotFoundError: If template not found at any tier.
        """
        if project_dir is not None:
            # FR-003: tier chain reached through the factory, never through a
            # direct ``charter.offering.resolver`` import of our own.
            result = ActiveCharterService.resolve_content_asset(name, project_dir, mission=mission)
            content = result.path.read_text(encoding="utf-8")
            origin = self._tier_to_origin(result.tier, mission, "templates", name)
            return TemplateResult(content=content, origin=origin, tier=result.tier)

        # No project context — doctrine-only lookup
        template = self._repo.get_content_template(mission, name)
        if template is None:
            raise FileNotFoundError(
                f"Content template '{name}' not found for mission '{mission}'"
            )
        return TemplateResult(
            content=template.content,
            origin=template.origin,
            tier=ResolutionTier.PACKAGE_DEFAULT,
        )

    @staticmethod
    def _tier_to_origin(tier: Any, mission: str, asset_type: str, filename: str) -> str:
        tier_prefix = {
            ResolutionTier.OVERRIDE: "override",
            ResolutionTier.LEGACY: "legacy",
            ResolutionTier.ORG: "org",
            ResolutionTier.GLOBAL_MISSION: "global",
            ResolutionTier.GLOBAL: "global",
            ResolutionTier.PACKAGE_DEFAULT: "doctrine",
        }
        prefix = tier_prefix.get(tier, "unknown")
        return f"{prefix}/{mission}/{asset_type}/{filename}"
