"""Shared runtime-detection helpers used by multiple migrations."""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from pathlib import Path

from packaging.version import InvalidVersion, Version

from specify_cli.runtime.home import get_kittify_home

from .metadata import ProjectMetadata


def global_runtime_configured() -> bool:
    """Return True when ``~/.kittify`` has been bootstrapped."""
    try:
        home = get_kittify_home()
    except RuntimeError:
        return False
    return (home / "cache" / "version.lock").is_file()


def uses_centralized_runtime(project_path: Path) -> bool:
    """Return True when project state indicates 2.x global runtime usage.

    The project's own ``.kittify/metadata.yaml`` stamp is the first and, for any
    dated project, the only input (#6551). A stamp at ``>= 2.0.0`` means the
    project was created or last migrated by a CLI that keeps missions in the
    global runtime, so project-local missions are optional -- regardless of which
    machine runs the migration.

    Consulting the operator's home first made this answer depend on the *person*,
    not the project: ``upgrade`` deliberately does not bootstrap ``~/.kittify``
    before running migrations (#3900), so on a second machine or a fresh CI runner
    ``0.6.7_ensure_missions`` and ``0.12.0_documentation_mission`` re-ran for a 4.x
    project and copied the packaged missions in. Ledger-diff re-evaluates a
    ``skipped`` record on every run (ADR 2026-10-17-1 §3), which is only idempotent
    while ``detect()`` is a function of project state.

    The home is still consulted, but only for the metadata-less shapes where
    there is no project stamp to read:

    * metadata-less path with ``.kittify/`` present -- ambiguous, so it keeps
      receiving the legacy repair migrations;
    * metadata-less worktree without ``.kittify/`` -- runtime-managed only when
      the home has actually been bootstrapped.

    An unparseable stamp (including the ``"unknown"`` default, and an unquoted
    numeric stamp that YAML parses as a float) is not treated as modern: a
    project we cannot date keeps today's legacy answer.
    """
    kittify_dir = project_path / ".kittify"
    metadata = ProjectMetadata.load(kittify_dir)
    if metadata is not None:
        try:
            return Version(metadata.version) >= Version("2.0.0")
        except (InvalidVersion, TypeError):
            # ``TypeError`` is an unquoted numeric stamp (``version: 2.0`` parses
            # as a float, not a string). Both mean "cannot date this project",
            # which is not evidence of a 2.x runtime.
            return False

    if not global_runtime_configured():
        return False

    return not kittify_dir.exists() and (project_path / KITTY_SPECS_DIR).exists()
