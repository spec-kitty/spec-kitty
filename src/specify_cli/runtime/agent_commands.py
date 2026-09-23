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
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, replace
from importlib.util import find_spec
from pathlib import Path

from kernel.paths import MISSION_ASSETS_SIBLING_PATTERN, is_windows
from kernel.sibling_paths import SiblingPathNotFound, resolve_installed_sibling
from specify_cli.core.config import DEFAULT_MISSION_KEY
from specify_cli.runtime.bootstrap import _get_cli_version
from specify_cli.runtime.home import get_kittify_home
from specify_cli.runtime.asset_preparation import _GlobalAssetPreparation
from specify_cli.tool_surface.operations import ApplyConsent, Disposition, FileState, OperationRoot, OwnerAssessment, OwnershipProof

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
    """The three SOURCE-side fields ``data-model.md``'s stamp contract names.

    Deliberately excludes any DESTINATION-side fact (see PLAN-ARCH-001 in
    ``data-model.md``) -- destination health is verified separately via
    ``_all_global_agent_commands_healthy()``, the stamp's contract's fourth,
    independent condition.
    """

    cli_version: str
    template_source_signature: str
    agent_keys: tuple[str, ...]


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
    """
    from specify_cli.shims import generator as shim_generator
    from specify_cli.template import asset_generator

    module_files: list[str] = [f for f in (__file__, asset_generator.__file__, shim_generator.__file__) if f]
    hasher = hashlib.sha256()  # noqa: TID251 -- raw code-signature integrity hash, not charter hashing
    for module_file in sorted(module_files):
        hasher.update(module_file.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(Path(module_file).read_bytes())
        hasher.update(b"\0")
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
    Render/write errors are handled separately and must NOT be caught here.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    cli_version = payload.get("cli_version")
    signature = payload.get("template_source_signature")
    agent_keys = payload.get("agent_keys")
    if not isinstance(cli_version, str) or not isinstance(signature, str):
        return None
    if not isinstance(agent_keys, list) or not all(isinstance(key, str) for key in agent_keys):
        return None
    return _FreshnessStamp(cli_version, signature, tuple(agent_keys))


def _freshness_stamp_matches(stamp: _FreshnessStamp | None, *, cli_version: str, template_source_signature: str, agent_keys: tuple[str, ...]) -> bool:
    """Return True when *stamp*'s three source-side fields all match current state.

    All three conditions are required (data-model.md's four-condition
    contract, conditions 1-3); the fourth, destination-health condition is
    checked separately by the caller so this function stays pure/testable.
    """
    return (
        stamp is not None and stamp.cli_version == cli_version and stamp.template_source_signature == template_source_signature and stamp.agent_keys == agent_keys
    )


def _freshness_short_circuit(
    agent_keys: list[str] | None,
    batch: _GlobalAssetPreparation | None,
    home: Path,
    root: OperationRoot,
    templates_dir: Path | None,
    consent: ApplyConsent,
    current_agent_keys: tuple[str, ...],
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

    Only applies to the full-fleet, non-batched call shape (``agent_keys is
    None`` and ``batch is None``) -- every other shape returns ``None``
    unconditionally, deferring to the render path exactly as before this WP.
    """
    if agent_keys is not None or batch is not None:
        return None
    resolved_templates_dir = _get_command_templates_dir() if templates_dir is None else templates_dir
    cli_version = _get_cli_version()
    try:
        signature = _template_source_signature(resolved_templates_dir)
    except OSError:
        return None
    stamp = _read_freshness_stamp(home / "cache" / _FRESHNESS_STAMP_FILENAME)
    if not _freshness_stamp_matches(stamp, cli_version=cli_version, template_source_signature=signature, agent_keys=current_agent_keys):
        return None
    try:
        healthy = _all_global_agent_commands_healthy(resolved_templates_dir, cli_version, list(current_agent_keys))
    except OSError:
        return None
    if not healthy:
        return None
    return OwnerAssessment("slash_commands", root, consent=consent)


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
    and edited generated files are preserved, independent of marker freshness;
    a managed marker naming a *different* CLI version proves canonical
    provenance and migrates in place even when the content changed between
    releases (#4609). Canonical command files that still cannot be migrated
    are never silent: one warning names them.

    **Freshness pre-check (Lever C primary, operator Ruling 6).** For the
    full-fleet, non-batched call shape (``agent_keys=None``, ``_batch=None``
    -- exactly what ``ensure_global_agent_commands()`` calls on every
    non-fast-pathed CLI startup), this reads a small on-disk stamp and,
    only when ALL of (cli_version, template_source_signature, agent_keys)
    match AND every configured agent's rendered destination is independently
    verified healthy, returns immediately with an empty assessment -- no
    render, no ``AssetPreparation`` construction at all. Both checks run
    strictly before any ``AssetPreparation`` object exists (data-model.md's
    SK-243 immunity property: this path never calls ``observe()`` on an
    ``AssetPreparation``, so it can never enter ``check_assets()``'s
    drift-recheck machinery). Any uncertainty -- an unreadable/malformed
    stamp, a source tree that cannot be walked, an unhealthy destination --
    falls through to the unconditional render-then-diff path below, never to
    a skip; a missed refresh must never be silent (Ruling 6's binding
    condition).
    """
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
    from specify_cli.runtime.asset_preparation import AssetPreparation, digest, global_asset_root, incomplete, retry_torn_read

    home = get_kittify_home()
    all_roots = tuple(get_global_command_dir(key) for key in AGENT_COMMAND_CONFIG)
    root = global_asset_root("slash_commands", (home, *all_roots))

    short_circuit = _freshness_short_circuit(agent_keys, _batch, home, root, templates_dir, consent, tuple(sorted(AGENT_COMMAND_CONFIG)))
    if short_circuit is not None:
        return short_circuit

    def _build() -> tuple[AssetPreparation, OwnerAssessment]:
        prepared = AssetPreparation("slash_commands", root, home / "cache", _LOCK_FILENAME, consent)
        keys = tuple(sorted(set(AGENT_COMMAND_CONFIG if agent_keys is None else agent_keys)))
        selected_roots: dict[str, Path] = {}
        canonical_names: set[str] = set()
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
        if agent_keys is None:
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
            freshness_payload = json.dumps(
                {
                    "cli_version": _get_cli_version(),
                    "template_source_signature": _template_source_signature(templates),
                    "agent_keys": list(keys),
                },
                sort_keys=True,
            ).encode("utf-8")
            prepared.overwrite_internal(
                freshness_path,
                FileState("file", sha256=digest(freshness_payload), mode=0o644),
                freshness_payload,
                OwnershipProof("managed_path", f"{prepared.owner}:freshness-stamp"),
            )
        stamp = home / "cache" / _VERSION_FILENAME if agent_keys is None else None
        assessment = prepared.finish(stamp, _get_cli_version())
        assessment = replace(
            assessment,
            effects=tuple(replace(effect, logical_owners=_command_effect_owners(effect.destination, selected_roots)) for effect in assessment.effects),
        )
        _warn_unmigrated_commands(assessment.dispositions, canonical_names)
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
