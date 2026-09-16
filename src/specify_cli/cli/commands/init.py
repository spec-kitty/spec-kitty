"""Init command implementation for Spec Kitty CLI."""

from __future__ import annotations

import logging
import json
import shutil
import stat
import subprocess
import sys
from kernel.clock import now_utc
from pathlib import Path
from collections.abc import Callable

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from ruamel.yaml import YAML

from specify_cli.cli import StepTracker, multi_select_with_arrows
from specify_cli.core import (
    AI_CHOICES,
)
from specify_cli.core.env import is_interactive
from kernel.clock import now_utc_iso
from specify_cli.core.constants import OCCURRENCE_MAP_FILENAME
from specify_cli.core.utils import safe_is_dir
from specify_cli.core.vcs import (
    is_git_available,
    VCSBackend,
)
from specify_cli.gitignore_manager import GitignoreManager
from specify_cli.core.agent_config import (
    AgentConfig,
    AgentConfigError,
    load_agent_config,
    save_agent_config,
)
from .init_help import INIT_COMMAND_DOC
from specify_cli.template import (
    copy_specify_base_from_local,
    copy_specify_base_from_package,
    get_local_repo_root,
)
from specify_cli.provisioning.default_charter import (
    DefaultCharterPackMissingError,
    provision_default_mission_type_activations,
)
from specify_cli.runtime.home import get_kittify_home, get_package_asset_root
from specify_cli.skills.installer import install_skills_for_agent
from specify_cli.skills.manifest import ManagedSkillManifest, save_manifest
from specify_cli.skills.registry import CanonicalSkill, SkillRegistry

# Module-level variables to hold injected dependencies
_console: Console | None = None
_show_banner: Callable[[], None] | None = None
_ensure_executable_scripts: Callable[[Path, StepTracker | None], None] | None = None


# =============================================================================
# Global runtime detection for streamlined init
# =============================================================================

_logger = logging.getLogger(__name__)
_EVENT_LOG_GITATTRIBUTES_ENTRY = "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log"
# coord-write-placement-closure-01KYCF83 WP06: decisions.events.jsonl reuses
# the SAME event-log union driver (structurally identical append-only JSONL
# envelope) -- see specify_cli/lanes/merge.py's _MERGE_DRIVERS comment.
_DECISION_LOG_GITATTRIBUTES_ENTRY = "kitty-specs/**/decisions.events.jsonl merge=spec-kitty-event-log"
# C-006 (#2709): the meta.json field-merge and traces union drivers register on
# the same surfaces as the event-log driver.
_META_GITATTRIBUTES_ENTRY = "kitty-specs/**/meta.json merge=spec-kitty-meta"
_TRACES_GITATTRIBUTES_ENTRY = "kitty-specs/**/traces/*.md merge=spec-kitty-traces"
# C-006 (#2804): the coord gate artifacts are filled on the target at accept time
# and scaffolded on the mission branch, so the squash integration needs a driver
# to keep the filled side instead of letting `-X theirs` win.
_ACCEPTANCE_MATRIX_GITATTRIBUTES_ENTRY = "kitty-specs/**/acceptance-matrix.json merge=spec-kitty-acceptance-matrix"
# WP11 (FR-008): repointed from issue-matrix.md -- WP05 migrated the canonical
# artifact to structured JSON (C-008); the .md pattern is inert on new repos.
_ISSUE_MATRIX_GITATTRIBUTES_ENTRY = "kitty-specs/**/issue-matrix.json merge=spec-kitty-issue-matrix"
# review-cycle-verdict-seam-rebuild-01KZ2W7W WP18 (T017/T078): review-cycle
# verdict artifacts become genuinely two-sided during the create-window
# migration (ADR 2026-08-03-1) -- a refuse-fail-closed driver (never a union)
# keeps a genuine two-verdict collision from being clobbered by `-X theirs`.
# Filename-anchored (never `tasks/*.md`), so `tasks/<wp>/baseline-tests.json`
# and `tasks/WP*.md` are unaffected.
_REVIEW_CYCLE_GITATTRIBUTES_ENTRY = "kitty-specs/**/tasks/*/review-cycle-*.md merge=spec-kitty-review-cycle"
_COMMAND_SKILL_AGENTS = {"codex", "vibe", "pi", "letta"}
_PENDING_COMMAND_SKILLS = ".kittify/init-command-skills.pending.json"


def _pending_command_skills(project: Path) -> tuple[str, ...] | None:
    """Read init's exact pending-delivery record, never an authored config flag."""
    path = project / _PENDING_COMMAND_SKILLS
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if path.parent.is_symlink() or not stat.S_ISREG(mode):
        raise ValueError(f"Unsafe pending command-delivery record: {path}")
    data = json.loads(path.read_bytes())
    if not isinstance(data, dict) or set(data) != {"schema_version", "agents"} or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError(f"Unrecognized pending command-delivery record: {path}")
    agents = data["agents"]
    if not isinstance(agents, list) or not agents or any(not isinstance(a, str) or a not in _COMMAND_SKILL_AGENTS for a in agents):
        raise ValueError(f"Invalid pending command-delivery agents: {path}")
    if agents != sorted(set(agents)):
        raise ValueError(f"Noncanonical pending command-delivery agents: {path}")
    return tuple(agents)


def _start_command_delivery(project: Path, agents: list[str]) -> None:
    """Reserve recovery only for new init, after runtime-root protection."""
    if not agents:
        return
    expected = tuple(sorted(set(agents)))
    pending = _pending_command_skills(project)
    if pending is not None:
        if pending != expected:
            raise ValueError("Pending command delivery has a different agent selection")
        return
    path = project / _PENDING_COMMAND_SKILLS
    with path.open("x", encoding="utf-8") as stream:
        json.dump({"schema_version": 1, "agents": list(expected)}, stream, sort_keys=True)
        stream.write("\n")


def _finish_command_delivery(project: Path, agents: list[str] | tuple[str, ...]) -> None:
    if not agents:
        return
    if _pending_command_skills(project) != tuple(sorted(set(agents))):
        raise ValueError("Pending command-delivery record changed; preserving it")
    (project / _PENDING_COMMAND_SKILLS).unlink()


def _install_command_skill_agents(project: Path, agents: list[str]) -> bool:
    """Retain init's per-agent warnings and the installer's ownership checks."""
    from specify_cli.skills import command_installer
    from specify_cli.skills.vibe_config import ensure_project_skill_path

    assert _console is not None
    complete = True
    for agent_key in agents:
        try:
            report = command_installer.install(project, agent_key)
            if agent_key == "vibe":
                ensure_project_skill_path(project)
            installed = len(report.added) + len(report.reused_shared)
            _console.print(f"[dim]{AI_CHOICES[agent_key]}: {installed} command skills installed[/dim]")
        except Exception as exc:
            complete = False
            _console.print(f"[yellow]Warning:[/yellow] Could not install skills for {AI_CHOICES[agent_key]}: {exc}")
    return complete


def _repair_requested_command_skills(project: Path, agents: list[str]) -> bool:
    """Restore clone-local command skills for explicitly requested agents."""
    data = YAML(typ="safe").load((project / ".kittify/config.yaml").read_text(encoding="utf-8"))
    configured_agents = data.get("agents", {}).get("available") if isinstance(data, dict) else None
    if not isinstance(configured_agents, list):
        return False
    command_agents = [agent for agent in agents if agent in _COMMAND_SKILL_AGENTS and agent in configured_agents]
    if not command_agents:
        return False

    from specify_cli.skills.command_installer import CANONICAL_COMMANDS
    from specify_cli.skills.vibe_config import ensure_project_skill_path, skill_path_configured

    skills_root = project / ".agents" / "skills"
    missing_skills = any(not (skills_root / f"spec-kitty.{command}" / "SKILL.md").is_file() for command in CANONICAL_COMMANDS)
    # #4433: the vibe pointer is part of vibe's command surface, so an
    # explicitly requested vibe gets it restored too — surgically, without
    # re-running the installer over present (possibly user-edited) skills.
    vibe_pointer_missing = "vibe" in command_agents and not skill_path_configured(project)
    if not (missing_skills or vibe_pointer_missing):
        return False

    protected = GitignoreManager(project).protect_all_agents()
    if not protected.success:
        raise ValueError("Cannot repair command delivery: " + "; ".join(protected.errors))
    if missing_skills:
        _console.print("[yellow]Restoring missing command skills for this initialized clone.[/yellow]")
        if not _install_command_skill_agents(project, command_agents):
            raise ValueError("Command-skill repair remains incomplete; resolve the reported collision or error")
    if vibe_pointer_missing and not skill_path_configured(project):
        # Reached when the skills were present and only the pointer was lost;
        # after an installer run the pointer is already restored.
        _console.print("[yellow]Restoring the missing vibe skill-path pointer for this initialized clone.[/yellow]")
        ensure_project_skill_path(project)
    return True


