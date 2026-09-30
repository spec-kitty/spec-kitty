"""Version detection for Spec Kitty projects.

Primary detection reads ``spec_kitty.schema_version`` from
``.kittify/metadata.yaml``.  Legacy projects without that field are treated as
schema version 0 (needs migration).  All heuristic file/directory checks have
been removed — the schema version integer is the sole source of truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .metadata import ProjectMetadata

if TYPE_CHECKING:
    from .migrations.base import BaseMigration


class VersionDetector:
    """Detects the schema version of a project from its metadata."""

    def __init__(self, project_path: Path) -> None:
        """Initialise the detector.

        Args:
            project_path: Root of the project (parent of ``.kittify/``).
        """
        self.project_path = project_path
        self.kittify_dir = project_path / ".kittify"

    def detect_version(self) -> str:
        """Return the project version string from metadata.yaml.

        Returns:
            The ``spec_kitty.version`` string stored in metadata, or
            ``"unknown"`` when the file is absent or unreadable.
        """
        if not self.kittify_dir.exists():
            return "unknown"

        metadata = ProjectMetadata.load(self.kittify_dir)
        if metadata is not None:
            return metadata.version

        return "unknown"

    def applicable_migrations(self, target_version: str) -> list[BaseMigration]:
        """Return the migrations a real upgrade run would apply.

        This is the single source of truth for "what is pending": it mirrors the
        real run's selection in ``upgrade`` exactly — the same
        ``"unknown" -> "0.0.0"`` normalization, the same
        :meth:`MigrationRegistry.get_applicable` call, and the same
        ``project_path`` so current-version ``detect()`` migrations are included.
        The compat-planner preview and the ``--dry-run`` preview both consult
        this method so the reported pending set can never diverge from the
        applied set (FR-009 / SC-004).

        Args:
            target_version: Version string to upgrade to (e.g. ``"2.1.3"``).

        Returns:
            Applicable migration instances, in application order.
        """
        from .migrations import auto_discover_migrations
        from .registry import MigrationRegistry

        auto_discover_migrations()
        current = self.detect_version()
        from_version = "0.0.0" if current == "unknown" else current
        applicable: list[BaseMigration] = MigrationRegistry.get_applicable(
            from_version, target_version, project_path=self.project_path
        )
        return applicable
