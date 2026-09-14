"""
Directive repository with two-source loading (built-in + project).

Provides:
- Two-source YAML loading (built-in package data + project filesystem)
- Field-level merge semantics for project overrides
- Query methods (list_all, get)
- Save for project directives
- ID normalization (accepts both "004" and "DIRECTIVE_004")
"""

import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.migration.id_normalizer import normalize_directive_id
from charter.offering.pack_paths import built_in_dir
from charter.offering.base import BaseDoctrineRepository
from .models import Directive
from .validation import reject_directive_inline_refs


class DirectiveRepository(BaseDoctrineRepository[Directive]):
    """Repository for loading and managing directive YAML files."""

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
        """Get default built-in directives directory from package data."""
        return built_in_dir(ArtifactKind.DIRECTIVE)

    @property
    def _schema(self) -> type[Directive]:
        return Directive

    @property
    def _glob(self) -> str:
        return "*.directive.yaml"

    def _pre_validate(self, data: dict[str, Any], yaml_file: Path) -> None:
        reject_directive_inline_refs(data, file_path=str(yaml_file))

    @staticmethod
    def _normalize_id(directive_id: str) -> str:
        """Normalize a directive identifier to the canonical ``DIRECTIVE_NNN`` form.

        Delegates to the single canonical authority
        (:func:`charter.offering.drg.migration.id_normalizer.normalize_directive_id`)
        so this repository, the ``--include directive:<id>`` selector, and the
        DRG migration pipeline all resolve identifiers through one algorithm
        rather than three drifting copies (#3816). Accepts:

        - ``"004"`` / ``"4"`` → ``"DIRECTIVE_004"`` (numeric shorthand)
        - ``"DIRECTIVE_004"`` → ``"DIRECTIVE_004"`` (pass-through)
        - ``"025-boy-scout-rule"`` → ``"DIRECTIVE_025"`` (the file-stem slug the
          ``--json`` / action-index surface advertises)
        - ``"use-c4-model-techniques"`` → ``"USE_C4_MODEL_TECHNIQUES"`` (a
          slug-named hub directive, folded to its UPPER_SNAKE ``id:``)
        """
        return normalize_directive_id(directive_id)

    def get(self, directive_id: str) -> Directive | None:
        """Get directive by exact declared ID, with normalized aliases as fallback.

        Accepts numeric shorthand ("004"), full ID ("DIRECTIVE_004"), and the
        file-stem slug the ``--json`` surface advertises ("025-boy-scout-rule").
        """
        if directive_id in self._items:
            return self._items[directive_id]
        return self._items.get(self._normalize_id(directive_id))

    def save(self, directive: Directive) -> Path:
        """Save directive to project directory.

        Returns:
            Path to the written YAML file.

        Raises:
            ValueError: If project_dir is not configured.
        """
        if self._project_dir is None:
            raise ValueError("Cannot save directive: project_dir not configured")

        self._project_dir.mkdir(parents=True, exist_ok=True)

        # Derive filename from ID
        match = re.search(r"\d+", directive.id)
        numeric = match.group() if match else directive.id.lower()
        slug = directive.title.lower().replace(" ", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        filename = f"{numeric}-{slug}.directive.yaml"

        yaml = YAML()
        yaml.default_flow_style = False
        yaml_file = self._project_dir / filename

        data = directive.model_dump(mode="json", exclude_none=True)

        with yaml_file.open("w") as f:
            yaml.dump(data, f)

        self._items[directive.id] = directive
        return yaml_file
