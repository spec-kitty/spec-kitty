"""Write a ``charter_packs.org.packs`` block into a test project's ``.kittify/config.yaml``.

Production has no writer for the org-pack registry (mission
``charter-pack-cutover-01M491G6`` deleted the unused ``save_pack_registry``,
#3732); tests that need a configured org pack write the canonical block with
this helper. Other keys already in the file are kept.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def write_org_packs(repo_root: Path, packs: Sequence[Mapping[str, Any]]) -> Path:
    """Set ``charter_packs.org.packs`` to *packs* (each a mapping with ``name`` and ``local_path``)."""
    config_path = repo_root / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    existing = yaml.load(config_path.read_text(encoding="utf-8")) if config_path.exists() else None
    config: dict[str, Any] = dict(existing) if isinstance(existing, Mapping) else {}
    section = config.get("charter_packs")
    section = dict(section) if isinstance(section, Mapping) else {}
    section["org"] = {"packs": [{key: str(value) if isinstance(value, Path) else value for key, value in pack.items()} for pack in packs]}
    config["charter_packs"] = section
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(config, handle)
    return config_path