def _resume_command_delivery(project: Path) -> bool:
    """Finish only interrupted command delivery; never rewrite saved config."""
    pending = _pending_command_skills(project)
    if pending is None:
        return False
    assert _console is not None
    config = project / ".kittify/config.yaml"
    data = YAML(typ="safe").load(config.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("agents"), dict) or "available" not in data["agents"]:
        raise ValueError("Initialization stopped before agent selection was saved; inspect .kittify/config.yaml before retrying")
    configured = load_agent_config(project)
    agents = [agent for agent in pending if agent in configured.available]
    protected = GitignoreManager(project).protect_all_agents()
    if not protected.success:
        raise ValueError("Cannot resume command delivery: " + "; ".join(protected.errors))
    _console.print("[yellow]Resuming interrupted command-skill delivery from saved configuration.[/yellow]")
    if not _install_command_skill_agents(project, agents):
        raise ValueError("Command delivery remains incomplete; resolve the reported collision or error before retrying init")
    _finish_command_delivery(project, pending)
    return True


def _validated_agent_selection(requested: str | None, configured: list[str]) -> list[str]:
    """Resolve the --ai selection against authored configuration, fail closed."""
    selected = list(dict.fromkeys(part.strip().lower() for part in requested.replace(";", ",").split(",") if part.strip())) if requested is not None else configured
    if requested is not None and (not selected or any(agent not in AI_CHOICES for agent in selected)):
        raise ValueError("Invalid --ai selection; choose from: " + ", ".join(AI_CHOICES))
    unconfigured = [agent for agent in selected if agent not in configured]
    if unconfigured:
        raise ValueError("Requested agents are not configured. Run: spec-kitty agent config add " + " ".join(unconfigured))
    return selected


def _check_initialized_command_skills(project: Path, requested: str | None) -> list[str]:
    """Diagnose clone-local delivery gaps without rewriting initialized projects."""
    from specify_cli.skills.command_installer import CANONICAL_COMMANDS
    from specify_cli.skills.paths import skill_path_observations
    from specify_cli.skills.vibe_config import skill_path_configured

    selected = _validated_agent_selection(requested, load_agent_config(project).available)
    if not _COMMAND_SKILL_AGENTS.intersection(selected):
        return selected
    missing = []
    for command in CANONICAL_COMMANDS:
        path = project / f".agents/skills/spec-kitty.{command}/SKILL.md"
        observations = skill_path_observations(project, path)
        if observations[-1].state.kind != "file" or path.stat().st_size == 0:
            missing.append(command)
    # #4433: vibe resolves the shared skills through the gitignored
    # ``.vibe/config.toml`` ``skill_paths`` pointer — an independently missable
    # part of the command surface (doctor already diagnoses it), so init's
    # "Already Initialized" verdict must agree with doctor's on what "ready"
    # means instead of exiting 0 over a broken vibe surface.
    vibe_pointer_missing = "vibe" in selected and not skill_path_configured(project)
    if missing or vibe_pointer_missing:
        gaps = []
        if missing:
            gaps.append("Configured agent command skills are missing or empty: " + ", ".join(missing))
        if vibe_pointer_missing:
            gaps.append("the vibe skill-path pointer (.vibe/config.toml skill_paths) is missing")
        raise ValueError("; ".join(gaps) + ". Run: spec-kitty agent config sync --create-missing --keep-orphaned")
    return selected


def _native_skill_gap(project: Path, root: str, skills: list[CanonicalSkill]) -> tuple[list[str], list[str]]:
    """Classify the expected native surface into absent and unusable names.

    A usable ``SKILL.md`` is a non-empty regular file. Anything else that is
    present (empty file, directory, symlink) is user content: it is reported,
    never overwritten (#4425 acceptance 3).
    """
    from specify_cli.skills.paths import skill_path_observations

    absent: list[str] = []
    unusable: list[str] = []
    for skill in skills:
        path = project / root / skill.name / "SKILL.md"
        observations = skill_path_observations(project, path)
        kind = observations[-1].state.kind
        if kind == "absent":
            absent.append(skill.name)
        elif kind != "file" or path.stat().st_size == 0:
            unusable.append(f"{root}/{skill.name}/SKILL.md")
    return absent, unusable


def _restore_native_project_skills(project: Path, agents: list[str]) -> None:
    """Finish clone-local delivery for NATIVE-root agents through the canonical installer.

    A clone carries tracked ``.kittify/`` but not the gitignored per-agent skill
    roots (``.claude/skills/`` etc.) that fresh init installs through
    ``install_skills_for_agent``; no ``agent config`` path re-delivers them
    (#4425 acceptance 2). The restore is additive only: absent skills are
    reinstalled from the packaged registry, while existing files — user-edited,
    third-party, or drifted — are preserved untouched (acceptance 3). The
    complete expected surface is verified both when nothing needs installation
    and after restoration, so an unusable existing file (empty, a directory, or
    a symlink) fails explicitly with its path instead of reporting verified.
    """
    from specify_cli import __version__ as _sk_version
    from specify_cli.core.config import AGENT_SKILL_CONFIG, SKILL_CLASS_NATIVE
    from specify_cli.skills.manifest import load_manifest
    from specify_cli.skills.paths import get_primary_project_skill_root

    native = [agent for agent in agents if (AGENT_SKILL_CONFIG.get(agent) or {}).get("class") == SKILL_CLASS_NATIVE]
    if not native:
        return
    skills = SkillRegistry.from_package().discover_skills()
    if not skills:
        raise ValueError("No packaged skills found to restore for: " + ", ".join(native))
    pending: dict[str, tuple[str, list[str]]] = {}
    unusable: list[str] = []
    for agent in native:
        root = get_primary_project_skill_root(agent)
        assert root is not None
        absent, broken = _native_skill_gap(project, root, skills)
        unusable.extend(broken)
        if absent:
            pending[agent] = (root, absent)
    if unusable:
        raise ValueError(
            "Existing agent skill files are unusable and were left untouched: "
            + ", ".join(unusable)
            + ". Rename or remove the affected files, then re-run: spec-kitty init --ai "
            + ",".join(native)
        )
    if not pending:
        return
    assert _console is not None
    protected = GitignoreManager(project).protect_all_agents()
    if not protected.success:
        raise ValueError("Cannot restore missing agent skills: " + "; ".join(protected.errors))
    for agent, (root, absent) in pending.items():
        entries = install_skills_for_agent(project, agent, skills)
        manifest = load_manifest(project)
        if manifest is None:
            _now_iso = now_utc_iso()
            manifest = ManagedSkillManifest(created_at=_now_iso, updated_at=_now_iso, spec_kitty_version=_sk_version)
        for entry in entries:
            manifest.add_entry(entry)
        save_manifest(manifest, project)
        # Post-install verification covers the complete expected surface, not
        # only the previously-absent names, so a write that landed unusable
        # (or one that never landed) is caught here.
        undelivered, still_broken = _native_skill_gap(project, root, skills)
        if still_broken:
            raise ValueError(f"Skill restoration for {agent} delivered unusable files: " + ", ".join(still_broken))
        if undelivered:
            raise ValueError(f"Skill restoration for {agent} did not deliver: " + ", ".join(undelivered))
        _console.print(f"[green]{AI_CHOICES[agent]}:[/green] restored {len(absent)} missing skills into {root} (existing files preserved)")


