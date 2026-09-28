"""Mission template repository for content-based access to mission assets."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.pack_paths import built_in_missions_root
from kernel.paths import MISSION_ASSETS_SIBLING_PATTERN

ParsedConfig = dict[str, Any] | list[Any]

#: Relative shape of this package's own data content (FR-004/FR-012). Owned
#: once at the kernel floor (:data:`kernel.paths.MISSION_ASSETS_SIBLING_PATTERN`
#: -- the ``packs/built-in/missions`` shape) and re-bound to this
#: module-local name so existing internal references and this module's own
#: tests keep resolving the identical pattern object, not a second,
#: independently-typed copy of the literal (mission
#: ``resolution-activation-foundation-01KZ9FKG``, WP02, FR-012). Mission
#: ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` (WP05) relocated
#: the missions data subdirectories from ``src/charter/offering/missions`` to
#: ``packs/built-in/missions`` -- ``packs/`` ships as a fixed-name,
#: site-packages-level sibling of every top-level package (the root
#: ``pyproject.toml``'s ``force-include = {"packs" = "packs"}``), so this is a
#: **literal** relative path, not a bare "missions" match. A bare "missions"
#: pattern would still match one ancestor level above this module's own
#: containing directory (``src/doctrine``) -- i.e. it would find
#: ``src/charter/offering/missions`` itself, the now data-less directory this
#: module's own 11 ``.py`` logic modules still live in -- before ever
#: considering the real data. A fully-qualified ``packs/built-in/missions``
#: pattern structurally cannot make that mistake.
_MISSIONS_ROOT_SIBLING_PATTERN = MISSION_ASSETS_SIBLING_PATTERN


class MalformedManifestError(Exception):
    """Raised when a mission's ``expected-artifacts.yaml`` is present but YAML-malformed.

    Fail-loud signal, distinct from absence (FR-007/SC-005,
    `#3412 <https://github.com/Priivacy-ai/spec-kitty/issues/3412>`_): a
    syntactically-corrupt manifest previously degraded to ``None`` -- byte-for-byte
    identical to "file not found" -- so an operator debugging a mission saw
    "not found" when the file was actually present-but-broken. This carries the
    offending ``path`` and the underlying parse error (``cause``) so the failure
    surfaces to the operator instead of being silently dropped.

    YAML-syntax malformation, present-but-unreadable
    (``OSError``/``UnicodeDecodeError``, FR-012), and present-but-non-mapping
    content are all widened to this raise, on both the built-in and org
    tiers (FR-007/FR-008/FR-012). Only a genuinely ABSENT manifest (no path
    resolved for it on that tier) still degrades to ``None`` -- that
    ``None`` truthfully means "absent", which is exactly the distinction
    this error restores.
    """

    def __init__(self, path: Path, cause: Exception) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"Malformed expected-artifacts manifest at {path}: {cause}")


class MissionsRootNotFound(Exception):
    """Raised when the missions-content root cannot be located (fail-closed).

    Replaces the previous silent ``Path(__file__).parent`` fallback (FR-004).

    ``default_missions_root`` (below) is not lazy: it resolves the built-in
    pack root and checks the ``missions`` leaf's existence eagerly on every
    call, via :func:`charter.offering.pack_paths.built_in_missions_root`. There is no
    ``dev_roots`` fallback tuple anywhere in the runtime-home topology
    (:mod:`specify_cli.runtime.home` re-exports the kernel-floor
    ``get_package_asset_root``/``get_kittify_home`` pair directly and carries
    no such tuple; the legacy ``specify_cli/missions`` importlib probe and any
    ``dev_root`` fallback were intentionally removed, DR-2) -- so a raised
    ``MissionsRootNotFound`` here is the final word for this call, not one
    entry in a multi-candidate chain.
    """


class TemplateResult:
    """Value object wrapping template content with origin metadata.

    Constructed internally by MissionTemplateRepository.
    Consumers should not instantiate directly.
    """

    __slots__ = ("_content", "_origin", "_tier")

    def __init__(self, content: str, origin: str, tier: Any = None) -> None:
        self._content = content
        self._origin = origin
        self._tier = tier

    @property
    def content(self) -> str:
        """Raw template text (UTF-8)."""
        return self._content

    @property
    def origin(self) -> str:
        """Human-readable origin label (e.g. 'doctrine/software-dev/command-templates/implement.md')."""
        return self._origin

    @property
    def tier(self) -> Any:
        """Resolution tier (ResolutionTier enum or None for doctrine-level lookups)."""
        return self._tier

    def __repr__(self) -> str:
        return f"TemplateResult(origin={self.origin!r}, tier={self.tier})"


class ConfigResult:
    """Value object wrapping parsed YAML config with origin metadata.

    Constructed internally by MissionTemplateRepository.
    Consumers should not instantiate directly.
    """

    __slots__ = ("_content", "_origin", "_parsed")

    def __init__(self, content: str, origin: str, parsed: ParsedConfig) -> None:
        self._content = content
        self._origin = origin
        self._parsed = parsed

    @property
    def content(self) -> str:
        """Raw YAML text (UTF-8)."""
        return self._content

    @property
    def origin(self) -> str:
        """Human-readable origin label (e.g. 'doctrine/software-dev/mission.yaml')."""
        return self._origin

    @property
    def parsed(self) -> ParsedConfig:
        """Pre-parsed YAML data (parsed with ruamel.yaml YAML(typ='safe'))."""
        return self._parsed

    def __repr__(self) -> str:
        return f"ConfigResult(origin={self.origin!r})"


class MissionTemplateRepository:
    """Single authority for mission asset access.

    Provides content-returning public methods (via TemplateResult and
    ConfigResult value objects) and private _*_path() methods for
    internal callers that need filesystem access.  All query methods
    return None (rather than raising) when the requested asset does
    not exist, so callers can implement their own fallback logic.
    """

    def __init__(self, missions_root: Path) -> None:
        self._root = missions_root

    # ------------------------------------------------------------------
    # Class-level constructor helpers
    # ------------------------------------------------------------------

    @classmethod
    def default_missions_root(cls) -> Path:
        """Return the missions-content root bundled alongside this package (FR-004).

        Delegates to :func:`charter.offering.pack_paths.built_in_missions_root`, itself
        a thin join onto :func:`charter.offering.pack_paths.built_in_root` -- the
        single built-in-pack-root authority, which in turn delegates to the
        kernel-floor primitive :func:`kernel.paths.get_built_in_pack_root`
        (DR-1: exactly one ``SPEC_KITTY_PACKS_ROOT`` env read across the
        whole resolution stack, FR-001/FR-003). This module no longer walks
        its own ``env_override=None`` sibling-path search.

        ``built_in_root()`` (and so ``built_in_missions_root()``) only proves
        ``packs/built-in`` exists -- it does not know about the ``missions``
        leaf beneath it -- so this method adds its own ``.is_dir()`` check on
        the joined leaf and fails closed with :class:`MissionsRootNotFound`
        when absent (I-4): a bare join would otherwise silently hand back a
        nonexistent path.

        Fails closed rather than falling back to this module's own directory;
        a missing built-in pack root propagates :class:`charter.offering.pack_paths.PackRootNotFound`
        unchanged from :func:`~charter.offering.pack_paths.built_in_root`.
        """
        root = built_in_missions_root()
        if root.is_dir():
            return root
        raise MissionsRootNotFound(
            f"Built-in pack root has no {_MISSIONS_ROOT_SIBLING_PATTERN.name!r} "
            f"leaf directory: {root}"
        )

    @classmethod
    def default(cls) -> MissionTemplateRepository:
        """Return a repository instance for the doctrine-bundled missions."""
        return cls(cls.default_missions_root())

    # ------------------------------------------------------------------
    # Enumeration interface
    # ------------------------------------------------------------------

    def list_missions(self) -> list[str]:
        """Return the names of all missions that contain a ``mission.yaml``.

        Returns:
            Sorted list of mission directory names.
        """
        if not self._root.is_dir():
            return []
        return sorted(
            d.name
            for d in self._root.iterdir()
            if d.is_dir() and (d / "mission.yaml").exists()
        )

    # ------------------------------------------------------------------
    # Public content-returning methods
    # ------------------------------------------------------------------

    def get_command_template(self, mission: str, name: str) -> TemplateResult | None:
        """Read a command template's content from charter.offering assets.

        Looks first for legacy
        ``<missions_root>/<mission>/command-templates/<name>.md``, then for
        canonical mission-step prompts at
        ``<missions_root>/mission-steps/<mission>/<name>/prompt.md``.

        Args:
            mission: Mission name (e.g. ``"software-dev"``).
            name: Template name without ``.md`` extension (e.g. ``"implement"``).

        Returns:
            TemplateResult with content and origin, or ``None`` if not found.
        """
        path = self._command_template_path(mission, name)
        if path is None:
            return None
        try:
            content = path.read_text(encoding="utf-8")
            origin = self._command_template_origin(mission, name, path)
            return TemplateResult(content=content, origin=origin)
        except (OSError, UnicodeDecodeError):
            return None

    def get_content_template(self, mission: str, name: str) -> TemplateResult | None:
        """Read a content template's content from charter.offering assets.

        Looks for ``<missions_root>/<mission>/templates/<name>``.

        Args:
            mission: Mission name.
            name: Template filename with extension (e.g. ``"spec-template.md"``).

        Returns:
            TemplateResult with content and origin, or ``None`` if not found.
        """
        path = self._content_template_path(mission, name)
        if path is None:
            return None
        try:
            content = path.read_text(encoding="utf-8")
            origin = f"doctrine/{mission}/templates/{name}"
            return TemplateResult(content=content, origin=origin)
        except (OSError, UnicodeDecodeError):
            return None

    def list_command_templates(self, mission: str) -> list[str]:
        """Return names of all command templates for a mission.

        Args:
            mission: Mission name (e.g. ``"software-dev"``).

        Returns:
            Sorted list of template names WITHOUT ``.md`` extension
            (e.g. ``["implement", "plan", "specify", "tasks"]``).
            Empty list if neither the legacy command-template directory nor
            the canonical mission-step prompt directory exists.
        """
        cmd_dir = self._root / mission / "command-templates"
        if cmd_dir.is_dir():
            return sorted(
                p.stem for p in cmd_dir.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "README.md"
            )

        steps_dir = self._root / "mission-steps" / mission
        if not steps_dir.is_dir():
            return []
        return sorted(
            step_dir.name
            for step_dir in steps_dir.iterdir()
            if step_dir.is_dir() and (step_dir / "prompt.md").is_file()
        )

    def list_content_templates(self, mission: str) -> list[str]:
        """Return filenames of all content templates for a mission.

        Args:
            mission: Mission name.

        Returns:
            Sorted list of template filenames WITH extension
            (e.g. ``["plan-template.md", "spec-template.md"]``).
            Empty list if mission or templates dir doesn't exist.
        """
        tpl_dir = self._root / mission / "templates"
        if not tpl_dir.is_dir():
            return []
        return sorted(
            p.name for p in tpl_dir.iterdir()
            if p.is_file() and p.name != "README.md"
        )

    # ------------------------------------------------------------------
    # Public config-returning methods
    # ------------------------------------------------------------------

    def get_action_index(self, mission: str, action: str) -> ConfigResult | None:
        """Read and parse an action's index.yaml from charter.offering assets.

        Args:
            mission: Mission name.
            action: Action name (e.g. ``"implement"``).

        Returns:
            ConfigResult with raw YAML text and parsed dict, or ``None`` if not found.
        """
        path = self._action_index_path(mission, action)
        if path is None:
            return None
        try:
            content = path.read_text(encoding="utf-8")
            yaml = YAML(typ="safe")
            parsed = cast(ParsedConfig | None, yaml.load(content))
            if parsed is None:
                return None
            origin = f"doctrine/{mission}/actions/{action}/index.yaml"
            return ConfigResult(content=content, origin=origin, parsed=parsed)
        except (OSError, UnicodeDecodeError, YAMLError):
            return None

    def get_action_guidelines(self, mission: str, action: str) -> TemplateResult | None:
        """Read an action's guidelines.md from charter.offering assets.

        ``mission-steps/<mission>/<action>/guidelines.md`` is the single owner
        (#5202): the former ``<mission>/actions/<action>/guidelines.md`` copy
        was an undocumented, silently-drifting duplicate and has been retired.

        Args:
            mission: Mission name.
            action: Action name.

        Returns:
            TemplateResult with content and origin, or ``None`` if not found.
        """
        path = self._action_guidelines_path(mission, action)
        if path is None:
            return None
        try:
            content = path.read_text(encoding="utf-8")
            origin = f"doctrine/mission-steps/{mission}/{action}/guidelines.md"
            return TemplateResult(content=content, origin=origin)
        except (OSError, UnicodeDecodeError):
            return None

    def get_mission_config(self, mission: str) -> ConfigResult | None:
        """Read and parse a mission's mission.yaml from charter.offering assets.

        Args:
            mission: Mission name.

        Returns:
            ConfigResult with raw YAML text and parsed dict, or ``None`` if not found.
        """
        path = self._mission_config_path(mission)
        if path is None:
            return None
        try:
            content = path.read_text(encoding="utf-8")
            yaml = YAML(typ="safe")
            parsed = cast(ParsedConfig | None, yaml.load(content))
            if parsed is None:
                return None
            origin = f"doctrine/{mission}/mission.yaml"
            return ConfigResult(content=content, origin=origin, parsed=parsed)
        except (OSError, UnicodeDecodeError, YAMLError):
            return None

    def get_expected_artifacts(self, mission: str) -> ConfigResult | None:
        """Read and parse a mission's expected-artifacts.yaml.

        Args:
            mission: Mission name (e.g. ``"software-dev"``).

        Returns:
            ConfigResult with raw YAML text and parsed data, or ``None`` if the
            manifest is genuinely absent (path ``None``) or present but empty
            (parses to ``None``).

        Raises:
            MalformedManifestError: If the manifest file is present but fails
                to parse as YAML (``YAMLError``) or cannot be read/decoded
                (``OSError``/``UnicodeDecodeError``, FR-012). Fail-loud,
                distinct from absence (FR-007/FR-012/SC-005, #3412): a
                present-but-broken manifest previously degraded to ``None``
                for the unreadable case, indistinguishable from "not found".
                It now surfaces the offending path and the underlying cause
                rather than being silently dropped.
        """
        path = self._expected_artifacts_path(mission)
        if path is None:
            return None
        try:
            content = path.read_text(encoding="utf-8")
            yaml = YAML(typ="safe")
            parsed = cast(ParsedConfig | None, yaml.load(content))
        except (YAMLError, OSError, UnicodeDecodeError) as exc:
            raise MalformedManifestError(path, exc) from exc
        if parsed is None:
            return None
        if not isinstance(parsed, Mapping):
            # Symmetry with the org tier (#3412/FR-008): a present-but-non-mapping
            # manifest (a top-level scalar/sequence) is present-but-unparseable-as-a-
            # manifest -> the sibling MalformedManifestError, distinct from absence and
            # from a schema/extra=forbid violation. Without this guard the value would
            # flow to model_validate and surface as ManifestSchemaError, breaking the
            # both-tiers-agree sibling model.
            raise MalformedManifestError(
                path, TypeError(f"expected a YAML mapping, got {type(parsed).__name__}")
            )
        origin = f"doctrine/{mission}/expected-artifacts.yaml"
        return ConfigResult(content=content, origin=origin, parsed=parsed)

    # ------------------------------------------------------------------
    # Private path methods (internal use only)
    # ------------------------------------------------------------------

    @property
    def _missions_root(self) -> Path:
        """Return the missions root directory (internal use only)."""
        return self._root

    def _command_template_path(self, mission: str, name: str) -> Path | None:
        """Return the path to a command template Markdown file.

        Looks for the legacy command-template file first, then the canonical
        mission-step prompt file.

        Args:
            mission: Mission name (e.g. ``"software-dev"``).
            name: Template name without extension (e.g. ``"implement"``).

        Returns:
            Path if the file exists, else ``None``.
        """
        path = self._root / mission / "command-templates" / f"{name}.md"
        if path.is_file():
            return path
        step_prompt = self._root / "mission-steps" / mission / name / "prompt.md"
        return step_prompt if step_prompt.is_file() else None

    def _command_template_origin(self, mission: str, name: str, path: Path) -> str:
        legacy = self._root / mission / "command-templates" / f"{name}.md"
        if path == legacy:
            return f"doctrine/{mission}/command-templates/{name}.md"
        return f"doctrine/mission-steps/{mission}/{name}/prompt.md"

    def _content_template_path(self, mission: str, name: str) -> Path | None:
        """Return the path to a content template file.

        Looks for ``<missions_root>/<mission>/templates/<name>``.

        Args:
            mission: Mission name.
            name: Template filename including extension (e.g. ``"spec-template.md"``).

        Returns:
            Path if the file exists, else ``None``.
        """
        path = self._root / mission / "templates" / name
        return path if path.is_file() else None

    def _action_index_path(self, mission: str, action: str) -> Path | None:
        """Return the path to an action's ``index.yaml``.

        Looks for ``<missions_root>/<mission>/actions/<action>/index.yaml``.

        Args:
            mission: Mission name.
            action: Action name (e.g. ``"implement"``).

        Returns:
            Path if the file exists, else ``None``.
        """
        path = self._root / mission / "actions" / action / "index.yaml"
        return path if path.is_file() else None

    def _action_guidelines_path(self, mission: str, action: str) -> Path | None:
        """Return the path to an action's ``guidelines.md``.

        Looks for ``<missions_root>/mission-steps/<mission>/<action>/guidelines.md``
        -- the single-owner location (#5202); the retired
        ``<missions_root>/<mission>/actions/<action>/guidelines.md`` copy is no
        longer consulted.

        Args:
            mission: Mission name.
            action: Action name.

        Returns:
            Path if the file exists, else ``None``.
        """
        path = self._root / "mission-steps" / mission / action / "guidelines.md"
        return path if path.is_file() else None

    def _mission_config_path(self, mission: str) -> Path | None:
        """Return the path to a mission's ``mission.yaml``.

        Args:
            mission: Mission name.

        Returns:
            Path if the file exists, else ``None``.
        """
        path = self._root / mission / "mission.yaml"
        return path if path.is_file() else None

    def _expected_artifacts_path(self, mission: str) -> Path | None:
        """Return the path to a mission's ``expected-artifacts.yaml``.

        The expected-artifacts manifest defines step-aware, class-tagged,
        blocking-semantics artifact requirements used by the dossier
        ``ManifestRegistry``.

        Args:
            mission: Mission name (e.g. ``"software-dev"``).

        Returns:
            Path if the file exists, else ``None``.
        """
        path = self._root / mission / "expected-artifacts.yaml"
        return path if path.is_file() else None


# Backward-compat alias so ``from charter.offering.missions.repository import MissionRepository``
# works the same as ``from charter.offering.missions import MissionRepository``.
MissionRepository = MissionTemplateRepository
