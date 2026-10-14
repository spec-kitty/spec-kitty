"""Manifest tracking for projected native agent profile files.

:class:`ProfileManifest` records every native agent profile file this tool has
written, keyed by output path, together with its SHA-256 content hash and the
source profile URN / tool / format. It mirrors the command-skills manifest
pattern: the manifest is the *state* record (what was installed) separate from
the projection *policy* (what should exist).

Stored at ``.kittify/agent_profiles_manifest.json`` (NOT
``tool-surface-profile-manifest.json``). The on-disk format is JSON with
``schema_version: 1``, sorted keys, and a stable entry ordering so it round-trips
losslessly.
"""

from __future__ import annotations

import json
from pathlib import Path

from kernel.text_decode import normalize_newlines
from specify_cli.skills.manifest_store import fingerprint, fingerprint_file

from ..model import NativeAgentProfile
from ._paths import absolutize_from_root, relativize_under_root

MANIFEST_FILENAME = "agent_profiles_manifest.json"
_KITTIFY_DIR = ".kittify"
SCHEMA_VERSION = 1

#: Provenance generation stamped on entries written by the current projector
#: (#1940). Bumped when the projection algorithm changes in a way that should
#: force re-projection; recorded per entry so stale generations are detectable.
PROJECTION_VERSION = 1


def manifest_path_for(project_root: Path) -> Path:
    """Return the canonical manifest path under ``project_root``."""
    return project_root / _KITTIFY_DIR / MANIFEST_FILENAME


def hash_content(content: str) -> str:
    """Return the SHA-256 hex digest of ``content`` (UTF-8 encoded)."""
    return str(fingerprint(content.encode("utf-8")))


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the file at ``path`` (raw on-disk bytes)."""
    return str(fingerprint_file(path))


def hash_file_normalized(path: Path) -> str | None:
    """Return the SHA-256 of the file's UTF-8 content with line endings
    normalized to LF (CRLF/CR -> LF), matching how the canonical render is
    hashed (:func:`hash_content`).

    Returns ``None`` when the file cannot be read as UTF-8 text -- a genuinely
    non-text or unreadable profile, which is never a line-ending-only match.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return hash_content(normalize_newlines(text))


def file_matches_hash(path: Path, expected_hash: str, *, raw_hash: str | None = None) -> bool:
    """True when the file at ``path`` matches ``expected_hash`` byte-for-byte, or
    after line-ending normalization (CRLF/CR -> LF).

    The canonical profile render is hashed as LF (:func:`hash_content`), but Git
    for Windows' default ``core.autocrlf=true`` checks tracked text out with CRLF
    line endings. A managed profile that differs from the render only in line
    endings is Git-clean (``git diff`` is empty) and must not read as drift
    (#6235) -- the same class PR #5593 fixed in Git's terms for the ``implement``
    planning-artifact filter (#5576), on a surface that fix did not reach.

    The raw comparison is tried first (reused via ``raw_hash`` when the caller
    already observed it, e.g. ``FileState.sha256``) so the common LF path never
    re-reads the file.
    """
    raw = raw_hash if raw_hash is not None else hash_file(path)
    if raw == expected_hash:
        return True
    normalized = hash_file_normalized(path)
    return normalized is not None and normalized == expected_hash


