"""
Styleguide repository with two-source loading (built-in + project).

Provides:
- Two-source YAML loading (built-in package data + project filesystem)
- Recursive scan to handle subdirectory structure (e.g. writing/)
- Field-level merge semantics for project overrides
- Query methods (list_all, get)
- Save for project styleguides
"""

import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from charter.offering.base import BaseArtifactRepository
from .models import Styleguide
from .validation import reject_styleguide_inline_refs


class StyleguideRepository(BaseArtifactRepository[Styleguide]):
    """Repository for loading and managing styleguide YAML files."""

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
        """Get default built-in styleguides directory from package data."""
        return built_in_dir(ArtifactKind.STYLEGUIDE)

    @property
    def _schema(self) -> type[Styleguide]:
        return Styleguide

    @property
    def _glob(self) -> str:
        return "*.styleguide.yaml"

    def _pre_validate(self, data: dict[str, Any], yaml_file: Path) -> None:
        reject_styleguide_inline_refs(data, file_path=str(yaml_file))

    def _merge(self, built_in: Styleguide, project_data: dict[str, Any]) -> Styleguide:
        merged = {**built_in.model_dump(exclude_defaults=True), **project_data}
        return Styleguide.model_validate(merged)

    def save(self, styleguide: Styleguide) -> Path:
        """Save styleguide to project directory.

        Returns:
            Path to the written YAML file.

        Raises:
            ValueError: If project_dir is not configured.
        """
        if self._project_dir is None:
            raise ValueError(
                "Cannot save styleguide: project_dir not configured"
            )

        self._project_dir.mkdir(parents=True, exist_ok=True)

        slug = re.sub(r"[^a-z0-9-]", "", styleguide.id)
        filename = f"{slug}.styleguide.yaml"
        yaml = YAML()
        yaml.default_flow_style = False
        yaml_file = self._project_dir / filename

        data = styleguide.model_dump(
            mode="json", exclude_defaults=True, exclude_none=True
        )

        with yaml_file.open("w") as f:
            yaml.dump(data, f)

        self._items[styleguide.id] = styleguide
        return yaml_file
