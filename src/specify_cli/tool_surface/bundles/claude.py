"""Claude Code plugin bundle projection and validation.

Projects the canonical tool surfaces into Claude Code's plugin bundle layout
(``.claude-plugin/``) and validates the result before publication. The bundle
includes command skills, charter skills, agent profiles, hooks, and MCP config;
it deliberately **excludes** session-presence files (CLAUDE.md, AGENTS.md, rules
/ steering files), which are project-install surfaces, not bundle components.

**Scope guard (FR-016, C-006):** :meth:`ClaudeCodeBundleProjector.project`
writes only the staging files under the caller-supplied ``output_dir`` and
returns an inert :class:`PluginBundle` descriptor. It never installs, registers,
enables, or publishes the bundle to any marketplace.

:class:`ClaudeBundleProjector` (WP04) is the CLI-driven build projector that
consumes public command and profile preparation APIs to retain the complete
build before any staging write; it is distinct from :class:`ClaudeCodeBundleProjector` (plan-level
projector used by the WP09 surface-plan pipeline).
"""

from __future__ import annotations

import subprocess
import json
from collections.abc import Sequence
from pathlib import Path

import typer

from ..enums import ToolSurfaceKind
from ..findings import (
    BUNDLE_COMPONENT_MISSING,
    SEVERITY_ERROR,
    SurfaceFinding,
    make_finding,
)
from ..model import SurfacePlan
from ..operations import ApplyConsent, AssessmentInputs, Diagnostic, OperationRoot, OwnerAssessment
from .model import (
    TARGET_CLAUDE_CODE,
    BundleEntry,
    BundleValidationResult,
    PluginBundle,
    BundleObservation,
    StagedFile,
)
from .projection import (
    BUNDLE_SURFACE_KINDS,
    bundle_entries_for_plans,
    plugin_manifest_payload,
    write_bundle,
    confined_output,
    json_bytes,
    observe_confined,
    observe_tree,
    prepare_staging,
    read_observed_file,
    staging_root,
)
from ._builder import (
    BuildError,
    command_members,
    finish_build,
    get_cli_version,
)
from .claude_wrapper import wrapper_bash_content, wrapper_cmd_content

# Claude Code plugin layout: manifest lives under ``.claude-plugin/``; hooks and
# MCP config use ``hooks/hooks.json`` and ``.mcp.json`` (NEVER ``settings.json``).
_MANIFEST_DIR = ".claude-plugin"
_MANIFEST_NAME = "plugin.json"

# Per-kind destination prefix inside the Claude Code bundle package.
_CLAUDE_LAYOUT: dict[ToolSurfaceKind, str] = {
    ToolSurfaceKind.COMMAND_SKILL: "skills",
    ToolSurfaceKind.CHARTER_SKILL: "skills",
    ToolSurfaceKind.AGENT_PROFILE: "agents",
    ToolSurfaceKind.HOOK: "hooks",
    ToolSurfaceKind.NATIVE_CONFIG: "",
}

# Required surface kinds a complete Claude Code bundle must carry.
_REQUIRED_KINDS: frozenset[ToolSurfaceKind] = frozenset(
    {
        ToolSurfaceKind.COMMAND_SKILL,
        ToolSurfaceKind.CHARTER_SKILL,
        ToolSurfaceKind.AGENT_PROFILE,
    }
)


def _agent_filename(profile_id: str) -> str:
    """Claude Code uses plain ``<profile-id>.md`` agent files."""
    return f"{profile_id}.md"


