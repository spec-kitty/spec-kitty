"""Persistence layer for ``.kittify/command-skills-manifest.json``.

This module is the canonical source for reading and writing the Skills Manifest
that records every ``.agents/skills/spec-kitty*/SKILL.md`` file that
Spec Kitty has installed on a project.

Invariants
----------
* The on-disk file format is JSON with ``schema_version: 1``, sorted keys,
  2-space indent, and a trailing newline.
* Entries are sorted by ``path`` before every write, so diffs are deterministic.
* Unknown future top-level fields are tolerated on load (a warning is emitted)
  but silently dropped on the next ``save()``.  This provides forward-compatibility
  without silent data loss: callers that care must round-trip through the typed
  dataclass and re-serialize.
* Known fields are strictly typed; type mismatches raise ``ManifestError``.
* Writes are atomic: the new content is written to ``<target>.tmp`` in the same
  directory, fsync'd, and renamed via ``os.replace`` so a crash mid-write cannot
  leave a corrupt file.
* ``ManifestEntry`` is a frozen dataclass for hashability.  Mutations happen via
  the ``with_agent_added`` / ``with_agent_removed`` helpers, which return new
  records.

Dependency notes
----------------
``jsonschema`` (>=4.0) is already listed in ``pyproject.toml`` (it is used by
several ``doctrine`` sub-packages), so no new dependency is introduced by
this module.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.resources
import json
import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


from specify_cli.core.no_follow import chmod_fd

from .manifest_errors import ManifestError

__all__ = [
    "SCHEMA_VERSION",
    "ManifestEntry",
    "SkillsManifest",
    "fingerprint",
    "fingerprint_file",
    "load",
    "remove_unsafe_symlinks",
    "repair_stale_manifest",
    "save",
]


SCHEMA_VERSION = 1
_MANIFEST_FILENAME = "command-skills-manifest.json"
_KITTIFY_DIR = ".kittify"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestEntry:
    """One record per installed skill-package file.

    ``agents`` is stored as a sorted tuple (no duplicates) for hashability.
    The JSON representation uses a list; the load/save boundary coerces between
    the two.
    """

    path: str
    """POSIX-style path relative to repo root (.agents/skills/spec-kitty*/SKILL.md)."""

    content_hash: str
    """64-char lowercase hex SHA-256 of the installed file content."""

    agents: tuple[str, ...]
    """Sorted tuple of agent keys that installed this entry (e.g. ``("codex", "vibe")``)."""

    installed_at: str
    """ISO-8601 UTC timestamp at which the entry was first written."""

    spec_kitty_version: str
    """CLI version string that wrote this entry (e.g. ``"3.2.0"``)."""

    def with_agent_added(self, agent_key: str) -> ManifestEntry:
        """Return a new entry with *agent_key* included in ``agents``."""
        new_agents = tuple(sorted(set(self.agents) | {agent_key}))
        return ManifestEntry(
            path=self.path,
            content_hash=self.content_hash,
            agents=new_agents,
            installed_at=self.installed_at,
            spec_kitty_version=self.spec_kitty_version,
        )

    def with_agent_removed(self, agent_key: str) -> ManifestEntry:
        """Return a new entry with *agent_key* removed from ``agents``."""
        new_agents = tuple(a for a in self.agents if a != agent_key)
        return ManifestEntry(
            path=self.path,
            content_hash=self.content_hash,
            agents=new_agents,
            installed_at=self.installed_at,
            spec_kitty_version=self.spec_kitty_version,
        )


@dataclass
class SkillsManifest:
    """In-memory representation of the skills manifest."""

    schema_version: int = SCHEMA_VERSION
    entries: list[ManifestEntry] = field(default_factory=list)

    def find(self, path: str) -> ManifestEntry | None:
        """Return the entry with the given *path*, or ``None``."""
        for entry in self.entries:
            if entry.path == path:
                return entry
        return None

    def upsert(self, entry: ManifestEntry) -> None:
        """Replace the existing entry for *entry.path*, or append if absent.

        This ensures no two entries share a ``path`` — it replaces by path rather
        than appending a duplicate.
        """
        self.entries = [e for e in self.entries if e.path != entry.path]
        self.entries.append(entry)

    def remove_path(self, path: str) -> None:
        """Remove the entry for *path* (no-op if absent)."""
        self.entries = [e for e in self.entries if e.path != path]


@dataclass
class ManifestRepairResult:
    """Result of a ``repair_stale_manifest()`` or ``remove_unsafe_symlinks()`` call."""

    added: list[str] = field(default_factory=list)
    """Relative paths added to the manifest (were missing from canonical set)."""

    removed: list[str] = field(default_factory=list)
    """Relative paths removed from the manifest (were orphaned / not canonical)."""

    symlinks_removed: list[str] = field(default_factory=list)
    """Absolute paths of unsafe symlink artifacts that were deleted."""

    drifted: list[str] = field(default_factory=list)
    """Relative paths whose on-disk content no longer matches the manifest hash.

    Drifted files are *not* auto-repaired here — they are reported so callers
    can route them through ``run_surface_repair()`` (Rule 3 / prompt policy).
    """

    @property
    def changed(self) -> bool:
        """Return True when any manifest mutations or symlink removals occurred."""
        return bool(self.added or self.removed or self.symlinks_removed)


# ---------------------------------------------------------------------------
# Schema loading (package-bundled)
# ---------------------------------------------------------------------------


def _load_schema() -> dict[str, Any]:
    """Load the bundled JSON schema from ``skills/data/skills-manifest.schema.json``."""
    pkg = importlib.resources.files("specify_cli.skills.data")
    schema_bytes = (pkg / "skills-manifest.schema.json").read_bytes()
    return json.loads(schema_bytes)  # type: ignore[no-any-return]


# Cached at module level so we only parse once per process.
_SCHEMA: dict[str, Any] | None = None


def _get_schema() -> dict[str, Any]:
    global _SCHEMA  # noqa: PLW0603
    if _SCHEMA is None:
        _SCHEMA = _load_schema()
    return _SCHEMA


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_against_schema(data: dict[str, Any]) -> None:
    """Validate *data* against the bundled JSON schema.

    Raises ``ManifestError("schema_validation_failed", errors=[...])`` on failure.
    """
    schema = _get_schema()
    # #4409: imported here, not at module scope — ``jsonschema`` eagerly
    # loads format checkers (``rfc3987_syntax.syntax_helpers``, ~1.8s) that
    # every CLI invocation would otherwise pay for without validating
    # anything. Same deferral as the charter validation modules.
    import jsonschema  # noqa: PLC0415 — deferred: see the cost note above

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        messages = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]
        raise ManifestError("schema_validation_failed", errors=messages)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load(repo_root: Path) -> SkillsManifest:
    """Load the skills manifest from ``<repo_root>/.kittify/command-skills-manifest.json``.

    Returns an empty ``SkillsManifest`` if the file does not exist.

    Forward-compatibility
    ~~~~~~~~~~~~~~~~~~~~~
    Unknown top-level fields (not defined in the schema) are tolerated: a warning
    is logged and the unknown fields are discarded.  On the next ``save()`` call
    only the known fields will be written.  This allows a newer Spec Kitty to
    write extra fields that an older CLI can read without crashing.

    Raises
    ------
    ManifestError("corrupt_json")
        The file exists but cannot be parsed as JSON.
    ManifestError("unsupported_schema_version")
        The ``schema_version`` field is present but not equal to ``1``.
    ManifestError("schema_validation_failed")
        The document is valid JSON but fails schema validation.
    ManifestError("duplicate_path")
        Two or more entries share the same ``path``.
    """
    manifest_path = repo_root / _KITTIFY_DIR / _MANIFEST_FILENAME

    if not manifest_path.exists():
        return SkillsManifest(schema_version=SCHEMA_VERSION, entries=[])

    raw = manifest_path.read_text(encoding="utf-8")

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(
            "corrupt_json",
            path=str(manifest_path),
            detail=str(exc),
        ) from exc

    if not isinstance(data, dict):
        raise ManifestError("schema_validation_failed", detail="Manifest root must be an object")

    # Check schema version before full schema validation so we emit a targeted
    # error message rather than a generic "const" failure from jsonschema.
    found_version = data.get("schema_version")
    if found_version != SCHEMA_VERSION:
        raise ManifestError("unsupported_schema_version", found=found_version)

    # Warn about and discard unknown top-level fields BEFORE schema validation.
    # The schema uses `additionalProperties: false`, so unknown fields would
    # otherwise fail validation.  We strip them here to provide
    # forward-compatibility: a newer Spec Kitty can write extra fields that an
    # older CLI tolerates.
    known_top_level = {"schema_version", "entries"}
    unknown = set(data.keys()) - known_top_level
    if unknown:
        warnings.warn(
            f"command-skills-manifest.json contains unknown top-level fields that will be dropped on next save: {sorted(unknown)}",
            stacklevel=2,
        )
        data = {k: v for k, v in data.items() if k in known_top_level}

    # Full schema validation (covers required fields, types, patterns, enums).
    _validate_against_schema(data)

    # Deserialize entries.
    entries: list[ManifestEntry] = []
    seen_paths: set[str] = set()
    for raw_entry in data.get("entries", []):
        entry_path: str = raw_entry["path"]
        if entry_path in seen_paths:
            raise ManifestError("duplicate_path", path=entry_path)
        seen_paths.add(entry_path)

        entries.append(
            ManifestEntry(
                path=entry_path,
                content_hash=raw_entry["content_hash"],
                agents=tuple(sorted(raw_entry["agents"])),
                installed_at=raw_entry["installed_at"],
                spec_kitty_version=raw_entry["spec_kitty_version"],
            )
        )

    return SkillsManifest(schema_version=SCHEMA_VERSION, entries=entries)


def save(repo_root: Path, manifest: SkillsManifest) -> None:
    """Atomically write *manifest* to ``<repo_root>/.kittify/command-skills-manifest.json``.

    Steps
    -----
    1. Validate the manifest against the bundled JSON schema — raises before
       touching disk if the manifest is invalid.
    2. Sort entries by ``path`` ascending.
    3. Serialize with ``json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False)``
       and append a trailing newline.
    4. Write to ``<target>.tmp`` in the same directory, ``os.fsync``, then
       ``os.replace`` to the final path.  This guarantees a crash mid-write
       cannot leave a corrupt file.

    Raises
    ------
    ManifestError("schema_validation_failed")
        The in-memory manifest is invalid — caller bug, not a file problem.
    """
    kittify_dir = repo_root / _KITTIFY_DIR
    kittify_dir.mkdir(parents=True, exist_ok=True)
    target = kittify_dir / _MANIFEST_FILENAME

    encoded = serialize(manifest)
    _save_bytes(target, encoded)


def serialize(manifest: SkillsManifest) -> bytes:
    """Validate and render the existing manifest format without persistence."""
    # Sort entries deterministically before serialization.
    sorted_entries = sorted(manifest.entries, key=lambda e: e.path)

    data: dict[str, Any] = {
        "schema_version": manifest.schema_version,
        "entries": [
            {
                "path": e.path,
                "content_hash": e.content_hash,
                "agents": sorted(e.agents),
                "installed_at": e.installed_at,
                "spec_kitty_version": e.spec_kitty_version,
            }
            for e in sorted_entries
        ],
    }

    # Validate before touching disk.
    _validate_against_schema(data)

    serialized = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return serialized.encode("utf-8")


def _save_bytes(target: Path, encoded: bytes, *, mode: int = 0o644) -> None:
    """Persist already rendered manifest bytes using the existing atomic writer."""
    tmp_path = target.with_suffix(".tmp")
    created = False
    try:
        with tmp_path.open("xb") as fh:
            created = True
            fh.write(encoded)
            fh.flush()
            chmod_fd(fh.fileno(), tmp_path, mode)
            os.fsync(fh.fileno())
        os.replace(tmp_path, target)
    except Exception:
        # Best-effort cleanup of the temp file; do not mask the original error.
        if created:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
        raise


def save_prepared(repo_root: Path, encoded: bytes, *, mode: int = 0o644) -> None:
    """Write assessment-time bytes without sampling time or rebuilding entries.

    The command owner checks parent confinement and all inputs before this call.
    Exclusive temporary creation refuses an unrelated occupant at the temp path.
    """
    target = repo_root / _KITTIFY_DIR / _MANIFEST_FILENAME
    _save_bytes(target, encoded, mode=mode)


# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------


def fingerprint(content: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of *content*.

    This is the canonical hashing routine used by the installer, renderer
    snapshot tests, and migration to ensure all components agree on the
    content-hash format stored in ``ManifestEntry.content_hash``.
    """
    return hashlib.sha256(content).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def fingerprint_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the bytes at *path*.

    Reads the file without following symlinks beyond what the OS normally
    does for ``open()``; callers that need stricter symlink policies should
    resolve the path themselves before calling this function.
    """
    return fingerprint(path.read_bytes())


# ---------------------------------------------------------------------------
# Manifest repair helpers (T028, T029, T030)
# ---------------------------------------------------------------------------


def repair_stale_manifest(
    project_root: Path,
    *,
    canonical_commands: list[str],
    spec_kitty_version: str = "unknown",
) -> ManifestRepairResult:
    """Adopt only canonical retained bytes through the checked command owner.

    Normalization cannot guess an agent, synthesize missing-file ownership or
    discard retired ownership before pruning. It never rewrites command bytes.
    """
    from specify_cli.core.agent_config import get_configured_agents
    from specify_cli.skills import command_installer
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    del spec_kitty_version
    manifest = load(project_root)
    result = ManifestRepairResult()
    for entry in manifest.entries:
        path = project_root / entry.path
        if any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(project_root)):
            continue
        if path.is_file() and not path.is_symlink() and fingerprint_file(path) != entry.content_hash:
            result.drifted.append(entry.path)
    agents = tuple(agent for agent in get_configured_agents(project_root) if agent in command_installer.SUPPORTED_AGENTS)
    if agents and set(canonical_commands) == set(command_installer.CANONICAL_COMMANDS):
        inputs = AssessmentInputs(OperationRoot("project", "project", project_root.absolute()), consent=ApplyConsent(automatic=True))
        assessment = command_installer.prepare_commands(inputs, agents, adopt_only=True)
        if not assessment.complete:
            raise command_installer.InstallerError("manifest_preparation_failed", diagnostics=assessment.diagnostics)
        if agents != tuple(agent for agent in get_configured_agents(project_root) if agent in command_installer.SUPPORTED_AGENTS):
            raise command_installer.InstallerError("precondition_changed", detail="Configured command owners changed")
        applied = command_installer.apply_commands(assessment, inputs.consent)
        if applied.outcome != "applied":
            raise command_installer.InstallerError(applied.outcome, diagnostics=applied.diagnostics)
        payload = assessment.prepared
        assert isinstance(payload, command_installer.PreparedCommands)
        result.added.extend(command.path for command in payload.commands if manifest.find(command.path) is None)
    return result


def remove_unsafe_symlinks(project_root: Path) -> ManifestRepairResult:
    """Unlink only exact manifest-owned package links; preserve unknown links.

    No target is read or mutated. Command installation subsequently prepares
    copy delivery. Prefix matching is never an ownership proof.
    """
    result = ManifestRepairResult()
    skills_dir = project_root / ".agents/skills"
    if (project_root / ".agents").is_symlink() or skills_dir.is_symlink() or not skills_dir.is_dir():
        return result
    manifest = load(project_root)
    owned = {project_root / Path(entry.path).parent for entry in manifest.entries}
    for path in sorted(owned):
        if path.parent != skills_dir or not path.is_symlink():
            continue
        path.unlink()
        result.symlinks_removed.append(str(path))
    return result