_GITHUB_DIFF_GITATTRIBUTES_ENTRIES = (
    "kitty-specs/**/status.json linguist-generated=true",
    "kitty-specs/**/status.events.jsonl linguist-generated=true",
    "kitty-specs/**/lanes.json linguist-generated=true",
    "kitty-specs/**/mission-events.jsonl linguist-generated=true",
    "kitty-specs/**/snapshot-latest.json linguist-generated=true",
    "kitty-specs/**/acceptance-matrix.json linguist-generated=true",
    f"kitty-specs/**/{OCCURRENCE_MAP_FILENAME} linguist-generated=true",
    "kitty-specs/**/tasks/** linguist-generated=true",
    "kitty-specs/**/research/evidence-log.csv linguist-generated=true",
    "kitty-specs/**/research/source-register.csv linguist-generated=true",
    "kitty-specs/**/test-transcripts/** linguist-generated=true",
    "kitty-specs/**/baseline/** linguist-generated=true",
    "kitty-specs/**/canary-evidence/** linguist-generated=true",
    ".kittify/workspaces/** linguist-generated=true",
    ".kittify/workspaces/** -diff",
    ".kittify/migrations/** linguist-generated=true",
    ".kittify/migrations/** -diff",
)


def _has_global_runtime() -> bool:
    """Check whether the global runtime has populated missions.

    Returns True when the global kittify home ``missions/`` directory exists
    and contains at least one subdirectory (indicating ``ensure_runtime()``
    has run).
    """
    try:
        global_home = get_kittify_home()
        missions_dir = global_home / "missions"
        if not safe_is_dir(missions_dir):
            return False
        # Check for at least one mission subdirectory. `safe_is_dir` can raise
        # `OSError` for a genuinely unreadable entry (rather than silently
        # answering `False` the way `Path.is_dir()` does on 3.14 only — see
        # its docstring); the enclosing `except (RuntimeError, OSError)` below
        # already treats that identically to "no global runtime", so this
        # function's own answer does not change, only the reasoning leading to
        # it: it is no longer a coincidence of the resolved interpreter.
        return any(safe_is_dir(p) for p in missions_dir.iterdir())
    except (RuntimeError, OSError):
        return False


def _prepare_project_minimal(project_path: Path) -> None:
    """Create the minimal project-specific .kittify/ skeleton.

    When the global runtime exists, init only needs to create the
    project-local directory structure.  Shared assets (missions,
    templates, scripts, AGENTS.md) are resolved from the global kittify
    home at runtime via the 4-tier resolver.

    Creates:
        - .kittify/                (project root)
        - .kittify/memory/         (project-local memory/context files)
    """
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "memory").mkdir(exist_ok=True)
    _logger.debug("Minimal project skeleton created at %s", kittify)


def _ensure_event_log_merge_attributes(project_path: Path) -> bool:
    """Ensure new projects get Spec Kitty git attributes."""
    attributes_path = project_path / ".gitattributes"
    lines: list[str] = []
    if attributes_path.exists():
        lines = attributes_path.read_text(encoding="utf-8").splitlines()
    required_entries = (
        _EVENT_LOG_GITATTRIBUTES_ENTRY,
        _DECISION_LOG_GITATTRIBUTES_ENTRY,
        _META_GITATTRIBUTES_ENTRY,
        _TRACES_GITATTRIBUTES_ENTRY,
        _ACCEPTANCE_MATRIX_GITATTRIBUTES_ENTRY,
        _ISSUE_MATRIX_GITATTRIBUTES_ENTRY,
        _REVIEW_CYCLE_GITATTRIBUTES_ENTRY,
        *_GITHUB_DIFF_GITATTRIBUTES_ENTRIES,
    )
    missing = [entry for entry in required_entries if entry not in lines]
    if not missing:
        return False

    lines.extend(missing)
    attributes_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return True


def _stamp_schema_metadata(kittify_dir: Path) -> bool:
    """Stamp ``schema_version`` and ``schema_capabilities`` into ``metadata.yaml``.

    Behavior (issue #840):

    - If ``metadata.yaml`` does not exist, create a minimal file containing
      both fields under the ``spec_kitty`` mapping.
    - If the file exists and lacks ``spec_kitty.schema_version``, insert it.
    - If the file exists and lacks ``spec_kitty.schema_capabilities``, insert it.
    - **Never** overwrite an existing ``schema_version`` or any existing key
      inside an existing ``schema_capabilities`` mapping. Operator-authored
      keys (top-level or nested) are preserved byte-identical via
      ``ruamel.yaml`` round-trip mode.
    - If both fields are already present, the file is not rewritten and this
      function returns ``False`` (idempotency guard).

    Args:
        kittify_dir: Path to the project's ``.kittify`` directory.

    Returns:
        ``True`` if the file was created or modified, ``False`` if it was
        left untouched.
    """
    from specify_cli.migration.schema_version import (
        CURRENT_SCHEMA_CAPABILITIES,
        CURRENT_SCHEMA_VERSION,
    )

    metadata_path = kittify_dir / "metadata.yaml"

    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    yaml_rt.width = 4096

    # Case 1: file does not exist — create a minimal stamped document.
    if not metadata_path.exists():
        kittify_dir.mkdir(parents=True, exist_ok=True)
        from ruamel.yaml.comments import CommentedMap

        data: CommentedMap = CommentedMap()
        spec_kitty_map: CommentedMap = CommentedMap()
        spec_kitty_map["schema_version"] = CURRENT_SCHEMA_VERSION
        caps_map: CommentedMap = CommentedMap()
        for cap, enabled in CURRENT_SCHEMA_CAPABILITIES.items():
            caps_map[cap] = enabled
        spec_kitty_map["schema_capabilities"] = caps_map
        data["spec_kitty"] = spec_kitty_map
        with metadata_path.open("w", encoding="utf-8") as fh:
            yaml_rt.dump(data, fh)
        return True

    # Case 2: file exists — round-trip parse, additive merge.
    with metadata_path.open("r", encoding="utf-8") as fh:
        data = yaml_rt.load(fh)

    # If the file is empty or holds something that isn't a mapping, treat it
    # as empty for the purpose of stamping (we still preserve nothing-to-keep).
    if data is None:
        from ruamel.yaml.comments import CommentedMap

        data = CommentedMap()

    if not isinstance(data, dict):
        # Operator authored a non-mapping document. Refuse to mutate it; the
        # additive stamp only makes sense on mappings.
        return False

    spec_kitty_node = data.get("spec_kitty")
    if not isinstance(spec_kitty_node, dict):
        from ruamel.yaml.comments import CommentedMap

        spec_kitty_node = CommentedMap()
        # Insert spec_kitty at the top to keep the schema header visible.
        data.insert(0, "spec_kitty", spec_kitty_node)

    changed = False

    # schema_version: insert only if missing; never overwrite.
    if "schema_version" not in spec_kitty_node:
        # Insert at position 0 of the spec_kitty map for visibility.
        spec_kitty_node.insert(0, "schema_version", CURRENT_SCHEMA_VERSION)
        changed = True

    # schema_capabilities: insert the canonical map only if entirely missing.
    # If a map already exists, do NOT merge into it — the operator owns it.
    if "schema_capabilities" not in spec_kitty_node:
        from ruamel.yaml.comments import CommentedMap

        caps_map = CommentedMap()
        for cap, enabled in CURRENT_SCHEMA_CAPABILITIES.items():
            caps_map[cap] = enabled
        spec_kitty_node["schema_capabilities"] = caps_map
        changed = True

    if not changed:
        # Idempotency: nothing missing — leave the file untouched.
        return False

    with metadata_path.open("w", encoding="utf-8") as fh:
        yaml_rt.dump(data, fh)
    return True


