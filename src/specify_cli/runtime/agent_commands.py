"""Bootstrap user-global canonical slash commands for the configured agents.

On every CLI startup, ``ensure_global_agent_commands()`` installs the
consumer-facing command files (prompt-driven + CLI-driven shims) into the
user-global command roots of the slash-command agents configured in the
current project (none outside a project, #6470):

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
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, replace
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.paths import MISSION_ASSETS_SIBLING_PATTERN, is_windows
from kernel.sibling_paths import SiblingPathNotFound, resolve_installed_sibling
from specify_cli.core.config import DEFAULT_MISSION_KEY
from specify_cli.runtime.bootstrap import _get_cli_version
from specify_cli.runtime.home import get_kittify_home
from specify_cli.runtime.asset_preparation import _GlobalAssetPreparation
from specify_cli.tool_surface.operations import ApplyConsent, Disposition, FileState, OperationRoot, OwnerAssessment, OwnershipProof

if TYPE_CHECKING:
    from specify_cli.runtime.asset_preparation import AssetPreparation

logger = logging.getLogger(__name__)

_VERSION_FILENAME = "agent-commands.lock"
_LOCK_FILENAME = ".agent-commands.lock"
_VERSION_MARKER_PREFIX = "<!-- spec-kitty-command-version:"
_VERSION_MARKER_HEAD_LINES = 20

#: Freshness pre-check stamp (Lever C primary, operator Ruling 6 --
#: ``reviews/plan.ruling.md``). Deliberately a NEW file, never a repurposing
#: of ``_VERSION_FILENAME``: that file's on-disk shape is a plain CLI-version
#: string (``AssetPreparation.finish(stamp, _get_cli_version())`` writes
#: ``version.encode()`` verbatim) and an existing test
#: (``test_current_version_lock_does_not_mask_partial_global_commands``)
#: asserts that shape stays exactly the plain version string -- reusing that
#: filename for JSON would either break that contract or force a dual-shape
#: reader. A new file sidesteps both, and "no migration needed" already holds
#: for any new file (data-model.md's stamp contract: absence degrades to the
#: existing unconditional-render behavior).
#:
#: WP04-C1-003 (review cycle 1): the filename deliberately ends in ``.lock``,
#: NOT ``.json``, even though its content is JSON. ``asset_preparation.py``'s
#: shared ``_write_order`` sorts every apply-time write by ``(stage, depth,
#: path)``, and its stage classification -- not source-code call order --
#: is what actually determines apply sequence within one batch: a
#: ``.lock``-suffixed name is stage 6 (dead last, same bucket as
#: ``_VERSION_FILENAME`` below), while an ordinary content file is the
#: default stage 3. Measured directly (see the WP04 report): under the
#: PRIOR ``.json`` name, this stamp's destination path was consistently
#: SHALLOWER than the rendered command files' destination paths, so it sorted
#: stage 3 depth 6 -- BEFORE every stage-3 depth-7+ command-file write, not
#: after. ``_apply_retained_assets`` applies writes in that exact sorted
#: order and returns a "partial" outcome (with everything already applied to
#: disk left in place) the instant one write fails -- so a command-file write
#: failure ordered AFTER the stamp would have left a stale-but-"fresh"-looking
#: stamp on disk from a run that never actually completed, even though the
#: overall call still surfaced as a raised failure to its caller. The
#: ``.lock`` suffix is the SAME late-apply convention ``_VERSION_FILENAME``
#: already relies on (that is why IT ends in ``.lock`` despite also holding
#: plain text content, not an empty lock): it guarantees this stamp is
#: written to disk only after every other effect in the SAME batch -- every
#: rendered command file, the inventory, everything -- has already applied
#: without error, matching data-model.md's "write only after a full,
#: successful render-and-apply cycle completes" contract for real, not only
#: in code-comment discipline. See ``TestFreshnessStampAppliesLast`` in
#: ``tests/specify_cli/runtime/test_agent_commands.py`` for the red/green
#: proof (temporarily reverting this suffix back to ``.json`` reproduces the
#: pre-fix ordering hazard and fails that test).
_FRESHNESS_STAMP_FILENAME = "agent-commands-freshness.lock"

#: Freshness stamp schema (#6470, WP06). Schema 2 records the agent keys
#: proven healthy at (cli_version, template_source_signature) instead of the
#: one full-fleet key set, so a scoped call can short-circuit, and it records
#: that the retired ``~/.agent/workflows`` cleanup ran. A stamp without it
#: (schema 1, written before this change) reads as absent: the first run on
#: new code builds once, and that build runs the cleanup.
_FRESHNESS_SCHEMA = 2

#: The retired Antigravity slash-command row, frozen here for ONE purpose:
#: re-rendering what the old writer put in ``~/.agent/workflows`` so a file
#: with no inventory record can be proven ours by byte equality before it is
#: removed (#6470). Antigravity no longer has an ``AGENT_COMMAND_CONFIG`` row
#: (it is a command-skill agent), so ``get_global_command_dir("antigravity")``
#: raises ``KeyError``; nothing else may read this constant.
_RETIRED_ANTIGRAVITY_KEY = "antigravity"
_RETIRED_ANTIGRAVITY_ROW: dict[str, str] = {"dir": ".agent/workflows", "ext": "md", "arg_format": "$ARGUMENTS"}
_COMMAND_FILE_PREFIX = "spec-kitty."


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

        if is_windows():
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
    return "ps" if is_windows() else "sh"


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


#: One managed marker line, capturing the CLI version it names. Byte-level
#: twin of ``_VERSION_MARKER_PREFIX`` so the predecessor check compares the
#: exact bytes the renderers emit (including the TOML agents, whose marker
#: sits inside the ``prompt = """..."""`` body rather than after frontmatter).
_VERSION_MARKER_LINE = re.compile(rb"(?m)^<!-- spec-kitty-command-version: ([^\r\n]+?) -->\r?\n")


def _is_canonical_predecessor(existing: bytes, desired: bytes, current_version: str) -> bool:
    """Return True when *existing* command-file bytes provably came from a spec-kitty release.

    #4609: a file whose managed marker names a DIFFERENT CLI version carries
    spec-kitty's own provenance stamp from that other release, so upgrading it
    in place is provenance-safe even when the rendered content changed between
    the two releases. Without this, a 3.2.7 -> 4.x upgrade silently left every
    content-changed command file (specify/plan/tasks/analyze) at the old
    version: the pre-4.x install wrote no asset inventory, so ``asset()``
    could prove neither ownership nor equality and preserved each file as an
    "Unproven existing asset" -- permanently, with no warning.

    A marker naming the CURRENT version only qualifies when the bytes are
    otherwise identical: current-version marker plus drifted content is a
    user edit of this release's own output, which stays preserved.
    """
    match = _VERSION_MARKER_LINE.search(existing)
    if match is None:
        return False
    declared = match.group(1).decode("utf-8", "replace").strip()
    if declared != current_version:
        return True
    return _VERSION_MARKER_LINE.sub(b"", existing) == _VERSION_MARKER_LINE.sub(b"", desired)


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


# ---------------------------------------------------------------------------
# Freshness pre-check (Lever C primary, operator Ruling 6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FreshnessStamp:
    """The SOURCE-side fields of the schema-2 freshness stamp.

    ``healthy_keys`` names the agents a completed build rendered at this
    ``cli_version`` and ``template_source_signature``. It is a claim about
    the source side only (PLAN-ARCH-001 in ``data-model.md``): destination
    health is still verified separately, for the requested keys, via
    ``_all_global_agent_commands_healthy()``. Only schema-2 stamps are read,
    and schema 2 means the retired ``~/.agent/workflows`` cleanup has run.
    """

    cli_version: str
    template_source_signature: str
    healthy_keys: tuple[str, ...]


def _rendering_pipeline_signature() -> bytes:
    """Return a content hash of the rendering CODE this output depends on.

    WP04-C1-004 (review cycle 1): ``_get_cli_version()`` returns the static
    ``pyproject.toml`` version string, not a build/commit-scoped value, so on
    an editable/dev install -- the exact install shape this mission's own WP
    agents and reviewers run under -- a contributor changing the rendering
    code without touching template content and without bumping
    ``pyproject.toml``'s version would otherwise go completely undetected by
    both the stamp comparison and the destination-health marker check (the
    marker only encodes ``cli_version``, unchanged). Hashing this module's own
    source plus the renderer modules it actually calls
    (``template.asset_generator.render_command_template`` /
    ``render_template_text``, ``shims.generator.generate_shim_content_for_agent``)
    folds that code surface into the freshness stamp's signature so a
    same-version rendering-code change is detected too. Deliberately not
    caught here, matching ``_template_source_signature``: a rendering module
    that cannot be located/read is a genuine failure the caller must fall
    through on, never mask as "unchanged".

    Landing fold (PR #4992): ``core.config.AGENT_COMMAND_CONFIG`` (each
    agent's ``arg_format``/``ext``) is itself a rendered-content input --
    ``render_command_template(arg_format=config["arg_format"],
    extension=config["ext"])`` reads it directly -- but was not part of this
    signature, so a same-version ``arg_format``-only edit changed rendered
    content while leaving the freshness stamp matching, wrongly skipping the
    re-render. A stable, sorted JSON dump of the config dict is folded into
    the hash below to close that hole.
    """
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.shims import generator as shim_generator
    from specify_cli.template import asset_generator

    module_files: list[str] = [f for f in (__file__, asset_generator.__file__, shim_generator.__file__) if f]
    hasher = hashlib.sha256()  # noqa: TID251 -- raw code-signature integrity hash, not charter hashing
    for module_file in sorted(module_files):
        hasher.update(module_file.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(Path(module_file).read_bytes())
        hasher.update(b"\0")
    hasher.update(json.dumps(AGENT_COMMAND_CONFIG, sort_keys=True).encode("utf-8"))
    return hasher.digest()


def _template_source_signature(templates_dir: Path) -> str:
    """Return a content-based signature of the command-templates source tree.

    Cheap relative to a full render (no YAML/Jinja parsing): one pass hashing
    every file's relative path and bytes, plus the rendering pipeline's own
    code (:func:`_rendering_pipeline_signature`, WP04-C1-004). Any content OR
    filename change anywhere under *templates_dir*, or any change to the
    rendering code itself, changes the digest -- this is what lets the
    freshness pre-check detect a template-source change (Ruling 6 staleness
    test (a)) without rendering anything. Deliberately not caught here: a
    source tree that cannot be walked/read is a genuine failure the caller
    must fall through on, never mask as "unchanged".
    """
    hasher = hashlib.sha256()  # noqa: TID251 -- raw source-tree integrity signature, not charter hashing
    for path in sorted(p for p in templates_dir.rglob("*") if p.is_file()):
        hasher.update(path.relative_to(templates_dir).as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    hasher.update(_rendering_pipeline_signature())
    return hasher.hexdigest()


def _read_freshness_stamp(path: Path) -> _FreshnessStamp | None:
    """Read the freshness stamp; anything unreadable or malformed reads as absent.

    Narrowly scoped to the READ only (data-model.md's PLAN-ARCH-002): a
    missing file, a torn/partial write, legacy content, or a schema this
    version does not recognise are all treated identically to "no stamp" --
    degrading back to today's unconditional render, never raising. This is
    REQUIRED regardless of filename choice (see the module-level comment on
    ``_FRESHNESS_STAMP_FILENAME``): the very first read of a freshly
    introduced stamp file is also just "absent", handled by the same path.
    A schema-1 stamp (no ``schema`` field, one ``agent_keys`` list) is such
    an unrecognised schema: it forces one build, which also runs the retired
    ``~/.agent/workflows`` cleanup (#6470). Render/write errors are handled
    separately and must NOT be caught here.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("schema") != _FRESHNESS_SCHEMA:
        return None
    cli_version = payload.get("cli_version")
    signature = payload.get("template_source_signature")
    healthy_keys = payload.get("healthy_keys")
    if not isinstance(cli_version, str) or not isinstance(signature, str):
        return None
    if not isinstance(healthy_keys, list) or not all(isinstance(key, str) for key in healthy_keys):
        return None
    return _FreshnessStamp(cli_version, signature, tuple(healthy_keys))


def _freshness_stamp_matches(stamp: _FreshnessStamp | None, *, cli_version: str, template_source_signature: str, agent_keys: tuple[str, ...]) -> bool:
    """Return True when *stamp* matches current sources and covers every requested key.

    Conditions 1-3 of data-model.md's four-condition contract, with the key
    condition widened from equality to coverage (#6470, WP06): a scoped call
    is fresh when each of its *agent_keys* is among the stamp's
    ``healthy_keys``. An empty request is covered by any matching stamp.
    The fourth, destination-health condition is checked separately by the
    caller so this function stays pure/testable.
    """
    return (
        stamp is not None
        and stamp.cli_version == cli_version
        and stamp.template_source_signature == template_source_signature
        and set(agent_keys) <= set(stamp.healthy_keys)
    )


def _freshness_short_circuit(
    batch: _GlobalAssetPreparation | None,
    home: Path,
    root: OperationRoot,
    templates_dir: Path | None,
    consent: ApplyConsent,
    requested_keys: tuple[str, ...],
) -> OwnerAssessment | None:
    """Return the short-circuit assessment when fresh+healthy; else ``None``.

    ``None`` means "fall through to the unconditional render path" -- the
    only two outcomes this function has. It never itself decides to skip on
    uncertainty: an unreadable/malformed stamp, a source tree that cannot be
    walked, or a destination-health check that cannot complete all read as
    "not fresh" (``None``), never as "fresh" (Ruling 6's binding condition:
    a missed refresh must never be silent). Runs entirely without
    constructing an ``AssetPreparation`` -- see
    ``assess_global_agent_commands``'s docstring for the SK-243 rationale.

    The caller decides eligibility (``assess_global_agent_commands``: a
    full-fleet call or one that opts in); *requested_keys* is the resolved
    key set, full-fleet or scoped. A batched call
    (``batch is not None``) returns ``None`` unconditionally, deferring to
    the render path exactly as before. Destination health is checked for the
    requested keys only; the retired ``~/.agent/workflows`` folder is never
    looked at here (a schema-2 stamp records that its cleanup already ran).
    """
    if batch is not None:
        return None
    resolved_templates_dir = _get_command_templates_dir() if templates_dir is None else templates_dir
    cli_version = _get_cli_version()
    try:
        signature = _template_source_signature(resolved_templates_dir)
    except OSError:
        return None
    stamp = _read_freshness_stamp(home / "cache" / _FRESHNESS_STAMP_FILENAME)
    if not _freshness_stamp_matches(stamp, cli_version=cli_version, template_source_signature=signature, agent_keys=requested_keys):
        return None
    try:
        healthy = _all_global_agent_commands_healthy(resolved_templates_dir, cli_version, list(requested_keys))
    except OSError:
        return None
    if not healthy:
        return None
    return OwnerAssessment("slash_commands", root, consent=consent)


def _stamp_payload(home: Path, templates: Path, built_keys: tuple[str, ...]) -> bytes:
    """Return the schema-2 stamp bytes a successful build of *built_keys* certifies.

    Prior ``healthy_keys`` are kept when the prior stamp names the same
    ``cli_version`` and signature (a scoped build adds to the fleet another
    scope already proved); otherwise only *built_keys* are claimed.
    """
    cli_version = _get_cli_version()
    signature = _template_source_signature(templates)
    prior = _read_freshness_stamp(home / "cache" / _FRESHNESS_STAMP_FILENAME)
    healthy = set(built_keys)
    if prior is not None and prior.cli_version == cli_version and prior.template_source_signature == signature:
        healthy.update(prior.healthy_keys)
    return json.dumps(
        {
            "schema": _FRESHNESS_SCHEMA,
            "cli_version": cli_version,
            "template_source_signature": signature,
            "healthy_keys": sorted(healthy),
            "retired_surfaces_cleaned": True,
        },
        sort_keys=True,
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Retired ``~/.agent/workflows`` cleanup (#6470, WP06)
# ---------------------------------------------------------------------------


def _retired_workflows_dir() -> Path:
    """Return the retired Antigravity global workflows folder (hard-coded, never via the config row)."""
    return Path.home() / _RETIRED_ANTIGRAVITY_ROW["dir"]


def _is_real_directory_below_home(path: Path) -> bool:
    """Return True when every component of *path* below the home folder is a real directory.

    A symlink anywhere below home (``~/.agent`` or ``~/.agent/workflows``),
    a non-directory, or an absent component returns False: the cleanup is
    refused, so it can never follow a link out of the home folder.
    """
    current = Path.home()
    for part in path.relative_to(current).parts:
        current = current / part
        if current.is_symlink() or not current.is_dir():
            return False
    return True


def _with_agent_upgrade_check(rendered: str) -> str:
    """Re-insert the agent upgrade-check block the old Antigravity render carried.

    ``render_command_template`` prepends that block only for agents with an
    ``AGENT_COMMAND_CONFIG`` row, which Antigravity no longer has. The old
    writer's Markdown output was frontmatter, marker line, blank line, body, the
    body starting with the block, so it is re-applied to the text after the
    first marker line and its blank separator.
    """
    from specify_cli.agent_upgrade_prompt import prepend_agent_upgrade_check

    match = re.search(r"(?m)^<!-- spec-kitty-command-version: [^\n]+ -->\n\n", rendered)
    if match is None:
        return rendered
    # Typed pin: ``specify_cli.*`` is ``follow_imports = "skip"``, so the helper reads as ``Any``.
    body: str = prepend_agent_upgrade_check(rendered[match.end() :])
    return rendered[: match.end()] + body


def _retired_antigravity_command_bytes(command: str, templates: Path, script_type: str) -> bytes | None:
    """Return what the old writer rendered into ``~/.agent/workflows`` for *command* at this version.

    ``None`` for a name that is not a current command (it cannot be proven
    by a current render and is kept).
    """
    from specify_cli.shims.generator import generate_shim_content
    from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, PROMPT_DRIVEN_COMMANDS
    from specify_cli.template.asset_generator import render_command_template

    row = _RETIRED_ANTIGRAVITY_ROW
    if command in PROMPT_DRIVEN_COMMANDS:
        rendered = render_command_template(
            template_path=templates / command / "prompt.md",
            script_type=script_type,
            agent_key=_RETIRED_ANTIGRAVITY_KEY,
            arg_format=row["arg_format"],
            extension=row["ext"],
        )
        return _with_agent_upgrade_check(rendered).encode("utf-8")
    if command in CLI_DRIVEN_COMMANDS:
        shim: str = generate_shim_content(command, _RETIRED_ANTIGRAVITY_KEY, row["arg_format"])
        return shim.encode("utf-8")
    return None


def _retire_antigravity_workflows(prepared: AssetPreparation, templates: Path, script_type: str) -> None:
    """Stage removal of Spec Kitty's own ``spec-kitty.*.md`` files in ``~/.agent/workflows``.

    Proof is one of two, never a name or a marker alone (plan A-M8):

    * an inventory record (``prepared.retire``, which also keeps an edited
      recorded file), or
    * for a file with no record, the exact CURRENT-version marker line AND
      byte equality with a render from the frozen retired row. A marker
      naming another version is never deletion proof (R-M5): the
      ``_is_canonical_predecessor`` different-version branch is for in-place
      upgrades, not removal.

    Other files and the folder itself are never touched; a symlinked or
    non-directory component refuses the whole cleanup.
    """
    workflows = _retired_workflows_dir()
    if not _is_real_directory_below_home(workflows):
        return
    if prepared.observe(workflows, members=True, role="destination_probe").kind != "directory":
        return
    cli_version = _get_cli_version()
    suffix = "." + _RETIRED_ANTIGRAVITY_ROW["ext"]
    for name in sorted(child.name for child in workflows.iterdir()):
        if not (name.startswith(_COMMAND_FILE_PREFIX) and name.endswith(suffix)):
            continue
        child = workflows / name
        if child.relative_to(prepared.root.path).as_posix() in prepared.previous:
            prepared.retire(child)
            continue
        if prepared.observe(child, role="destination_probe").kind != "file" or not _file_has_current_version_marker(child, cli_version):
            continue
        canonical = _retired_antigravity_command_bytes(name[len(_COMMAND_FILE_PREFIX) : -len(suffix)], templates, script_type)
        if canonical is not None:
            prepared.retire_canonical(child, canonical, "retired-antigravity-render")


# ---------------------------------------------------------------------------
# Startup scope (#6470, #3048 context)
# ---------------------------------------------------------------------------


def _project_slash_agent_scope() -> list[str]:
    """Return the slash-command agents configured in the project at the working directory.

    Outside a project, without ``.kittify/config.yaml``, or with an
    unreadable config, the scope is empty: nothing is written. An empty list
    never means "all agents".
    """
    from specify_cli.core.paths import locate_project_root

    project_root = locate_project_root()
    if project_root is None or not (project_root / ".kittify" / "config.yaml").is_file():
        return []
    from specify_cli.core.agent_config import AgentConfigError, get_configured_agents
    from specify_cli.core.config import configured_slash_agents

    try:
        configured = get_configured_agents(project_root)
    except AgentConfigError as exc:
        logger.debug("global command scope: unreadable agent config, writing none: %s", exc)
        return []
    return list(configured_slash_agents(configured))


def assess_global_agent_commands(
    *,
    agent_keys: list[str] | None = None,
    consent: ApplyConsent = ApplyConsent(),
    templates_dir: Path | None = None,
    script_type: str | None = None,
    _batch: _GlobalAssetPreparation | None = None,
    _short_circuit: bool = False,
) -> OwnerAssessment:
    """Read/render the entire selected agent bundle without installing sources.

    ``agent_keys=None`` selects every slash-command agent; a list (including
    an empty one, which selects none) selects exactly those agents. A scoped
    call never updates the all-agent version stamp. Unknown prefixed paths
    and edited generated files are preserved, independent of marker freshness;
    a managed marker naming a *different* CLI version proves canonical
    provenance and migrates in place even when the content changed between
    releases (#4609). Canonical command files that still cannot be migrated
    are never silent: one warning names them.

    Every build also stages removal of Spec Kitty's own files from the
    retired ``~/.agent/workflows`` folder (``_retire_antigravity_workflows``,
    #6470) and writes the schema-2 freshness stamp for the keys it built.

    **Freshness pre-check (Lever C primary, operator Ruling 6).** For a
    non-batched call (``_batch=None``) that is either full-fleet
    (``agent_keys=None``) or opts in with ``_short_circuit=True`` -- what
    ``ensure_global_agent_commands()`` passes, scoped or project-scoped, on
    every non-fast-pathed CLI startup -- this reads a small on-disk stamp and,
    only when (cli_version, template_source_signature) match, every
    requested key is among the stamp's ``healthy_keys``, AND every requested
    agent's rendered destination is independently verified healthy, returns
    immediately with an empty assessment -- no
    render, no ``AssetPreparation`` construction at all. Both checks run
    strictly before any ``AssetPreparation`` object exists (data-model.md's
    SK-243 immunity property: this path never calls ``observe()`` on an
    ``AssetPreparation``, so it can never enter ``check_assets()``'s
    drift-recheck machinery). Any uncertainty -- an unreadable/malformed
    stamp, a source tree that cannot be walked, an unhealthy destination --
    falls through to the unconditional render-then-diff path below, never to
    a skip; a missed refresh must never be silent (Ruling 6's binding
    condition). A scoped call that does not opt in always builds: its
    callers (the tool-surface provider) recheck and apply the returned
    assessment, which needs the retained preparation a build carries.
    """
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
    from specify_cli.runtime.asset_preparation import AssetPreparation, build_serialized, digest, global_asset_root, incomplete

    home = get_kittify_home()
    all_roots = tuple(get_global_command_dir(key) for key in AGENT_COMMAND_CONFIG)
    root = global_asset_root("slash_commands", (home, *all_roots))

    requested_keys = tuple(sorted(set(AGENT_COMMAND_CONFIG if agent_keys is None else agent_keys)))
    eligible = agent_keys is None or _short_circuit
    short_circuit = _freshness_short_circuit(_batch, home, root, templates_dir, consent, requested_keys) if eligible else None
    if short_circuit is not None:
        return short_circuit

    def _build() -> tuple[AssetPreparation, OwnerAssessment]:
        prepared = AssetPreparation("slash_commands", root, home / "cache", _LOCK_FILENAME, consent)
        keys = requested_keys
        selected_roots: dict[str, Path] = {}
        canonical_names: set[str] = set()
        templates = _get_command_templates_dir() if templates_dir is None else templates_dir
        resolved_script_type = _resolve_script_type() if script_type is None else script_type
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
            rendered = _render_agent_commands(key, templates, resolved_script_type)
            canonical = {name for name, _content in rendered}
            canonical_names.update(canonical)
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
                    # #4609: a managed marker naming a different CLI version
                    # proves the bytes are an older release's canonical output
                    # (the pre-4.x line wrote no inventory to prove it with),
                    # so they are a canonical predecessor even when the
                    # rendered content changed between the two releases.
                    predecessor = _is_canonical_predecessor(existing_bytes, content, _get_cli_version())
                prepared.asset(target, content, 0o444, canonical_predecessor=predecessor)
            if state.kind == "directory":
                for existing in output.iterdir():
                    if existing.name not in canonical:
                        prepared.retire(existing)
        _retire_antigravity_workflows(prepared, templates, resolved_script_type)
        # Written into the SAME AssetPreparation batch as the rendered
        # command files above, staged, locked and applied atomically
        # together with the render it describes (data-model.md's "write
        # only after a full, successful render-and-apply cycle
        # completes" contract): a partial/failed run never reaches here
        # with a *different* set of effects than what actually gets
        # applied, and a torn write cannot poison the stamp into
        # claiming freshness the destination files don't back up.
        #
        # Deliberately ``prepared.overwrite_internal()`` (the public
        # counterpart of the same primitive ``finish()`` uses for
        # ``_VERSION_FILENAME`` below -- PR-BOUNDARY-001), NEVER
        # ``prepared.asset()``: ``asset()``'s drift-preservation logic
        # is correct for USER-facing command files (never clobber an
        # edit it cannot prove is unowned) but wrong for this internal
        # cache-only bookkeeping file -- a hand-corrupted or torn-write
        # stamp is never "owned" by the prior inventory entry, so
        # ``asset()`` would PRESERVE it forever (a verified failure mode:
        # every subsequent read stays malformed, degrading this whole
        # mechanism back to "always slow" permanently instead of
        # self-healing on the very next successful render, contradicting
        # data-model.md's explicit "overwrite with a fresh,
        # correctly-shaped stamp on success" requirement).
        freshness_path = home / "cache" / _FRESHNESS_STAMP_FILENAME
        prepared.parents(freshness_path)
        freshness_payload = _stamp_payload(home, templates, keys)
        prepared.overwrite_internal(
            freshness_path,
            FileState("file", sha256=digest(freshness_payload), mode=0o644),
            freshness_payload,
            OwnershipProof("managed_path", f"{prepared.owner}:freshness-stamp"),
        )
        stamp = home / "cache" / _VERSION_FILENAME if agent_keys is None else None
        assessment = prepared.finish(stamp, _get_cli_version())
        if selected_roots:
            # With no agent selected (a project-scoped startup outside a
            # project) the effects keep the owner itself as logical owner:
            # an empty owner tuple is not a valid effect.
            assessment = replace(
                assessment,
                effects=tuple(replace(effect, logical_owners=_command_effect_owners(effect.destination, selected_roots)) for effect in assessment.effects),
            )
        retired_prefix = _retired_workflows_dir().relative_to(root.path).as_posix() + "/"
        _warn_unmigrated_commands(tuple(d for d in assessment.dispositions if not (d.path or "").startswith(retired_prefix)), canonical_names)
        return prepared, assessment

    try:
        # #4017 rescope: escalate ONLY the local build (never `_batch.include()`,
        # called once below on the stabilized result) so an escalated rebuild
        # can never replay stale partial mutations into a shared, cross-owner
        # batch.
        prepared, assessment = build_serialized(_build, logger=logger)
        if _batch is not None:
            _batch.include(prepared, assessment.effects)
        return assessment
    except (OSError, ValueError, KeyError) as exc:
        return incomplete("slash_commands", root, exc)


def _warn_unmigrated_commands(dispositions: tuple[Disposition, ...], canonical_names: set[str]) -> None:
    """Name every canonical command file this assessment could not migrate (#4609).

    ``asset()`` deliberately preserves an existing file it cannot prove is
    unedited canonical output -- that refusal is the safe half of the
    contract; this warning is the other half: the ones it refused are never
    silent. Scoped to the canonical filename set so a user's own unrelated
    ``spec-kitty.*`` file or an unproven command directory is not reported
    here (those keeps are deliberate too, and ``retire()`` already keeps them
    namelessly).
    """
    unmigrated = sorted(
        f"{disposition.path} ({disposition.reason})"
        for disposition in dispositions
        if disposition.state in {"preserve", "consent_required"} and (disposition.path or "").rsplit("/", 1)[-1] in canonical_names
    )
    if not unmigrated:
        return
    logger.warning(
        "spec-kitty could not migrate %d global command file(s) and left them unchanged: %s. "
        "Their contents differ from this version's canonical command output and could not be "
        "proven unedited; remove the named files and run any spec-kitty command to reinstall them.",
        len(unmigrated),
        ", ".join(unmigrated),
    )


def _apply_command_assessment(assessment: OwnerAssessment, *, rebuild: Callable[[], OwnerAssessment]) -> None:
    """Mirror ``bootstrap.ensure_runtime()``'s re-assess-under-lock (#4017 WP03)
    via the shared ``asset_preparation.apply_with_reassess`` helper (#4174
    landing-pass) -- see its docstring for the full mechanism.
    """
    from specify_cli.runtime.asset_preparation import apply_with_reassess, startup_asset_error

    if not assessment.complete:
        raise startup_asset_error(assessment.owner_key, assessment.diagnostics)
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
        raise startup_asset_error(result.owner_key, result.diagnostics)


def _sync_agent_commands(agent_key: str, templates_dir: Path, script_type: str) -> None:
    """Retain the existing scoped owner entry point using prepared output."""
    _apply_command_assessment(
        assess_global_agent_commands(agent_keys=[agent_key], templates_dir=templates_dir, script_type=script_type),
        rebuild=lambda: assess_global_agent_commands(agent_keys=[agent_key], templates_dir=templates_dir, script_type=script_type),
    )


def ensure_global_agent_commands(*, agent_keys: list[str] | None = None) -> None:
    """Ensure actual global command health, retaining unchanged bytes and mtimes.

    Without *agent_keys* (the CLI startup call) the scope is the slash-command
    agents configured in the project at the working directory, and none
    outside a project (#6470, #3048 context): an unconfigured agent's home
    folder is never written. Pass *agent_keys* to name the agents explicitly.
    """
    keys = _project_slash_agent_scope() if agent_keys is None else agent_keys
    _apply_command_assessment(
        assess_global_agent_commands(agent_keys=keys, _short_circuit=True),
        rebuild=lambda: assess_global_agent_commands(agent_keys=keys),
    )
