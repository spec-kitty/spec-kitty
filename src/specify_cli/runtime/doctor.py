"""Global runtime health checks for spec-kitty doctor.

Provides reusable check functions that detect:
- Missing ~/.kittify/ directory (1A-11)
- version.lock mismatch with CLI version (1A-12)
- Corrupted/missing managed mission directories (1A-13)
- Stale legacy shared assets in project .kittify/ (1A-10)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from charter.activation.api import GovernanceDiagnosticCode
from charter.activation.resolver import (
    GovernanceResolutionError,
    resolve_project_governance,
)
from specify_cli.runtime.home import get_kittify_home

# Managed mission directories expected under ~/.kittify/missions/.
# These correspond to the bundled missions shipped with the package.
MANAGED_MISSION_DIRS: tuple[str, ...] = (
    "missions/software-dev",
    "missions/research",
    "missions/documentation",
)


@dataclass
class DoctorCheck:
    """Result of a single doctor health check."""

    name: str
    passed: bool
    message: str
    severity: str  # "error", "warning", "info"


def check_global_runtime_exists() -> DoctorCheck:
    """Check if ~/.kittify/ exists (1A-11)."""
    home = get_kittify_home()
    if home.is_dir():
        return DoctorCheck("global_runtime_exists", True, f"{home} exists", "info")
    return DoctorCheck(
        "global_runtime_exists",
        False,
        f"Missing global runtime: {home}",
        "error",
    )


def check_version_lock() -> DoctorCheck:
    """Check if version.lock matches CLI version (1A-12)."""
    home = get_kittify_home()
    version_file = home / "cache" / "version.lock"
    if not version_file.exists():
        return DoctorCheck(
            "version_lock",
            False,
            "version.lock missing (incomplete update?)",
            "warning",
        )
    from specify_cli import __version__

    try:
        stored = version_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        return DoctorCheck(
            "version_lock",
            False,
            f"Cannot read version lock {version_file}: {exc}",
            "warning",
        )
    if stored == __version__:
        return DoctorCheck(
            "version_lock",
            True,
            f"Version lock: {stored} (matches CLI)",
            "info",
        )
    return DoctorCheck(
        "version_lock",
        False,
        f"Version mismatch: lock={stored}, CLI={__version__}",
        "warning",
    )


def check_mission_integrity() -> DoctorCheck:
    """Check if all expected managed mission directories exist (1A-13)."""
    home = get_kittify_home()
    missing = []
    for managed_dir in MANAGED_MISSION_DIRS:
        if not (home / managed_dir).is_dir():
            missing.append(managed_dir)
    if not missing:
        return DoctorCheck(
            "mission_integrity",
            True,
            f"{len(MANAGED_MISSION_DIRS)} mission dirs present",
            "info",
        )
    return DoctorCheck(
        "mission_integrity",
        False,
        f"Missing: {', '.join(missing)}",
        "error",
    )


def check_stale_legacy_assets(project_dir: Path) -> DoctorCheck:
    """Count legacy shared assets in project .kittify/ (1A-10)."""
    kittify = project_dir / ".kittify"
    if not kittify.exists():
        return DoctorCheck("stale_legacy", True, "No .kittify/ directory", "info")

    stale_count = 0
    shared_dirs = {"templates", "missions", "scripts", "command-templates"}
    shared_files = {"AGENTS.md"}

    for item in kittify.iterdir():
        if item.name in shared_dirs and item.is_dir():
            stale_count += sum(1 for f in item.rglob("*") if f.is_file())
        elif item.name in shared_files and item.is_file():
            stale_count += 1

    if stale_count == 0:
        return DoctorCheck("stale_legacy", True, "No stale shared assets", "info")
    return DoctorCheck(
        "stale_legacy",
        False,
        f"{stale_count} shared assets could be migrated. Run 'spec-kitty migrate'.",
        "warning",
    )


def check_governance_resolution(project_dir: Path) -> DoctorCheck:
    """Validate charter-centric governance resolution for this project."""
    try:
        resolution = resolve_project_governance(project_dir)
    except GovernanceResolutionError as exc:
        return DoctorCheck(
            "governance_resolution",
            False,
            str(exc),
            "error",
        )
    except Exception as exc:
        return DoctorCheck(
            "governance_resolution",
            False,
            f"Could not resolve governance: {exc}",
            "warning",
        )

    unknown = [d.message for d in resolution.diagnostics if d.code is GovernanceDiagnosticCode.UNKNOWN_SELECTION_DROPPED]
    if unknown:
        # #6407/#6460: a selected id that exists in no layer is dropped; a green line would hide the typo,
        # so the check fails (warning severity) and `agent status doctor` reports the project unhealthy.
        return DoctorCheck(
            "governance_resolution",
            False,
            "Governance resolved, but selected artifact(s) were dropped: " + " | ".join(unknown),
            "warning",
        )

    if resolution.metadata.get("template_set_source") == "fallback":
        return DoctorCheck(
            "governance_resolution",
            True,
            (
                f"Resolved governance with template fallback '{resolution.template_set}'. "
                "Set governance.charter.template_set in .kittify/charter/charter.yaml to make this explicit."
            ),
            "warning",
        )

    return DoctorCheck(
        "governance_resolution",
        True,
        (
            f"Resolved governance: {len(resolution.paradigms)} paradigm(s), "
            f"{len(resolution.directives)} directive(s), "
            f"{len(resolution.tools)} tool(s), template_set={resolution.template_set}"
        ),
        "info",
    )


_VERSION_MARKER_HEAD_LINES = 15


def resolve_command_file_dirs(project_path: Path) -> dict[str, Path]:
    """Return ``{agent_key: user-global command directory}`` for the project's configured agents.

    The directory ``check_command_file_health`` inspects, resolved through
    ``get_global_command_dir`` (so ``$CLAUDE_CONFIG_DIR`` and the other
    documented config roots are honoured, #7701). Unknown directories are skipped.
    """
    from specify_cli.agent_utils.directories import AGENT_DIR_TO_KEY, get_agent_dirs_for_project
    from specify_cli.runtime.agent_commands import get_global_command_dir

    resolved: dict[str, Path] = {}
    for agent_root, _subdir in get_agent_dirs_for_project(project_path):
        agent_key = AGENT_DIR_TO_KEY.get(agent_root)
        if agent_key is None or agent_key in resolved:
            continue
        try:
            resolved[agent_key] = get_global_command_dir(agent_key)
        except KeyError:
            continue
    return resolved


def check_command_file_health(project_path: Path) -> list[dict[str, str]]:
    """Check all agent command files for correctness.

    For each agent configured in the project and each of the 15 consumer
    commands, this function verifies the file at that agent's user-global
    command directory (see ``get_global_command_dir``, canonical since the
    ``3.1.2_globalize_commands`` migration):

    - The command file exists.
    - The file head contains the current ``<!-- spec-kitty-command-version: X.Y.Z -->``
      marker (stale or missing marker indicates a file that needs regeneration).
      The marker may sit on line 1 (legacy layout) or just after the YAML
      frontmatter that carries the slash-command picker description.
    - The file type is correct: prompt-driven commands should be long (>50 non-empty
      lines) and CLI-driven commands should be short (<15 non-empty lines).

    Args:
        project_path: Root directory of the project, used only to determine
            which agents are configured (``get_agent_dirs_for_project``).

    Returns:
        List of issue dicts, each with keys:
        ``agent``, ``command``, ``file``, ``issue``, ``severity``.
        An empty list means all files are healthy.
    """
    try:
        from specify_cli import __version__
        from specify_cli.agent_utils.directories import AGENT_DIR_TO_KEY, get_agent_dirs_for_project
        from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS, PROMPT_DRIVEN_COMMANDS
        from specify_cli.core.config import AGENT_COMMAND_CONFIG
        from specify_cli.runtime.agent_commands import get_global_command_dir
    except ImportError:
        return []

    try:
        from importlib.metadata import version as pkg_version

        current_version = pkg_version("spec-kitty-cli")
    except Exception:
        current_version = __version__

    expected_marker = f"<!-- spec-kitty-command-version: {current_version} -->"

    def _compute_filename(command: str, agent_key: str) -> str:
        config = AGENT_COMMAND_CONFIG.get(agent_key)
        if config is None:
            return f"spec-kitty.{command}.md"
        ext: str = config["ext"]
        stem = command
        if agent_key == "codex":
            stem = stem.replace("-", "_")
        return f"spec-kitty.{stem}.{ext}" if ext else f"spec-kitty.{stem}"

    issues: list[dict[str, str]] = []
    agent_dirs = get_agent_dirs_for_project(project_path)

    for agent_root, _subdir in agent_dirs:
        agent_key = AGENT_DIR_TO_KEY.get(agent_root)
        if agent_key is None:
            continue

        # Command files live in the user-global command dir since the
        # 3.1.2_globalize_commands migration, not under the project root.
        agent_dir = get_global_command_dir(agent_key)

        for command in sorted(PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS):
            filename = _compute_filename(command, agent_key)
            file_path = agent_dir / filename
            file_display = str(file_path)
            is_prompt_driven = command in PROMPT_DRIVEN_COMMANDS

            if not file_path.exists():
                issues.append(
                    {
                        "agent": agent_key,
                        "command": command,
                        "file": file_display,
                        "issue": "missing",
                        "severity": "error",
                    }
                )
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError as exc:
                issues.append(
                    {
                        "agent": agent_key,
                        "command": command,
                        "file": file_display,
                        "issue": f"unreadable: {exc}",
                        "severity": "error",
                    }
                )
                continue

            # Version marker check — scan the file head, not just line 1, so
            # the post-fix layout (frontmatter on line 1, marker after the
            # closing ``---``) is recognized as healthy.
            head_lines = content.splitlines()[:_VERSION_MARKER_HEAD_LINES]
            marker_present = any(line.strip() == expected_marker for line in head_lines)
            if not marker_present:
                issues.append(
                    {
                        "agent": agent_key,
                        "command": command,
                        "file": file_display,
                        "issue": f"stale or missing version marker (expected: {expected_marker})",
                        "severity": "warning",
                    }
                )

            # Type check: prompt-driven should be long, CLI-driven should be short.
            # Threshold accounts for the new YAML frontmatter (~3 extra lines).
            non_empty_lines = [line for line in content.splitlines() if line.strip()]
            line_count = len(non_empty_lines)
            if is_prompt_driven and line_count < 50:
                issues.append(
                    {
                        "agent": agent_key,
                        "command": command,
                        "file": file_display,
                        "issue": f"prompt-driven command has only {line_count} non-empty lines (expected >50)",
                        "severity": "warning",
                    }
                )
            elif not is_prompt_driven and line_count >= 15:
                issues.append(
                    {
                        "agent": agent_key,
                        "command": command,
                        "file": file_display,
                        "issue": f"CLI-driven command has {line_count} non-empty lines (expected <15 for thin shim)",
                        "severity": "warning",
                    }
                )

    return issues


def run_global_checks(
    project_dir: Path | None = None,
) -> list[DoctorCheck]:
    """Run all global runtime health checks.

    Args:
        project_dir: Optional project directory for legacy asset detection.

    Returns:
        List of DoctorCheck results.
    """
    checks = [
        check_global_runtime_exists(),
        check_version_lock(),
        check_mission_integrity(),
    ]
    if project_dir:
        checks.append(check_stale_legacy_assets(project_dir))
        checks.append(check_governance_resolution(project_dir))
    return checks


# --- leftovers under a previous user-global root (#7723) ----------------------

#: How a leftover file was proven to be Spec Kitty's own output.
PROOF_CURRENT_RENDER = "current_render"
PROOF_CANONICAL_PREDECESSOR = "canonical_predecessor"
PROOF_HISTORICAL_RENDER = "historical_render"
PROOF_OWNERSHIP_RECORD = "ownership_record"


@dataclass(frozen=True)
class LeftoverFile:
    """A file Spec Kitty wrote under an agent's previous user-global root, which it no longer reads.

    Reported only (operator ruling Q2=A); removal is the operator's, see #7758.
    """

    kind: str  # "command" or "skill"
    agent: str
    path: Path
    old_root: Path
    proof: str


def find_old_root_leftovers(agent_keys: list[str] | None = None, *, kinds: tuple[str, ...] = ("command", "skill")) -> list[LeftoverFile]:
    """Proven Spec Kitty files left under the home mirror of a moved agent config root, read-only.

    For each agent with a documented user-global config root (``$CLAUDE_CONFIG_DIR`` ...)
    whose resolved command directory or skill root differs from the ``$HOME`` mirror of its
    project path (``~/.claude/commands``, ``~/.claude/skills``), the mirror is scanned. A
    command file is listed when it equals today's render or carries a Spec Kitty version
    marker for the same command (#4609); a skill file when its bytes are a render shipped for
    that exact skill path (#7700). Either is also listed when the global asset inventory
    records it with these exact bytes (Spec Kitty's own ownership record, e.g. a projection an
    older release wrote). Anything else is not listed. Symlinks are never followed.
    """
    from specify_cli.core.config import AGENT_PROJECT_CONFIG_DIRS, agent_user_config_root

    found: list[LeftoverFile] = []
    for agent in agent_keys if agent_keys is not None else list(AGENT_PROJECT_CONFIG_DIRS):
        config_dir = AGENT_PROJECT_CONFIG_DIRS.get(agent)
        if config_dir is None or agent_user_config_root(agent) is None:
            continue
        if "command" in kinds:
            found.extend(_command_leftovers(agent))
        if "skill" in kinds:
            found.extend(_skill_leftovers(agent, Path.home() / config_dir / "skills"))
    return found


def _moved_mirror(mirror: Path, current: Path | None) -> bool:
    """Whether *mirror* is a real directory the agent no longer reads from.

    An alias of the current root (a symlinked ``$HOME``, a ``..`` spelling) is the same
    directory, never a moved one: its files are the live install, not leftovers.
    """
    if current is None or not mirror.is_dir() or mirror.is_symlink():
        return False
    return not _same_directory(mirror, current)


def _same_directory(left: Path, right: Path) -> bool:
    """``os.path.samefile`` when both exist; else compare the resolved paths."""
    import os

    try:
        return os.path.samefile(left, right)
    except OSError:
        return left.resolve() == right.resolve()


def _command_leftovers(agent: str) -> list[LeftoverFile]:
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.runtime.agent_commands import get_global_command_dir

    config = AGENT_COMMAND_CONFIG.get(agent)
    if config is None:
        return []
    mirror = Path.home() / str(config["dir"]).strip("/")
    if not _moved_mirror(mirror, get_global_command_dir(agent)):
        return []
    renders = _current_command_renders(agent)
    recorded = _recorded_file_digests("slash_commands")
    found: list[LeftoverFile] = []
    for path in sorted(mirror.iterdir()):
        desired = renders.get(path.name)
        if desired is None or path.is_symlink() or not path.is_file():
            continue
        existing = path.read_bytes()
        proof = _command_proof(existing, desired) or _ownership_proof(path, existing, recorded)
        if proof is not None:
            found.append(LeftoverFile("command", agent, path, mirror, proof))
    return found


def _current_command_renders(agent: str) -> dict[str, bytes]:
    """Today's ``{filename: bytes}`` for *agent*; empty (nothing proven) when rendering fails."""
    from specify_cli.runtime.agent_commands import _get_command_templates_dir, _render_agent_commands, _resolve_script_type

    try:
        return dict(_render_agent_commands(agent, _get_command_templates_dir(), _resolve_script_type()))
    except (OSError, ValueError, KeyError):
        return {}


def _command_proof(existing: bytes, desired: bytes) -> str | None:
    from specify_cli.runtime.agent_commands import _is_canonical_predecessor
    from specify_cli.runtime.bootstrap import _get_cli_version

    if existing == desired:
        return PROOF_CURRENT_RENDER
    if _is_canonical_predecessor(existing, desired, _get_cli_version()):
        return PROOF_CANONICAL_PREDECESSOR
    return None


def _skill_leftovers(agent: str, mirror: Path) -> list[LeftoverFile]:
    from specify_cli.runtime.agent_skills import global_skill_names
    from specify_cli.skills.paths import get_primary_global_skill_root
    from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES

    if not _moved_mirror(mirror, get_primary_global_skill_root(agent)):
        return []
    # The user-global skill owner names the shipped skills (built-in only, as for every global root).
    names = set(global_skill_names()) | set(RETIRED_CANONICAL_SKILL_NAMES)
    recorded = _recorded_file_digests("global_skills")
    found: list[LeftoverFile] = []
    for skill_dir in sorted(mirror.iterdir()):
        if skill_dir.name in names and skill_dir.is_dir() and not skill_dir.is_symlink():
            found.extend(_proven_skill_files(agent, mirror, skill_dir, recorded))
    return found


def _proven_skill_files(agent: str, mirror: Path, skill_dir: Path, recorded: dict[Path, str]) -> list[LeftoverFile]:
    from specify_cli.runtime.asset_preparation import digest
    from specify_cli.skills.historical_renders import is_historical_render

    found: list[LeftoverFile] = []
    for path in sorted(skill_dir.rglob("*")):
        if path.is_symlink() or not path.is_file() or any(parent.is_symlink() for parent in path.parents if skill_dir in parent.parents):
            continue
        relative = path.relative_to(skill_dir).as_posix()
        existing = path.read_bytes()
        if is_historical_render(skill_dir.name, relative, str(digest(existing))):
            found.append(LeftoverFile("skill", agent, path, mirror, PROOF_HISTORICAL_RENDER))
        elif (proof := _ownership_proof(path, existing, recorded)) is not None:
            found.append(LeftoverFile("skill", agent, path, mirror, proof))
    return found


def _recorded_file_digests(owner: str) -> dict[Path, str]:
    """``{path: sha256}`` of the files *owner*'s global asset inventory records, read-only.

    Reads ``<owner>-assets.json`` and its ``-external`` sidecar through the inventory's own
    parser (#7722 anchoring included). An absent, unreadable or invalid inventory proves
    nothing, so it yields no entries: the report can only under-list, never over-list.
    """
    import json

    from specify_cli.runtime.asset_preparation import _read_inventory

    cache = get_kittify_home() / "cache"
    recorded: dict[Path, str] = {}
    for name in (f"{owner}-assets.json", f"{owner}-external-assets.json"):
        inventory = cache / name
        if inventory.is_symlink() or not inventory.is_file():
            continue
        try:
            entries = _read_inventory(json.loads(inventory.read_bytes()), inventory)
        except (OSError, ValueError, UnicodeError):
            continue  # an unreadable record proves nothing; the file stays unlisted
        recorded.update({path: str(record["sha256"]) for path, record in entries.items() if record.get("kind") == "file" and record.get("sha256")})
    return recorded


def _ownership_proof(path: Path, existing: bytes, recorded: dict[Path, str]) -> str | None:
    """``ownership_record`` when the inventory records *path* with exactly these bytes."""
    import os

    from specify_cli.runtime.asset_preparation import digest

    sha256 = recorded.get(Path(os.path.abspath(path)))
    return PROOF_OWNERSHIP_RECORD if sha256 is not None and sha256 == str(digest(existing)) else None


def leftover_removal_hint(leftovers: list[LeftoverFile]) -> str:
    """The ``rm`` line an operator can run to remove *leftovers* (quoted paths); nothing is run."""
    import shlex

    return "rm " + " ".join(shlex.quote(str(item.path)) for item in leftovers)