class ClaudeCodeBundleProjector:
    """Project + validate Claude Code plugin bundles (staging only)."""

    distribution_target = TARGET_CLAUDE_CODE
    # Manifest sits under ``.claude-plugin/`` for this target.
    manifest_relative_path = f"{_MANIFEST_DIR}/{_MANIFEST_NAME}"

    def entries(self, plan: Sequence[SurfacePlan], project_root: Path) -> tuple[BundleEntry, ...]:
        """Select the canonical members without writing the staging tree."""
        return bundle_entries_for_plans(
            plan,
            project_root,
            layout=_CLAUDE_LAYOUT,
            agent_filename=_agent_filename,
            bundle_kinds=BUNDLE_SURFACE_KINDS,
        )

    def project(
        self,
        plan: Sequence[SurfacePlan],
        project_root: Path,
        output_dir: Path,
    ) -> PluginBundle:
        """Project all bundleable surfaces into the Claude Code layout.

        Writes staging files under ``output_dir`` and returns an inert
        :class:`PluginBundle` descriptor. No install/publish side effect occurs.
        """
        entries = self.entries(plan, project_root)
        manifest_rel = self.manifest_relative_path
        manifest = plugin_manifest_payload(self.distribution_target)
        write_bundle(output_dir, entries, manifest_rel, manifest)
        return PluginBundle(
            distribution_target=self.distribution_target,
            entries=entries,
            manifest_path=output_dir / manifest_rel,
        )

    def validate(
        self,
        bundle: PluginBundle,
        required_surface_kinds: set[ToolSurfaceKind] | None = None,
    ) -> BundleValidationResult:
        """Validate that every required surface kind is present in ``bundle``."""
        required = frozenset(required_surface_kinds) if required_surface_kinds is not None else _REQUIRED_KINDS
        return _validate_bundle(bundle, required)


def _validate_bundle(
    bundle: PluginBundle,
    required: frozenset[ToolSurfaceKind],
) -> BundleValidationResult:
    """Shared validation: report a finding for every missing required kind."""
    present = bundle.kinds()
    missing: list[SurfaceFinding] = []
    warnings: list[str] = []
    for kind in sorted(required - present, key=str):
        missing.append(
            make_finding(
                BUNDLE_COMPONENT_MISSING,
                SEVERITY_ERROR,
                (f"Plugin bundle for {bundle.distribution_target} is missing required surface kind: {kind}"),
                surface_id=f"{bundle.distribution_target}.{kind}",
                details={"distribution_target": bundle.distribution_target},
            )
        )
    if bundle.manifest_path is None:
        warnings.append(f"Bundle for {bundle.distribution_target} has no manifest path.")
    return BundleValidationResult(
        passed=not missing,
        missing_surfaces=tuple(missing),
        warnings=tuple(warnings),
        distribution_target=bundle.distribution_target,
    )