def _get_package_templates_root() -> Path | None:
    """Return the package-bundled templates directory (read-only).

    This is the ``src/charter/offering/templates/`` directory which contains
    ``command-templates/``, ``AGENTS.md``, etc.

    Returns None if the templates directory cannot be located.

    Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
    (FR-005/R-14, required-together with R-09) relocated the missions data to
    ``packs/built-in/missions``. Two distinct root shapes now reach this
    function:

    * ``SPEC_KITTY_TEMPLATE_ROOT``-driven test/dev overrides still hand
      ``get_package_asset_root()`` a synthetic root where ``missions/`` and
      ``templates/`` are siblings (mirroring the pre-relocation
      ``src/charter/offering/{missions,templates}`` shape) -- ``.parent / "templates"``
      is still correct there, and is tried first.
    * The real, non-override production resolution now routes through the
      kernel sibling-path primitive to ``packs/built-in/missions``, whose
      *actual* parent (``packs/built-in``) does **not** carry ``templates/``
      (that stays under ``src/charter/offering/templates``, untouched by this
      mission). Falls back to :func:`charter.activation.catalog.resolve_doctrine_root`
      for this shape.
    """
    try:
        pkg_root = get_package_asset_root()
    except FileNotFoundError:
        return None

    sibling_templates_dir = pkg_root.parent / "templates"
    if sibling_templates_dir.is_dir():
        return Path(sibling_templates_dir)

    from charter.activation.catalog import resolve_doctrine_root  # noqa: PLC0415

    try:
        doctrine_root = resolve_doctrine_root()
        templates_dir = doctrine_root / "templates"
        if templates_dir.is_dir():
            return Path(templates_dir)
    except FileNotFoundError:
        pass
    return None


def _resolve_mission_command_templates_dir(
    project_path: Path,
    mission: str,
    *,
    scratch_parent: Path | None = None,
) -> Path:
    """Materialize the resolved command templates for one mission into scratch space.

    Each template file is resolved independently through the runtime's 6-tier
    precedence chain so mixed-tier command sets still produce the correct
    effective directory for init-time consumers.
    """
    from specify_cli.runtime.resolver import resolve_command

    candidate_dirs: list[Path] = [
        project_path / ".kittify" / "overrides" / "command-templates",
        project_path / ".kittify" / "command-templates",
    ]

    try:
        global_home = get_kittify_home()
    except RuntimeError:
        global_home = None
    if global_home is not None:
        candidate_dirs.extend(
            [
                global_home / "missions" / mission / "command-templates",
                global_home / "command-templates",
            ]
        )

    try:
        package_root = get_package_asset_root()
    except FileNotFoundError:
        package_root = None
    if package_root is not None:
        candidate_dirs.append(package_root / mission / "command-templates")

    template_names: set[str] = set()
    for candidate_dir in candidate_dirs:
        if not candidate_dir.is_dir():
            continue
        template_names.update(path.name for path in candidate_dir.glob("*.md") if path.is_file())

    scratch_base = scratch_parent or (project_path / ".kittify")
    resolved_dir = scratch_base / f".resolved-command-templates-{mission}"
    if resolved_dir.exists():
        shutil.rmtree(resolved_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)

    for template_name in sorted(template_names):
        try:
            resolved = resolve_command(template_name, project_path, mission)
        except FileNotFoundError:
            continue
        shutil.copy2(resolved.path, resolved_dir / template_name)

    return resolved_dir


# =============================================================================
# VCS Detection and Configuration
# =============================================================================


class VCSNotFoundError(Exception):
    """Raised when no VCS tools are available."""

    pass


def _is_non_interactive_mode(flag: bool) -> bool:
    # The explicit ``--non-interactive`` flag forces non-interactive; otherwise
    # defer to the single non-interactive authority. Routing through
    # ``is_interactive`` adds the ``SPEC_KITTY_FORCE_INTERACTIVE`` escape hatch
    # the old local matrix omitted (#2912).
    return flag or not is_interactive()


def _primary_next_step_agent(selected_agents: list[str]) -> str:
    """Choose the selected harness whose command syntax should drive init UX."""
    for agent in selected_agents:
        if agent in _COMMAND_SKILL_AGENTS:
            return agent
    return selected_agents[0]


def _agent_command_token(agent_key: str, command: str) -> str:
    """Render the command token visible inside the selected harness."""
    if agent_key == "codex":
        return f"$spec-kitty.{command}"
    if agent_key == "pi":
        return f"/skill:spec-kitty.{command}"
    if agent_key == "letta":
        return f"/spec-kitty.{command}"
    return f"/spec-kitty.{command}"


def _workflow_lines_for_agent(agent_key: str) -> tuple[str, list[str]]:
    """Return next-step heading and installed workflow commands for a harness."""
    if agent_key in _COMMAND_SKILL_AGENTS:
        heading = "Build with command skills:"
        commands = [
            ("specify", "write the spec"),
            ("plan", "write the plan"),
            ("tasks", "create work packages"),
        ]
    else:
        heading = "Build with slash commands:"
        commands = [
            ("specify", "write the spec"),
            ("plan", "write the plan"),
            ("tasks", "create work packages"),
        ]

    return heading, [f"[cyan]{_agent_command_token(agent_key, command)}[/] ({description})" for command, description in commands]


def _detect_default_vcs() -> VCSBackend:
    """Detect the default VCS based on tool availability.

    Returns VCSBackend.GIT if git is available.
    Raises VCSNotFoundError if git is not available.

    Note: Only git is supported.
    """
    if is_git_available():
        return VCSBackend.GIT
    else:
        raise VCSNotFoundError("git is not available. Please install git.")


