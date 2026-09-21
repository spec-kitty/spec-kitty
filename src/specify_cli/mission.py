"""Mission system for Spec Kitty.

This module provides the infrastructure for loading and managing missions,
which allow Spec Kitty to support multiple domains (software dev, research,
writing, etc.) with domain-specific templates, workflows, and validation.
"""

from specify_cli.core.constants import (
    KITTY_SPECS_DIR,
    MISSION_TYPE_RESEARCH,
    MISSION_TYPE_SOFTWARE_DEV,
)
import os
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# WP02 / FR-012 (C-001): the single boundary-safe mission-type canonicalizer lives
# in ``charter`` so ``specify_cli`` may consume it without crossing the layer rule.
from charter.activation.mission_type_key import read_mission_type
from specify_cli.mission_metadata import load_meta_or_empty

if TYPE_CHECKING:
    # Type-only: the charter import is otherwise kept lazy/local (T020/T021)
    # so this module's runtime import graph is unchanged for callers that
    # never hit the org-aware fallback path.
    from charter.offering.missions.models import MissionType


class MissionError(Exception):
    """Base exception for mission-related errors."""

    pass


class MissionNotFoundError(MissionError):
    """Raised when a mission cannot be found."""

    pass


MISSION_ROOT_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "version",
    "domain",
    "workflow",
    "artifacts",
    "paths",
    "validation",
    "mcp_tools",
    "agent_context",
    "task_metadata",
    "commands",
    "task_types",
)

# These keys belonged to the retired mission-DSL v1 state machine (mission
# dead-port-disposition-01M1TZVN removed its interpreter and deleted the
# ``states:``/``transitions:`` blocks from the built-in packs). Tolerance is
# retained on purpose: third-party packs and project ``.kittify/overrides``
# ``mission.yaml`` files may still carry the keys, and mission discovery must
# not skip an otherwise valid mission over inert DSL residue.
MISSION_COMPAT_IGNORED_FIELDS: tuple[str, ...] = (
    "mission",
    "initial",
    "states",
    "transitions",
    "guards",
    "inputs",
    "outputs",
)


def _packaged_missions_dir() -> Path:
    return Path(__file__).resolve().parent / "missions"


def _mission_dir_if_valid(path: Path) -> Path | None:
    return path if path.is_dir() and (path / "mission.yaml").exists() else None


def _mission_path_by_name(mission_name: str, kittify_dir: Path) -> Path | None:
    project_path = _mission_dir_if_valid(kittify_dir / "missions" / mission_name)
    if project_path is not None:
        return project_path
    return _mission_dir_if_valid(_packaged_missions_dir() / mission_name)


class PhaseConfig(BaseModel):
    """Workflow phase definition."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Phase identifier")
    description: str = Field(..., description="Phase description")


class ArtifactsConfig(BaseModel):
    """Required and optional artifacts."""

    model_config = ConfigDict(extra="forbid")

    required: list[str] = Field(default_factory=list, description="Artifacts required for acceptance")
    optional: list[str] = Field(default_factory=list, description="Optional artifacts and directories")


class ValidationConfig(BaseModel):
    """Validation rules for the mission."""

    model_config = ConfigDict(extra="forbid")

    checks: list[str] = Field(default_factory=list, description="Validation checks executed for this mission")
    custom_validators: bool = Field(default=False, description="Whether validators.py should be invoked")


class WorkflowConfig(BaseModel):
    """Mission workflow configuration."""

    model_config = ConfigDict(extra="forbid")

    phases: list[PhaseConfig] = Field(..., min_length=1, description="Ordered workflow phases")


class MCPToolsConfig(BaseModel):
    """Mission MCP tool recommendations."""

    model_config = ConfigDict(extra="forbid")

    required: list[str] = Field(default_factory=list)
    recommended: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class CommandConfig(BaseModel):
    """Command customization for a mission."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., description="Command-specific prompt/description")


class TaskTypeConfig(BaseModel):
    """Task type metadata used for agent-profile suggestion and task routing."""

    model_config = ConfigDict(extra="forbid")

    agent_role: str | None = Field(default=None, description="Suggested agent role/profile")
    description: str | None = Field(default=None, description="Human-readable task type description")


class TaskMetadataConfig(BaseModel):
    """Task metadata definitions."""

    model_config = ConfigDict(extra="forbid")

    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


VALID_PATH_KEYS: frozenset[str] = frozenset({"workspace", "tests", "deliverables", "documentation", "data"})
"""Canonical path-convention keys (C-005). Single authority reused by MissionConfig validation
and the project-level ``path_conventions`` override reader."""