class ClaudeBundleProjector:
    """CLI-driven build projector for Claude Code plugin bundles (WP04).

    Produces a complete, ``claude plugin validate --strict``-ready bundle at
    ``<output_dir>/claude-code/`` containing:

    * ``.claude-plugin/plugin.json`` — manifest with real version from
      ``importlib.metadata``.
    * ``skills/<name>/SKILL.md`` — all canonical command skills rendered via
      the shared ``command_installer`` infrastructure.
    * ``agents/<profile-id>.md`` — built-in agent profiles rendered via
      :class:`ClaudeCodeProfileRenderer`.
    * ``hooks/hooks.json`` — empty placeholder (non-trivial hooks added later).
    * ``bin/spec-kitty-wrapper`` — bash runtime bootstrap with uvx fallback.
    * ``bin/spec-kitty-wrapper.cmd`` — Windows CMD equivalent.
    * ``marketplace.json`` — git-based distribution catalog (written alongside
      the bundle under ``<output_dir>/marketplace.json``).

    **Scope guard (FR-016, C-006):** :meth:`build` writes staging files only
    under the caller-supplied ``output_dir``.  It never installs, registers,
    enables, or publishes the bundle.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def build(self, *, skip_validate: bool = False) -> Path:
        """Build the Claude Code plugin bundle.

        Returns the bundle directory path.

        Raises
        ------
        BuildError
            When a required build step fails (e.g. no profiles found, too
            few skills).
        typer.Exit
            When ``claude plugin validate --strict`` exits non-zero.
        """
        bundle_dir = self._output_dir / "claude-code"
        assessment = self.prepare(ApplyConsent(automatic=True))
        finish_build(assessment)
        self._validate(bundle_dir, skip=skip_validate)
        return bundle_dir

    def prepare(self, consent: ApplyConsent = ApplyConsent()) -> OwnerAssessment:
        """Freeze skills, profiles, hooks, wrappers and sibling catalog together."""
        root = staging_root(self._output_dir)
        output = confined_output(self._output_dir, root)
        directory = output / "claude-code"
        inputs = AssessmentInputs(root, consent=consent)
        try:
            version = get_cli_version()
            files, commands = command_members(directory / "skills", root)
            profiles, observations = self._profile_members(directory, root)
            files += profiles
            hooks_path = directory / "hooks/hooks.json"
            hook_observations = observe_confined(root.path, hooks_path)
            observations += hook_observations
            hook_state = hook_observations[-1].state
            if hook_state.kind not in {"file", "absent"}:
                raise BuildError("Unknown hook destination is not a regular file")
            hooks = read_observed_file(hook_observations[-1]) if hook_state.kind == "file" else json_bytes({"hooks": {}}, legacy=True)
            hook_data = json.loads(hooks)
            if not isinstance(hook_data, dict):
                raise BuildError("Required Claude hooks must be a JSON object")
            skills = sorted("./" + (root.path / f.path).parent.relative_to(directory).as_posix() for f in files if Path(f.path).name == "SKILL.md")
            agents = sorted("./" + (root.path / f.path).relative_to(directory).as_posix() for f in profiles)
            manifest = self._manifest_payload(version, skills, agents, bool(hook_data) and hook_data != {"hooks": {}})
            files += (
                StagedFile(hooks_path.relative_to(root.path).as_posix(), hooks, hook_state.mode or 0o644, managed=hook_state.kind == "absent"),
                StagedFile(
                    (directory / "bin/spec-kitty-wrapper").relative_to(root.path).as_posix(), wrapper_bash_content(version).encode("utf-8"), 0o700, wrapper=True
                ),
                StagedFile(
                    (directory / "bin/spec-kitty-wrapper.cmd").relative_to(root.path).as_posix(), wrapper_cmd_content(version).encode("utf-8"), wrapper=True
                ),
                StagedFile((directory / ".claude-plugin/plugin.json").relative_to(root.path).as_posix(), json_bytes(manifest, legacy=True), manifest=True),
                StagedFile(
                    (output / "marketplace.json").relative_to(root.path).as_posix(), json_bytes(self._marketplace_payload(version), legacy=True), manifest=True
                ),
            )
            return prepare_staging(inputs, files, (output,), observations, suppliers=(commands,), version=version)
        except (OSError, ValueError, BuildError) as exc:
            return OwnerAssessment(
                "plugin_bundle", root, complete=False, consent=consent, diagnostics=(Diagnostic("bundle_input_invalid", "plugin_bundle", "error", str(exc)),)
            )

    @staticmethod
    def _profile_members(directory: Path, root: OperationRoot) -> tuple[tuple[StagedFile, ...], tuple[BundleObservation, ...]]:
        from charter.activation.doctrine_service_builder import _build_activation_aware_doctrine_service
        from ..profiles.projection import ProfileProjector

        source = _built_in_profiles_dir().resolve()
        observations = observe_tree(source)
        repository = _build_activation_aware_doctrine_service(
            root.path,
            org_roots=[],
        ).agent_profile_repository
        if repository.skipped_profiles():
            raise BuildError(f"Invalid built-in profile sources: {repository.skipped_profiles()}")
        projections = ProfileProjector(repository).prepare("claude", root.path)
        if not projections:
            raise BuildError(f"No built-in agent profiles found under {source}. Bundle must include profiles per FR-020.")
        files = tuple(
            StagedFile((directory / "agents" / item.native.output_path.name).relative_to(root.path).as_posix(), item.content, logical_owners=("agent_profiles",))
            for item in projections
        )
        return files, observations

    @staticmethod
    def _manifest_payload(version: str, skills: list[str], agents: list[str], has_hooks: bool) -> dict[str, object]:
        """Retain explicit prepared component paths in the Claude manifest."""
        if not skills:
            raise BuildError("Claude plugin manifest has no skills to declare.")
        if not agents:
            raise BuildError("Claude plugin manifest has no agents to declare.")

        manifest: dict[str, object] = {
            "name": "spec-kitty",
            "displayName": "Spec Kitty",
            "version": version,
            "description": ("Spec-Driven Development toolkit — spec, plan, implement, review, merge."),
            "author": {
                "name": "Spec Kitty",
                "url": "https://github.com/spec-kitty/spec-kitty",
            },
            "skills": skills,
            "agents": agents,
        }
        if has_hooks:
            manifest["hooks"] = "hooks/hooks.json"
        return manifest

    @staticmethod
    def _marketplace_payload(version: str) -> dict[str, object]:
        """Write ``marketplace.json`` alongside the bundle in *output_dir*.

        The marketplace catalog enables ``claude plugin marketplace add <repo-url>``
        for git-based plugin installs.  The file is a build artefact (excluded
        from the source repository via ``.gitignore``).

        Parameters
        ----------
        output_dir:
            The root output directory (e.g. ``dist/spec-kitty-plugins/``).
            ``marketplace.json`` is written here, not inside the bundle subdir.
        version:
            The resolved package version string; embedded in the catalog for
            informational purposes.
        """
        catalog: dict[str, object] = {
            "name": "spec-kitty-plugins",
            "description": "Spec Kitty skills, agent profiles, and runtime wrappers for Claude Code.",
            "version": version,
            "owner": {"name": "Spec Kitty"},
            "plugins": [
                {
                    "name": "spec-kitty",
                    "source": {
                        "source": "git-subdir",
                        "url": "https://github.com/spec-kitty/spec-kitty.git",
                        "path": "dist/spec-kitty-plugins/claude-code",
                    },
                    "category": "Developer Tools",
                },
            ],
        }
        return catalog

    def _validate(self, bundle_dir: Path, *, skip: bool) -> None:
        """Run ``claude plugin validate --strict`` against the bundle.

        Skips gracefully when the ``claude`` CLI is not on PATH; surfaces
        errors and exits non-zero on validation failure.
        """
        if skip:
            typer.echo(
                "Warning: Skipping claude plugin validate (--skip-validate passed).",
                err=True,
            )
            return
        try:
            result = subprocess.run(
                ["claude", "plugin", "validate", "--strict", str(bundle_dir)],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            typer.echo(
                "Warning: claude CLI not found — skipping validation. Install claude CLI to validate.",
                err=True,
            )
            return
        if result.returncode != 0:
            typer.echo("claude plugin validate --strict FAILED:", err=True)
            if result.stdout:
                typer.echo(result.stdout, err=True)
            if result.stderr:
                typer.echo(result.stderr, err=True)
            raise typer.Exit(code=1)
        typer.echo("claude plugin validate --strict passed.")


def _built_in_profiles_dir() -> Path:
    """Return the path to the built-in agent profiles source directory.

    Built-in content was flattened out of ``src/charter/offering/agent_profiles/built-in``
    into the ``packs/built-in/agent_profiles`` pack root (relocation mission);
    resolve it through the shared :func:`built_in_dir` seam (the single
    per-kind authority — no inline ``/ "built-in" / <plural>`` join). The
    import stays function-local (deferred) to keep this runtime module free of
    a module-level ``doctrine`` import that would trip the runtime -> charter
    -> doctrine boundary ratchet.
    """
    from charter.drg import ArtifactKind  # noqa: PLC0415 — deferred; see docstring
    from charter.pack_paths import built_in_dir  # noqa: PLC0415 — deferred; see docstring

    # Typed pin: ``charter.*`` is ``follow_imports = "skip"`` in pyproject, so the
    # facade re-export is ``Any`` to mypy; the runtime type is ``Path``.
    profiles_dir: Path = built_in_dir(ArtifactKind.AGENT_PROFILE)
    return profiles_dir


# Re-export so ``copilot``/``vscode`` projectors can share validation logic.
__all__ = [
    "ClaudeCodeBundleProjector",
    "ClaudeBundleProjector",
    # BuildError: demoted — re-exported from _builder; no cross-module src/
    # from-import callers of this module (WP01 harden-dead-symbol-gate-01KW0RJR).
    "_validate_bundle",
]
