"""
Procedure repository with two-source loading (built-in + project).
"""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from charter.offering.base import BaseArtifactRepository
from .models import Procedure
from .validation import reject_procedure_inline_refs


class ProcedureRepository(BaseArtifactRepository[Procedure]):
    """Repository for loading and managing procedure YAML files."""

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
        """Get default built-in procedures directory from package data."""
        return built_in_dir(ArtifactKind.PROCEDURE)

    @property
    def _schema(self) -> type[Procedure]:
        return Procedure

    @property
    def _glob(self) -> str:
        return "*.procedure.yaml"

    def _pre_validate(self, data: dict[str, Any], yaml_file: Path) -> None:
        reject_procedure_inline_refs(data, file_path=str(yaml_file))

    def save(self, procedure: Procedure) -> Path:
        """Save procedure to project directory."""
        if self._project_dir is None:
            raise ValueError("Cannot save procedure: project_dir not configured")

        self._project_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{procedure.id}.procedure.yaml"
        yaml = YAML()
        yaml.default_flow_style = False
        yaml_file = self._project_dir / filename

        data = procedure.model_dump(mode="json", exclude_none=True)
        with yaml_file.open("w") as f:
            yaml.dump(data, f)

        self._items[procedure.id] = procedure
        return yaml_file
