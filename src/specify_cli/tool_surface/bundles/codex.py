"""Codex plugin bundle projection (WP06).

Projects the canonical tool surfaces into Codex's plugin bundle layout
(``.codex-plugin/``) and validates the result before publication.  The bundle
includes command skills and a marketplace catalog; it deliberately **excludes**
agent-level components (``"agents"`` key) and a hooks manifest pointer
(``"hooks"`` key) because the Codex plugin spec does not support either.

Per the Codex plugin contract (plugin-manifest-codex-01):

*  ``"hooks"`` MUST NOT appear as a top-level key — hooks are discovered by
   filesystem presence of the ``hooks/`` directory, not a manifest pointer.
*  ``"agents"`` MUST NOT appear at any level — Codex plugin-level agent
   packaging is unconfirmed; omit entirely.

**Scope guard (FR-016, C-006):**  :meth:`CodexBundleProjector.build` writes
only staging files under the caller-supplied ``output_dir`` and returns the
bundle directory path.  It never installs, registers, enables, or publishes the
bundle.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ._builder import (
    BuildError,
    command_members,
    finish_build,
    get_cli_version,
    to_semver,
)
from ..operations import ApplyConsent, AssessmentInputs, Diagnostic, OperationRoot, OwnerAssessment
from .model import BundleObservation, StagedFile
from .projection import (
    confined_output, json_bytes, observe_bundle_path, observe_tree,
    prepare_staging, read_observed_file, staging_root,
)

# Codex plugin manifest lives under ``.codex-plugin/`` (not ``.claude-plugin/``).
_MANIFEST_DIR = ".codex-plugin"
_MANIFEST_NAME = "plugin.json"

# MCP companion file name and the manifest pointer the Codex schema expects.
# Per plugin-manifest-codex-01, ``mcpServers`` points at ``./.mcp.json`` and is
# emitted ONLY when a ``.mcp.json`` companion is present in the bundle.
_MCP_JSON_NAME = ".mcp.json"
_MCP_POINTER = f"./{_MCP_JSON_NAME}"

# Keys that Codex plugin.json must NEVER contain.
_FORBIDDEN_KEYS: frozenset[str] = frozenset({"hooks", "agents"})

# Top-level scalar fields required by the Codex plugin schema.
_REQUIRED_SCALAR_FIELDS: tuple[str, ...] = ("name", "version", "description")

# Required nested fields in the ``interface`` sub-object. The pinned OpenAI
# requirements (spec-kitty-internal-plugins#2 §2.3) split them into fields a
# listing needs for rendering and URLs the MCP review needs.
_REQUIRED_INTERFACE_FIELDS: tuple[str, ...] = (
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "supportURL",
    "privacyPolicyURL",
    "defaultPrompt",
    "logo",
    "composerIcon",
)

# Per-field character limits from the pinned contract. ``shortDescription`` and
# ``displayName`` are 30, not the 120 the old constant assumed.
_INTERFACE_MAX_LEN: dict[str, int] = {
    "displayName": 30,
    "shortDescription": 30,
    "longDescription": 4000,
    "developerName": 80,
}
_CAPABILITIES_MAX_ITEMS = 20
_CAPABILITY_MAX_LEN = 120
_DEFAULT_PROMPT_MAX_ITEMS = 3
_DEFAULT_PROMPT_MAX_LEN = 128

# Identity and links the directory resolves the listing from.
_AUTHOR_NAME = "Spec Kitty"
_DEVELOPER_NAME = "Spec Kitty, Inc."
_PROJECT_URL = "https://github.com/spec-kitty/spec-kitty"
_PROJECT_HOMEPAGE = "https://spec-kitty.ai/"
_PROJECT_DOCS_URL = "https://docs.spec-kitty.ai/"
_PROJECT_SUPPORT_URL = f"{_PROJECT_URL}/issues"
_PROJECT_PRIVACY_URL = "https://spec-kitty.ai/privacy"
_LICENSE = "MIT"

# Square brand asset declared as ``./assets/logo.png`` and staged from the
# package so a wheel install ships it too.
_BUNDLE_ASSET_DIR = "assets"
_BRAND_LOGO_NAME = "logo.png"
_BRAND_LOGO_POINTER = f"./{_BUNDLE_ASSET_DIR}/{_BRAND_LOGO_NAME}"

# Install instructions emitted after marketplace.json is written.
_INSTALL_HINT = (
    "  To install: codex plugin marketplace add dist/spec-kitty-plugins/codex/marketplace.json\n"
    "  Or:         codex plugin install dist/spec-kitty-plugins/codex"
)


class CodexBundleProjector:
    """CLI-driven build projector for Codex plugin bundles (WP06).

    Produces a complete bundle at ``<output_dir>/codex/`` containing:

    * ``.codex-plugin/plugin.json`` — manifest with real version from
      ``importlib.metadata``; ``"hooks"`` and ``"agents"`` keys absent.
    * ``skills/<name>/SKILL.md`` — all canonical command skills.
    * ``marketplace.json`` — repo-local marketplace catalog.

    **Scope guard (FR-016, C-006):**  :meth:`build` writes staging files only
    under the caller-supplied ``output_dir``.  It never installs, registers,
    enables, or publishes the bundle.
    """

    def __init__(self, output_dir: Path) -> None:
        self.bundle_dir = output_dir / "codex"

    def build(self, *, skip_validate: bool = False) -> Path:
        """Build the Codex plugin bundle.

        Returns the bundle directory path.

        Raises
        ------
        BuildError
            When a required build step fails (e.g. too few skills, forbidden
            keys detected in the manifest, required fields missing).
        """
        assessment = self.prepare(ApplyConsent(automatic=True))
        finish_build(assessment)
        if skip_validate:
            typer.echo("Warning: Skipping Codex plugin validation (--skip-validate passed).", err=True)
        typer.echo(f"Codex marketplace.json written to {self.bundle_dir / 'marketplace.json'}")
        typer.echo(_INSTALL_HINT)
        return self.bundle_dir

    def prepare(self, consent: ApplyConsent = ApplyConsent()) -> OwnerAssessment:
        """Retain the entire CLI bundle without invoking any writer or validator."""
        root = staging_root(self.bundle_dir)
        directory = confined_output(self.bundle_dir, root)
        inputs = AssessmentInputs(root, consent=consent)
        try:
            version = get_cli_version()
            files, commands = command_members(directory / "skills", root)
            companions, observations, directories = self._companions(directory, root)
            assets, asset_observations = self._brand_asset(directory, root)
            observations += asset_observations
            manifest = self._manifest_payload(version, any(Path(f.path).name == _MCP_JSON_NAME for f in companions))
            files += companions + assets + (
                StagedFile((directory / _MANIFEST_DIR / _MANIFEST_NAME).relative_to(root.path).as_posix(),
                           json_bytes(manifest, legacy=True), manifest=True),
                StagedFile((directory / "marketplace.json").relative_to(root.path).as_posix(),
                           json_bytes(self._marketplace_payload(), legacy=True), manifest=True),
            )
            return prepare_staging(inputs, files, (directory,), observations, suppliers=(commands,), version=version,
                                   supporting_dirs=directories)
        except (OSError, ValueError, BuildError) as exc:
            return OwnerAssessment("plugin_bundle", root, complete=False, consent=consent,
                                   diagnostics=(Diagnostic("bundle_input_invalid", "plugin_bundle", "error", str(exc)),))

    @staticmethod
    def _companions(directory: Path, root: OperationRoot) -> tuple[tuple[StagedFile, ...], tuple[BundleObservation, ...], tuple[tuple[str, int], ...]]:
        import charter.offering as offering

        source = Path(offering.__file__).parent.resolve()
        observations = [observe_bundle_path(source / _MCP_JSON_NAME), observe_bundle_path(source / "hooks", members=True)]
        files: list[StagedFile] = []
        directories: list[tuple[str, int]] = []
        for observation in observations:
            if observation.state.kind == "symlink":
                raise ValueError(f"Unsafe optional bundle source: {observation.path}")
        mcp = observations[0]
        if mcp.state.kind != "absent":
            if mcp.state.kind != "file":
                raise ValueError("MCP companion is not a regular file")
            content = read_observed_file(mcp)
            if not isinstance(json.loads(content), dict):
                raise ValueError("MCP companion must be a JSON object")
            files.append(StagedFile((directory / _MCP_JSON_NAME).relative_to(root.path).as_posix(), content, mcp.state.mode or 0o644))
        hooks = source / "hooks"
        if observations[1].state.kind != "absent":
            if observations[1].state.kind != "directory":
                raise ValueError("Hooks source is not a directory")
            for observed in observe_tree(hooks):
                observations.append(observed)
                if observed.state.kind == "directory":
                    assert observed.state.mode is not None
                    directories.append(((directory / "hooks" / observed.path.relative_to(hooks)).relative_to(root.path).as_posix(),
                                        observed.state.mode))
                if observed.state.kind == "file":
                    files.append(StagedFile((directory / "hooks" / observed.path.relative_to(hooks)).relative_to(root.path).as_posix(),
                                            read_observed_file(observed), observed.state.mode or 0o644))
        return tuple(files), tuple(observations), tuple(directories)

    @staticmethod
    def _brand_asset(directory: Path, root: OperationRoot) -> tuple[tuple[StagedFile, ...], tuple[BundleObservation, ...]]:
        """Stage the square brand mark the manifest declares.

        The manifest points at ``./assets/logo.png``, so the bundle must contain
        it: a listing that cannot resolve a declared image is worse than one with
        no image field. The source ships inside the package (``*.png`` artifact),
        so an installed CLI builds the same bundle as a source checkout.
        """
        source = Path(__file__).parent / _BUNDLE_ASSET_DIR / _BRAND_LOGO_NAME
        observation = observe_bundle_path(source)
        if observation.state.kind != "file":
            raise BuildError(f"Brand asset is missing from the package: {source}")
        content = read_observed_file(observation)
        destination = (directory / _BUNDLE_ASSET_DIR / _BRAND_LOGO_NAME).relative_to(root.path).as_posix()
        return (StagedFile(destination, content, observation.state.mode or 0o644),), (observation,)

    # ------------------------------------------------------------------
    # Manifest generation
    # ------------------------------------------------------------------

    def _manifest_payload(self, version: str, has_mcp: bool) -> dict[str, object]:
        manifest: dict[str, object] = {
            "name": "spec-kitty",
            "version": to_semver(version),
            "description": "Spec-Driven Development toolkit.",
            "author": {"name": _AUTHOR_NAME, "url": _PROJECT_URL},
            "homepage": _PROJECT_HOMEPAGE,
            "repository": _PROJECT_URL,
            "license": _LICENSE,
            # The plugin shells out to the ``spec-kitty`` CLI, which makes it a
            # desktop-only plugin for the Codex directory.
            "requires_local_executor": True,
            "interface": {
                "displayName": "Spec Kitty",
                # 23 characters: the pinned limit is 30, and the old constant
                # (120) let a 34-character value through.
                "shortDescription": "Spec-Driven Development",
                "longDescription": (
                    "Spec Kitty turns agreed intent into a verified result: specify, plan, "
                    "slice tasks into work packages, implement with review, and land under a "
                    "charter you control."
                ),
                "developerName": _DEVELOPER_NAME,
                "category": "Developer Tools",
                "capabilities": [
                    "Specification-first mission workflow",
                    "Work-package implementation with review gates",
                    "Charter and doctrine governance",
                ],
                "websiteURL": _PROJECT_DOCS_URL,
                "supportURL": _PROJECT_SUPPORT_URL,
                "privacyPolicyURL": _PROJECT_PRIVACY_URL,
                "defaultPrompt": ["Turn this idea into a spec, plan and tasks with Spec Kitty."],
                "logo": _BRAND_LOGO_POINTER,
                "composerIcon": _BRAND_LOGO_POINTER,
            },
            "skills": "./skills/",
        }
        # FR-027: advertise the MCP companion only when it was actually staged
        # into the bundle ("when applicable"). Absent companion => no pointer.
        if has_mcp:
            manifest["mcpServers"] = _MCP_POINTER
        self._validate_manifest(manifest)
        return manifest

    def _validate_manifest(self, manifest: dict[str, object]) -> None:
        """Assert the manifest is schema-valid for the Codex plugin format.

        Raises
        ------
        BuildError
            When forbidden keys are present, a required field is missing, or a
            pinned per-field limit is exceeded.
        """
        self._validate_required_fields(manifest)
        self._validate_interface_limits(manifest["interface"])
        self._validate_component_pointers(manifest)

    @staticmethod
    def _validate_required_fields(manifest: dict[str, object]) -> None:
        """Forbidden keys, required scalars, author block and interface fields."""
        found_forbidden = _FORBIDDEN_KEYS & set(manifest)
        if found_forbidden:
            raise BuildError(
                f"Codex plugin.json must NOT contain: {sorted(found_forbidden)}"
            )

        for key in _REQUIRED_SCALAR_FIELDS:
            if not manifest.get(key):
                raise BuildError(
                    f"Codex plugin.json missing required field: {key!r}"
                )

        author = manifest.get("author")
        if not isinstance(author, dict) or not author.get("name"):
            raise BuildError(
                "Codex plugin.json missing required field: 'author.name'"
            )

        iface = manifest.get("interface")
        if not isinstance(iface, dict):
            raise BuildError(
                "Codex plugin.json missing required field: 'interface'"
            )
        for sub in _REQUIRED_INTERFACE_FIELDS:
            if not iface.get(sub):
                raise BuildError(
                    f"Codex plugin.json missing required field: 'interface.{sub}'"
                )

    @staticmethod
    def _validate_interface_limits(iface: object) -> None:
        """Pinned per-field limits: string lengths, capabilities, default prompts."""
        assert isinstance(iface, dict)  # guarded by _validate_required_fields
        for field, limit in _INTERFACE_MAX_LEN.items():
            value = iface.get(field, "")
            if isinstance(value, str) and len(value) > limit:
                raise BuildError(
                    f"Codex plugin.json 'interface.{field}' exceeds {limit} characters."
                )

        # capabilities: a bounded list of bounded strings.
        capabilities = iface.get("capabilities")
        if not isinstance(capabilities, list) or len(capabilities) > _CAPABILITIES_MAX_ITEMS:
            raise BuildError(
                "Codex plugin.json 'interface.capabilities' must be a list of at most "
                f"{_CAPABILITIES_MAX_ITEMS} items."
            )
        if any(not isinstance(item, str) or len(item) > _CAPABILITY_MAX_LEN for item in capabilities):
            raise BuildError(
                "Codex plugin.json 'interface.capabilities' items must be strings of at most "
                f"{_CAPABILITY_MAX_LEN} characters."
            )

        # defaultPrompt: one to three short prompts.
        prompts = iface.get("defaultPrompt")
        if not isinstance(prompts, list) or not 1 <= len(prompts) <= _DEFAULT_PROMPT_MAX_ITEMS:
            raise BuildError(
                "Codex plugin.json 'interface.defaultPrompt' must be a list of 1 to "
                f"{_DEFAULT_PROMPT_MAX_ITEMS} prompts."
            )
        if any(not isinstance(prompt, str) or len(prompt) > _DEFAULT_PROMPT_MAX_LEN for prompt in prompts):
            raise BuildError(
                "Codex plugin.json 'interface.defaultPrompt' entries must be strings of at most "
                f"{_DEFAULT_PROMPT_MAX_LEN} characters."
            )

    @staticmethod
    def _validate_component_pointers(manifest: dict[str, object]) -> None:
        """Bundled component paths are host-relative and carry the ``./`` prefix."""
        for field in ("skills", "mcpServers"):
            pointer = manifest.get(field)
            if isinstance(pointer, str) and not pointer.startswith("./"):
                raise BuildError(f"Codex plugin.json {field!r} path must start with './'.")

    # ------------------------------------------------------------------
    # Marketplace catalog
    # ------------------------------------------------------------------

    @staticmethod
    def _marketplace_payload() -> dict[str, object]:
        """Write repo-local ``marketplace.json`` for Codex plugin install.

        The file is written to ``dist/spec-kitty-plugins/codex/marketplace.json``
        (the canonical output location per C-006).  A secondary copy is NOT
        written to ``.agents/plugins/marketplace.json`` — that would violate the
        C-006 output-dir constraint and pollute the project tree.

        Emits install instructions to stdout after writing.
        """
        marketplace: dict[str, object] = {
            "name": "spec-kitty-plugins",
            "interface": {"displayName": "Spec Kitty Plugins"},
            "plugins": [
                {
                    "name": "spec-kitty",
                    "source": {"source": "local", "path": "."},
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Productivity",
                }
            ],
        }
        return marketplace


__all__ = ["CodexBundleProjector"]
