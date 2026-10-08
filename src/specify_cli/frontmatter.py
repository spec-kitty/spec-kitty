"""Frontmatter management with absolute consistency enforcement.

This module provides the ONLY way to read and write YAML frontmatter
in spec-kitty markdown files. All frontmatter operations MUST go through
these functions to ensure absolute consistency.

LLMs and scripts should NEVER manually edit YAML frontmatter.
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.constructor import DuplicateKeyError

from kernel.atomic import atomic_write

# The additive PID-reuse identity baseline (C-007), historically co-written
# alongside ``shell_pid`` at claim-write time (D3b); WP05
# (coord-write-placement-closure-01KYCF83, FR-008) confirms that write is
# retired -- both fields now travel solely via the claim transition's
# ``policy_metadata`` sidecar into the event log, and ``core.stale_detection``
# (the claim-liveness consumer) resolves both from the reduced snapshot, never
# frontmatter. Declared once here — the single shared constant mirrors the
# ``"shell_pid"`` field-name pattern in ``WP_FIELD_ORDER`` below (retained for
# legacy-file classification; see the ``WP_RUNTIME_FIELDS`` note) — so the
# field name cannot drift into a re-duplicated literal (Sonar S1192).
SHELL_PID_BASELINE_FIELD = "shell_pid_created_at"


class FrontmatterError(Exception):
    """Error in frontmatter operations."""

    pass


class FrontmatterManager:
    """Manages YAML frontmatter with enforced consistency.

    Rules:
    1. Always use ruamel.yaml for parsing/writing
    2. Never quote scalar values (let YAML decide)
    3. Use consistent indentation (2 spaces)
    4. Preserve comments
    5. Sort keys in consistent order
    """

    # Standard field order for work package frontmatter.
    # Mutable status fields (lane, review_status, reviewed_by, review_feedback)
    # are managed exclusively via the canonical event log and are NOT written here.
    WP_FIELD_ORDER = [
        "work_package_id",
        "title",
        "dependencies",  # List of WP IDs this WP depends on (e.g., ['WP01', 'WP02'])
        "requirement_refs",  # Requirement IDs mapped to this WP (e.g., ['FR-001', 'NFR-002'])
        # "tracker_refs" is intentionally NOT listed here (WP07/T029, FR-006/FR-013):
        # it is event-sourced (emitted by WP08's map-requirements + WP06's
        # move-task as an InnerStateChanged delta) and read from the reduced
        # snapshot. Keeping it in this static authored schema would dual-home
        # it (dynamic-in-events AND static-in-frontmatter) -- the #2093
        # violation FR-013's arch test (WP10) catches. A legacy WP file that
        # still carries an authored ``tracker_refs:`` line is read tolerantly
        # into the ``remaining`` (sorted trailing) bucket, never an error.
        "planning_base_branch",  # Planning branch active when the WP prompt was generated
        "merge_target_branch",  # Final branch where completed WP changes must land
        "branch_strategy",  # Human-readable branch contract to prevent landing on wrong stream
        "base_branch",  # Git branch this workspace was created from (e.g., "kitty/mission-010-feature-lane-a" or "main")
        "base_commit",  # Git commit SHA this WP was created from (snapshot for validation)
        "created_at",  # ISO timestamp when workspace was created
        "subtasks",
        "phase",
        "assignee",
        "agent",
        "shell_pid",
        SHELL_PID_BASELINE_FIELD,  # PID-reuse identity baseline co-written with shell_pid (C-007)
        "scope",  # Optional: "codebase-wide" for audit/cutover WPs that need whole-repo access
        "history",
    ]

    def __init__(self) -> None:
        """Initialize with ruamel.yaml configured for consistency."""
        self.yaml = YAML()
        self.yaml.default_flow_style = False
        self.yaml.preserve_quotes = False  # Don't preserve quotes - let YAML decide
        self.yaml.width = 4096  # Prevent line wrapping
        self.yaml.indent(mapping=2, sequence=2, offset=0)
        # Fail closed on duplicate frontmatter keys (WP09, FR-007/C-002). The
        # round-trip loader already defaults to this, but pinning it explicitly
        # makes the guard a hard invariant of this canonical boundary: a future
        # ``typ``/config change cannot silently reintroduce YAML last-wins
        # semantics. Duplicates raise ``DuplicateKeyError``, translated into a
        # legible ``FrontmatterError`` (see ``read`` / ``_format_duplicate_key_error``).
        self.yaml.allow_duplicate_keys = False

    def read(self, file_path: Path) -> tuple[dict[str, Any], str]:
        """Read frontmatter and body from a markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            Tuple of (frontmatter_dict, body_text)

        Raises:
            FrontmatterError: If file has no frontmatter or is malformed
        """
        if not file_path.exists():
            raise FrontmatterError(f"File not found: {file_path}")

        content = file_path.read_text(encoding="utf-8-sig")

        if not content.startswith("---"):
            raise FrontmatterError(f"File has no frontmatter: {file_path}")

        # Find closing ---
        lines = content.split("\n")
        closing_idx = -1
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                closing_idx = i
                break

        if closing_idx == -1:
            raise FrontmatterError(f"Malformed frontmatter (no closing ---): {file_path}")

        # Parse frontmatter
        frontmatter_text = "\n".join(lines[1:closing_idx])
        try:
            frontmatter = self.yaml.load(frontmatter_text)
            if frontmatter is None:
                frontmatter = {}
        except DuplicateKeyError as e:
            # Fail closed *legibly* (WP09, FR-007): a single ruamel raise names
            # only the FIRST duplicate. Enumerate every duplicated key via WP03's
            # raw-text detector so the operator sees each offending key and line.
            raise FrontmatterError(self._format_duplicate_key_error(file_path, content, e)) from e
        except Exception as e:
            raise FrontmatterError(f"Invalid YAML in {file_path}: {e}") from e

        # Frontmatter must be a mapping. A YAML list/scalar (structurally-malformed
        # doc) would otherwise blow up the key access below with a TypeError that
        # escapes this method's documented FrontmatterError-only contract and
        # aborts callers mid-scan (#2883 item 4).
        if not isinstance(frontmatter, dict):
            raise FrontmatterError(f"Frontmatter is not a mapping in {file_path}: parsed as {type(frontmatter).__name__}")

        # Ensure dependencies field exists for WP files only (backward compatibility with pre-0.11.0)
        if file_path.name.startswith("WP") and "dependencies" not in frontmatter:
            frontmatter["dependencies"] = []

        # Get body (everything after closing ---)
        body = "\n".join(lines[closing_idx + 1 :])

        return frontmatter, body

    @staticmethod
    def _format_duplicate_key_error(file_path: Path, content: str, error: DuplicateKeyError) -> str:
        """Build a legible duplicate-key message naming every offending key.

        Consumes WP03's raw-text detector
        (:func:`specify_cli.status.dup_key_repair.find_duplicate_keys_in_text`)
        to enumerate ALL duplicated top-level keys with their 1-based line
        numbers -- ruamel's own raise names only the first. The import is
        deferred to break the ``frontmatter`` <-> ``status`` package cycle
        (``status`` sits above this foundational boundary and imports it back).

        Falls back to ruamel's own message for a duplicate the top-level
        scanner does not enumerate (e.g. a *nested* duplicate key), so the key
        stays named in every case.
        """
        # Deferred import (cycle break): see docstring. Routed through the
        # ``status`` facade (SR-2 module-boundary rule) — safe here because this
        # is a function-scoped import, so the facade is fully initialized by the
        # time this read path runs.
        from specify_cli.status import find_duplicate_keys_in_text

        duplicates = find_duplicate_keys_in_text(content)
        if duplicates:
            detail = "; ".join(
                f"'{key}' (lines {', '.join(str(occ.line_index + 1) for occ in occurrences)})"
                for key, occurrences in duplicates.items()
            )
            return f"Duplicate frontmatter key(s) in {file_path}: {detail}"
        return f"Duplicate frontmatter key in {file_path}: {error}"

    def write(self, file_path: Path, frontmatter: dict[str, Any], body: str) -> None:
        """Write frontmatter and body to a markdown file.

        Args:
            file_path: Path to markdown file
            frontmatter: Dictionary of frontmatter fields
            body: Body text (everything after frontmatter)
        """
        file_path.write_text(self.render(frontmatter, body), encoding="utf-8")

    def render(self, frontmatter: dict[str, Any], body: str) -> str:
        """Render *frontmatter* and *body* as the text :meth:`write` puts in a markdown file.

        Args:
            frontmatter: Dictionary of frontmatter fields (normalized: keys sorted, values cleaned)
            body: Body text, emitted verbatim after the closing ``---``
        """
        normalized = self._normalize_frontmatter(frontmatter)
        buffer = io.StringIO()
        buffer.write("---\n")
        self.yaml.dump(normalized, buffer)
        buffer.write("---\n")
        buffer.write(body)
        return buffer.getvalue()

    def get_field(self, file_path: Path, field: str, default: Any = None) -> Any:
        """Get a single field from frontmatter.

        Args:
            file_path: Path to markdown file
            field: Field name to get
            default: Default value if field doesn't exist

        Returns:
            Field value or default
        """
        frontmatter, _ = self.read(file_path)
        return frontmatter.get(field, default)

    def _normalize_frontmatter(self, frontmatter: dict[str, Any]) -> CommentedMap:
        """Normalize frontmatter for consistent output.

        Args:
            frontmatter: Raw frontmatter dictionary

        Returns:
            Normalized CommentedMap with consistent field order
        """
        # Create ordered map
        normalized = CommentedMap()

        # Add fields in standard order (if they exist)
        for field in self.WP_FIELD_ORDER:
            if field in frontmatter:
                normalized[field] = frontmatter[field]

        # Add any remaining fields (alphabetically)
        remaining = sorted(set(frontmatter.keys()) - set(self.WP_FIELD_ORDER))
        for field in remaining:
            normalized[field] = frontmatter[field]

        return normalized

    def _validate_dependencies(self, dependencies: Any) -> list[str]:
        """Validate dependencies field format.

        Args:
            dependencies: Dependencies value to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not isinstance(dependencies, list):
            errors.append(f"dependencies must be a list, got {type(dependencies).__name__}")
            return errors

        wp_pattern = re.compile(r"^WP\d{2}$")
        seen = set()

        for dep in dependencies:
            if not isinstance(dep, str):
                errors.append(f"Dependency must be string, got {type(dep).__name__}")
            elif not wp_pattern.match(dep):
                errors.append(f"Invalid WP ID format: {dep} (must be WP## like WP01, WP02)")
            elif dep in seen:
                errors.append(f"Duplicate dependency: {dep}")
            else:
                seen.add(dep)

        return errors

    def validate(self, file_path: Path) -> list[str]:
        """Validate frontmatter consistency.

        Args:
            file_path: Path to markdown file

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        try:
            frontmatter, _ = self.read(file_path)
        except FrontmatterError as e:
            return [str(e)]

        # Check for required fields (work packages only)
        # Note: `lane` is no longer a required frontmatter field — lane state
        # is managed exclusively via the canonical event log.
        if file_path.name.startswith("WP"):
            required = ["work_package_id", "title"]
            for field in required:
                if field not in frontmatter:
                    errors.append(f"Missing required field: {field}")

            # Validate dependencies field (if present)
            if "dependencies" in frontmatter:
                dep_errors = self._validate_dependencies(frontmatter["dependencies"])
                errors.extend(dep_errors)

        return errors


# WP05 (coord-write-placement-closure-01KYCF83, FR-008): the claim
# ``shell_pid``/``shell_pid_created_at`` frontmatter write this comment used
# to describe is RETIRED -- ``spec-kitty implement`` no longer writes those
# two fields into ``tasks/WP##.md`` at claim time at all (the claim triple
# rides the ``planned -> claimed`` transition's ``policy_metadata`` sidecar
# into the event log instead; see
# ``cli.commands.agent.workflow_executor._implement_write_claim_and_commit``:
# "the WP file is NOT mutated for the claim ... this function writes 0
# runtime bytes to the WP file"). Only ``base_branch``/``base_commit``/
# ``planning_base_branch`` are still genuinely written, and only once, at
# workspace-creation time (a distinct, still-live seam this WP does not
# touch). ``shell_pid``/``SHELL_PID_BASELINE_FIELD`` remain listed below
# purely as a legacy-classification tolerance: a WP file authored before this
# retirement may still carry a stale ``shell_pid`` value on disk, and
# consumers of :data:`WP_RUNTIME_FIELDS` (below) must still recognize it as a
# non-blocking, runtime-only key rather than a real content change. Derived
# from :attr:`FrontmatterManager.WP_FIELD_ORDER` -- the ONE canonical
# field-name source -- so this set can never diverge from the class that
# actually owns those field names (#2570.1). Consumed by
# ``cli.commands.implement_cores._drop_runtime_frontmatter_only_wp`` (WP01,
# the allocator's dirty-tree claim guard); move-task (WP07) reaches the same
# decision transitively by reusing that ``resolve_planning_artifact_staging``
# seam rather than re-classifying keys itself -- the ONE shared source so no
# consumer hardcodes a fresh (and driftable) runtime-field tuple.
_RUNTIME_FIELD_NAMES = (
    "shell_pid",
    SHELL_PID_BASELINE_FIELD,
    "base_branch",
    "base_commit",
    "planning_base_branch",
)
WP_RUNTIME_FIELDS: frozenset[str] = frozenset(
    field for field in FrontmatterManager.WP_FIELD_ORDER if field in _RUNTIME_FIELD_NAMES
)

# Global instance for convenience
_manager = FrontmatterManager()


# Convenience functions that use the global manager
def read_frontmatter(file_path: Path) -> tuple[dict[str, Any], str]:
    """Read frontmatter and body from a markdown file."""
    return _manager.read(file_path)


def write_frontmatter(file_path: Path, frontmatter: dict[str, Any], body: str) -> None:
    """Write frontmatter and body to a markdown file."""
    _manager.write(file_path, frontmatter, body)


def locked_update_frontmatter(
    wp_path: Path,
    mutate: Callable[[dict[str, Any]], bool | None],
    *,
    feature_dir: Path,
    repo_root: Path | None = None,
    fallback_to_dir_name: bool = False,
) -> dict[str, Any]:
    """Read-modify-write a work package's frontmatter under the Mission write lock; return what was written.

    The lock is :func:`~specify_cli.status.mission_write.mission_write_lock` for *feature_dir*, keyed on the
    Mission's canonical lock key, so every writer of one Mission converges on one lock file and nests
    re-entrantly on a thread that already holds it. The frontmatter and the body are read INSIDE the lock;
    *mutate* edits that fresh frontmatter dict in place and the file is replaced atomically with the body
    exactly as it was read. *mutate* is only called here (never stored); it returns ``False`` to say nothing
    changed and skip the write, any other value writes.

    *fallback_to_dir_name* is for the healing migrations (see
    :func:`~specify_cli.status.mission_write.mission_write_lock`): a Mission whose coordination key cannot
    be read is locked on its directory name.

    Raises:
        FrontmatterError: *wp_path* is missing, has no frontmatter, or the frontmatter is malformed.
    """
    # Lazy: ``specify_cli.status`` imports this module, so the lock door cannot be a module-scope import.
    from specify_cli.status.mission_write import mission_write_lock

    with mission_write_lock(feature_dir, repo_root=repo_root, fallback_to_dir_name=fallback_to_dir_name):
        frontmatter, body = _manager.read(wp_path)
        if mutate(frontmatter) is not False:
            atomic_write(wp_path, _manager.render(frontmatter, body))
        return frontmatter


def get_field(file_path: Path, field: str, default: Any = None) -> Any:
    """Get a single field from frontmatter."""
    return _manager.get_field(file_path, field, default)


def validate_frontmatter(file_path: Path) -> list[str]:
    """Validate frontmatter consistency."""
    return _manager.validate(file_path)


def normalize_file(file_path: Path) -> bool:
    """Normalize an existing file's frontmatter.

    Args:
        file_path: Path to markdown file

    Returns:
        True if file was modified, False if already normalized
    """
    try:
        # Read current content
        original_content = file_path.read_text(encoding="utf-8-sig")

        # Read and rewrite (which normalizes)
        frontmatter, body = _manager.read(file_path)
        _manager.write(file_path, frontmatter, body)

        # Check if changed
        new_content = file_path.read_text(encoding="utf-8-sig")
        return original_content != new_content

    except FrontmatterError:
        return False


__all__ = [
    "SHELL_PID_BASELINE_FIELD",
    "WP_RUNTIME_FIELDS",
    "FrontmatterError",
    "FrontmatterManager",
    "read_frontmatter",
    "write_frontmatter",
    "locked_update_frontmatter",
    "get_field",
    "validate_frontmatter",
    "normalize_file",
]
