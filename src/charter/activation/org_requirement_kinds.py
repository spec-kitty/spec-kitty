"""Org-tier ``requirement-kinds.yaml`` resolver (#5956 loader seam).

Sibling of :mod:`charter.activation.org_expected_artifacts`: iterates the org
pack chain, ``<root>/missions/<mission_type>/requirement-kinds.yaml``, last
matching file wins, whole-file (never field-merged). A present-but-unparseable
file raises :class:`~charter.offering.missions.repository.MalformedManifestError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.missions.repository import MalformedManifestError

__all__ = ["REQUIREMENT_KINDS_FILENAME", "read_requirement_kinds_file", "resolve_org_requirement_kinds"]

REQUIREMENT_KINDS_FILENAME = "requirement-kinds.yaml"


def resolve_org_requirement_kinds(chain: list[Path], mission_type: str) -> Mapping[str, Any] | None:
    """Return the parsed org-tier file for *mission_type*, last matching file wins.

    ``None`` only for genuine absence across the whole chain.
    """
    result: Mapping[str, Any] | None = None
    for root in chain:
        parsed = read_requirement_kinds_file(root / "missions" / mission_type / REQUIREMENT_KINDS_FILENAME)
        if parsed is not None:
            result = parsed
    return result


def read_requirement_kinds_file(path: Path) -> Mapping[str, Any] | None:
    """Read *path* as a YAML mapping; ``None`` only when the file is absent."""
    if not path.is_file():
        return None
    try:
        parsed = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        raise MalformedManifestError(path, exc) from exc
    if not isinstance(parsed, Mapping):
        raise MalformedManifestError(path, TypeError(f"expected a YAML mapping, got {type(parsed).__name__}"))
    return parsed
