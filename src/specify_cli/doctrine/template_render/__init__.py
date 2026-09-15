"""Template render helpers for ``spec-kitty doctrine org init --template``.

WP01 delivers validation and TEMPLATE resolve. WP02 adds ignore-copy /
substitute / pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specify_cli.doctrine.template_render.resolve import (
    ParsedTemplate,
    ResolveError,
    ResolvedTemplateSource,
    merge_branch_refs,
    parse_template_ref,
    resolve_template_source,
)
from specify_cli.doctrine.template_render.validation import (
    ValidationResult,
    validate_local_path,
    validate_org_name,
)

DEFAULT_LOCAL_PATH = "pack"

__all__ = [
    "DEFAULT_LOCAL_PATH",
    "ParsedTemplate",
    "RenderRequest",
    "ResolveError",
    "ResolvedTemplateSource",
    "ValidationResult",
    "merge_branch_refs",
    "parse_template_ref",
    "resolve_template_source",
    "validate_local_path",
    "validate_org_name",
]


@dataclass(frozen=True, slots=True)
class RenderRequest:
    """Inputs for a template render (consumed by WP02 pipeline / WP03 CLI)."""

    pack_path: Path
    template: str | None
    org_name: str | None = None
    local_path: str | None = None
    branch: str | None = None
    force: bool = False