def _is_inside_git_work_tree(target: Path) -> bool:
    """Return True when ``target`` is inside a git work tree.

    The caller MUST already have verified ``is_git_available()`` is True;
    this helper assumes the ``git`` binary is on ``PATH`` and only answers
    the work-tree question. If the binary is missing the subprocess call
    will raise ``FileNotFoundError``, which we treat as "not in a work
    tree" so the caller's existing ``git not detected`` branch keeps
    ownership of the binary-missing message (no double-print).

    The target directory must already exist before this is called; if it
    doesn't, ``cwd=`` will raise and we again return False.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(target),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _display_vcs_info(_detected_vcs: VCSBackend, console: Console) -> None:
    """Display informational message about VCS selection.

    Args:
        detected_vcs: The detected/selected VCS backend (always GIT)
        console: Rich console for output
    """
    console.print("[green]✓ git detected[/green] - will be used for version control")


def _save_vcs_config(config_path: Path, _detected_vcs: VCSBackend) -> None:
    """Save VCS preference to config.yaml.

    Args:
        config_path: Path to .kittify directory
        detected_vcs: The detected/selected VCS backend (always GIT)
    """
    config_file = config_path / "config.yaml"

    yaml = YAML()
    yaml.preserve_quotes = True

    # Load existing config or create new
    if config_file.exists():
        with open(config_file) as f:
            config = yaml.load(f) or {}
    else:
        config = {}
        config_path.mkdir(parents=True, exist_ok=True)

    # Add/update vcs section (git only)
    config["vcs"] = {
        "type": "git",
    }

    # Write back
    with open(config_file, "w") as f:
        yaml.dump(config, f)


def init(  # noqa: C901
    project_name: str | None = typer.Argument(
        None,
        help="Name for your new project directory (omit to initialize current directory)",
    ),
    ai_assistant: str | None = typer.Option(None, "--ai", help="Comma-separated AI assistants (claude,codex,gemini,...)", rich_help_panel="Selection"),
    non_interactive: bool = typer.Option(False, "--non-interactive", "--yes", help="Run without interactive prompts (suitable for CI/CD)"),
) -> None:
    """Initialize a new Spec Kitty project."""
    # Use the injected dependencies
    assert _console is not None
    assert _show_banner is not None
    assert _ensure_executable_scripts is not None

    _show_banner()
    non_interactive = _is_non_interactive_mode(non_interactive)

    # Handle '.' as shorthand for current directory
    if project_name == ".":
        project_name = None

    # Default behavior: no positional argument initializes in the current directory.
    here = project_name is None

    if here:
        try:
            project_path = Path.cwd()
            project_name = project_path.name
        except (OSError, FileNotFoundError) as e:
            _console.print("[red]Error:[/red] Cannot access current directory")
            _console.print(f"[dim]{e}[/dim]")
            _console.print("[yellow]Hint:[/yellow] Your current directory may have been deleted or is no longer accessible")
            raise typer.Exit(1) from e
    else:
        assert project_name is not None
        project_path = Path(project_name).resolve()
        if project_path.exists():
            error_panel = Panel(
                f"Directory '[cyan]{project_name}[/cyan]' already exists\nPlease choose a different project name or remove the existing directory.",
                title="[red]Directory Conflict[/red]",
                border_style="red",
                padding=(1, 2),
            )
            _console.print()
            _console.print(error_panel)
            raise typer.Exit(1)

    selected_agents_from_option: list[str] | None = None
    if ai_assistant:
        raw_agents = [part.strip().lower() for part in ai_assistant.replace(";", ",").split(",") if part.strip()]
        if not raw_agents:
            _console.print("[red]Error:[/red] --ai flag did not contain any valid agent identifiers")
            raise typer.Exit(1)
        selected_agents_from_option = []
        seen_agents: set[str] = set()
        invalid_agents: list[str] = []
        for key in raw_agents:
            if key not in AI_CHOICES:
                invalid_agents.append(key)
                continue
            if key not in seen_agents:
                selected_agents_from_option.append(key)
                seen_agents.add(key)
        if invalid_agents:
            _console.print(f"[red]Error:[/red] Invalid AI assistant(s): {', '.join(invalid_agents)}. Choose from: {', '.join(AI_CHOICES.keys())}")
            raise typer.Exit(1)

    # T004 — Idempotency check: exit 0 cleanly if already initialized.
    # This prevents silent re-init and makes CI-driven init safe to re-run.
    # #4425: a re-run also verifies the requested agents' managed surfaces —
    # command-skill gaps are diagnosed (exit 1 with the recovery command),
    # NATIVE-root gaps are restored additively through the canonical installer.
    _config_yaml = project_path / ".kittify" / "config.yaml"
    if _config_yaml.exists():
        try:
            resumed = _resume_command_delivery(project_path)
            if not resumed:
                if selected_agents_from_option:
                    _repair_requested_command_skills(project_path, selected_agents_from_option)
                selected = _check_initialized_command_skills(project_path, ai_assistant)
                _restore_native_project_skills(project_path, selected)
        except (OSError, ValueError, AgentConfigError) as exc:
            _console.print(f"[red]Initialization incomplete:[/red] {exc}")
            raise typer.Exit(1) from exc
        if resumed:
            raise typer.Exit(0)
        _console.print(
            Panel(
                "[yellow]Already initialized.[/yellow]\n"
                "Agent skill surfaces were verified on this re-run: missing per-agent\n"
                "skill roots were restored. A missing or unusable managed surface exits 1\n"
                "naming the affected paths — shared command skills with the recovery command\n"
                "[cyan]spec-kitty agent config sync --create-missing --keep-orphaned[/cyan];\n"
                "an unusable per-agent skill file is preserved untouched, so rename or\n"
                "remove it and re-run init.\n"
                "Run [cyan]spec-kitty upgrade[/cyan] to migrate to the latest version.",
                title="[yellow]Already Initialized[/yellow]",
                border_style="yellow",
                padding=(1, 2),
            )
        )
        raise typer.Exit(0)

    current_dir = Path.cwd()

    setup_lines = [
        "[cyan]Specify Project Setup[/cyan]",
        "",
        f"{'Project':<15} [green]{project_path.name}[/green]",
        f"{'Working Path':<15} [dim]{current_dir}[/dim]",
    ]

    # Add target path only if different from working dir
    if not here:
        setup_lines.append(f"{'Target Path':<15} [dim]{project_path}[/dim]")

    _console.print(Panel("\n".join(setup_lines), border_style="cyan", padding=(1, 2)))

    # Detect VCS (git only, jj support removed)
    selected_vcs: VCSBackend | None = None
    try:
        selected_vcs = _detect_default_vcs()
        _console.print()
        _display_vcs_info(selected_vcs, _console)
        _console.print()
        # FR-005 (#636): When the git binary IS available but the target
        # directory is not inside a git work tree, surface one actionable
        # info line. We probe the target if it exists, else its parent —
        # the question is "will the scaffold land inside a repo?".
        # The scaffold itself still completes (canonical invariant
        # 01KQ84P1AJ8H3FPJN9J5C12CBY: non-git init is allowed; silent
        # non-git init is not).
        probe_dir = project_path if project_path.exists() else project_path.parent
        if not _is_inside_git_work_tree(probe_dir):
            _console.print(
                "[yellow]Target is not a git repository.[/yellow] "
                "After init, run `git init` in the target before using "
                "`spec-kitty agent`, `dashboard`, `dispatch`, `next`, or `implement` commands."
            )
    except VCSNotFoundError:
        # git not available - not an error, just informational
        selected_vcs = None
        _console.print("[yellow]ℹ git not detected[/yellow] - install git for version control")

    if ai_assistant:
        assert selected_agents_from_option is not None
        selected_agents = selected_agents_from_option
    else:
        if non_interactive:
            _console.print("[red]Error:[/red] --ai is required in non-interactive mode")
            raise typer.Exit(1)
        selected_agents = multi_select_with_arrows(
            AI_CHOICES,
            "Choose your AI assistant(s):",
            default_keys=["copilot"],
        )

    if not selected_agents:
        _console.print("[red]Error:[/red] No AI assistants selected")
        raise typer.Exit(1)

    # Build agent config to save later
    agent_config = AgentConfig(
        available=selected_agents,
        auto_commit=True,
    )

    template_mode = "package"
    local_repo = get_local_repo_root()
    if local_repo is not None:
        template_mode = "local"

    ai_display = ", ".join(AI_CHOICES[key] for key in selected_agents)
    _console.print(f"[cyan]Selected AI assistant(s):[/cyan] {ai_display}")

    # Download and set up project
    # New tree-based progress (no emojis); include earlier substeps
    tracker = StepTracker("Initialize Specify Project")
    # Flag to allow suppressing legacy headings
    sys._specify_tracker_active = True
    # Pre steps recorded as completed before live rendering
    tracker.add("precheck", "Check required tools")
    tracker.complete("precheck", "ok")
    tracker.add("ai-select", "Select AI assistant(s)")
    tracker.complete("ai-select", ai_display)
    tracker.add("runtime", "Bootstrap global runtime")
    for agent_key in selected_agents:
        label = AI_CHOICES[agent_key]
        tracker.add(f"{agent_key}-fetch", f"{label}: fetch latest release")
        tracker.add(f"{agent_key}-download", f"{label}: download template")
        tracker.add(f"{agent_key}-extract", f"{label}: extract template")
        tracker.add(f"{agent_key}-zip-list", f"{label}: archive contents")
        tracker.add(f"{agent_key}-extracted-summary", f"{label}: extraction summary")
        tracker.add(f"{agent_key}-cleanup", f"{label}: cleanup")
        tracker.add(f"{agent_key}-skills", f"{label}: install skill pack")
    for key, label in [
        ("chmod", "Ensure scripts executable"),
        ("final", "Finalize"),
    ]:
        tracker.add(key, label)

    if not here and not project_path.exists():
        project_path.mkdir(parents=True)

    templates_root: Path | None = None  # Track template source for later use
    base_prepared = False
    command_skill_agents: list[str] = []

    with Live(tracker.render(), console=_console, refresh_per_second=8, transient=True) as live:
        tracker.attach_refresh(lambda: live.update(tracker.render()))
        try:
            # Bootstrap global runtime — hard fail on error (FR-003)
            tracker.start("runtime")
            try:
                from specify_cli.runtime.bootstrap import ensure_runtime

                ensure_runtime()
                tracker.complete("runtime", "ok")
            except Exception as exc:
                tracker.error("runtime", str(exc))
                _console.print(f"[red]Error:[/red] Failed to bootstrap global runtime: {exc}")
                raise typer.Exit(1) from exc

            # Global canonical skills are NOT installed here: the CLI root
            # callback already dispatched the retained global owner
            # (``ensure_global_agent_skills()`` in ``specify_cli/__init__.py``)
            # before this command body ran, and the per-agent loop below
            # installs each selected agent's project skills through the
            # current installer contract (``install_skills_for_agent`` /
            # command delivery). The former standalone phase here imported
            # the removed private ``_sync_global_skill`` writer and failed
            # with an ImportError on every first run (#4166).
            # Skill pack installation state
            from specify_cli import __version__ as _sk_version

            _now_iso = now_utc_iso()
            skill_manifest = ManagedSkillManifest(
                created_at=_now_iso,
                updated_at=_now_iso,
                spec_kitty_version=_sk_version,
            )
            skill_registry_per_agent: SkillRegistry | None = None
            shared_root_installed: set[str] = set()

            for agent_key in selected_agents:
                source_detail = "local checkout" if template_mode == "local" else "packaged data"
                tracker.start(f"{agent_key}-fetch")
                tracker.complete(f"{agent_key}-fetch", source_detail)
                tracker.start(f"{agent_key}-download")
                tracker.complete(f"{agent_key}-download", "local files")
                tracker.start(f"{agent_key}-extract")
                try:
                    if not base_prepared:
                        # Global runtime was bootstrapped above; use minimal project setup
                        use_global = _has_global_runtime() and template_mode == "package"
                        if use_global:
                            _prepare_project_minimal(project_path)
                            pkg_templates = _get_package_templates_root()
                            if pkg_templates is not None:
                                templates_root = pkg_templates
                            else:
                                # Package templates not found -- fall back to full copy
                                use_global = False
                        if not use_global:
                            if template_mode == "local":
                                # Invariant: template_mode is only set to "local"
                                # right after local_repo is confirmed non-None
                                # (see get_local_repo_root() above). An explicit
                                # raise (not assert) keeps this guard live under
                                # `python -O` and lets the surrounding
                                # `except Exception` translate it via
                                # tracker.error(...) + re-raise, same as before.
                                if local_repo is None:
                                    raise RuntimeError("local_repo must be set when template_mode is 'local'")
                                copy_specify_base_from_local(local_repo, project_path)
                            else:
                                copy_specify_base_from_package(project_path)
                            # Track templates root for later use (AGENTS.md, .claudeignore)
                            pkg_templates = _get_package_templates_root()
                            if pkg_templates is not None:
                                templates_root = pkg_templates
                        base_prepared = True
                except Exception as exc:
                    tracker.error(f"{agent_key}-extract", str(exc))
                    raise
                else:
                    tracker.complete(f"{agent_key}-extract", "agent configured (commands managed globally)")
                    tracker.start(f"{agent_key}-zip-list")
                    tracker.complete(f"{agent_key}-zip-list", "templates ready")
                    tracker.start(f"{agent_key}-extracted-summary")
                    tracker.complete(f"{agent_key}-extracted-summary", "commands ready")
                    tracker.start(f"{agent_key}-cleanup")
                    tracker.complete(f"{agent_key}-cleanup", "done")

                # Install skill pack for this agent (non-fatal).
                # T002: Only NATIVE-class agents install into per-agent directories
                # (e.g. .claude/skills/, .qwen/skills/).  SHARED-class agents
                # previously installed into .agents/skills/ — that shared root is
                # intentionally NOT seeded during init (FR-003).
                tracker.start(f"{agent_key}-skills")
                try:
                    from specify_cli.core.config import AGENT_SKILL_CONFIG, SKILL_CLASS_SHARED, SKILL_CLASS_WRAPPER

                    agent_skill_class = (AGENT_SKILL_CONFIG.get(agent_key) or {}).get("class", "")
                    if agent_skill_class == SKILL_CLASS_WRAPPER:
                        # WRAPPER agents have no installable root.
                        tracker.complete(f"{agent_key}-skills", "skipped (wrapper)")
                    elif agent_key in ("codex", "vibe", "pi", "letta"):
                        # Render only after config is finalized: an absent config
                        # intentionally has different REASONS activation semantics.
                        command_skill_agents.append(agent_key)
                        tracker.complete(
                            f"{agent_key}-skills",
                            "queued until project configuration is saved",
                        )
                    elif agent_skill_class == SKILL_CLASS_SHARED:
                        # Other SHARED-class agents install their canonical skills
                        # via the legacy installer path below (doctrine/tactic
                        # skills), not command-skills.
                        tracker.complete(f"{agent_key}-skills", "skipped (global runtime)")
                    else:
                        if skill_registry_per_agent is None:
                            if template_mode == "local" and local_repo is not None:
                                skill_registry_per_agent = SkillRegistry.from_local_repo(local_repo)
                            else:
                                skill_registry_per_agent = SkillRegistry.from_package()
                        agent_skills = skill_registry_per_agent.discover_skills()
                        if agent_skills:
                            entries = install_skills_for_agent(
                                project_path,
                                agent_key,
                                agent_skills,
                                shared_root_installed=shared_root_installed,
                            )
                            for entry in entries:
                                skill_manifest.add_entry(entry)
                            tracker.complete(f"{agent_key}-skills", f"{len(agent_skills)} skills installed")
                        else:
                            tracker.complete(f"{agent_key}-skills", "no skills found")
                except Exception as exc:
                    tracker.error(f"{agent_key}-skills", str(exc))
                    _logger.warning("Skill installation failed for %s: %s", agent_key, exc)
                    # Non-fatal: wrappers are already installed

            # Save managed skill manifest
            if skill_manifest.entries:
                save_manifest(skill_manifest, project_path)

            # Ensure scripts are executable (POSIX)
            _ensure_executable_scripts(project_path, tracker)

            # Protect runtime roots before publishing project identity or
            # declaring initialization complete. A failed protection check
            # must remain resumable: config.yaml is the idempotency boundary.
            manager = GitignoreManager(project_path)
            result = manager.protect_all_agents()
            if result.modified:
                _console.print("[cyan]Updated .gitignore to exclude AI agent directories:[/cyan]")
                for entry in result.entries_added:
                    _console.print(f"  • {entry}")
                if result.entries_skipped:
                    _console.print(f"  ({len(result.entries_skipped)} already protected)")
            elif result.entries_skipped:
                _console.print(f"[dim]All {len(result.entries_skipped)} agent directories already in .gitignore[/dim]")
            for warning in result.warnings:
                _console.print(f"[yellow]⚠️  {warning}[/yellow]")
            for error in result.errors:
                _console.print(f"[red]❌ {error}[/red]")
            if not result.success:
                raise typer.Exit(1)

            # Config existence alone must not hide a newly interrupted command
            # delivery. Authored pre-existing config never reaches this boundary.
            _start_command_delivery(project_path, command_skill_agents)

            # T001: No git initialization. init is file-creation-only.
            # Git management is the user's responsibility. Running init inside
            # an existing repo leaves the repo untouched.

            # Persist a local canonical ProjectInitialized event before any
            # SaaS fan-out so local dashboards and TeamSpace import always
            # see a complete project history (issue #1067).
            try:
                from specify_cli.identity.project import ensure_identity
                from specify_cli.status import emit_project_initialized
                from specify_cli import __version__ as _sk_runtime_version

                # WRITE-AUTHORIZED BOUNDARY (#2263, FR-003): project init may persist
                # identity to .kittify/config.yaml. Do NOT swap to resolve_identity.
                _identity = ensure_identity(project_path)
                if _identity.project_uuid is not None:
                    emit_project_initialized(
                        project_path,
                        project_uuid=str(_identity.project_uuid),
                        project_slug=_identity.project_slug,
                        actor="spec-kitty init",
                        runtime_version=_sk_runtime_version or None,
                    )
            except Exception as _proj_init_exc:  # noqa: BLE001
                _logger.debug("ProjectInitialized event emission skipped: %s", _proj_init_exc)

            tracker.complete("final", "project ready")
        except typer.Exit:
            raise
        except Exception as e:
            tracker.error("final", str(e))
            _console.print(Panel(f"Initialization failed: {e}", title="Failure", border_style="red"))
            if not here and project_path.exists():
                shutil.rmtree(project_path)
            raise typer.Exit(1) from e
        finally:
            # Force final render
            pass

    # Final static tree (ensures finished state visible after Live context ends)
    _console.print(tracker.render())
    _console.print("\n[bold green]Project ready.[/bold green]")

    # Agent folder security notice
    agent_folder_map = {
        "claude": ".claude/",
        "gemini": ".gemini/",
        "cursor": ".cursor/",
        "qwen": ".qwen/",
        "opencode": ".opencode/",
        "codex": ".agents/skills/",
        "vibe": ".vibe/",
        "windsurf": ".windsurf/",
        "kilocode": ".kilocode/",
        "auggie": ".augment/",
        "copilot": ".github/",
        "antigravity": ".agent/",
        # "roo" removed — Roo Code shut down on 2026-05-15 (C-007)
        "q": ".amazonq/",
        "kiro": ".kiro/",
        "pi": ".agents/skills/",
        "letta": ".agents/skills/",
        "llxprt": ".llxprt/",
    }

    notice_entries = []
    for agent_key in selected_agents:
        folder = agent_folder_map.get(agent_key)
        if folder:
            notice_entries.append((AI_CHOICES[agent_key], folder))

    if notice_entries:
        body_lines = [
            "Some agents may store credentials, auth tokens, or other identifying and private artifacts in the agent folder within your project.",  # noqa: E501
            "Consider adding the following folders (or subsets) to [cyan].gitignore[/cyan]:",
            "",
        ]
        body_lines.extend(f"- {display}: [cyan]{folder}[/cyan]" for display, folder in notice_entries)
        security_notice = Panel(
            "\n".join(body_lines),
            title="[yellow]Agent Folder Security[/yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
        _console.print()
        _console.print(security_notice)

    # Boxed "Next steps" section. Keep first-run guidance short: immediate
    # setup blocker, first workflow command, then optional tools.
    steps_lines = [
        f"Project: [green]{project_path}[/green]",
        f"Agents: [cyan]{', '.join(selected_agents)}[/cyan]",
    ]
    # FR-005 (#636): when target is not inside a git work tree, make git init
    # a numbered required action. Recompute against the now-existing project_path.
    inside_git = _is_inside_git_work_tree(project_path)
    steps_lines.append("Git: [green]ready[/green]" if inside_git else "Git: [yellow]not initialized[/yellow]")
    steps_lines.append("")
    step_num = 1
    if not here:
        steps_lines.append(f"{step_num}. Enter the project: [cyan]cd {project_name}[/cyan]")
        step_num += 1
    else:
        steps_lines.append(f"{step_num}. Stay in this project directory.")
        step_num += 1
    if not inside_git:
        steps_lines.append(f"{step_num}. [yellow]Required:[/yellow] run [cyan]git init[/cyan] here before agent, dashboard, dispatch, next, and implement commands")
        step_num += 1

    primary_agent = _primary_next_step_agent(selected_agents)
    workflow_heading, workflow_lines = _workflow_lines_for_agent(primary_agent)
    steps_lines.append(f"{step_num}. {workflow_heading} {' -> '.join(workflow_lines)}")
    step_num += 1

    steps_lines.append(f"{step_num}. Run the mission loop: [cyan]spec-kitty next --agent <agent> --mission <slug>[/cyan]")
    steps_lines.append("")
    steps_lines.append("[dim]Optional[/dim]")
    steps_lines.append(f"- [cyan]{_agent_command_token(primary_agent, 'charter')}[/cyan] - add project governance when needed")
    steps_lines.append("- [cyan]spec-kitty dashboard[/cyan] - open local project dashboard")
    steps_lines.append("- [cyan]spec-kitty retrospect summary[/cyan] - review learning status after merge")
    steps_lines.append(f"- [cyan]{_agent_command_token(primary_agent, 'analyze')}[/cyan] - check artifact alignment")
    steps_lines.append("")
    steps_lines.append("[dim]Docs: https://docs.spec-kitty.ai/[/dim]")

    steps_panel = Panel("\n".join(steps_lines), title="Next Steps", border_style="cyan", padding=(1, 2))
    _console.print()
    _console.print(steps_panel)

    # Vibe-specific next steps (shown when vibe is among selected agents)
    if "vibe" in selected_agents:
        vibe_steps_lines = [
            "1. Install Vibe if you haven't already:",
            "     [cyan]curl -LsSf https://mistral.ai/vibe/install.sh | bash[/cyan]",
            "   or",
            "     [cyan]uv tool install mistral-vibe[/cyan]",
            "2. Launch Vibe in this project:",
            "     [cyan]vibe[/cyan]",
            "3. Inside Vibe, invoke your first workflow:",
            "     [cyan]/spec-kitty.specify <describe what you want to build>[/cyan]",
        ]
        vibe_panel = Panel(
            "\n".join(vibe_steps_lines),
            title="Next Steps for Mistral Vibe",
            border_style="cyan",
            padding=(1, 2),
        )
        _console.print()
        _console.print(vibe_panel)

    if "pi" in selected_agents:
        pi_steps_lines = [
            "1. Install Pi if you haven't already:",
            "     [cyan]curl -fsSL https://pi.dev/install.sh | sh[/cyan]",
            "2. Launch Pi in this project:",
            "     [cyan]pi[/cyan]",
            "3. Invoke your first Spec Kitty command skill:",
            "     [cyan]/skill:spec-kitty.specify <describe what you want to build>[/cyan]",
        ]
        pi_panel = Panel(
            "\n".join(pi_steps_lines),
            title="Next Steps for Pi",
            border_style="cyan",
            padding=(1, 2),
        )
        _console.print()
        _console.print(pi_panel)

    if "letta" in selected_agents:
        letta_steps_lines = [
            "1. Install Letta Code if you haven't already:",
            "     [cyan]npm install -g @letta-ai/letta-code[/cyan]",
            "2. Launch Letta Code in this project:",
            "     [cyan]letta[/cyan]",
            "3. Ask Letta Code to use the Spec Kitty specify skill:",
            "     [cyan]/spec-kitty.specify <describe what you want to build>[/cyan]",
        ]
        letta_panel = Panel(
            "\n".join(letta_steps_lines),
            title="Next Steps for Letta Code",
            border_style="cyan",
            padding=(1, 2),
        )
        _console.print()
        _console.print(letta_panel)

    enhancement_lines = [
        "Optional quality checks.",
        "",
        f"○ [cyan]{_agent_command_token(primary_agent, 'analyze')}[/] [bright_black](optional)[/bright_black] - "
        f"Cross-artifact consistency & alignment report (after [cyan]{_agent_command_token(primary_agent, 'tasks')}[/])",
    ]
    enhancements_panel = Panel("\n".join(enhancement_lines), title="Optional Enhancements", border_style="cyan", padding=(1, 2))
    _console.print()
    _console.print(enhancements_panel)

    if _ensure_event_log_merge_attributes(project_path):
        _console.print("[dim]Updated .gitattributes for Spec Kitty generated artifacts[/dim]")

    # #4146: the attribute mapping above is inert without its git-config half
    # (``merge.<key>.name`` / ``.driver``). Install both halves of every
    # registered merge driver here so the union driver is active from the very
    # first lane claim, not only after the first merge/auto-rebase self-heals
    # it. No-op (by the helper's own guard) when the target is not a git
    # repository yet -- that case keeps relying on the merge-path self-heal.
    from specify_cli.lanes.merge import _ensure_merge_driver_git_config

    try:
        _ensure_merge_driver_git_config(project_path)
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        # Git is optional during init. A stale .git entry, missing binary, or
        # unusable repository must not turn best-effort driver wiring into a
        # late scaffold failure; merge paths self-heal the config later.
        _console.print(
            f"Could not configure Spec Kitty merge drivers; continuing without local git configuration: {exc}",
            style="yellow",
            markup=False,
            soft_wrap=True,
        )

    # Fresh-init provisioning (FR-009/010/011, NFR-004): seed
    # mission_type_activations from the shipped default charter pack so a
    # brand-new project always has an explicit, non-empty activation set.
    # This is the load-bearing prerequisite for removing the config-absent
    # implicit backfill elsewhere in the charter runtime (mission
    # resolution-activation-foundation-01KZ9FKG, WP04) -- unlike the
    # best-effort steps around it, this one fails closed (C-A4): a broken
    # install missing default.yaml must stop init, never silently produce an
    # empty or implicit mission-type set.
    try:
        provision_default_mission_type_activations(project_path)
    except DefaultCharterPackMissingError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    # Copy AGENTS.md from template source (not user project)
    # In global runtime mode, AGENTS.md resolves from ~/.kittify/ so skip copying.
    if templates_root and not _has_global_runtime():
        agents_target = project_path / ".kittify" / "AGENTS.md"
        agents_template = templates_root / "AGENTS.md"
        if not agents_target.exists() and agents_template.exists():
            shutil.copy2(agents_template, agents_target)

    # Generate .claudeignore from template source (always -- project-specific)
    if templates_root:
        claudeignore_template = templates_root / "claudeignore-template"
        claudeignore_dest = project_path / ".claudeignore"
        if claudeignore_template.exists() and not claudeignore_dest.exists():
            shutil.copy2(claudeignore_template, claudeignore_dest)
            _console.print("[dim]Created .claudeignore to optimize AI assistant scanning[/dim]")

    # Create project metadata for upgrade tracking
    try:
        import platform as plat
        import sys as system
        from specify_cli import __version__
        from specify_cli.upgrade.metadata import ProjectMetadata

        metadata = ProjectMetadata(
            version=__version__,
            initialized_at=now_utc(),
            python_version=plat.python_version(),
            platform=system.platform,
            platform_version=plat.platform(),
        )
        metadata.save(project_path / ".kittify")
    except Exception as e:
        # Don't fail init if metadata creation fails
        _console.print(f"[dim]Note: Could not create project metadata: {e}[/dim]")

    # Stamp schema_version + schema_capabilities into metadata.yaml so
    # downstream commands (charter setup, next, etc.) work without operators
    # hand-editing the file. See issue #840.
    try:
        _stamp_schema_metadata(project_path / ".kittify")
    except Exception as e:
        # Stamp is additive and best-effort: never fail init.
        _console.print(f"[dim]Note: Could not stamp schema metadata: {e}[/dim]")

    # Save VCS preference to config.yaml
    if selected_vcs:
        try:
            _save_vcs_config(project_path / ".kittify", selected_vcs)
        except Exception as e:
            # Don't fail init if VCS config creation fails
            _console.print(f"[dim]Note: Could not save VCS config: {e}[/dim]")

    # Save agent configuration to config.yaml
    agent_config_saved = False
    try:
        save_agent_config(project_path, agent_config)
        agent_config_saved = True
        _console.print("[dim]Saved agent configuration[/dim]")
    except Exception as e:
        # Don't fail init if agent config creation fails
        _console.print(f"[dim]Note: Could not save agent config: {e}[/dim]")

    # Install each selected command-skill owner once, with final render inputs.
    # Keep config creation after runtime-root protection (the resumability gate),
    # and reuse the installer for shared-root ownership and collision protection.
    commands_complete = _install_command_skill_agents(project_path, command_skill_agents)
    if agent_config_saved and commands_complete:
        _finish_command_delivery(project_path, command_skill_agents)
    elif command_skill_agents:
        _console.print("[yellow]Command delivery is incomplete; retry init after resolving the reported error.[/yellow]")

    # Write session presence orientation for each configured agent (FR-003).
    try:
        from specify_cli.session_presence.manager import SessionPresenceManager

        sp_result = SessionPresenceManager(project_path, agent_config).install()
        for change in sp_result.changes:
            _console.print(f"[dim]{change}[/dim]")
    except Exception as e:
        # Never fail init due to session presence errors
        _console.print(f"[dim]Note: Could not write session presence: {e}[/dim]")

    # Run tool-surface repair after all agent config has been flushed to disk.
    # NFR-007: --yes (non_interactive) does NOT imply --repair-drift; drifted
    # files are only reported, never overwritten, unless the caller explicitly
    # passes --repair-drift=overwrite (not yet exposed on init; defaults False).
    try:
        from specify_cli.tool_surface.repair import (
            render_surface_summary_lines,
            run_surface_repair,
        )

        _surface_summary = run_surface_repair(
            project_path,
            interactive=not non_interactive,
            repair_drift=False,
        )
        for _line in render_surface_summary_lines(_surface_summary):
            _console.print(_line)
        if _surface_summary.drifted_reported and non_interactive:
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        # Never fail init due to surface repair errors.
        _console.print(f"[dim]Note: Could not run tool surface repair: {e}[/dim]")

    # Clean up temporary directories used during init.
    # In full-copy mode: .kittify/templates/ holds the copied base templates.
    # In global-runtime mode: .kittify/.scratch/ holds base command templates
    # and .kittify/.resolved-* / .kittify/.merged-* hold resolver output.
    # User projects should only have the generated agent commands, not the sources.
    for cleanup_name in ("templates", "command-templates", ".scratch"):
        cleanup_dir = project_path / ".kittify" / cleanup_name
        if cleanup_dir.exists():
            try:
                shutil.rmtree(cleanup_dir)
            except PermissionError:
                _console.print(f"[dim]Note: Could not remove .kittify/{cleanup_name}/ (permission denied)[/dim]")
            except Exception as e:
                _console.print(f"[dim]Note: Could not remove .kittify/{cleanup_name}/: {e}[/dim]")
    # Also clean up resolver scratch dirs (.resolved-* and .merged-*)
    kittify_dir = project_path / ".kittify"
    if kittify_dir.is_dir():
        for scratch in kittify_dir.iterdir():
            if scratch.is_dir() and (scratch.name.startswith(".resolved-") or scratch.name.startswith(".merged-")):
                try:  # noqa: SIM105
                    shutil.rmtree(scratch)
                except Exception:  # noqa: S110
                    pass  # best-effort cleanup


def register_init_command(
    app: typer.Typer,
    *,
    console: Console,
    show_banner: Callable[[], None],
    activate_mission: Callable[[Path, str, str, Console], str] | None = None,
    ensure_executable_scripts: Callable[[Path, StepTracker | None], None],
) -> None:
    """Register the init command with injected dependencies."""
    global _console, _show_banner, _ensure_executable_scripts

    # Store the dependencies
    _console = console
    _show_banner = show_banner
    _ensure_executable_scripts = ensure_executable_scripts

    # Set the docstring
    init.__doc__ = INIT_COMMAND_DOC

    # Ensure app is in multi-command mode by checking if there are existing commands
    # If not, add a hidden dummy command to force subcommand mode
    if not hasattr(app, "registered_commands") or not app.registered_commands:

        @app.command("__force_multi_command_mode__", hidden=True)
        def _dummy() -> None:
            pass

    # Register the command with explicit name to ensure it's always a subcommand
    app.command("init")(init)