class MissionConfig(BaseModel):
    """Complete mission configuration schema."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Mission display name")
    description: str = Field(..., description="Mission description")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Semver version (major.minor.patch)")
    domain: Literal["software", "research", "writing", "seo", "other"] = Field(..., description="Mission domain classification")
    workflow: WorkflowConfig = Field(..., description="Workflow definition")
    artifacts: ArtifactsConfig = Field(..., description="Artifacts required/optional")
    paths: dict[str, str] = Field(
        default_factory=dict,
        description="Path conventions (workspace/tests/deliverables/documentation/data/etc.)",
    )
    validation: ValidationConfig = Field(default_factory=ValidationConfig, description="Validation settings")
    mcp_tools: MCPToolsConfig | None = Field(default=None, description="MCP tool recommendations")
    agent_context: str | None = Field(default=None, description="Agent instructions/personality")
    task_metadata: TaskMetadataConfig | None = Field(default=None, description="Task metadata definitions")
    commands: dict[str, CommandConfig] | None = Field(default=None, description="Command-specific prompts")
    task_types: dict[str, TaskTypeConfig] | None = Field(
        default=None,
        description="Task type metadata for routing/profile suggestion",
    )

    def model_post_init(self, __context: Any) -> None:  # pragma: no cover - simple warning logic
        """Warn on unknown path convention keys while permitting customization."""
        unknown_paths = set(self.paths.keys()) - VALID_PATH_KEYS
        if unknown_paths:
            warnings.warn(
                f"Unknown path conventions: {sorted(unknown_paths)}. Known conventions: {sorted(VALID_PATH_KEYS)}",
                stacklevel=2,
            )


def _format_validation_error(config_path: Path, error: ValidationError) -> str:
    """Return a human-friendly validation error message."""
    header = [
        f"Invalid mission configuration in {config_path}:",
        "",
        "Detected issues:",
    ]
    for err in error.errors():
        path = " -> ".join(str(part) for part in err.get("loc", ())) or "<root>"
        message = err.get("msg", "Invalid value")
        detail = f"- {path}: {message}"
        if err.get("type") == "extra_forbidden" and len(err.get("loc", ())) == 1:
            valid_fields = ", ".join(MISSION_ROOT_FIELDS)
            detail += f" (check for typos; valid root fields: {valid_fields})"
        header.append(detail)
    header.append("")
    header.append("Refer to kitty-specs/005-refactor-mission-system/data-model.md for the schema definition.")
    return "\n".join(header)


class Mission:
    """Represents a Spec Kitty mission with its configuration and resources."""

    def __init__(self, mission_path: Path, config: MissionConfig | None = None):
        """Initialize a mission from a directory path, or from a pre-built config.

        Args:
            mission_path: Path to the mission directory containing mission.yaml.
                When *config* is supplied this is a descriptive marker path
                only (T021, #3831) -- it need not exist on disk.
            config: A pre-validated :class:`MissionConfig` to use verbatim,
                bypassing the on-disk ``mission.yaml`` load. Used to build a
                neutral, in-memory identity for a registered org mission
                type that has no ``mission.yaml`` at any resolver tier
                (:func:`_build_neutral_org_mission`). ``None`` (default)
                preserves the original on-disk-load behavior unchanged.

        Raises:
            MissionNotFoundError: If *config* is ``None`` and the mission
                directory or its ``mission.yaml`` doesn't exist.
        """
        self.path = mission_path.resolve()

        if config is not None:
            self.config = config
            return

        if not self.path.exists():
            raise MissionNotFoundError(f"Mission directory not found: {self.path}")

        self.config = self._load_and_validate_config()

    def _load_and_validate_config(self) -> MissionConfig:
        """Load and validate mission configuration from mission.yaml.

        Returns:
            MissionConfig instance containing validated configuration

        Raises:
            MissionNotFoundError: If mission.yaml doesn't exist
            MissionError: If YAML is malformed or validation fails
            yaml.YAMLError: If mission.yaml is malformed
        """
        config_file = self.path / "mission.yaml"

        if not config_file.exists():
            raise MissionNotFoundError(f"Mission config not found: {config_file}\nExpected mission.yaml in mission directory")

        with open(config_file) as f:
            try:
                raw_config = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise MissionError(f"Invalid mission.yaml: {e}")

        if not isinstance(raw_config, dict):
            raise MissionError(f"Mission config must be a mapping/dictionary in {config_file}, got {type(raw_config).__name__} instead.")

        # Drop known compatibility keys from hybrid mission.yaml files.
        # Unknown extra fields still fail validation as before.
        normalized_config = {key: value for key, value in raw_config.items() if key not in MISSION_COMPAT_IGNORED_FIELDS}

        try:
            return MissionConfig.model_validate(normalized_config)
        except ValidationError as error:
            raise MissionError(_format_validation_error(config_file, error)) from error

    @property
    def name(self) -> str:
        """Get the mission name (e.g., 'Software Dev Kitty')."""
        return self.config.name

    @property
    def description(self) -> str:
        """Get the mission description."""
        return self.config.description

    @property
    def version(self) -> str:
        """Get the mission version."""
        return self.config.version

    @property
    def domain(self) -> str:
        """Get the mission domain (e.g., 'software', 'research')."""
        return self.config.domain

    @property
    def templates_dir(self) -> Path:
        """Get the templates directory for this mission."""
        return self.path / "templates"

    @property
    def command_templates_dir(self) -> Path:
        """Get the command templates directory for this mission."""
        return self.path / "command-templates"

    def get_template(self, template_name: str) -> Path:
        """Get path to a template file.

        Args:
            template_name: Name of template (e.g., 'spec-template.md')

        Returns:
            Path to the template file

        Raises:
            FileNotFoundError: If template doesn't exist
        """
        template_path = self.templates_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}\nMission: {self.name}\nAvailable templates: {self.list_templates()}")

        return template_path

    def get_command_template(self, command_name: str, project_dir: Path | None = None) -> Path:
        """Get path to a command template file.

        When *project_dir* is provided the 4-tier resolver is used
        (override > legacy > global > package default).  When omitted the
        method falls back to the original direct-path behaviour so that
        existing callers continue to work unchanged.

        Args:
            command_name: Name of command (e.g., 'plan', 'implement')
            project_dir: Optional project root for 4-tier resolution.

        Returns:
            Path to the command template file

        Raises:
            FileNotFoundError: If command template doesn't exist
        """
        # Support both with and without .md extension
        if not command_name.endswith(".md"):
            command_name = f"{command_name}.md"

        # When a project directory is supplied, use the 4-tier resolver
        if project_dir is not None:
            from specify_cli.runtime.resolver import resolve_command

            mission_type = self.path.name  # e.g. "software-dev"
            result = resolve_command(command_name, project_dir, mission=mission_type)
            return result.path

        command_path = self.command_templates_dir / command_name

        if not command_path.exists():
            raise FileNotFoundError(f"Command template not found: {command_path}\nMission: {self.name}\nAvailable commands: {self.list_commands()}")

        return command_path

    def list_templates(self) -> list[str]:
        """List all available templates in this mission."""
        if not self.templates_dir.exists():
            return []
        return [f.name for f in self.templates_dir.glob("*.md")]

    def list_commands(self) -> list[str]:
        """List all available command templates in this mission."""
        if not self.command_templates_dir.exists():
            return []
        return [f.stem for f in self.command_templates_dir.glob("*.md")]

    def get_validation_checks(self) -> list[str]:
        """Get list of validation checks for this mission."""
        return list(self.config.validation.checks)

    def has_custom_validators(self) -> bool:
        """Check if mission has custom validators.py."""
        return self.config.validation.custom_validators

    def get_workflow_phases(self) -> list[dict[str, str]]:
        """Get workflow phases for this mission.

        Returns:
            List of dicts with 'name' and 'description' keys
        """
        return [phase.model_dump() for phase in self.config.workflow.phases]

    def get_required_artifacts(self) -> list[str]:
        """Get list of required artifacts for this mission."""
        return list(self.config.artifacts.required)

    def get_optional_artifacts(self) -> list[str]:
        """Get list of optional artifacts for this mission."""
        return list(self.config.artifacts.optional)

    def get_path_conventions(self) -> dict[str, str]:
        """Get path conventions for this mission (e.g., workspace, tests)."""
        return dict(self.config.paths)

    def get_mcp_tools(self) -> dict[str, list[str]]:
        """Get MCP tools configuration for this mission.

        Returns:
            Dict with 'required', 'recommended', 'optional' lists
        """
        mcp_tools = self.config.mcp_tools
        if mcp_tools is None:
            return {"required": [], "recommended": [], "optional": []}
        return {
            "required": list(mcp_tools.required),
            "recommended": list(mcp_tools.recommended),
            "optional": list(mcp_tools.optional),
        }

    def get_agent_context(self) -> str:
        """Get agent personality/instructions for this mission."""
        return self.config.agent_context or ""

    def get_command_config(self, command_name: str) -> dict[str, str]:
        """Get configuration for a specific command.

        Args:
            command_name: Name of command (e.g., 'plan', 'implement')

        Returns:
            Dict with command configuration (e.g., 'prompt')
        """
        if not self.config.commands:
            return {}

        command = self.config.commands.get(command_name)
        return command.model_dump() if command else {}

    def __repr__(self) -> str:
        return f"Mission(name='{self.name}', domain='{self.domain}', version='{self.version}')"


def get_active_mission(project_root: Path | None = None) -> Mission:
    """Get the currently active mission for a project.

    Args:
        project_root: Path to project root (defaults to current directory)

    Returns:
        Mission object for the active mission

    Raises:
        MissionNotFoundError: If no active mission is configured
    """
    if project_root is None:
        project_root = Path.cwd()

    kittify_dir = project_root / ".kittify"

    if not kittify_dir.exists():
        raise MissionNotFoundError(f"No .kittify directory found in {project_root}\nIs this a Spec Kitty project? Run 'spec-kitty init' to create one.")

    # Check for active-mission symlink
    active_mission_link = kittify_dir / "active-mission"

    if active_mission_link.exists():
        mission_path: Path | None = None
        if active_mission_link.is_symlink():
            # Resolve symlink to actual mission directory (supports relative targets)
            mission_path = active_mission_link.resolve()
        elif active_mission_link.is_file():
            try:
                mission_name = active_mission_link.read_text(encoding="utf-8-sig").strip()
            except OSError:
                mission_name = ""
            if mission_name:
                mission_path = kittify_dir / "missions" / mission_name
        if mission_path is None:
            # Fallback to interpreting the target path directly
            try:
                target = Path(os.readlink(active_mission_link))
                mission_path = (active_mission_link.parent / target).resolve()
            except (OSError, RuntimeError):
                mission_path = None

        if mission_path is None:
            mission_path = kittify_dir / "missions" / "software-dev"
    else:
        # Default to software-dev if no active mission set
        mission_path = kittify_dir / "missions" / "software-dev"

    if not mission_path.exists():
        packaged_path = _mission_path_by_name(mission_path.name, kittify_dir)
        if packaged_path is not None:
            mission_path = packaged_path

    if not mission_path.exists():
        raise MissionNotFoundError(f"Active mission directory not found: {mission_path}\nAvailable missions: {list_available_missions(kittify_dir)}")

    return Mission(mission_path)


def list_available_missions(kittify_dir: Path | None = None) -> list[str]:
    """List all available missions in a project.

    Args:
        kittify_dir: Path to .kittify directory (defaults to current project)

    Returns:
        List of mission names (directory names)
    """
    if kittify_dir is None:
        kittify_dir = Path.cwd() / ".kittify"

    missions = set()
    for missions_dir in (kittify_dir / "missions", _packaged_missions_dir()):
        if not missions_dir.exists():
            continue
        for mission_dir in missions_dir.iterdir():
            if _mission_dir_if_valid(mission_dir) is not None:
                missions.add(mission_dir.name)

    return sorted(missions)


def _registered_org_mission_type(mission_name: str, project_dir: Path) -> "MissionType | None":
    """Return the activated org/project ``MissionType`` for *mission_name*, or ``None``.

    T021 (#3831): a project may register a mission type via a sparse
    ``mission_types/<type>.yaml`` (id/display_name/action_sequence) with no
    corresponding ``mission.yaml`` at any resolver tier. This probes the
    charter FR-006 activation gate first (``existing_mission_types`` -- an
    id that is not activated is treated as unregistered and never inspected
    further), then loads the full layered roster (built-in -> org ->
    project precedence, ``charter.missions.resolve_layered_mission_types``)
    the same way ``spec-kitty charter mission-type list`` does, and looks
    *mission_name* up in it.

    Returns ``None`` both when the type is not activated at all and when it
    is activated but no layer has a loadable ``MissionType`` file for it --
    the caller (:func:`get_mission_by_name`) treats both as "no org type
    either" and raises its own ``MissionNotFoundError`` (T022); this helper
    does not need to distinguish the two.
    """
    from charter.activation.mission_type_profiles import existing_mission_types  # noqa: PLC0415
    from charter.activation.pack_context import PackContext  # noqa: PLC0415
    from charter.missions import MissionTemplateRepository, resolve_layered_mission_types  # noqa: PLC0415

    if mission_name not in existing_mission_types(project_dir):
        return None

    pack_context = PackContext.from_config(project_dir)
    mission_types_dirs = (MissionTemplateRepository.default_missions_root() / "mission_types",)
    roster = resolve_layered_mission_types(mission_types_dirs, pack_context)
    return roster.get(mission_name)


def _neutral_workflow_from_action_sequence(action_sequence: list[str] | None) -> WorkflowConfig:
    """Derive a minimal, always-valid ``WorkflowConfig`` for a sparse org type.

    ``WorkflowConfig.phases`` requires at least one entry (``min_length=1``);
    a sparse org registration (T021) carries no software-dev-shaped phase
    list at all. When the type declares an ``action_sequence`` this renders
    it as a single descriptive phase (never software-dev's own multi-phase
    workflow); when it declares none (``docs-audit``'s fixture case, where
    ``action_sequence`` is ``None``) a single generic phase is used instead,
    so the schema's non-empty invariant is satisfied without inventing
    per-step phases the type never declared.
    """
    if action_sequence:
        description = "Derived from the mission type's action_sequence: " + " -> ".join(action_sequence)
    else:
        description = "Org mission type declares no action_sequence; no workflow phases are implied."
    return WorkflowConfig(phases=[PhaseConfig(name="org-mission-type", description=description)])


def _build_neutral_org_mission(mission_name: str, project_dir: Path, kittify_dir: Path) -> Mission | None:
    """Build a neutral, in-memory ``Mission`` for a registered, sparse org type.

    T021 (#3831): no resolver tier has a ``mission.yaml`` for *mission_name*,
    but the project has activated it as an org mission type via a bare
    ``mission_types/<type>.yaml`` (id/display_name/action_sequence -- no
    software-dev-shaped path/artifact conventions). The resulting
    :class:`Mission` carries the org type's own identity (``name`` =
    ``display_name``) and neutral conventions: ``paths`` projects the type's
    own ``path_conventions`` slot (WP02) when declared, else stays empty
    (path-convention checks then no-op rather than applying software-dev's
    ``src/``/``tests/``, SC-004); ``artifacts`` stays empty; and the
    workflow is a minimal single phase derived from the type's
    ``action_sequence`` (see :func:`_neutral_workflow_from_action_sequence`).

    Returns ``None`` when *mission_name* is not a registered org type
    either, so the caller can raise its own ``MissionNotFoundError`` (T022)
    instead of silently substituting software-dev.
    """
    mission_type = _registered_org_mission_type(mission_name, project_dir)
    if mission_type is None:
        return None

    config = MissionConfig(
        name=mission_type.display_name,
        description=(
            f"Org-registered mission type '{mission_type.id}' -- no mission.yaml "
            "exists for it at any resolver tier, so this identity is built from its "
            "sparse mission_types/ registration with neutral conventions (no "
            "software-dev path/artifact assumptions apply)."
        ),
        version="0.0.0",
        domain="other",
        workflow=_neutral_workflow_from_action_sequence(mission_type.action_sequence),
        artifacts=ArtifactsConfig(),
        # WP02's path_conventions slot lets an org type declare its own
        # conventions; a type that declares none (``None``, e.g. the
        # docs-audit fixture) yields the neutral empty mapping -- the
        # path-convention check no-ops rather than applying software-dev's
        # src/tests shape (SC-004).
        paths=dict(mission_type.path_conventions or {}),
    )
    # No mission.yaml exists on disk for this synthetic identity -- this is a
    # descriptive marker path only (mirrors the project-tier layout); Mission
    # skips the on-disk existence check whenever a pre-built config is given.
    mission_path = kittify_dir / "missions" / mission_name
    return Mission(mission_path, config=config)


def get_mission_by_name(mission_name: str, kittify_dir: Path | None = None) -> Mission:
    """Get a mission by name.

    Resolves *mission_name* through the org-aware precedence chain
    (:func:`specify_cli.runtime.resolver.resolve_mission`: override -> legacy
    -> org -> global-mission -> package) instead of the legacy, org-blind
    two-tier lookup that only ever checked ``kittify_dir/missions/`` and the
    packaged missions directory (T020, #3831/#4088). When no tier has a
    ``mission.yaml`` but *mission_name* is a registered org/project mission
    type with only a sparse ``mission_types/<type>.yaml`` registration, a
    neutral in-memory ``Mission`` is built from that registration instead
    (T021) -- never a silent software-dev substitution.

    Args:
        mission_name: Name of the mission (e.g., 'software-dev', 'research')
        kittify_dir: Path to .kittify directory (defaults to current project)

    Returns:
        Mission object

    Raises:
        MissionNotFoundError: If *mission_name* resolves to no
            ``mission.yaml`` at any resolver tier AND is not a registered
            org/project mission type.
    """
    if kittify_dir is None:
        kittify_dir = Path.cwd() / ".kittify"

    project_dir = kittify_dir.parent

    from specify_cli.runtime.resolver import ResolutionTier, resolve_mission  # noqa: PLC0415

    try:
        result = resolve_mission(mission_name, project_dir)
    except FileNotFoundError:
        pass
    else:
        if result.tier is ResolutionTier.PACKAGE_DEFAULT:
            # Keep built-in (package-tier) missions on the historical
            # ``specify_cli/missions/`` source rather than the resolver's
            # ``packs/built-in/missions/`` package tier. This holds built-in
            # behaviour byte-unchanged (NFR-001) and avoids a split-brain with
            # ``discover_missions``/``list_available_missions``/
            # ``get_active_mission``, which read ``_packaged_missions_dir()``.
            # Unifying the two package roots (and deleting the ``specify_cli``
            # copy) is the #2652 convergence, not this targeted slice.
            legacy_pkg = _mission_dir_if_valid(_packaged_missions_dir() / mission_name)
            return Mission(legacy_pkg if legacy_pkg is not None else result.path.parent)
        return Mission(result.path.parent)

    neutral_mission = _build_neutral_org_mission(mission_name, project_dir, kittify_dir)
    if neutral_mission is not None:
        return neutral_mission

    available = list_available_missions(kittify_dir)
    raise MissionNotFoundError(f"Mission '{mission_name}' not found.\nAvailable missions: {', '.join(available) if available else 'none'}")


# =============================================================================
# Per-Feature Mission Functions (v0.8.0+)
# =============================================================================


def _canonical_meta_mission_type(meta: dict[str, Any]) -> str | None:
    """Return the canonical mission-type key recorded in ``meta``, or ``None``.

    Thin delegate to the one shared runtime reader
    :func:`charter.mission_type_key.read_mission_type` (rc3 M5, FR-001). Reads
    **only** the canonical ``mission_type`` field — the legacy ``mission`` field
    is no longer consulted (FR-002, legacy-resolution retirement). A typeless /
    absent / blank / non-string value yields ``None``, never a substituted
    ``software-dev`` default (FR-003).
    """
    return read_mission_type(meta)


def get_mission_type(feature_dir: Path) -> str:
    """Extract the canonical mission-type key from a feature's meta.json.

    Reads the recorded ``mission_type`` (or legacy ``mission``) field via the
    single boundary-safe canonicalizer. A typeless / absent / unreadable
    meta.json degrades to the empty string — the **neutral** governance result
    (FR-003a) — and is NEVER silently defaulted to ``software-dev`` (FR-001 /
    FR-012). Callers that need a concrete template for a typeless mission handle
    the neutral value at their own boundary (e.g. template-file selection in
    :func:`get_mission_for_feature`, preserved per C-006).

    Args:
        feature_dir: Path to the feature directory (kitty-specs/<feature>/)

    Returns:
        The canonical mission-type key (e.g. ``'software-dev'``, ``'research'``),
        or ``''`` when the mission is typeless.
    """
    meta = load_meta_or_empty(feature_dir)
    return _canonical_meta_mission_type(meta) or ""


def get_deliverables_path(feature_dir: Path, mission_slug: str | None = None) -> str | None:
    """Extract deliverables_path from feature's meta.json.

    For research missions, deliverables go in a separate location from
    kitty-specs/ planning artifacts. This function reads that location
    from meta.json.

    Args:
        feature_dir: Path to the feature directory (kitty-specs/<feature>/)
        mission_slug: Feature slug for default path generation (optional)

    Returns:
        Deliverables path string if configured, or a default path for research
        missions, or None for non-research missions.

    Example:
        >>> get_deliverables_path(Path("kitty-specs/001-market-research"))
        'docs/research/001-market-research/'
    """
    # Try to read from meta.json
    meta = load_meta_or_empty(feature_dir)
    if meta:
        deliverables_path = meta.get("deliverables_path")
        if deliverables_path:
            return deliverables_path

        # Check if this is a research mission - provide default if so.
        # Route through the single canonicalizer (WP02 / FR-012); a typeless
        # mission yields ``None`` here — never a ``software-dev`` default — which
        # is behaviour-preserving since only ``research`` produces a path.
        mission = _canonical_meta_mission_type(meta)
        if mission == MISSION_TYPE_RESEARCH:
            # Generate default path using slug from meta or directory name
            slug = meta.get("slug") or mission_slug or feature_dir.name
            return f"docs/research/{slug}/"

    # If no meta.json but mission_slug provided, check mission from directory structure
    # and provide default for research missions
    if mission_slug:
        return f"docs/research/{mission_slug}/"

    return None


# Control characters and bidirectional-formatting overrides that can spoof
# a rendered path (e.g. RTL override making 'evil' read as 'live') or smuggle
# a null byte past a downstream C-string-based file API.
_FORBIDDEN_DELIVERABLES_CHARS = frozenset(
    {
        chr(0x00),  # NULL -- classic C-string truncation vector
        chr(0x202A),  # LEFT-TO-RIGHT EMBEDDING
        chr(0x202B),  # RIGHT-TO-LEFT EMBEDDING
        chr(0x202C),  # POP DIRECTIONAL FORMATTING
        chr(0x202D),  # LEFT-TO-RIGHT OVERRIDE
        chr(0x202E),  # RIGHT-TO-LEFT OVERRIDE
        chr(0x2066),  # LEFT-TO-RIGHT ISOLATE
        chr(0x2067),  # RIGHT-TO-LEFT ISOLATE
        chr(0x2068),  # FIRST STRONG ISOLATE
        chr(0x2069),  # POP DIRECTIONAL ISOLATE
    }
)

# Windows-style absolute path: a drive letter followed by a separator, e.g.
# 'C:\' or 'C:/'. Path.is_absolute() on POSIX is False for these — they need
# an explicit rule.
_WINDOWS_DRIVE_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def validate_deliverables_path(deliverables_path: str) -> tuple[bool, str]:
    """Validate that a deliverables_path is acceptable.

    Validation happens in two phases:

    1. Lexical checks against the RAW input (never a resolved path):
       - No control characters or bidirectional-override characters (null
         byte, RTL/LTR overrides/isolates) — these can smuggle bytes past
         downstream APIs or visually spoof the rendered path.
       - Must not be empty/whitespace-only (including strings that are only
         slashes, which normalize to nothing).
       - Must not reference a home directory (``~``).
       - Must not be a Windows-style absolute path (leading backslash or a
         drive letter such as ``C:\\``) or a POSIX absolute path (leading
         ``/``). ``Path.is_absolute()`` is False for the Windows form on
         POSIX, so both need explicit rules.
       - Must not contain ``..`` anywhere — a substring check, matching the
         canonical dotted-traversal guard in
         ``core/paths.py::assert_safe_path_segment``, so it also rejects
         dot-only segments like ``"..."`` without a separate rule.
       - Must not be a bare ``.``/``./`` (ambiguous project-root reference).
       - Must not be exactly ``research`` or ``research/`` at root
         (ambiguous — see ADR 7).

    2. Containment checks on a SEPARATE resolved copy (the raw string is
       never resolved for the checks above, since resolving makes every
       path absolute and would defeat the absolute-path rule):
       - The resolved path must stay within the project root (current
         working directory) — symlinks that escape the root are rejected
         via ``Path.relative_to`` (NOT ``str.startswith``, which is
         vulnerable to the sibling-prefix bypass — see the same pattern in
         ``doctrine/sources/https_source.py``).
       - The resolved path, relative to the project root, must not land in
         ``kitty-specs/`` (reserved for planning artifacts) — compared
         case-insensitively so a case-variant or a symlink cannot bypass it.

    Args:
        deliverables_path: The path to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is empty string.
    """
    raw = deliverables_path

    if any(char in raw for char in _FORBIDDEN_DELIVERABLES_CHARS):
        return (
            False,
            "deliverables_path must not contain control characters or bidirectional "
            "text overrides (e.g. null bytes, RTL/LTR overrides)",
        )

    stripped = raw.strip()
    if not stripped:
        return False, "deliverables_path must not be empty or whitespace-only"

    if stripped.startswith("~"):
        return False, "deliverables_path must not reference a home directory (~)"

    if stripped.startswith("\\") or _WINDOWS_DRIVE_ABSOLUTE_RE.match(stripped):
        return (
            False,
            "deliverables_path should be a relative path, not a Windows-style absolute path",
        )

    if stripped.startswith("/"):
        return False, "deliverables_path should be a relative path, not absolute"

    if ".." in stripped:
        return False, "deliverables_path must not contain directory traversal ('..')"

    normalized = stripped.rstrip("/")

    if normalized in ("", "."):
        return (
            False,
            "deliverables_path must not be a bare '.' (ambiguous project-root reference)",
        )

    if normalized == "research":
        return (
            False,
            "deliverables_path should not be just 'research/' at root (ambiguous). Use 'docs/research/<feature>/' or 'research-outputs/<feature>/' instead.",
        )

    # --- Phase 2: containment checks on a SEPARATE resolved copy ---
    project_root = Path.cwd().resolve()
    candidate = (project_root / normalized).resolve()
    try:
        relative = candidate.relative_to(project_root)
    except ValueError:
        return (
            False,
            "deliverables_path must resolve to a location inside the project root "
            "(symlink escape detected)",
        )

    relative_posix = relative.as_posix().lower()
    if relative_posix == KITTY_SPECS_DIR or relative_posix.startswith(f"{KITTY_SPECS_DIR}/"):
        return (
            False,
            f"deliverables_path must NOT resolve inside {KITTY_SPECS_DIR}/ (reserved for planning artifacts)",
        )

    return True, ""


def get_mission_for_feature(feature_dir: Path, project_root: Path | None = None) -> Mission:
    """Get the mission for a specific feature.

    Reads the mission key from the feature's meta.json and loads the
    corresponding mission through the org-aware loader
    (:func:`get_mission_by_name`, T020/T021).

    T022 (FR-007/SC-003) -- the two cases are handled identically here, but
    resolve to two different, deliberate outcomes:

    * **Typeless** (``meta.json`` has no ``mission_type``): a
      TEMPLATE-FILE-SELECTION path (it returns a ``Mission`` template
      object), not a governance read. Per C-006/FR-003a the ``software-dev``
      *template* default is preserved -- ``get_mission_type`` yields the
      neutral empty key, coalesced to ``software-dev`` below -- and it
      always resolves (built-in), so no warning is ever emitted.
    * **Typed but unresolvable** (a real ``mission_type`` that matches no
      ``mission.yaml`` at any resolver tier AND no registered org mission
      type): :func:`get_mission_by_name` raises ``MissionNotFoundError``,
      which now propagates to the caller unchanged -- a visible, diagnosable
      failure. The former warn-and-substitute-to-software-dev fallback (the
      #3831 defect for this path) has been removed; there is no silent
      software-dev substitution for a typed value.

    Args:
        feature_dir: Path to the feature directory (kitty-specs/<feature>/)
        project_root: Optional project root (defaults to finding .kittify)

    Returns:
        Mission object for the feature

    Raises:
        MissionNotFoundError: If feature meta.json not found and no default
            available, or (T022) a typed ``mission_type`` resolves to
            neither a ``mission.yaml`` nor a registered org mission type.
    """
    mission_type = get_mission_type(feature_dir) or MISSION_TYPE_SOFTWARE_DEV

    # Find project root if not provided
    if project_root is None:
        # Walk up from feature_dir to find .kittify
        current = feature_dir.resolve()
        while current != current.parent:
            if (current / ".kittify").exists():
                project_root = current
                break
            current = current.parent

        if project_root is None:
            raise MissionNotFoundError(f"Could not find .kittify directory from {feature_dir}\nIs this a Spec Kitty project?")

    kittify_dir = project_root / ".kittify"

    return get_mission_by_name(mission_type, kittify_dir)


def discover_missions(project_root: Path | None = None) -> dict[str, tuple[Mission, str]]:
    """Discover all available missions with their sources.

    Scans the project's .kittify/missions/ directory for valid mission
    configurations and returns them with source indicators.

    Args:
        project_root: Path to project root (defaults to current directory)

    Returns:
        Dict mapping mission key to (Mission, source) tuple.
        Source is one of: "project", "built-in"
        (Currently both are in the same location, but conceptually distinct)
    """
    if project_root is None:
        project_root = Path.cwd()

    kittify_dir = project_root / ".kittify"

    missions: dict[str, tuple[Mission, str]] = {}

    for missions_dir, source in (
        (_packaged_missions_dir(), "built-in"),
        (kittify_dir / "missions", "project"),
    ):
        if not missions_dir.exists():
            continue
        for mission_dir in missions_dir.iterdir():
            if _mission_dir_if_valid(mission_dir) is None:
                continue
            try:
                mission = Mission(mission_dir)
                missions[mission_dir.name] = (mission, source)
            except MissionError as e:
                warnings.warn(f"Skipping invalid mission '{mission_dir.name}': {e}", stacklevel=2)

    return missions
