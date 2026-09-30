"""State-roots diagnostic for spec-kitty CLI.

Resolves the three state roots (project, global_runtime, global_sync),
checks on-disk presence of every registered state surface, validates
gitignore coverage for repo-local runtime surfaces, and returns a
structured report.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specify_cli.paths import get_runtime_root
from specify_cli.state.contract import (
    STATE_SURFACES,
    AuthorityClass,
    GitClass,
    StateRoot,
    StateSurface,
)


# Documentation-only prefix carried by the declarative GLOBAL_SYNC surface
# patterns (e.g. ``~/.spec-kitty/config.toml``). The authoritative root is
# ``get_runtime_root().base`` (which honors ``SPEC_KITTY_HOME``); this prefix is
# stripped before joining so resolution never recomputes the home (FR-010).
_GLOBAL_SYNC_PATTERN_PREFIX = "~/.spec-kitty/"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class StateRootInfo:
    """Resolved state root with existence status."""

    name: str
    label: str
    resolved_path: Path
    exists: bool


@dataclass
class SurfaceCheckResult:
    """Result of checking a single state surface."""

    surface: StateSurface
    present: bool
    gitignore_covered: bool
    warning: str | None = None


@dataclass
class StateRootsReport:
    """Aggregated report from check_state_roots()."""

    roots: list[StateRootInfo] = field(default_factory=list)
    surfaces: list[SurfaceCheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """True when no warnings were generated."""
        return len(self.warnings) == 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "healthy": self.healthy,
            "roots": [
                {
                    "name": r.name,
                    "label": r.label,
                    "resolved_path": str(r.resolved_path),
                    "exists": r.exists,
                }
                for r in self.roots
            ],
            "surfaces": [
                {
                    "name": s.surface.name,
                    "path_pattern": s.surface.path_pattern,
                    "root": s.surface.root.value,
                    "authority": s.surface.authority.value,
                    "git_class": s.surface.git_class.value,
                    "present": s.present,
                    "gitignore_covered": s.gitignore_covered,
                    "warning": s.warning,
                }
                for s in self.surfaces
            ],
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_gitignore_covered(repo_root: Path, path: str) -> bool | None:
    """Check if a path is covered by .gitignore rules.

    Returns True if ignored, False if not ignored, None if git is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", path],
            cwd=str(repo_root),
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _check_surface_present(repo_root: Path, surface: StateSurface) -> bool:
    """Check if a surface exists on disk."""
    if surface.root == StateRoot.PROJECT:
        path = repo_root / surface.path_pattern
    elif surface.root == StateRoot.FEATURE:
        # Feature surfaces live under repo_root (e.g. kitty-specs/<feature>/...)
        path = repo_root / surface.path_pattern
    elif surface.root == StateRoot.GLOBAL_RUNTIME:
        if surface.path_pattern.startswith("~/"):
            # Resolve from home directory (handles both ~/.kittify/...
            # and siblings like ~/.kittify_update_*)
            relative = surface.path_pattern[2:]  # Strip ~/
            path = Path.home() / relative
        else:
            from specify_cli.runtime.home import get_kittify_home

            path = get_kittify_home() / surface.path_pattern
    elif surface.root == StateRoot.GLOBAL_SYNC:
        # Anchor global-sync surfaces at the authoritative runtime root, which
        # honors SPEC_KITTY_HOME. The declarative patterns keep their
        # documentation-only "~/.spec-kitty/" prefix; strip it before joining.
        sync_base = get_runtime_root().base
        if surface.path_pattern.startswith(_GLOBAL_SYNC_PATTERN_PREFIX):
            relative = surface.path_pattern[len(_GLOBAL_SYNC_PATTERN_PREFIX) :]
            path = sync_base / relative
        else:
            path = sync_base / surface.path_pattern
    elif surface.root == StateRoot.GIT_INTERNAL:
        # Resolve git common-dir (worktree-aware — .git may be a file, not a dir)
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            git_common = Path(result.stdout.strip())
            if not git_common.is_absolute():
                git_common = (repo_root / git_common).resolve()
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_common = repo_root / ".git"
        relative = surface.path_pattern.replace(".git/", "")
        path = git_common / relative
    else:
        return False

    # Handle wildcard and placeholder patterns
    if "*" in str(path):
        # Use glob to check for actual matches
        parent = path.parent
        pattern = path.name  # e.g., ".kittify_update_*"
        # Walk up past any placeholder parents
        while "<" in str(parent) or "*" in str(parent):
            pattern = parent.name + "/" + pattern
            parent = parent.parent
        return any(True for _ in parent.glob(pattern))
    elif "<" in str(path):
        # Placeholder paths (like <feature>) -- check parent dir existence
        parent = path.parent
        while "<" in str(parent):
            parent = parent.parent
        return parent.is_dir()

    return path.exists()


