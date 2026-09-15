"""Managed skill manifest: tracks installed skill files for drift detection."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from specify_cli.core.atomic import atomic_write
from kernel.clock import now_utc_iso
from specify_cli.skills.paths import SkillPathObservation, recheck_skill_paths, skill_path_observations

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "skills-manifest.json"


@dataclass
class ManagedFileEntry:
    """A single file installed by the skill manager.

    Manifest paths are portable relative paths and always use POSIX separators.
    """

    skill_name: str  # e.g., "spec-kitty-setup-doctor"
    source_file: str  # Relative within skill dir, e.g., "SKILL.md"
    installed_path: str  # Relative from project root, e.g., ".claude/skills/spec-kitty-setup-doctor/SKILL.md"
    installation_class: str  # "shared-root-capable", "native-root-required", "wrapper-only"
    agent_key: str  # "claude", "codex", etc.
    content_hash: str  # "sha256:<hex>"
    installed_at: str  # ISO 8601 UTC
    delivery_mode: str = "copy"  # "copy" or "symlink"

    def __post_init__(self) -> None:
        """Normalize paths produced on Windows or loaded from older manifests.

        Invariant: skill file and directory names must never contain
        backslashes. On POSIX a backslash is a legal filename character, and
        this normalizer rewrites it to ``/`` unconditionally -- an entry for a
        file literally named ``a\\b.md`` would end up pointing at ``a/b.md``,
        a path that does not exist (verifier/drift false positive). Such names
        are unsupported by contract; ``test_manifest_backslash_in_skill_file_name_is_rewritten``
        pins this behavior so any change to it is a conscious decision.
        """
        self.source_file = self.source_file.replace("\\", "/")
        self.installed_path = self.installed_path.replace("\\", "/")


@dataclass
class ManagedSkillManifest:
    """Top-level manifest tracking all managed skill files."""

    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    spec_kitty_version: str = ""
    entries: list[ManagedFileEntry] = field(default_factory=list)

    def add_entry(self, entry: ManagedFileEntry) -> None:
        """Add a new entry, replacing any existing entry with the same (installed_path, agent_key).

        Shared-root agents intentionally share ``installed_path`` so deduplication
        must include ``agent_key`` to avoid collapsing entries for different agents.
        """
        self.entries = [
            e
            for e in self.entries
            if not (e.installed_path == entry.installed_path and e.agent_key == entry.agent_key)
        ]
        self.entries.append(entry)

    def remove_entries_for_agent(self, agent_key: str) -> list[ManagedFileEntry]:
        """Remove and return all entries for a specific agent."""
        removed = [e for e in self.entries if e.agent_key == agent_key]
        self.entries = [e for e in self.entries if e.agent_key != agent_key]
        return removed

    def find_by_skill(self, skill_name: str) -> list[ManagedFileEntry]:
        """Find all entries for a specific skill."""
        return [e for e in self.entries if e.skill_name == skill_name]

    def find_by_installed_path(self, installed_path: str) -> ManagedFileEntry | None:
        """Find entry by installed path."""
        for e in self.entries:
            if e.installed_path == installed_path:
                return e
        return None


def _render_manifest(manifest: ManagedSkillManifest) -> str:
    """Serialize the managed-skill schema in its established wire format."""
    data = asdict(manifest)
    return json.dumps(data, indent=2) + "\n"


@dataclass(frozen=True)
class PreparedSkillManifest:
    """Exact serialized output and preconditions; no live manifest or clock."""

    target: Path
    content: bytes
    observations: tuple[SkillPathObservation, ...]
    changed: bool
    mode: int


def _retain_entry_times(
    entries: list[ManagedFileEntry], previous: ManagedSkillManifest
) -> list[ManagedFileEntry]:
    old = {(entry.installed_path, entry.agent_key): entry for entry in previous.entries}
    order = {key: index for index, key in enumerate(old)}
    retained = []
    for entry in entries:
        prior = old.get((entry.installed_path, entry.agent_key))
        same_identity = prior is not None and (
            prior.skill_name, prior.source_file, prior.installation_class
        ) == (entry.skill_name, entry.source_file, entry.installation_class)
        retained.append(replace(entry, installed_at=prior.installed_at) if prior is not None and same_identity else replace(entry))
    return sorted(retained, key=lambda entry: (
        order.get((entry.installed_path, entry.agent_key), len(order)), entry.installed_path, entry.agent_key,
    ))


def prepare_manifest(
    manifest: ManagedSkillManifest, project_path: Path, *, operation_time: str | None = None
) -> PreparedSkillManifest:
    """Prepare one exact save, preserving historical identity and current raw bytes."""
    target = project_path / ".kittify" / MANIFEST_FILENAME
    observations = skill_path_observations(project_path, target)
    state = observations[-1].state
    if state.kind not in {"file", "absent"}:
        raise ValueError(f"Skills manifest is not a regular file: {target}")
    raw = target.read_bytes() if state.kind == "file" else None
    previous = _parse_manifest(raw.decode("utf-8")) if raw is not None else None
    desired = replace(manifest, entries=[replace(entry) for entry in manifest.entries])
    if previous is not None:
        desired.created_at = previous.created_at
        desired.entries = _retain_entry_times(desired.entries, previous)
        comparable = replace(desired, updated_at=previous.updated_at)
        if comparable == previous:
            assert raw is not None
            recheck_skill_paths(observations)
            return PreparedSkillManifest(target, raw, observations, False, state.mode if state.mode is not None else 0o600)
    prepared_time = operation_time or desired.updated_at
    if not prepared_time or (previous is not None and prepared_time == previous.updated_at):
        prepared_time = operation_time or (desired.created_at if previous is None else "") or now_utc_iso()
    desired.created_at = desired.created_at or prepared_time
    desired.updated_at = prepared_time
    content = _render_manifest(desired).encode("utf-8")
    recheck_skill_paths(observations)
    return PreparedSkillManifest(target, content, observations, content != raw, state.mode if state.mode is not None else 0o600)


def save_manifest(manifest: ManagedSkillManifest | PreparedSkillManifest, project_path: Path) -> None:
    """Save retained bytes, or prepare immediately for an existing direct caller."""
    prepared = manifest if isinstance(manifest, PreparedSkillManifest) else prepare_manifest(manifest, project_path)
    target = project_path / ".kittify" / MANIFEST_FILENAME
    if prepared.target != target:
        raise ValueError("Prepared skills manifest belongs to another project")
    recheck_skill_paths(prepared.observations)
    if prepared.changed:
        atomic_write(target, prepared.content, mkdir=True)
        if target.stat().st_mode & 0o7777 != prepared.mode:
            target.chmod(prepared.mode)
    if isinstance(manifest, ManagedSkillManifest):
        saved = _parse_manifest(prepared.content.decode("utf-8"))
        manifest.created_at, manifest.updated_at = saved.created_at, saved.updated_at
        manifest.entries = saved.entries


def _parse_manifest(raw: str) -> ManagedSkillManifest:
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
        raise ValueError("Invalid skills manifest shape")
    if set(data) - {"version", "created_at", "updated_at", "spec_kitty_version", "entries"}:
        raise ValueError("Unknown skills manifest fields")
    entries = []
    for entry_data in data.get("entries", []):
        if not isinstance(entry_data, dict) or any(not isinstance(value, str) for value in entry_data.values()):
            raise ValueError("Invalid skills manifest entry")
        entry = ManagedFileEntry(**entry_data)
        if entry.delivery_mode not in {"copy", "symlink"}:
            raise ValueError("Invalid skill delivery mode")
        entries.append(entry)
    if len({(entry.installed_path, entry.agent_key) for entry in entries}) != len(entries):
        raise ValueError("Duplicate skills manifest owner")
    if type(data.get("version", 1)) is not int or data.get("version", 1) != 1:
        raise ValueError("Unsupported skills manifest version")
    for key in ("created_at", "updated_at", "spec_kitty_version"):
        if not isinstance(data.get(key, ""), str):
            raise ValueError(f"Invalid skills manifest {key}")
    return ManagedSkillManifest(
        version=data.get("version", 1), created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""), spec_kitty_version=data.get("spec_kitty_version", ""),
        entries=entries,
    )


def load_manifest(project_path: Path, *, strict: bool = False) -> ManagedSkillManifest | None:
    """Load manifest from .kittify/skills-manifest.json.

    Returns None if the file is missing or contains malformed JSON.
    """
    target = project_path / ".kittify" / MANIFEST_FILENAME
    try:
        observations = skill_path_observations(project_path, target)
        if observations[-1].state.kind == "absent":
            return None
        if observations[-1].state.kind != "file":
            raise ValueError(f"Skills manifest is not a regular file: {target}")
        manifest = _parse_manifest(target.read_text(encoding="utf-8"))
        recheck_skill_paths(observations)
        return manifest
    except (OSError, ValueError, TypeError, KeyError) as exc:
        if strict:
            raise ValueError(f"Invalid skills manifest: {exc}") from exc
        logger.warning("Failed to load skills manifest: %s", exc)
        return None


def clear_manifest(project_path: Path) -> None:
    """Delete the manifest file if it exists."""
    target = project_path / ".kittify" / MANIFEST_FILENAME
    if target.exists():
        target.unlink()


def compute_content_hash(file_path: Path) -> str:
    """Compute sha256 hash of file content."""
    content = file_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
    return f"sha256:{digest}"
