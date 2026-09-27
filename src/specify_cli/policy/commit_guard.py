"""Pre-commit ownership guard.

Validates that staged files in a worktree belong to the WP's owned_files
scope and blocks modifications to kitty-specs/ from implementation branches.
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR, is_occurrence_map_path
import fnmatch
from dataclasses import dataclass, field

from specify_cli.lanes.branch_naming import is_lane_branch
from specify_cli.policy.config import CommitGuardConfig


@dataclass
class CommitGuardResult:
    """Result of pre-commit guard validation."""

    allowed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OwnershipScope:
    """Active WP ownership context resolved at guard invocation time."""

    owned_files: list[str]
    active_wp_id: str | None = None
    lane_id: str | None = None
    context_source: str = "absent"
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None
    warnings: list[str] = field(default_factory=list)


def is_implementation_branch(branch_name: str) -> bool:
    """Return True if the branch is a lane implementation branch.

    Delegates to the naming authority's :func:`is_lane_branch` (FR-008):
    matches legacy, plain-legacy and new lane grammars, and every lane-id
    width the authority's single grammar fragment accepts.
    """
    return is_lane_branch(branch_name)


def validate_staged_files(
    staged_files: list[str],
    owned_files: list[str],
    branch_name: str,
    policy: CommitGuardConfig,
    ownership_scope: OwnershipScope | None = None,
) -> CommitGuardResult:
    """Validate staged files against ownership and protected path rules.

    Args:
        staged_files: Relative paths of files staged for commit.
        owned_files: Glob patterns from WP frontmatter.
        branch_name: Current git branch name.
        policy: Commit guard configuration.
        ownership_scope: Active WP context resolved at guard invocation time.

    Returns:
        CommitGuardResult with allowed status and any violations.
    """
    if not policy.enabled or policy.mode == "off":
        return CommitGuardResult(allowed=True)

    if not is_implementation_branch(branch_name):
        return CommitGuardResult(allowed=True)

    violations: list[str] = []
    warnings = list(ownership_scope.warnings) if ownership_scope else []
    effective_owned_files = list(ownership_scope.owned_files) if ownership_scope else owned_files

    if policy.enforce_ownership and ownership_scope and ownership_scope.diagnostic_code:
        violations.append(ownership_scope.diagnostic_message or _format_context_diagnostic(ownership_scope))

    # Check kitty-specs/ protection.
    # #2980: a bulk-edit mission's own occurrence map is the single permitted
    # kitty-specs/ lane write (DIRECTIVE_035). The exception is expressed once in
    # ``is_occurrence_map_path`` and honored identically by the move-task
    # lane-hygiene guard, so the two guards no longer disagree on it.
    if policy.block_mission_specs:
        for f in staged_files:
            if f.startswith(f"{KITTY_SPECS_DIR}/") and not is_occurrence_map_path(f):
                violations.append(f"Protected path: {f} — implementation branches must not modify kitty-specs/")

    # Check ownership enforcement.
    if policy.enforce_ownership and ownership_scope and ownership_scope.active_wp_id and not effective_owned_files and not ownership_scope.diagnostic_code:
        violations.append(
            "ACTIVE_WP_OWNERSHIP_MISSING: "
            f"active_wp={ownership_scope.active_wp_id} has no owned_files; "
            f"lane_id={ownership_scope.lane_id or 'unknown'}; "
            f"context_source={ownership_scope.context_source}"
        )

    if policy.enforce_ownership and effective_owned_files and not (ownership_scope and ownership_scope.diagnostic_code):
        for f in staged_files:
            if f.startswith(f"{KITTY_SPECS_DIR}/"):
                continue  # Already flagged above
            if not _matches_any_glob(f, effective_owned_files):
                violations.append(_format_scope_violation(f, effective_owned_files, ownership_scope))

    if not violations:
        return CommitGuardResult(allowed=True, warnings=warnings)

    if policy.mode == "warn":
        return CommitGuardResult(allowed=True, warnings=warnings + violations)

    # mode == "block"
    return CommitGuardResult(allowed=False, violations=violations, warnings=warnings)


def _format_context_diagnostic(scope: OwnershipScope) -> str:
    return (
        f"{scope.diagnostic_code}: Cannot prove active WP for ownership guard; "
        f"active_wp={scope.active_wp_id or 'unknown'}; "
        f"lane_id={scope.lane_id or 'unknown'}; "
        f"context_source={scope.context_source}"
    )


def _format_scope_violation(
    filepath: str,
    owned_files: list[str],
    ownership_scope: OwnershipScope | None,
) -> str:
    if ownership_scope and ownership_scope.active_wp_id:
        return (
            f"ACTIVE_WP_SCOPE_VIOLATION: {filepath} is outside "
            f"active_wp={ownership_scope.active_wp_id} owned_files {owned_files}; "
            f"lane_id={ownership_scope.lane_id or 'unknown'}; "
            f"context_source={ownership_scope.context_source}"
        )
    return f"Out of scope: {filepath} — not matched by owned_files {owned_files}"


def _matches_any_glob(filepath: str, patterns: list[str]) -> bool:
    """Check if filepath matches any of the ownership glob patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(filepath, pattern):
            return True
        # Also check prefix match for ** patterns.
        prefix = pattern.replace("/**", "").replace("/*", "").rstrip("/")
        if prefix and filepath.startswith(prefix + "/"):
            return True
    return False