def _check_gitignore(repo_root: Path, surface: StateSurface) -> bool:
    """Check gitignore coverage for repo-local surfaces."""
    if surface.root not in (StateRoot.PROJECT,):
        return True  # Non-repo surfaces don't need gitignore
    if surface.git_class in (
        GitClass.TRACKED,
        GitClass.OUTSIDE_REPO,
        GitClass.GIT_INTERNAL,
    ):
        return True  # Tracked or external surfaces don't need gitignore

    result = _is_gitignore_covered(repo_root, surface.path_pattern)
    if result is None:
        return True  # Can't verify, don't warn
    return result


def _generate_warning(
    surface: StateSurface, present: bool, gitignore_covered: bool
) -> str | None:
    """Generate a warning if a runtime surface is present but not ignored."""
    if surface.root != StateRoot.PROJECT:
        return None
    if surface.git_class in (
        GitClass.TRACKED,
        GitClass.OUTSIDE_REPO,
        GitClass.GIT_INTERNAL,
    ):
        return None
    if surface.authority not in (AuthorityClass.LOCAL_RUNTIME, AuthorityClass.DERIVED):
        return None
    if not present:
        return None
    if gitignore_covered:
        return None

    return (
        f"{surface.name} ({surface.path_pattern}) is present but not gitignored. "
        f"Authority: {surface.authority.value}. Risk: accidental commit."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_state_roots(repo_root: Path) -> StateRootsReport:
    """Run state-roots diagnostic and return a structured report.

    Resolves the three state roots, checks surface presence on disk,
    validates gitignore coverage for repo-local runtime surfaces, and
    collects warnings.

    Args:
        repo_root: Path to the project repository root.

    Returns:
        A StateRootsReport with roots, surfaces, and any warnings.
    """
    from specify_cli.runtime.home import get_kittify_home

    report = StateRootsReport()

    # Resolve roots
    project_root = repo_root / ".kittify"
    global_runtime = get_kittify_home()
    # Authoritative runtime root (honors SPEC_KITTY_HOME); never recompute the
    # default home independently (FR-010).
    global_sync = get_runtime_root().base

    report.roots = [
        StateRootInfo(
            "project", "Project-local state", project_root, project_root.is_dir()
        ),
        StateRootInfo(
            "global_runtime",
            "Global runtime home",
            global_runtime,
            global_runtime.is_dir(),
        ),
        StateRootInfo(
            "global_sync", "Global sync/auth home", global_sync, global_sync.is_dir()
        ),
    ]

    # Check each surface
    for surface in STATE_SURFACES:
        present = _check_surface_present(repo_root, surface)
        gitignore_covered = _check_gitignore(repo_root, surface)
        warning = _generate_warning(surface, present, gitignore_covered)

        result = SurfaceCheckResult(
            surface=surface,
            present=present,
            gitignore_covered=gitignore_covered,
            warning=warning,
        )
        report.surfaces.append(result)

        if warning:
            report.warnings.append(warning)

    return report
