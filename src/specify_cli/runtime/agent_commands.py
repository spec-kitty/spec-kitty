"""Bootstrap user-global canonical slash commands for all configured agents.

On every CLI startup, ``ensure_global_agent_commands()`` installs all 15
consumer-facing command files (8 prompt-driven + 7 CLI-driven shims) into the
user-global agent command roots:

    ~/.claude/commands/
    ~/.gemini/commands/
    ~/.github/prompts/
    ... (one directory per configured agent)

This mirrors ``ensure_global_agent_skills()`` exactly — same version-lock
mechanism, same exclusive-lock concurrency guard, same read-only output files.

See ADR ``docs/adr/3.x/2026-04-07-1-global-slash-command-installation.md``
for the design rationale.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
import os
import re
import sys
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path

from kernel.paths import MISSION_ASSETS_SIBLING_PATTERN
from kernel.sibling_paths import SiblingPathNotFound, resolve_installed_sibling
from specify_cli.core.config import DEFAULT_MISSION_KEY
from specify_cli.runtime.bootstrap import _get_cli_version
from specify_cli.runtime.home import get_kittify_home
from specify_cli.runtime.asset_preparation import _GlobalAssetPreparation
from specify_cli.tool_surface.operations import ApplyConsent, OwnerAssessment

logger = logging.getLogger(__name__)

_VERSION_FILENAME = "agent-commands.lock"
_LOCK_FILENAME = ".agent-commands.lock"
_VERSION_MARKER_PREFIX = "<!-- spec-kitty-command-version:"
_VERSION_MARKER_HEAD_LINES = 20


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def get_global_command_dir(agent_key: str) -> Path:
    """Return the user-global command directory for *agent_key*.

    Mirrors the project-local ``AGENT_COMMAND_CONFIG[agent_key]["dir"]`` path
    beneath the user's home directory unless the agent has a documented
    user-global config root.  For example::

        "claude" → ~/.claude/commands/
        "gemini" → ~/.gemini/commands/
        "copilot" → ~/.github/prompts/
        "opencode" → ~/.config/opencode/commands/
        "llxprt" → ~/Library/Preferences/llxprt-code/commands/ (macOS)
    """
    from specify_cli.core.config import AGENT_COMMAND_CONFIG

    if agent_key == "opencode":
        custom_config_dir = os.environ.get("OPENCODE_CONFIG_DIR")
        if custom_config_dir:
            return Path(custom_config_dir).expanduser() / "commands"

        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home).expanduser() / "opencode" / "commands"

        return Path.home() / ".config" / "opencode" / "commands"

    if agent_key == "llxprt":
        # LLxprt resolves its user-global config root via envPaths('llxprt-code')
        # (packages/storage/src/config/path-resolver.ts); the legacy ~/.llxprt
        # tree is migrated to that layout at startup and is no longer read.
        custom_config_home = os.environ.get("LLXPRT_CONFIG_HOME")
        if custom_config_home:
            return Path(custom_config_home).expanduser() / "commands"

        if sys.platform == "darwin":
            return Path.home() / "Library" / "Preferences" / "llxprt-code" / "commands"

        if os.name == "nt":
            app_data = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
            return Path(app_data) / "llxprt-code" / "Config" / "commands"

        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home).expanduser() / "llxprt-code" / "commands"

        return Path.home() / ".config" / "llxprt-code" / "commands"

    config = AGENT_COMMAND_CONFIG[agent_key]
    return Path.home() / str(config["dir"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


#: The relative shape sought below, anchored on the (cheaply-discovered,
#: never-imported) ``charter.offering`` package's own file location (formerly
#: the top-level ``doctrine`` package, relocated by mission
#: ``charter-code-topology-01M152G1``, CR-06). Mission
#: ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` (FR-005)
#: relocated the missions data to ``packs/built-in/missions`` -- a directory
#: that, unlike the pre-relocation shape, sits at a *different* relative
#: depth from the doctrine offering package directory in an installed wheel
#: (``<site-packages>/packs/built-in/missions``, one parent hop) versus an
#: editable checkout (``<repo>/packs/built-in/missions``, two parent hops,
#: since an extra ``src/`` level sits in between). No single fixed-depth
#: ``Path(...).parent / ...`` join can express both, so this is resolved via
#: the shared kernel sibling-path-resolution primitive instead (the same
#: ancestor-walk-covers-both-layouts algorithm :mod:`kernel.paths` and
#: :mod:`charter.offering.missions.repository` already use), anchored on the
#: doctrine offering package's own file rather than this module's. Owned once
#: at the kernel floor (:data:`kernel.paths.MISSION_ASSETS_SIBLING_PATTERN`)
#: and re-bound to this module-local name (FR-012, mission
#: ``resolution-activation-foundation-01KZ9FKG`` WP02) instead of a second,
#: independently-typed ``packs/built-in/missions`` literal -- the
#: ``_get_command_templates_dir`` body below is unchanged, it just now
#: passes the shared constant.
_MISSIONS_SIBLING_PATTERN = MISSION_ASSETS_SIBLING_PATTERN

#: Dotted import path of the doctrine offering package post-relocation
#: (CR-06). Kept as a name (not a literal repeated below) so the two lookup
#: strategies in :func:`_get_command_templates_dir` stay in lockstep.
_OFFERING_MODULE = "charter.offering"


def _get_command_templates_dir() -> Path:
    """Return the command-templates directory from the doctrine offering package.

    Uses import metadata rather than ``import charter.offering`` so CLI
    startup does not execute the offering package's (or its ``charter``
    parent's) heavier imports before command dispatch. :mod:`kernel.sibling_paths`
    has zero dependency on ``charter.offering`` (C-001 layer direction), so
    resolving through it below does not reintroduce that heavy import either.

    ``importlib.util.find_spec("charter.offering")`` would itself import the
    ``charter`` parent package (dotted ``find_spec`` always imports parent
    packages first) -- exactly the heavy import this function exists to
    avoid -- so the search location is resolved via the cheap, top-level
    ``find_spec("charter")`` instead, with ``offering`` appended by hand.

    Raises ``FileNotFoundError`` if the doctrine offering package is absent or
    the relocated missions data cannot be located as its sibling, either of
    which indicates a corrupted install.
    """
    if os.environ.get("SPEC_KITTY_TEMPLATE_ROOT"):
        from specify_cli.runtime.home import get_package_asset_root

        package_asset_root = get_package_asset_root()
        # Typed pin: ``specify_cli.*`` is ``follow_imports = "skip"`` in pyproject, so
        # ``DEFAULT_MISSION_KEY`` resolves to ``Any`` to mypy even though its module
        # annotates it as ``str`` -- the runtime type of this expression is ``Path``.
        legacy_command_templates: Path = package_asset_root / DEFAULT_MISSION_KEY / "command-templates"
        if legacy_command_templates.exists():
            return legacy_command_templates

    loaded_offering = sys.modules.get(_OFFERING_MODULE)
    loaded_file = getattr(loaded_offering, "__file__", None)
    if isinstance(loaded_file, str) and loaded_file:
        anchor = Path(loaded_file)
    else:
        try:
            charter_spec = find_spec("charter")
        except (ModuleNotFoundError, ValueError):
            charter_spec = None
        locations = list(charter_spec.submodule_search_locations or ()) if charter_spec is not None else []
        if not locations:
            raise FileNotFoundError("doctrine offering package has no search location; installation may be corrupted")
        # A file-shaped anchor (matching the sys.modules branch above) so the
        # primitive's ancestor walk starts from the package *directory*, not
        # one level above it. ``offering`` is appended by hand rather than
        # resolved via find_spec("charter.offering") -- see docstring.
        anchor = Path(locations[0]) / "offering" / "__init__.py"

    try:
        missions_root = resolve_installed_sibling(
            anchor_file=anchor,
            env_override=None,
            sibling_relative_path=_MISSIONS_SIBLING_PATTERN,
        )
    except SiblingPathNotFound as exc:
        raise FileNotFoundError("doctrine offering package has no search location; installation may be corrupted") from exc
    # Typed pin: see the ``legacy_command_templates`` comment above -- same
    # ``DEFAULT_MISSION_KEY``-resolves-to-``Any`` mypy artifact.
    resolved: Path = missions_root / "mission-steps" / DEFAULT_MISSION_KEY
    return resolved


def _resolve_script_type() -> str:
    """Return the platform-appropriate script type string."""
    return "ps" if os.name == "nt" else "sh"


def _compute_output_filename(command: str, agent_key: str) -> str:
    """Return the on-disk filename for *command* rendered for *agent_key*."""
    from specify_cli.core.config import AGENT_COMMAND_CONFIG

    config = AGENT_COMMAND_CONFIG.get(agent_key)
    if config is None:
        return f"spec-kitty.{command}.md"

    ext: str = config["ext"]
    stem = command
    if ext:
        return f"spec-kitty.{stem}.{ext}"
    return f"spec-kitty.{stem}"


def _expected_command_filenames(agent_key: str, templates_dir: Path) -> set[str]:
    """Return the complete managed command filename set for *agent_key*.

    The prompt-driven half is only valid when its backing template is present.
    Missing templates therefore make the health check fail instead of allowing a
    partial command install to be stamped as current.
    """
    from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, PROMPT_DRIVEN_COMMANDS

    # Templates now live under per-step subdirectories: {step}/prompt.md
    template_commands = {step_dir.name for step_dir in templates_dir.iterdir() if step_dir.is_dir() and (step_dir / "prompt.md").is_file()}
    if not template_commands >= PROMPT_DRIVEN_COMMANDS:
        return set()

    return {_compute_output_filename(command, agent_key) for command in sorted(PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS)}


def _file_has_current_version_marker(path: Path, cli_version: str) -> bool:
    """Return True when *path* has this CLI version's managed marker."""
    expected = f"{_VERSION_MARKER_PREFIX} {cli_version} -->"
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    return any(line.strip() == expected for line in content.splitlines()[:_VERSION_MARKER_HEAD_LINES])


