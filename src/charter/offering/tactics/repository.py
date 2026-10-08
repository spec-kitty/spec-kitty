"""
Tactic repository with two-source loading (built-in + project).

Provides:
- Two-source YAML loading (built-in package data + project filesystem)
- Field-level merge semantics for project overrides
- Query methods (list_all, get)
- Save for project tactics
"""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from charter.offering.base import BaseArtifactRepository
from .models import Tactic
from .validation import reject_tactic_inline_refs


class TacticRepository(BaseArtifactRepository[Tactic]):
    """Repository for loading and managing tactic YAML files."""

    def __init__(
        self,
        built_in_dir: Path | None = None,
        *,
        org_dirs: list[Path] | None = None,
        project_dir: Path | None = None,
        active_languages: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(
            built_in_dir=built_in_dir or self._default_built_in_dir(),
            org_dirs=org_dirs,
            project_dir=project_dir,
            active_languages=active_languages,
        )

    @staticmethod
    def _default_built_in_dir() -> Path:
        """Get default built-in tactics directory from package data."""
        return built_in_dir(ArtifactKind.TACTIC)

    @property
    def _schema(self) -> type[Tactic]:
        return Tactic

    @property
    def _glob(self) -> str:
        return "*.tactic.yaml"

    def _pre_validate(self, data: dict[str, Any], yaml_file: Path) -> None:
        reject_tactic_inline_refs(data, file_path=str(yaml_file))

    def save(self, tactic: Tactic) -> Path:
        """Save tactic to project directory.

        Returns:
            Path to the written YAML file.

        Raises:
            ValueError: If project_dir is not configured.
        """
        if self._project_dir is None:
            raise ValueError("Cannot save tactic: project_dir not configured")

        self._project_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{tactic.id}.tactic.yaml"
        yaml = YAML()
        yaml.default_flow_style = False
        yaml_file = self._project_dir / filename

        data = tactic.model_dump(mode="json", exclude_none=True)

        with yaml_file.open("w") as f:
            yaml.dump(data, f)

        self._items[tactic.id] = tactic
        return yaml_file
