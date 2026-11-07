"""Mission directory structure helpers.

Lane checkouts are created only by ``specify_cli.lanes.lane_checkout``
(Mission ``lane-worktree-model-hardening-01M6QY1M`` WP09, FR-021). The legacy
worktree creators that lived here (``create_wp_workspace``,
``create_feature_worktree``) and their directory scaffolding
(``setup_feature_directory``) had no production caller and were removed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


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

    # Always include the mission directory in paths; ``feature_dir`` is the
    # legacy alias key kept for older prompts (#5206).
    feature_dir_str = str(feature_dir)
    paths["mission_dir"] = feature_dir_str
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
        "mission_dir": feature_dir_str,
        # Compatibility aliases for older templates/prompts
        "FEATURE_DIR": feature_dir_str,
        "AVAILABLE_DOCS": available_docs,
    }