def _agent_commands_healthy(agent_key: str, templates_dir: Path, cli_version: str) -> bool:
    """Return True when one agent's global command directory is complete."""
    expected = _expected_command_filenames(agent_key, templates_dir)
    if not expected:
        return False

    output_dir = get_global_command_dir(agent_key)
    if not output_dir.is_dir():
        return False

    existing = {path.name for path in output_dir.iterdir() if path.is_file() and path.name.startswith("spec-kitty.")}
    if existing != expected:
        return False

    return all(_file_has_current_version_marker(output_dir / filename, cli_version) for filename in expected)


def _all_global_agent_commands_healthy(
    templates_dir: Path,
    cli_version: str,
    agent_keys: list[str] | None = None,
) -> bool:
    """Return True when every command-layer agent has a complete command set."""
    from specify_cli.core.config import AGENT_COMMAND_CONFIG

    keys = agent_keys if agent_keys is not None else list(AGENT_COMMAND_CONFIG.keys())
    return all(_agent_commands_healthy(agent_key, templates_dir, cli_version) for agent_key in keys)


def _render_agent_commands(
    agent_key: str,
    templates_dir: Path,
    script_type: str,
) -> tuple[tuple[str, bytes], ...]:
    """Render the complete agent bundle; any missing source fails the batch."""
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.shims.generator import generate_shim_content_for_agent
    from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, PROMPT_DRIVEN_COMMANDS
    from specify_cli.template.asset_generator import render_command_template

    config = AGENT_COMMAND_CONFIG[agent_key]
    rendered: list[tuple[str, bytes]] = []
    for command in sorted(PROMPT_DRIVEN_COMMANDS):
        template = templates_dir / command / "prompt.md"
        content = render_command_template(
            template_path=template,
            script_type=script_type,
            agent_key=agent_key,
            arg_format=config["arg_format"],
            extension=config["ext"],
        )
        rendered.append((_compute_output_filename(command, agent_key), content.encode("utf-8")))
    for command in sorted(CLI_DRIVEN_COMMANDS):
        content = generate_shim_content_for_agent(command, agent_key)
        rendered.append((_compute_output_filename(command, agent_key), content.encode("utf-8")))
    return tuple(rendered)


