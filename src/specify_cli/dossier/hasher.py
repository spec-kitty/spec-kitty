"""Deterministic SHA256 hashing utilities for mission artifacts.

This module is the single owning definition (C-001) of the **canonical
dossier snapshot hash** used across the CLI and the SaaS server
(spec-kitty#2180). It also provides per-artifact content hashing and the
normalized WP static-projection input the snapshot hash is computed over.

Canonical dossier snapshot hash (:func:`compute_dossier_snapshot_hash`):
    sort entries by artifact path; join ``"{path}\\t{content_hash}"`` lines
    with newlines; ``sha256`` the utf-8 bytes; prefix the hex digest with
    ``sha256:``. This is byte-identical to the server's
    ``apps/dossier/materialize.py::_compute_snapshot_hash`` (cross-repo
    contract C-003). The prior concat-of-hashes / bare-hex form is retired.

See: kitty-specs/dossier-parity-reconciler-01KXYXVP/spec.md (FR-001..FR-003,
C-001, C-004) and kitty-specs/042-local-mission-dossier-authority-parity-export/data-model.md
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specify_cli.status.wp_metadata import WPMetadata


def hash_file(file_path: Path) -> str:
    """Compute SHA256 hash of file content (bytes).

    Reads file in binary mode and computes deterministic SHA256 hash,
    immune to encoding assumptions and timezone differences.

    Args:
        file_path: Path to file to hash

    Returns:
        64-character lowercase hex string (SHA256)

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read (permission denied)
        IOError: If other I/O errors occur during reading

    Examples:
        >>> from pathlib import Path
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        ...     f.write('Hello, world!')
        ...     path = Path(f.name)
        >>> hash1 = hash_file(path)
        >>> hash2 = hash_file(path)
        >>> hash1 == hash2
        True
        >>> len(hash1)
        64
    """
    hasher = hashlib.sha256()  # noqa: TID251 - production raw SHA-256 owner
    try:
        with open(file_path, "rb") as f:
            # Read in 8KB chunks to avoid memory issues with large files
            while chunk := f.read(8192):
                hasher.update(chunk)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {file_path}") from e
    except PermissionError as e:
        raise PermissionError(f"Permission denied reading file: {file_path}") from e
    except OSError as e:
        raise OSError(f"I/O error reading file: {file_path}") from e

    return hasher.hexdigest()


def hash_file_with_validation(file_path: Path) -> tuple[str | None, str | None]:
    """Hash file with UTF-8 validation, return (hash_or_none, error_reason).

    Attempts to read file as UTF-8 text (validates encoding), then hashes
    the bytes. If UTF-8 validation fails, captures error reason without
    silent corruption.

    UTF-8 validation is explicit: BOM (Byte Order Mark), CJK characters,
    and multi-byte sequences are handled correctly. Invalid UTF-8 sequences
    cause explicit error_reason return, never silent fallback.

    Args:
        file_path: Path to file to hash and validate

    Returns:
        Tuple of (hash_or_none, error_reason):
        - On success: (64-char hex string, None)
        - On UTF-8 error: (None, "invalid_utf8")
        - On file access error: (None, "unreadable")

    Examples:
        >>> from pathlib import Path
        >>> import tempfile
        >>> # Valid UTF-8 file
        >>> with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
        ...     f.write('Hello, 世界!')  # Chinese characters
        ...     path = Path(f.name)
        >>> hash_val, error = hash_file_with_validation(path)
        >>> error is None
        True
        >>> len(hash_val) == 64
        True
        >>> # Invalid UTF-8 file
        >>> import os
        >>> with tempfile.NamedTemporaryFile(delete=False) as f:
        ...     f.write(b'\xff\xfe')  # Invalid UTF-8 sequence
        ...     path = Path(f.name)
        >>> hash_val, error = hash_file_with_validation(path)
        >>> error
        'invalid_utf8'
        >>> hash_val is None
        True
    """
    try:
        # Read entire file as bytes
        with open(file_path, "rb") as f:
            content_bytes = f.read()

        # Validate UTF-8 encoding by attempting decode
        try:
            content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return None, "invalid_utf8"

        # Hash the bytes directly
        hasher = hashlib.sha256()  # noqa: TID251 - production raw SHA-256 owner
        hasher.update(content_bytes)
        return hasher.hexdigest(), None

    except FileNotFoundError:
        return None, "unreadable"
    except PermissionError:
        return None, "unreadable"
    except OSError:
        return None, "unreadable"


def compute_dossier_snapshot_hash(entries: list[tuple[str, str | None]]) -> str:
    """Compute the ONE canonical dossier snapshot hash (FR-001, FR-003, C-001).

    This is the single owning definition of the snapshot hash. It is
    byte-identical to the SaaS server's
    ``apps/dossier/materialize.py::_compute_snapshot_hash`` (cross-repo
    contract C-003, spec-kitty#2180) — do NOT change the ordering, separator,
    or algorithm without updating the server in lock-step.

    Algorithm:
        1. Sort ``(artifact_path, content_hash)`` entries by path (tuple sort).
        2. Join ``"{path}\\t{content_hash or ''}"`` lines with ``"\\n"``.
        3. ``sha256`` the utf-8 encoded bytes.
        4. Prefix the lowercase hex digest with ``"sha256:"``.

    Content-addressed and order-independent: any artifact add/remove/update
    changes the digest; the on-disk scan order does not. An empty ``entries``
    list hashes the empty string, a stable sentinel shared with the server.

    Args:
        entries: ``(artifact_path, content_hash)`` pairs. ``content_hash`` may
            be ``None`` (treated as the empty string, matching the server).

    Returns:
        The canonical ``"sha256:<64-hex>"`` digest.

    Examples:
        >>> compute_dossier_snapshot_hash([("b.md", "y"), ("a.md", "x")]) == \
        ...     compute_dossier_snapshot_hash([("a.md", "x"), ("b.md", "y")])
        True
    """
    lines = "\n".join(f"{path}\t{content_hash or ''}" for path, content_hash in sorted(entries))
    digest = hashlib.sha256(lines.encode("utf-8")).hexdigest()  # noqa: TID251 - canonical snapshot-hash owner
    return f"sha256:{digest}"


# ── Normalized WP static projection (FR-002, C-004) ─────────────────────────

# The canonical, churn-free subset of WP frontmatter that defines a work
# package's *content* (its contract) — as opposed to its runtime execution /
# review state (lane, agent, shell_pid, history, assignee, review_* , etc.),
# which mutate during a mission and MUST NOT move the content hash (AS-4).
#
# This shape is load-bearing for cross-repo parity: #2686 (server-side WP
# projection) and #2684 (runtime-state eviction) conform to THIS definition
# rather than redefining it (C-004, A-002). Add a field here only if it is
# genuinely part of the WP's authored specification, never its live state.
WP_STATIC_PROJECTION_FIELDS: tuple[str, ...] = (
    "work_package_id",
    "title",
    "dependencies",
    "requirement_refs",
    "tracker_refs",
    "priority",
    "execution_mode",
    "owned_files",
    "create_intent",
    "authoritative_surface",
    "scope",
    "task_type",
    "subtasks",
    "phase",
)

# The complement of WP_STATIC_PROJECTION_FIELDS, authored here so the
# exhaustiveness guard (tests/dossier/test_canonical_hash.py) can prove EVERY
# WPMetadata field is consciously classified — a newly-authored field must be
# placed in one of these sets, never silently dropped from the content hash
# (#2883 item 1). Split into two sets for intent clarity.
#
# Runtime / review state: mutates during a mission (execution + review) and MUST
# NOT move the content hash (AS-4).
WP_RUNTIME_PROJECTION_FIELDS: frozenset[str] = frozenset(
    {
        "agent",
        "agent_profile",
        "model",
        "role",
        "assignee",
        "lane",
        "status",
        "review_status",
        "shell_pid",
        "shell_pid_created_at",
        "history",
        "activity_log",
        "review_feedback",
        "review_feedback_file",
        "pre_review_test_scope",
        "reviewed_by",
        "reviewer",
        "reviewer_agent",
        "reviewer_shell_pid",
        "approved_by",
    }
)

# Descriptive / structural / identity metadata: authored, but deliberately NOT
# part of the WP's hashed content contract (branch+vcs config, mission identity,
# free-form descriptive fields). Revisit membership if any becomes load-bearing
# for content parity.
WP_DESCRIPTIVE_PROJECTION_FIELDS: frozenset[str] = frozenset(
    {
        "base_branch",
        "base_commit",
        "branch_strategy",
        "planning_base_branch",
        "merge_target_branch",
        "created_at",
        "description",
        "subtitle",
        "estimated_duration",
        "tags",
        "feature_slug",
        "mission_id",
        "mission_number",
        "mission_slug",
        "phases",
        "work_package_title",
        "wp_code",
    }
)


def wp_static_projection(meta: WPMetadata) -> dict[str, Any]:
    """Project a :class:`WPMetadata` onto its canonical static content fields.

    Returns only the :data:`WP_STATIC_PROJECTION_FIELDS` — the authored WP
    contract — dropping every runtime-mutable field so downstream hashing is
    immune to execution/review churn (FR-002, AS-4).

    Args:
        meta: Parsed WP frontmatter.

    Returns:
        A plain ``dict`` of the static projection (JSON-serializable values).
    """
    return {field: getattr(meta, field) for field in WP_STATIC_PROJECTION_FIELDS}


def hash_wp_static_projection(meta: WPMetadata) -> str:
    """Content-hash the normalized WP static projection (FR-002, C-004).

    Serializes :func:`wp_static_projection` deterministically (sorted keys,
    compact separators) and returns its ``sha256`` hex digest. This is the
    per-WP ``content_hash`` input to :func:`compute_dossier_snapshot_hash`,
    replacing raw ``WP##.md`` byte hashing so runtime-mutable churn does not
    change the dossier snapshot hash.

    Args:
        meta: Parsed WP frontmatter.

    Returns:
        64-character lowercase hex string (bare digest, no ``sha256:`` prefix
        — it is a per-artifact content hash, matching the raw-byte form's
        shape so it validates as an ``ArtifactRef.content_hash_sha256``).
    """
    payload = json.dumps(
        wp_static_projection(meta),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()  # noqa: TID251 - canonical WP projection-hash owner
