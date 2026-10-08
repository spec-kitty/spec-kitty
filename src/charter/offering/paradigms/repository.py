"""
Paradigm repository with two-source loading (built-in + project).
"""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from charter.offering.base import BaseArtifactRepository
from .models import Paradigm
from .validation import reject_paradigm_inline_refs


class ParadigmRepository(BaseArtifactRepository[Paradigm]):
    """Repository for loading and managing paradigm YAML files."""

    def __init__(
        self,
        built_in_dir: Path | None = None,
        *,
        org_dirs: list[Path] | None = None,
        project_dir: Path | None = None,
    ) -> None:
        super().__init__(
            built_in_dir=built_in_dir or self._default_built_in_dir(),
            org_dirs=org_dirs,
            project_dir=project_dir,
        )

    @staticmethod
    def _default_built_in_dir() -> Path:
        """Get default built-in paradigms directory from package data."""
        return built_in_dir(ArtifactKind.PARADIGM)

    @property
    def _schema(self) -> type[Paradigm]:
        return Paradigm

    @property
    def _glob(self) -> str:
        return "*.paradigm.yaml"

    def _pre_validate(self, data: dict[str, Any], yaml_file: Path) -> None:
        reject_paradigm_inline_refs(data, file_path=str(yaml_file))

    def save(self, paradigm: Paradigm) -> Path:
        """Save paradigm to project directory."""
        if self._project_dir is None:
            raise ValueError("Cannot save paradigm: project_dir not configured")

        self._project_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{paradigm.id}.paradigm.yaml"
        yaml = YAML()
        yaml.default_flow_style = False
        yaml_file = self._project_dir / filename

        data = paradigm.model_dump(mode="json", exclude_none=True)
        with yaml_file.open("w") as f:
            yaml.dump(data, f)

        self._items[paradigm.id] = paradigm
        return yaml_file