def _command_effect_owners(path: Path, roots: dict[str, Path]) -> tuple[str, ...]:
    """Attribute members/parents physically; shared cache supports the batch."""
    owners = tuple(key for key, directory in roots.items() if path == directory or path.parent == directory or path in directory.parents)
    return owners or tuple(roots)


def assess_global_agent_commands(
    *,
    agent_keys: list[str] | None = None,
    consent: ApplyConsent = ApplyConsent(),
    templates_dir: Path | None = None,
    script_type: str | None = None,
    _batch: _GlobalAssetPreparation | None = None,
) -> OwnerAssessment:
    """Read/render the entire selected agent bundle without installing sources.

    A scoped call never updates the all-agent stamp. Unknown prefixed paths
    and edited generated files are preserved, independent of marker freshness.
    """
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
    from specify_cli.runtime.asset_preparation import AssetPreparation, global_asset_root, incomplete, retry_torn_read

    home = get_kittify_home()
    all_roots = tuple(get_global_command_dir(key) for key in AGENT_COMMAND_CONFIG)
    root = global_asset_root("slash_commands", (home, *all_roots))

    def _build() -> tuple[AssetPreparation, OwnerAssessment]:
        prepared = AssetPreparation("slash_commands", root, home / "cache", _LOCK_FILENAME, consent)
        keys = tuple(sorted(set(AGENT_COMMAND_CONFIG if agent_keys is None else agent_keys)))
        selected_roots: dict[str, Path] = {}
        templates = _get_command_templates_dir() if templates_dir is None else templates_dir
        prepared.observe(templates, members=True)
        for command in sorted(PROMPT_DRIVEN_COMMANDS):
            prepared.source(templates / command / "prompt.md")
        for key in keys:
            if key not in AGENT_COMMAND_CONFIG:
                raise ValueError(f"Unknown slash-command agent: {key}")
            output = get_global_command_dir(key)
            selected_roots[key] = output
            # #4017 rescope: ``output`` is this owner's OWN managed
            # destination, never a source read -- see the identical
            # rationale on ``assess_global_agent_skills``'s
            # ``destination_root`` probe. Without this tag, an untagged
            # probe here (and the untagged ``target`` probe below) defaults
            # to "source_read", which only ever upgrades and never
            # downgrades -- permanently poisoning this whole tree's role
            # and turning a concurrent peer's legitimate destination
            # materialization into unretractable "source drift".
            state = prepared.observe(output, members=True, role="destination_probe")
            if state.kind not in {"directory", "absent"}:
                prepared.preserve(output, "Unproven command directory replacement")
                continue
            rendered = _render_agent_commands(key, templates, _resolve_script_type() if script_type is None else script_type)
            canonical = {name for name, _content in rendered}
            for name, content in rendered:
                target = output / name
                predecessor = False
                if prepared.observe(target, role="destination_probe").kind == "file":
                    # #4174 landing-pass: read these EXISTING DESTINATION bytes
                    # directly, never via `prepared.source()` -- that helper's
                    # default role is "source_read", and re-observing `target`
                    # under that role here would silently downgrade both
                    # `target` and (via observe()'s ancestor walk) `output`
                    # itself from "destination_probe" to "source_read",
                    # permanently disabling Concern 2's peer-tolerance for the
                    # whole destination tree on any WARM reassess where
                    # existing command files are already present. The
                    # `observe()` call just above already confirmed this is a
                    # regular file under the owner's own managed destination.
                    existing_bytes = target.read_bytes()
                    marker = rb"(?m)^<!-- spec-kitty-command-version: [^\r\n]+ -->\r?\n"
                    predecessor = bool(re.search(marker, existing_bytes)) and re.sub(marker, b"", existing_bytes) == re.sub(marker, b"", content)
                prepared.asset(target, content, 0o444, canonical_predecessor=predecessor)
            if state.kind == "directory":
                for existing in output.iterdir():
                    if existing.name not in canonical:
                        prepared.retire(existing)
        stamp = home / "cache" / _VERSION_FILENAME if agent_keys is None else None
        assessment = prepared.finish(stamp, _get_cli_version())
        assessment = replace(
            assessment,
            effects=tuple(replace(effect, logical_owners=_command_effect_owners(effect.destination, selected_roots)) for effect in assessment.effects),
        )
        return prepared, assessment

    try:
        # #4017 rescope: retry ONLY the local build (never `_batch.include()`,
        # called once below on the stabilized result) so a retry can never
        # replay stale partial mutations into a shared, cross-owner batch.
        prepared, assessment = retry_torn_read(_build)
        if _batch is not None:
            _batch.include(prepared, assessment.effects)
        return assessment
    except (OSError, ValueError, KeyError) as exc:
        return incomplete("slash_commands", root, exc)


