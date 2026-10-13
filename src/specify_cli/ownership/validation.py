"""Ownership validation for spec-kitty work packages.

Validates that:
- No two WPs have overlapping owned_files glob patterns.
- Each WP's authoritative_surface is a prefix of at least one owned_files entry.
- execution_mode is consistent with the owned_files paths (warnings only).

Codebase-wide WPs (scope == "codebase-wide") are exempt from overlap,
authoritative-surface, and execution-mode consistency checks.
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
import difflib
import fnmatch
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.ownership.models import WorkProductKind, OwnershipManifest

if TYPE_CHECKING:
    from specify_cli.status import WPMetadata

__all__ = [
    "ValidationResult",
    "build_wp_manifests",
    "validate_no_overlap",
    "validate_authoritative_surface",
    "validate_execution_mode_consistency",
    "validate_all",
    "validate_ownership",
    "validate_glob_matches",
]

logger = logging.getLogger(__name__)


def is_glob_pattern(path: str) -> bool:
    """Return True when *path* contains glob metacharacters.

    A path with any of ``*``, ``?``, ``[``, or ``{`` is treated as a glob
    pattern.  A plain literal path (e.g. ``src/foo/bar.py``) has none of
    these characters.
    """
    return any(c in path for c in ("*", "?", "[", "{"))


@dataclass
class GlobValidationResult:
    """Result of :func:`validate_glob_matches`.

    Separates hard errors (literal-path zero-match) from soft warnings
    (glob-pattern zero-match) so the call site can route them independently.
    """

    errors: list[str] = field(default_factory=list)
    """Literal-path entries that matched zero files — hard error."""
    warnings: list[str] = field(default_factory=list)
    """Glob-pattern entries that matched zero files — soft warning."""
    info: list[str] = field(default_factory=list)
    """Informational notes (e.g. create_intent suppression notices)."""

    @property
    def passed(self) -> bool:
        """True when there are no hard errors."""
        return len(self.errors) == 0


# Paths considered "planning only" for execution_mode consistency checks.
_PLANNING_PREFIXES = (f"{KITTY_SPECS_DIR}/", "docs/")
# Paths considered "code" for execution_mode consistency checks.
_CODE_PREFIXES = ("src/", "tests/")


@dataclass
class ValidationResult:
    """Structured result of ownership validation across all WPs in a feature."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True if there are no hard errors."""
        return len(self.errors) == 0


def _globs_overlap(pattern_a: str, pattern_b: str) -> bool:
    """Return True if the two glob patterns can match a common path.

    Strategy: we test whether each pattern matches the other as a literal,
    and also whether a synthetic "worst-case" path derived from each pattern
    is matched by the other.  This catches the most common overlap cases
    (e.g. ``src/**`` vs ``src/context/**``) without requiring pathspec.
    """
    # Exact equality → trivially overlap
    if pattern_a == pattern_b:
        return True

    # Strip trailing wildcards to get the path prefix of each pattern.
    def _prefix(pattern: str) -> str:
        for suffix in ("/**", "/*", "**", "*"):
            if pattern.endswith(suffix):
                return pattern[: -len(suffix)]
        return pattern

    prefix_a = _prefix(pattern_a)
    prefix_b = _prefix(pattern_b)

    # One prefix is a path-prefix of the other → the globs overlap.
    if prefix_a and prefix_b:
        if prefix_b.startswith(prefix_a) or prefix_a.startswith(prefix_b):
            return True

    # Fnmatch cross-check: does pattern_a match the literal prefix_b (or vice versa)?
    if fnmatch.fnmatch(prefix_b, pattern_a) or fnmatch.fnmatch(prefix_a, pattern_b):
        return True

    return False


def _dependency_reachability(
    dependencies: Mapping[str, list[str]],
) -> dict[str, set[str]]:
    """Compute, for each WP, the set of WPs it transitively depends on.

    ``dependencies[wp]`` is the list of WP ids that ``wp`` directly depends on.
    The returned mapping ``reach[wp]`` is the transitive closure of those edges
    — every ancestor reachable by following ``depends-on`` edges from ``wp``.

    Two WPs ``a`` and ``b`` are **sequential** (one runs strictly after the
    other, never concurrently) iff ``b in reach[a]`` or ``a in reach[b]``; the
    dependency DAG forces an execution order between them. WPs with no directed
    path between them are **concurrent** (the lane allocator may place them on
    parallel lanes), and only those must not share ``owned_files``.
    """
    reach: dict[str, set[str]] = {}

    def _walk(node: str, seen: set[str]) -> set[str]:
        if node in reach:
            return reach[node]
        acc: set[str] = set()
        for dep in dependencies.get(node, ()):  # direct ancestors
            if dep in seen:
                continue  # defensive: ignore cycles (validated elsewhere)
            acc.add(dep)
            acc |= _walk(dep, seen | {dep})
        reach[node] = acc
        return acc

    for wp_id in dependencies:
        _walk(wp_id, {wp_id})
    return reach


def validate_no_overlap(
    manifests: dict[str, OwnershipManifest],
    dependencies: Mapping[str, list[str]] | None = None,
) -> list[str]:
    """Check that no two *concurrent* WPs have overlapping owned_files patterns.

    Codebase-wide WPs are excluded (they are expected to overlap with
    everything). When *dependencies* is supplied, **same-lane sequential** WPs —
    those with a directed dependency path between them — are also exempt: a
    linearized refactor chain shares one execution worktree and runs in
    dependency order, so two such WPs legitimately own the same files. The
    no-overlap guard exists to stop *parallel* (dependency-unordered) WPs from
    colliding, so only concurrent pairs are flagged. Lane computation separately
    groups WPs with overlapping write scopes, including sequential pairs, in
    one lane; this validation exemption does not override lane placement.
    When *dependencies* is ``None`` the legacy all-pairs behaviour is preserved.

    Args:
        manifests: Mapping of WP ID (e.g. ``"WP01"``) to its OwnershipManifest.
        dependencies: Optional mapping of WP ID to the WP ids it depends on.
            Used to exempt sequential (same-lane) pairs from the overlap check.

    Returns:
        List of error messages.  Empty list means no disallowed overlaps.
    """
    errors: list[str] = []

    # Filter out codebase-wide WPs -- they are allowed to overlap with anything.
    narrow_manifests = {
        wp_id: m for wp_id, m in manifests.items() if not m.is_codebase_wide
    }
    skipped = set(manifests.keys()) - set(narrow_manifests.keys())
    for wp_id in sorted(skipped):
        logger.info("Skipping overlap check for %s (codebase-wide scope)", wp_id)

    reach = _dependency_reachability(dependencies) if dependencies else {}

    wp_ids = list(narrow_manifests.keys())

    for wp_a, wp_b in combinations(wp_ids, 2):
        # Same-lane sequential pair (a directed dependency path exists either
        # way) → never concurrent → sharing owned_files is legitimate.
        if reach and (wp_b in reach.get(wp_a, ()) or wp_a in reach.get(wp_b, ())):
            logger.info(
                "Skipping overlap check for sequential pair %s/%s (dependency-ordered)",
                wp_a,
                wp_b,
            )
            continue

        manifest_a = narrow_manifests[wp_a]
        manifest_b = narrow_manifests[wp_b]

        for glob_a in manifest_a.owned_files:
            for glob_b in manifest_b.owned_files:
                if _globs_overlap(glob_a, glob_b):
                    errors.append(
                        f"Overlap: {wp_a} ({glob_a!r}) and {wp_b} ({glob_b!r}) "
                        f"claim overlapping paths."
                    )

    return errors


def validate_authoritative_surface(manifest: OwnershipManifest) -> list[str]:
    """Check that authoritative_surface is a prefix of at least one owned_files entry.

    Codebase-wide WPs are skipped -- they may have broad authoritative_surface
    values like ``"/"`` that do not follow the narrow prefix convention.

    Args:
        manifest: The OwnershipManifest to validate.

    Returns:
        List of error messages.  Empty list means the manifest is valid.
    """
    if manifest.is_codebase_wide:
        return []

    errors: list[str] = []
    surface = manifest.authoritative_surface

    if not surface:
        errors.append("authoritative_surface is empty.")
        return errors

    for pattern in manifest.owned_files:
        if pattern == surface or pattern.startswith(surface):
            return []  # At least one match — valid

    errors.append(
        f"authoritative_surface {surface!r} is not a prefix of any owned_files entry: "
        f"{list(manifest.owned_files)!r}"
    )
    return errors


def validate_execution_mode_consistency(manifest: OwnershipManifest) -> list[str]:
    """Warn when owned_files are inconsistent with execution_mode.

    These are warnings, not hard errors, because users can manually override
    inferred values.  Codebase-wide WPs are exempt because an audit WP may
    legitimately mix code and planning paths.

    Args:
        manifest: The OwnershipManifest to check.

    Returns:
        List of warning messages.  Empty list means no inconsistencies found.
    """
    if manifest.is_codebase_wide:
        return []

    warnings: list[str] = []

    if manifest.execution_mode == WorkProductKind.PLANNING_ARTIFACT:
        # All owned_files should be under kitty-specs/ or docs/
        bad = [
            p
            for p in manifest.owned_files
            if not any(p.startswith(prefix) for prefix in _PLANNING_PREFIXES)
        ]
        if bad:
            warnings.append(
                f"planning_artifact WP owns files outside planning paths "
                f"(kitty-specs/, docs/): {bad!r}"
            )

    elif manifest.execution_mode == WorkProductKind.CODE_CHANGE:
        # At least one owned_files entry should be under src/ or tests/ (not kitty-specs-only)
        has_code_path = any(
            p.startswith(prefix) for p in manifest.owned_files for prefix in _CODE_PREFIXES
        )
        if manifest.owned_files and not has_code_path:
            warnings.append(
                f"code_change WP does not own any files under src/ or tests/. "
                f"owned_files: {list(manifest.owned_files)!r}"
            )

    return warnings


def validate_all(
    manifests: dict[str, OwnershipManifest],
    dependencies: Mapping[str, list[str]] | None = None,
) -> ValidationResult:
    """Run all ownership validations across every WP in a feature.

    Args:
        manifests: Mapping of WP ID to OwnershipManifest.
        dependencies: Optional mapping of WP ID to the WP ids it depends on.
            When supplied, same-lane sequential (dependency-ordered) WPs are
            exempt from the owned_files overlap check — only concurrent
            (parallel-lane) WPs must not share files.

    Returns:
        A ValidationResult with errors (hard) and warnings (soft).
    """
    result = ValidationResult()

    # Cross-WP: overlap detection (hard error) — concurrent pairs only when a
    # dependency graph is supplied.
    result.errors.extend(validate_no_overlap(manifests, dependencies))

    # Per-WP: authoritative_surface prefix (hard error)
    # Per-WP: execution_mode consistency (warning)
    for wp_id, manifest in manifests.items():
        surface_errors = validate_authoritative_surface(manifest)
        result.errors.extend(f"{wp_id}: {e}" for e in surface_errors)

        mode_warnings = validate_execution_mode_consistency(manifest)
        result.warnings.extend(f"{wp_id}: {w}" for w in mode_warnings)

    return result


def build_wp_manifests(
    frontmatters: Mapping[str, WPMetadata],
) -> dict[str, OwnershipManifest]:
    """Build ownership manifests from WP frontmatter, ready for validation.

    This is the pure, filesystem-free seam between WP frontmatter and ownership
    validation. WPs that do not declare ownership (no ``execution_mode`` or empty
    ``owned_files``) are skipped, mirroring finalize-tasks. Because
    :meth:`OwnershipManifest.from_frontmatter` carries the ``scope`` field
    through (including ``codebase-wide``), callers can exercise the full
    overlap/exemption decision with plain ``WPMetadata`` stubs — no temp files,
    no finalize-command mocking.

    Args:
        frontmatters: Mapping of WP ID to its parsed ``WPMetadata``.

    Returns:
        Mapping of WP ID to ``OwnershipManifest`` for WPs that declare ownership.
    """
    manifests: dict[str, OwnershipManifest] = {}
    for wp_id, fm in frontmatters.items():
        if fm.execution_mode and fm.owned_files:
            manifests[wp_id] = OwnershipManifest.from_frontmatter(fm)
    return manifests


# Public alias used by __init__.py
validate_ownership = validate_all


def _nearest_match_suggestion(pattern: str, repo_root: Path) -> str | None:
    """Return a nearest-match suggestion for a literal path that exists nowhere.

    Collects all files under the pattern's parent directory (if the parent
    exists) and uses :func:`difflib.get_close_matches` to find the closest
    name.  Returns a formatted hint string or ``None`` when no candidates
    are available.
    """
    path = Path(pattern)
    parent = repo_root / path.parent
    if not parent.is_dir():
        return None
    siblings = [str(p.relative_to(repo_root)) for p in parent.iterdir() if p.is_file()]
    matches = difflib.get_close_matches(pattern, siblings, n=1, cutoff=0.5)
    if matches:
        return f"Did you mean '{matches[0]}'?"
    return None


def validate_glob_matches(
    manifests: dict[str, OwnershipManifest],
    repo_root: Path,
    create_intent: dict[str, list[str]] | None = None,
) -> GlobValidationResult:
    """Check owned_files entries against the repository for zero-match conditions.

    Classifies each entry as a literal path or a glob pattern, then applies
    different severity rules:

    - **Literal path + zero matches** → hard error (exit 1), with a
      nearest-match suggestion when one can be found.  Suppressed (becomes an
      info note) when the path appears in *create_intent* for that WP.
    - **Glob pattern + zero matches** → soft warning (may be in-flight work).

    Args:
        manifests: Mapping of WP ID to OwnershipManifest.
        repo_root: Root directory of the repository for glob resolution.
        create_intent: Optional mapping of WP ID → list of paths that are
            planned-new-file entries.  A literal-path zero-match whose path
            appears in this list is suppressed (no hard error).

    Returns:
        :class:`GlobValidationResult` with separate ``errors``, ``warnings``,
        and ``info`` lists.  Call sites should emit ``errors`` to stderr and
        exit 1 if ``result.passed`` is False.
    """
    _create_intent: dict[str, list[str]] = create_intent or {}
    result = GlobValidationResult()

    for wp_id in sorted(manifests):
        manifest = manifests[wp_id]
        wp_intent_paths = set(_create_intent.get(wp_id, []))

        for pattern in manifest.owned_files:
            matched = any(repo_root.glob(pattern))
            if matched:
                continue

            if is_glob_pattern(pattern):
                # Glob zero-match → soft warning only
                result.warnings.append(
                    f"{wp_id}: owned_files glob '{pattern}' matches "
                    f"zero files in the repository"
                )
            elif pattern in wp_intent_paths:
                # Literal path suppressed by create_intent
                result.info.append(
                    f"{wp_id}: owned_files path '{pattern}' has no match "
                    f"— suppressed by create_intent (planned-new-file)."
                )
            else:
                # Literal path zero-match → hard error
                suggestion = _nearest_match_suggestion(pattern, repo_root)
                msg = (
                    f"{wp_id}: owned_files path '{pattern}' is a literal "
                    f"file path that matches zero files in the repository."
                )
                if suggestion:
                    msg += f" {suggestion}"
                msg += (
                    " If this file will be created during implementation, "
                    f"declare it in the WP frontmatter:\n  create_intent:\n    - {pattern}"
                )
                result.errors.append(msg)

    return result
