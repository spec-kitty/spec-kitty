"""
Toolguide repository with two-source loading (built-in + project).
"""

import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from charter.offering.base import BaseArtifactRepository
from .models import Toolguide
from .validation import reject_toolguide_inline_refs


class ToolguideRepository(BaseArtifactRepository[Toolguide]):
    """Repository for loading and managing toolguide YAML files."""

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
        """Return the shipped built-in toolguides directory (``packs/built-in/toolguides/``)."""
        return built_in_dir(ArtifactKind.TOOLGUIDE)

    @property
    def _schema(self) -> type[Toolguide]:
        return Toolguide

    @property
    def _glob(self) -> str:
        return "*.toolguide.yaml"

    def _pre_validate(self, data: dict[str, Any], yaml_file: Path) -> None:
        reject_toolguide_inline_refs(data, file_path=str(yaml_file))

    def save(self, toolguide: Toolguide) -> Path:
        if self._project_dir is None:
            raise ValueError("Cannot save toolguide: project_dir not configured")

        self._project_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9-]", "", toolguide.id)
        filename = f"{slug}.toolguide.yaml"
        yaml = YAML()
        yaml.default_flow_style = False
        yaml_file = self._project_dir / filename
        data = toolguide.model_dump(mode="json", exclude_none=True)
        with yaml_file.open("w") as f:
            yaml.dump(data, f)
        self._items[toolguide.id] = toolguide
        return yaml_file
