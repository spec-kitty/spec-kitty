"""Worktree management utilities for spec-kitty feature development.

This module provides functions for creating and managing workspaces (git worktrees)
for parallel feature development. Uses the VCS abstraction layer.

All functions are location-aware and work correctly whether called from main
repository or existing worktree/workspace.

Workspace routing by execution_mode:
- ``code_change`` WPs  → standard git worktree (full checkout, no sparse exclusions)
- ``planning_artifact`` WPs → in-repo workspace (``repo_root`` returned directly)
"""

from __future__ import annotations

import contextlib
import logging
import re
import shutil
import subprocess
import warnings
from pathlib import Path
from typing import Any

from kernel.paths import is_windows

from .constants import KITTIFY_DIR, KITTY_SPECS_DIR, WORKTREES_DIR
from .git_preflight import GitPreflightError
from .vcs import get_vcs
from specify_cli.ownership.models import WorkProductKind
from specify_cli.ownership.workspace_strategy import create_planning_workspace
from specify_cli.status import WPMetadata

logger = logging.getLogger(__name__)


def _ensure_spec_kitty_exclude(worktree_path: Path) -> None:
    """Ensure ``.spec-kitty/`` is listed in the worktree's ``info/exclude`` file.

    FR-016 (legacy-sparse-and-review-lock-hardening, WP07): the per-worktree
    exclude file at ``<git-common-dir>/worktrees/<name>/info/exclude`` is a
    belt-and-braces defense against spec-kitty's own runtime-state directory
    showing up as untracked content in the worktree's ``git status`` output.
    Even when the higher-level deny-list filter regresses, the exclude file
    keeps git itself from surfacing ``.spec-kitty/`` as drift.

    This is a no-op when:
        * ``worktree_path`` is not a git repo (``git rev-parse --git-dir``
          fails);
        * the ``.spec-kitty/`` entry is already present (idempotent; the
          helper never duplicates lines on re-invocation).

    Detection / write failures are swallowed — this is an advisory writer,
    not a preflight, and must never break worktree creation.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        logger.debug(
            "Could not resolve git-dir for %s; skipping spec-kitty exclude setup",
            worktree_path,
        )
        return
    if result.returncode != 0:
        logger.debug(
            "git rev-parse --git-dir failed for %s (rc=%s); skipping spec-kitty exclude setup",
            worktree_path,
            result.returncode,
        )
        return
    git_dir_raw = result.stdout.strip()
    if not git_dir_raw:
        return
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = (worktree_path / git_dir).resolve()
    info_dir = git_dir / "info"
    try:
        info_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    exclude_path = info_dir / "exclude"

    existing_lines: list[str] = []
    if exclude_path.exists():
        try:
            existing_lines = exclude_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return

    if any(line.strip() == ".spec-kitty/" for line in existing_lines):
        return

    existing_lines.append(".spec-kitty/")
    try:
        exclude_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")
    except OSError:
        # If we can't write, just skip - not critical (FR-016 is belt-and-braces).
        return


def _exclude_from_git(worktree_path: Path, patterns: list[str]) -> None:
    """Add patterns to worktree's .git/info/exclude to prevent committing.

    This prevents symlinks created in worktrees from being committed and
    overwriting real files in main on merge (fixes issue #79).

    Args:
        worktree_path: Path to the worktree root
        patterns: List of patterns to exclude (e.g., [".kittify/memory"])
    """
    # In a worktree, .git is a file pointing to the real git dir
    git_path = worktree_path / ".git"
    if not git_path.exists():
        return

    # Find the actual git directory
    if git_path.is_file():
        # Worktree: .git file contains "gitdir: /path/to/real/.git/worktrees/name"
        try:
            content = git_path.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                git_dir = Path(content[7:].strip())
                exclude_file = git_dir / "info" / "exclude"
            else:
                return
        except (OSError, ValueError):
            return
    else:
        # Regular repo or already resolved
        exclude_file = git_path / "info" / "exclude"

    # Ensure info directory exists
    exclude_file.parent.mkdir(parents=True, exist_ok=True)

    # Read existing exclusions
    existing: set[str] = set()
    if exclude_file.exists():
        with contextlib.suppress(OSError):
            existing = set(exclude_file.read_text(encoding="utf-8").splitlines())

    # Add new patterns if not already present
    new_patterns = [p for p in patterns if p not in existing]
    if new_patterns:
        try:
            with exclude_file.open("a", encoding="utf-8") as f:
                # Add comment if this is our first addition
                marker = "# Added by spec-kitty (worktree symlinks)"
                if marker not in existing:
                    f.write(f"\n{marker}\n")
                for pattern in new_patterns:
                    f.write(f"{pattern}\n")
        except OSError:
            # If we can't write, just skip - not critical
            pass


def create_wp_workspace(
    repo_root: Path,
    workspace_path: Path,
    workspace_name: str,
    wp_frontmatter: WPMetadata,
) -> Path:
    """Create a workspace for a work package, routing by execution_mode.

    Routes workspace creation based on the WP's ``execution_mode`` field
    from the ownership manifest embedded in its frontmatter:

    * ``code_change``        → creates a standard git worktree at ``workspace_path``
    * ``planning_artifact``  → returns ``repo_root`` (work directly in-repo, no
      worktree created, full repo visible)

    Args:
        repo_root: Absolute path to the repository root.
        workspace_path: Where a ``code_change`` worktree would be created.
        workspace_name: Branch name for a ``code_change`` worktree.
        wp_frontmatter: Parsed WP frontmatter as typed :class:`WPMetadata`.

    Returns:
        Path to the workspace.  For ``code_change`` this is ``workspace_path``
        (after creation); for ``planning_artifact`` this is ``repo_root``.

    Raises:
        RuntimeError: If worktree creation fails for a ``code_change`` WP.
        FileExistsError: If ``workspace_path`` already exists and is not a
            valid git worktree (``code_change`` only).
    """
    raw_mode = wp_frontmatter.execution_mode or WorkProductKind.CODE_CHANGE
    owned_files_raw: list[str] = list(wp_frontmatter.owned_files)
    wp_code = wp_frontmatter.work_package_id
    mission_slug = wp_frontmatter.feature_slug or ""

    try:
        mode = WorkProductKind(raw_mode)
    except ValueError:
        mode = WorkProductKind.CODE_CHANGE

    if mode == WorkProductKind.PLANNING_ARTIFACT:
        result_path = create_planning_workspace(
            mission_slug=mission_slug,
            wp_code=wp_code,
            owned_files=list(owned_files_raw) if isinstance(owned_files_raw, (list, tuple)) else [],
            repo_root=repo_root,
        )
        return Path(result_path)

    # code_change: create a standard git worktree (full checkout)
    workspace_path.parent.mkdir(parents=True, exist_ok=True)

    if workspace_path.exists():
        # Reuse if it is already a valid worktree
        git_marker = workspace_path / ".git"
        if git_marker.exists():
            return workspace_path
        raise FileExistsError(f"Workspace path already exists but is not a worktree: {workspace_path}")

    vcs = get_vcs(repo_root)
    result = vcs.create_workspace(
        workspace_path=workspace_path,
        workspace_name=workspace_name,
        base_branch=wp_frontmatter.base_branch,
        base_commit=wp_frontmatter.base_commit,
        repo_root=repo_root,
    )

    if not result.success:
        raise RuntimeError(f"Failed to create workspace: {result.error}")

    # FR-016 (WP07): write ``.spec-kitty/`` to the per-worktree exclude file so
    # git never surfaces spec-kitty's own runtime-state directory as drift.
    _ensure_spec_kitty_exclude(workspace_path)

    return workspace_path


def _existing_worktree_is_valid(worktree_path: Path) -> bool:
    """Return True when an existing path is a usable git worktree.

    Prefers the VCS abstraction's ``is_repo`` check and falls back to a simple
    ``.git`` marker probe when the abstraction is unavailable or errors. A valid
    git worktree has ``.git`` as a file (pointing to the main repo) or directory
    (standalone repo).
    """
    is_valid_workspace = False
    try:
        vcs = get_vcs(worktree_path)
        is_valid_workspace = vcs.is_repo(worktree_path)
    except Exception:
        logger.debug("VCS check failed for %s, falling back to .git marker", worktree_path, exc_info=True)

    if not is_valid_workspace:
        git_marker = worktree_path / ".git"
        is_valid_workspace = git_marker.exists()
    return is_valid_workspace


def _create_workspace_with_fallback(repo_root: Path, worktree_path: Path, branch_name: str) -> None:
    """Create the worktree via the VCS abstraction, falling back to direct git.

    Get VCS implementation and create the workspace (full checkout, no sparse
    exclusions). Deterministic preflight failures re-raise without attempting
    the legacy direct-git fallback (it would hit the same blocking condition);
    non-deterministic ones raise ``RuntimeError`` or trigger the git fallback.
    """
    try:
        vcs = get_vcs(repo_root)
        result = vcs.create_workspace(
            workspace_path=worktree_path,
            workspace_name=branch_name,
            repo_root=repo_root,
        )

        if not result.success:
            # Always construct the typed error first so we can branch on
            # ``exc.is_deterministic`` — the canonical API (NFR-007).
            # Deterministic failures (untrusted repo, missing repo,
            # worktree-enumeration) cannot be recovered by the legacy
            # direct-git fallback; non-deterministic ones raise RuntimeError.
            exc = GitPreflightError(
                f"Failed to create workspace: {result.error}",
                error_code=result.error_code or "",
            )
            if exc.is_deterministic:
                raise exc
            raise RuntimeError(f"Failed to create workspace: {result.error}")

    except GitPreflightError:
        # Deterministic preflight failure — re-raise without attempting the
        # legacy direct-git fallback (it would hit the same blocking condition).
        raise
    except Exception as e:
        # If VCS abstraction fails, fall back to direct git command with warning
        warnings.warn(
            f"VCS abstraction failed ({type(e).__name__}: {e}); falling back to direct git commands. See: VCS abstraction layer documentation",
            DeprecationWarning,
            stacklevel=2,
        )
        try:
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), "-b", branch_name],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.CalledProcessError as git_error:
            raise RuntimeError(f"Failed to create workspace: {git_error.stderr}") from git_error


def _compose_worktree_feature_dir(worktree_path: Path, branch_name: str) -> Path:
    """Compose the feature-directory path inside a lane worktree (C-PLACEMENT / FR-002).

    Single canonical seam for the ``worktree_path / kitty-specs / <dir>``
    placement join.  ``branch_name`` MUST come from the ``mission_dir_name``
    naming seam (``specify_cli.lanes.branch_naming.mission_dir_name``) —
    **never** re-derived inline.  The on-disk placement path is therefore
    determined once, here, and is byte-identical across the reuse arm and
    the create arm (NFR-004 / idempotency).

    This seam is aligned with the factory placement projection
    (``mission_runtime.resolution.resolve_placement_only``) as the write-side
    canonical authority (D-12): read and write both resolve placement from the
    same naming seam rather than from ad-hoc inline joins.

    Args:
        worktree_path: The root of the lane worktree
            (``repo_root / .worktrees / <branch_name>``).
        branch_name: The worktree directory name produced by
            ``mission_dir_name(mission_slug, mid8=...)``.

    Returns:
        The ``kitty-specs/<branch_name>`` directory path inside the worktree.
    """
    return worktree_path / str(KITTY_SPECS_DIR) / branch_name


def create_feature_worktree(
    repo_root: Path,
    mission_slug: str,
    mission_id: str | None = None,
) -> tuple[Path, Path]:
    """Create workspace (git worktree) for feature development.

    Creates a new workspace with a feature branch and sets up the
    feature directory structure. Uses VCS abstraction.

    The worktree is named ``<human-slug>-<mid8>[-lane-<id>]`` using the new
    identity-stable format (FR-033).  The ``mission_id`` is required; if it
    is missing, the call fails with a clear error pointing at the backfill
    command (FR-052 edge case).

    Args:
        repo_root: Repository root path
        mission_slug: Feature identifier (e.g., "083-foo-bar" or "foo-bar").
        mission_id: ULID from ``meta.json``.  Required.  Must be present for
            new and backfilled legacy missions; raise on missing (FR-052).

    Returns:
        Tuple of (worktree_path, feature_dir)

    Raises:
        RuntimeError: If workspace creation fails or ``mission_id`` is missing.
        FileExistsError: If worktree path already exists.

    Examples:
        >>> repo_root = Path("/path/to/repo")
        >>> worktree, feature_dir = create_feature_worktree(
        ...     repo_root, "new-feature", mission_id="01KNXQS9ATWWFXS3K5ZJ9E5008"
        ... )
        >>> assert worktree.exists()
        >>> assert feature_dir.exists()
    """
    if not mission_id:
        raise RuntimeError(
            "create_feature_worktree requires mission_id from meta.json. "
            "For legacy missions that pre-date mission_id, run "
            "`spec-kitty migrate backfill-identity` first."
        )

    from specify_cli.lanes.branch_naming import mission_dir_name, resolve_mid8

    # resolve_mid8 derives the mid8 from the declared mission_id (authoritative,
    # FR-004/NFR-003); mission_dir_name composes <human-slug>-<mid8> canonically,
    # stripping any NNN- prefix.  The mid8 derivation MOVES here — it is not
    # removed — so the compose is byte-identical to the prior inline f-string.
    branch_name = mission_dir_name(
        mission_slug,
        mid8=resolve_mid8("", mission_id=mission_id),
    )

    # Create worktree at .worktrees/<human-slug>-<mid8>
    worktree_path = repo_root / WORKTREES_DIR / branch_name

    # Ensure .worktrees directory exists
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if worktree already exists
    if worktree_path.exists():
        if _existing_worktree_is_valid(worktree_path):
            feature_dir = _compose_worktree_feature_dir(worktree_path, branch_name)
            return (worktree_path, feature_dir)
        raise FileExistsError(f"Worktree path already exists: {worktree_path}")

    _create_workspace_with_fallback(repo_root, worktree_path, branch_name)

    # FR-016 (WP07): write ``.spec-kitty/`` to the per-worktree exclude file so
    # git never surfaces spec-kitty's own runtime-state directory as drift in
    # the lane worktree. Invoked once, immediately after the worktree exists.
    _ensure_spec_kitty_exclude(worktree_path)

    # Create feature directory structure (FR-002 / C-PLACEMENT)
    feature_dir = _compose_worktree_feature_dir(worktree_path, branch_name)
    feature_dir.mkdir(parents=True, exist_ok=True)

    # Setup feature directory (symlinks, subdirectories, etc.)
    setup_feature_directory(feature_dir, worktree_path, repo_root)

    return (worktree_path, feature_dir)


def setup_feature_directory(feature_dir: Path, worktree_path: Path, repo_root: Path, create_symlinks: bool = True) -> None:
    """Setup standard feature directory structure.

    Creates:
    - kitty-specs/###-name/ directory
    - Subdirectories: checklists/, research/, tasks/
    - Symlinks to .kittify/memory/ (or file copies on Windows)
    - spec.md from template
    - tasks/README.md

    Args:
        feature_dir: Feature directory path
        worktree_path: Worktree root path
        repo_root: Main repository root path
        create_symlinks: If True, create symlinks; else copy files (Windows)

    Examples:
        >>> feature_dir = Path("/path/to/.worktrees/001-feature/kitty-specs/001-feature")
        >>> setup_feature_directory(feature_dir, feature_dir.parent.parent, repo_root)
        >>> assert (feature_dir / "checklists").exists()
    """
    # Ensure feature directory exists
    feature_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (feature_dir / "checklists").mkdir(exist_ok=True)
    (feature_dir / "research").mkdir(exist_ok=True)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    # Create tasks/.gitkeep and README.md
    (tasks_dir / ".gitkeep").touch()

    # Create tasks/README.md with frontmatter format reference
    tasks_readme_content = """# Tasks Directory

This directory contains work package (WP) prompt files.

## Directory Structure (v0.9.0+)

```
tasks/
├── WP01-setup-infrastructure.md
├── WP02-user-authentication.md
├── WP03-api-endpoints.md
└── README.md
```

All WP files are stored flat in `tasks/`.

## Status Tracking

Status is tracked in `status.events.jsonl`, not in WP frontmatter.
Use `spec-kitty agent tasks move-task` to change WP status.

## Work Package File Format

Each WP file **MUST** use YAML frontmatter:

```yaml
---
work_package_id: "WP01"
title: "Work Package Title"
subtasks:
  - "T001"
  - "T002"
phase: "Phase 1 - Setup"
assignee: ""
agent: ""
shell_pid: ""
history:
  - at: "2025-01-01T00:00:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP01 -- Work Package Title

[Content follows...]
```

## Moving Between Lanes

Use the CLI to emit a status transition event:
```bash
spec-kitty agent tasks move-task <WPID> --to <lane>
```

Example:
```bash
spec-kitty agent tasks move-task WP01 --to doing
```

## File Naming

- Format: `WP01-kebab-case-slug.md`
- Examples: `WP01-setup-infrastructure.md`, `WP02-user-auth.md`
"""
    (tasks_dir / "README.md").write_text(tasks_readme_content, encoding="utf-8")

    # Create worktree .kittify directory if it doesn't exist
    worktree_kittify = worktree_path / KITTIFY_DIR
    worktree_kittify.mkdir(exist_ok=True)

    # Setup shared team-memory store (.kittify/memory/) and AGENTS.md via symlink
    # (or copy on Windows). The charter itself lives separately at
    # .kittify/charter/ and is not part of this symlink.
    # Calculate relative path from worktree to main repo
    # Worktree: .worktrees/001-feature/.kittify/memory
    # Main:     .kittify/memory
    # Relative: ../../../.kittify/memory
    relative_memory_path = Path("../../../.kittify/memory")
    relative_agents_path = Path("../../../.kittify/AGENTS.md")

    worktree_memory = worktree_kittify / "memory"
    worktree_agents = worktree_kittify / "AGENTS.md"

    # Detect if we're on Windows or symlinks are not supported
    on_windows = is_windows()
    use_copy = on_windows or not create_symlinks

    # Setup memory/ symlink or copy
    if worktree_memory.is_symlink():
        # Remove existing symlink first (can't use rmtree on symlinks)
        worktree_memory.unlink()
    elif worktree_memory.exists() and worktree_memory.is_dir():
        # Remove existing directory (from git worktree add)
        shutil.rmtree(worktree_memory)

    if use_copy:
        # Copy memory directory
        main_memory = repo_root / KITTIFY_DIR / "memory"
        if main_memory.exists() and main_memory.is_dir():
            shutil.copytree(main_memory, worktree_memory)
    else:
        # Create relative symlink
        try:
            worktree_memory.symlink_to(relative_memory_path, target_is_directory=True)
        except (OSError, NotImplementedError):
            # Symlink failed, fall back to copy
            main_memory = repo_root / KITTIFY_DIR / "memory"
            if main_memory.exists() and main_memory.is_dir():
                shutil.copytree(main_memory, worktree_memory)

    # Setup AGENTS.md symlink or copy
    if worktree_agents.exists():
        worktree_agents.unlink()

    main_agents = repo_root / KITTIFY_DIR / "AGENTS.md"
    if main_agents.exists():
        if use_copy:
            shutil.copy2(main_agents, worktree_agents)
        else:
            try:
                worktree_agents.symlink_to(relative_agents_path)
            except (OSError, NotImplementedError):
                shutil.copy2(main_agents, worktree_agents)

    # Exclude symlinks from git to prevent them from being committed
    # This fixes issue #79: symlinks overwriting main repo files on merge
    _exclude_from_git(worktree_path, [".kittify/memory", ".kittify/AGENTS.md"])

    # Copy spec template if it exists
    spec_file = feature_dir / "spec.md"
    if not spec_file.exists():
        # Try to find spec template
        spec_template_candidates = [
            repo_root / KITTIFY_DIR / "templates" / "spec-template.md",
            repo_root / "templates" / "spec-template.md",
        ]

        for template in spec_template_candidates:
            if template.exists():
                shutil.copy2(template, spec_file)
                break
        # No template found: leave spec.md absent rather than creating a
        # zero-byte stray file that would vacuously satisfy the per-type
        # artifact presence gate (#228; #223 residue).


# Structural directories that anchor a mission's layout regardless of the
# writer-declared artifact set (WP prompt files, checklist stubs). These are
# NOT the artifact inventory (which is sourced from the mission writer metadata
# in ``_feature_writer_artifacts``); they are recommended-layout anchors whose
# presence/absence drives warnings and the ``*_dir`` path aliases.
_RECOMMENDED_LAYOUT_DIRS: tuple[str, ...] = ("checklists", "research", "tasks")
_STRUCTURAL_ARTIFACT_DIRS: tuple[str, ...] = ("checklists", "tasks")


def _artifact_inventory_key(artifact_name: str, suffix: str) -> str:
    """Derive a stable inventory key (e.g. ``research_file``, ``contracts_dir``).

    ``spec.md`` -> ``spec_file``; ``data-model.md`` -> ``data_model_file``;
    ``contracts/`` -> ``contracts_dir``. Non-alphanumerics collapse to ``_`` so
    the key is a valid, deterministic identifier.
    """
    stem = artifact_name.rstrip("/")
    if not artifact_name.endswith("/"):
        stem = stem.rsplit(".", 1)[0]
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", stem).strip("_").lower()
    return f"{slug}_{suffix}"


def _feature_writer_artifacts(feature_dir: Path) -> tuple[list[str], list[str]]:
    """Return ``(file_artifacts, dir_artifacts)`` from the canonical mission
    writer metadata (mission.yaml ``artifacts``) for ``feature_dir``'s mission.

    Sources the inventory from a single canonical writer schema (C-005 / FR-010),
    never a hardcoded key set. Resolves the mission recorded in the feature's
    ``meta.json``; when it cannot be resolved (no ``.kittify`` / typeless legacy
    feature) it falls back to the packaged ``software-dev`` writer metadata —
    still a canonical source, not a second hardcoded copy. Directory artifacts
    are distinguished from file artifacts by a trailing ``/`` in the metadata.
    """
    from specify_cli.mission import (
        MISSION_TYPE_SOFTWARE_DEV,
        MissionError,
        get_mission_by_name,
        get_mission_for_feature,
    )

    try:
        mission = get_mission_for_feature(feature_dir)
    except MissionError:
        try:
            mission = get_mission_by_name(MISSION_TYPE_SOFTWARE_DEV)
        except MissionError:
            return [], []

    artifacts = [*mission.get_required_artifacts(), *mission.get_optional_artifacts()]
    file_artifacts = [name for name in artifacts if not name.endswith("/")]
    dir_artifacts = [name for name in artifacts if name.endswith("/")]
    return file_artifacts, dir_artifacts


def _inventory_writer_artifacts(
    feature_dir: Path,
    *,
    paths: dict[str, str],
    artifact_files: dict[str, str],
    artifact_dirs: dict[str, str],
    available_docs: list[str],
) -> None:
    """Populate the artifact inventory from the mission writer metadata.

    Only artifacts that exist on disk are recorded (no false positives). Keys are
    derived deterministically so callers/templates see stable ``*_file`` /
    ``*_dir`` aliases (FR-010).
    """
    file_artifacts, dir_artifacts = _feature_writer_artifacts(feature_dir)

    for name in file_artifacts:
        candidate = feature_dir / name
        if not candidate.is_file():
            continue
        candidate_str = str(candidate)
        key = _artifact_inventory_key(name, "file")
        paths.setdefault(key, candidate_str)
        artifact_files.setdefault(key, candidate_str)
        available_docs.append(name)

    for name in dir_artifacts:
        candidate = feature_dir / name.rstrip("/")
        if not candidate.is_dir():
            continue
        candidate_str = str(candidate)
        key = _artifact_inventory_key(name, "dir")
        paths.setdefault(key, candidate_str)
        artifact_dirs.setdefault(key, candidate_str)


def validate_feature_structure(feature_dir: Path, check_tasks: bool = False) -> dict[str, Any]:
    """Validate feature directory structure and required files.

    Checks for:
    - Required files: spec.md
    - Recommended directories: checklists/, research/, tasks/
    - Optional: tasks.md (if check_tasks=True)

    Args:
        feature_dir: Feature directory path
        check_tasks: If True, validate tasks.md and task files exist

    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "errors": [list of error messages],
            "warnings": [list of warning messages],
            "paths": {dict of important paths}
        }

    Examples:
        >>> feature_dir = Path("/path/to/kitty-specs/001-feature")
        >>> result = validate_feature_structure(feature_dir)
        >>> assert "valid" in result
        >>> assert "errors" in result
    """
    errors: list[str] = []
    warnings_list: list[str] = []
    paths: dict[str, str] = {}
    artifact_files: dict[str, str] = {}
    artifact_dirs: dict[str, str] = {}
    available_docs: list[str] = []

    # Check if feature directory exists
    if not feature_dir.exists():
        errors.append(f"Feature directory not found: {feature_dir}")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings_list,
            "paths": paths,
            "artifact_files": artifact_files,
            "artifact_dirs": artifact_dirs,
            "available_docs": available_docs,
            "FEATURE_DIR": "",
            "AVAILABLE_DOCS": available_docs,
        }

    # Check required files exist
    spec_file = feature_dir / "spec.md"
    if not spec_file.exists():
        errors.append("Missing required file: spec.md")
    else:
        spec_file_str = str(spec_file)
        paths["spec_file"] = spec_file_str
        artifact_files["spec_file"] = spec_file_str
        available_docs.append("spec.md")

    plan_file = feature_dir / "plan.md"
    if plan_file.exists():
        plan_file_str = str(plan_file)
        paths["plan_file"] = plan_file_str
        artifact_files["plan_file"] = plan_file_str
        available_docs.append("plan.md")

    # Check recommended directory structure (warnings only). ``research`` is
    # warned about for legacy-layout familiarity, but the research *artifact* is
    # the file ``research.md`` (inventoried from writer metadata below), NOT a
    # directory — so a bare ``research/`` directory is deliberately excluded from
    # the ``*_dir`` inventory (FR-010 research_dir file-vs-dir fix).
    for dir_name in _RECOMMENDED_LAYOUT_DIRS:
        if not (feature_dir / dir_name).exists():
            warnings_list.append(f"Missing recommended directory: {dir_name}/")
    for dir_name in _STRUCTURAL_ARTIFACT_DIRS:
        dir_path = feature_dir / dir_name
        if dir_path.exists():
            dir_path_str = str(dir_path)
            paths[f"{dir_name}_dir"] = dir_path_str
            artifact_dirs[f"{dir_name}_dir"] = dir_path_str

    # Check task files if requested
    if check_tasks:
        tasks_file = feature_dir / "tasks.md"
        if not tasks_file.exists():
            errors.append("Missing required file: tasks.md")
        else:
            tasks_file_str = str(tasks_file)
            paths["tasks_file"] = tasks_file_str
            artifact_files["tasks_file"] = tasks_file_str
            if "tasks.md" not in available_docs:
                available_docs.append("tasks.md")
    else:
        tasks_file = feature_dir / "tasks.md"
        if tasks_file.exists():
            tasks_file_str = str(tasks_file)
            paths["tasks_file"] = tasks_file_str
            artifact_files["tasks_file"] = tasks_file_str
            available_docs.append("tasks.md")

    # Always include feature_dir in paths
    feature_dir_str = str(feature_dir)
    paths["feature_dir"] = feature_dir_str
    artifact_dirs["feature_dir"] = feature_dir_str

    # Inventory the planning artifacts the mission writer actually produces
    # (research.md, data-model.md, quickstart.md, contracts/, …) from the
    # canonical writer metadata rather than a hardcoded spec/plan/tasks set
    # (FR-010 / C-005). Only artifacts present on disk are recorded.
    _inventory_writer_artifacts(
        feature_dir,
        paths=paths,
        artifact_files=artifact_files,
        artifact_dirs=artifact_dirs,
        available_docs=available_docs,
    )

    available_docs = sorted(set(available_docs))

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings_list,
        "paths": paths,
        "artifact_files": artifact_files,
        "artifact_dirs": artifact_dirs,
        "available_docs": available_docs,
        # Compatibility aliases for older templates/prompts
        "FEATURE_DIR": feature_dir_str,
        "AVAILABLE_DOCS": available_docs,
    }
