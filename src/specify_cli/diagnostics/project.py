"""Project diagnostics behind ``spec-kitty verify --diagnostics``.

Moved out of the retired bundled dashboard package (#5530); the dashboard
health probe went with the dashboard.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from charter.activation.mission_type_key import read_mission_type

if TYPE_CHECKING:
    from specify_cli.manifest import WorktreeStatus

__all__ = ["run_diagnostics"]


def _resolve_mission_from_feature(feature_dir: Path) -> str | None:
    """Resolve mission key from a feature's meta.json."""
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError:
        # Best-effort diagnostics probe: a corrupt meta.json degrades to
        # "mission unknown" rather than breaking the diagnostics report.
        return None
    # rc3 M5 (FR-002): canonical field only via the one shared reader — the
    # legacy `mission` fallback is retired.
    if meta:
        mission_type: str | None = read_mission_type(meta)
        return mission_type
    return None


def _detect_git_branch(project_dir: Path, diagnostics: dict[str, Any]) -> None:
    """Populate diagnostics['git_branch'] and related worktree flags."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        diagnostics["git_branch"] = result.stdout.strip()
    except subprocess.CalledProcessError:
        diagnostics["issues"].append("Could not detect git branch")


def _collect_current_feature(
    feature_dir: Path | None,
    worktree_status: WorktreeStatus,
    diagnostics: dict[str, Any],
) -> None:
    """Populate diagnostics['current_feature'] from the provided feature_dir."""
    try:
        mission_slug: str | None = feature_dir.name if feature_dir is not None else None
        if mission_slug:
            feature_status = worktree_status.get_feature_status(mission_slug.strip())
            diagnostics["current_feature"] = {
                "detected": True,
                "name": mission_slug.strip(),
                "state": feature_status["state"],
                "branch_exists": feature_status["branch_exists"],
                "branch_merged": feature_status["branch_merged"],
                "worktree_exists": feature_status["worktree_exists"],
                "worktree_path": feature_status["worktree_path"],
                "artifacts_in_main": feature_status["artifacts_in_main"],
                "artifacts_in_worktree": feature_status["artifacts_in_worktree"],
            }
    except Exception as exc:  # best-effort probe: report the failure, never abort the diagnostics run
        diagnostics["current_feature"] = {"detected": False, "error": str(exc)}


def _build_observations(
    diagnostics: dict[str, Any],
    primary: str,
    worktree_summary: dict[str, Any],
    total_missing: int,
) -> list[str]:
    """Return a list of human-readable observations about the project state."""
    observations: list[str] = []
    if diagnostics["git_branch"] == primary and diagnostics["in_worktree"]:
        observations.append("Unusual: In worktree but on main branch")
    current_feature = diagnostics.get("current_feature") or {}
    in_development = current_feature.get("detected") and current_feature.get("state") == "in_development"
    if in_development and not current_feature.get("worktree_exists"):
        observations.append(f"Mission {current_feature.get('name')} has no worktree but has development artifacts")
    if total_missing > 0:
        observations.append(f"Mission integrity: {total_missing} expected files not found")
    if worktree_summary.get("active_worktrees", 0) > 5:
        observations.append(f"Multiple worktrees active: {worktree_summary['active_worktrees']}")
    return observations


def run_diagnostics(project_dir: Path, *, feature_dir: Path | None = None) -> dict[str, Any]:
    """Run comprehensive diagnostics on the project setup using enhanced verification."""
    # Imported lazily so callers (and tests) can substitute lightweight stubs.
    from specify_cli.manifest import FileManifest, WorktreeStatus

    kittify_dir = project_dir / ".kittify"
    mission_type = _resolve_mission_from_feature(feature_dir) if feature_dir is not None else None

    manifest = FileManifest(kittify_dir, mission_type=mission_type)
    worktree_status = WorktreeStatus(project_dir)

    diagnostics: dict[str, Any] = {
        "project_path": str(project_dir),
        "current_working_directory": str(Path.cwd()),
        "git_branch": None,
        "in_worktree": ".worktrees" in str(Path.cwd()),
        "worktrees_exist": (project_dir / ".worktrees").exists(),
        "active_mission": mission_type or "no mission context",
        "file_integrity": {},
        "worktree_overview": {},
        "current_feature": {},
        "all_features": [],
        "observations": [],
        "issues": [],
    }

    _detect_git_branch(project_dir, diagnostics)

    file_check = manifest.check_files()
    expected_files = manifest.get_expected_files()
    total_missing = len(file_check["missing"])
    diagnostics["file_integrity"] = {
        "total_expected": sum(len(f) for f in expected_files.values()),
        "total_present": len(file_check["present"]),
        "total_missing": total_missing,
        "missing_files": list(file_check["missing"].keys()) if file_check["missing"] else [],
    }

    worktree_summary = worktree_status.get_worktree_summary()
    diagnostics["worktree_overview"] = worktree_summary
    diagnostics["all_features"] = [
        {
            "name": slug,
            "state": s["state"],
            "branch_exists": s["branch_exists"],
            "branch_merged": s["branch_merged"],
            "worktree_exists": s["worktree_exists"],
            "worktree_path": s["worktree_path"],
            "artifacts_in_main": s["artifacts_in_main"],
            "artifacts_in_worktree": s["artifacts_in_worktree"],
        }
        for slug in worktree_status.get_all_features()
        for s in [worktree_status.get_feature_status(slug)]
    ]

    _collect_current_feature(feature_dir, worktree_status, diagnostics)

    from specify_cli.core.git_ops import resolve_primary_branch

    primary = resolve_primary_branch(project_dir)
    diagnostics["observations"] = _build_observations(diagnostics, primary, worktree_summary, total_missing)

    return diagnostics