def _apply_command_assessment(assessment: OwnerAssessment, *, rebuild: Callable[[], OwnerAssessment]) -> None:
    """Mirror ``bootstrap.ensure_runtime()``'s re-assess-under-lock (#4017 WP03)
    via the shared ``asset_preparation.apply_with_reassess`` helper (#4174
    landing-pass) -- see its docstring for the full mechanism.
    """
    from specify_cli.runtime.asset_preparation import apply_with_reassess

    if not assessment.complete:
        raise RuntimeError("; ".join(d.message for d in assessment.diagnostics))
    if not assessment.effects:
        return
    result = apply_with_reassess(
        assessment,
        rebuild,
        ApplyConsent(automatic=True),
        converged_log_message="global agent commands already materialized by a concurrent peer; nothing applied.",
        logger=logger,
    )
    if result.outcome not in {"applied", "skipped"}:
        raise RuntimeError("; ".join(d.message for d in result.diagnostics))


def _sync_agent_commands(agent_key: str, templates_dir: Path, script_type: str) -> None:
    """Retain the existing scoped owner entry point using prepared output."""
    _apply_command_assessment(
        assess_global_agent_commands(agent_keys=[agent_key], templates_dir=templates_dir, script_type=script_type),
        rebuild=lambda: assess_global_agent_commands(agent_keys=[agent_key], templates_dir=templates_dir, script_type=script_type),
    )


def ensure_global_agent_commands(*, agent_keys: list[str] | None = None) -> None:
    """Ensure actual global command health, retaining unchanged bytes and mtimes."""
    _apply_command_assessment(
        assess_global_agent_commands(agent_keys=agent_keys),
        rebuild=lambda: assess_global_agent_commands(agent_keys=agent_keys),
    )
