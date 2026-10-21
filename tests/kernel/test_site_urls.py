"""Every shipped first-party address is built from the one owned domain (#6468)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from ruamel.yaml import YAML

from kernel.site_urls import DOCS_BASE_URL, OWNED_DOMAIN
from scripts.generate_schemas import SCHEMA_ID_BASE

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_FILES = sorted((_REPO_ROOT / "src/charter/offering/schemas").glob("*.schema.yaml")) + [
    _REPO_ROOT / "src/specify_cli/skills/data/skills-manifest.schema.json"
]


def _schema_id(path: Path) -> object:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8")).get("$id")
    return YAML(typ="safe").load(path.read_text(encoding="utf-8")).get("$id")


def test_docs_base_is_the_owned_docs_site() -> None:
    cname = (_REPO_ROOT / "docs" / "CNAME").read_text(encoding="utf-8").strip()
    assert urlsplit(DOCS_BASE_URL) == ("https", cname, "", "", "")
    assert cname.endswith("." + OWNED_DOMAIN)


def test_schema_id_base_is_on_the_owned_domain() -> None:
    assert urlsplit(SCHEMA_ID_BASE)[:2] == ("https", OWNED_DOMAIN)


def test_every_shipped_schema_id_starts_at_the_base() -> None:
    assert len(_SCHEMA_FILES) >= 14
    ids = {path.name: _schema_id(path) for path in _SCHEMA_FILES}
    off_base = {name: schema_id for name, schema_id in ids.items() if schema_id is not None and not str(schema_id).startswith(SCHEMA_ID_BASE + "/")}
    assert off_base == {}
    assert sum(schema_id is not None for schema_id in ids.values()) >= 14