class ProfileManifest:
    """Read/write tracker for projected native agent profile files."""

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        self._entries: dict[str, NativeAgentProfile] = {}

    @classmethod
    def load(cls, project_root: Path) -> ProfileManifest:
        """Load the manifest for ``project_root`` (empty when absent)."""
        manifest = cls(manifest_path_for(project_root))
        manifest._read()
        return manifest

    def _read(self) -> None:
        from ._paths import observe_node

        state = observe_node(self.manifest_path)
        if state.kind == "absent":
            return
        if state.kind != "file":
            raise ValueError(f"Profile manifest is not a regular file: {self.manifest_path}")
        project_root = self.manifest_path.parent.parent
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or type(data.get("schema_version")) is not int
            or data.get("schema_version") != SCHEMA_VERSION
            or not isinstance(data.get("entries"), list)
        ):
            raise ValueError("Invalid profile manifest schema or entries")
        for raw in data.get("entries", []):
            if not isinstance(raw, dict):
                raise ValueError("Invalid profile manifest entry")
            try:
                entry = _entry_from_json(raw, project_root)
            except (KeyError, TypeError, OverflowError) as exc:
                raise ValueError(f"Invalid profile manifest entry: {exc}") from exc
            if str(entry.output_path) in self._entries:
                raise ValueError(f"Duplicate profile manifest output: {entry.output_path}")
            self._entries[str(entry.output_path)] = entry

    def record(self, profile: NativeAgentProfile) -> None:
        """Insert or replace the entry for ``profile.output_path``."""
        self._entries[str(profile.output_path)] = profile

    def get_hash(self, output_path: Path) -> str | None:
        """Return the recorded hash for ``output_path`` or ``None``."""
        entry = self._entries.get(str(output_path))
        return entry.file_hash if entry is not None else None

    def all_entries(self) -> list[NativeAgentProfile]:
        """Return every recorded entry, ordered by output path."""
        return [self._entries[key] for key in sorted(self._entries)]

    def remove(self, output_path: Path) -> None:
        """Drop the entry for ``output_path`` if present (no-op otherwise)."""
        self._entries.pop(str(output_path), None)

    def save(self, prepared: bytes | None = None, *, exclusive: bool = False) -> None:
        """Write the manifest to disk, creating ``.kittify/`` as needed."""
        content = self.render_bytes() if prepared is None else prepared
        if not exclusive and self.manifest_path.is_file() and self.manifest_path.read_bytes() == content:
            return
        if not self.manifest_path.parent.is_dir():
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("xb" if exclusive else "wb") as stream:
            stream.write(content)

    def render_bytes(self) -> bytes:
        """Serialize the current entries without touching the filesystem."""
        project_root = self.manifest_path.parent.parent
        payload = {
            "schema_version": SCHEMA_VERSION,
            "entries": [_entry_to_json(e, project_root) for e in self.all_entries()],
        }
        return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _entry_to_json(entry: NativeAgentProfile, project_root: Path) -> dict[str, object]:
    return {
        "profile_urn": entry.profile_urn,
        "source_layer": entry.source_layer,
        "tool_key": entry.tool_key,
        # Repo-relative on disk (#2589); the in-memory Path and the manifest
        # KEY (str(entry.output_path), used by get_hash/prune/.exists() below)
        # stay absolute -- only this serialized copy is relativized.
        "output_path": relativize_under_root(entry.output_path, project_root),
        "format": entry.format,
        "file_hash": entry.file_hash,
        # Provenance (#1940). Always written by the current projector so new
        # manifests are full 8-field entries.
        "source_path": entry.source_path,
        "source_hash": entry.source_hash,
        "projection_version": entry.projection_version,
    }


def _required_str(raw: dict[str, object], key: str) -> str:
    """Validate record structure, not whether a legacy identity authorizes writes."""
    value = raw[key]
    if not isinstance(value, str) or not value:
        raise TypeError(f"manifest field {key!r} must be a nonempty string")
    return value


def _opt_str(raw: dict[str, object], key: str) -> str | None:
    """Read an optional string field, defaulting to ``None`` when absent.

    Uses ``raw.get`` (not subscripting) so a legacy 6-field entry that predates
    the provenance keys deserializes cleanly rather than raising ``KeyError``.
    """
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise TypeError(f"manifest field {key!r} must be a string or null")
    return value


def _opt_int(raw: dict[str, object], key: str) -> int | None:
    """Read an optional int field, defaulting to ``None`` when absent."""
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"manifest field {key!r} must be an int or null")
    return value


def _entry_from_json(raw: dict[str, object], project_root: Path) -> NativeAgentProfile:
    return NativeAgentProfile(
        profile_urn=_required_str(raw, "profile_urn"),
        source_layer=_required_str(raw, "source_layer"),
        tool_key=_required_str(raw, "tool_key"),
        output_path=absolutize_from_root(_required_str(raw, "output_path"), project_root),
        format=_required_str(raw, "format"),
        file_hash=_opt_str(raw, "file_hash"),
        source_path=_opt_str(raw, "source_path"),
        source_hash=_opt_str(raw, "source_hash"),
        projection_version=_opt_int(raw, "projection_version"),
    )
