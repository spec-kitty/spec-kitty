"""Every shipped first-party address is built from the one owned domain (#6468)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from ruamel.yaml import YAML

from specify_cli.compat._detect.install_method import InstallMethod
from specify_cli.compat.remediation import RemediationIntent, _manual_note
from specify_cli.compat.upgrade_hint import build_upgrade_hint

from kernel import site_urls
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


def test_every_shipped_schema_id_starts_at_the_base() -> None:
    assert urlsplit(SCHEMA_ID_BASE)[:2] == ("https", OWNED_DOMAIN)
    assert len(_SCHEMA_FILES) >= 14
    ids = {path.name: _schema_id(path) for path in _SCHEMA_FILES}
    off_base = {name: schema_id for name, schema_id in ids.items() if schema_id is not None and not str(schema_id).startswith(SCHEMA_ID_BASE + "/")}
    assert off_base == {}
    assert sum(schema_id is not None for schema_id in ids.values()) >= 14


def test_install_and_upgrade_page_exists() -> None:
    assert (_REPO_ROOT / "docs" / f"{site_urls.INSTALL_AND_UPGRADE_PAGE}.md").is_file()


def test_docs_url_joins_one_slash() -> None:
    assert site_urls.docs_url("/guides/x/") == f"{DOCS_BASE_URL}/guides/x"


def test_unknown_install_hint_links_the_install_guide() -> None:
    note = build_upgrade_hint(InstallMethod.UNKNOWN).note
    assert note is not None
    assert site_urls.INSTALL_AND_UPGRADE_URL in note


def test_unknown_upgrade_remediation_links_the_install_guide() -> None:
    """Both call sites print the same link, so they cannot drift apart again."""
    note = _manual_note("unknown", RemediationIntent.UPGRADE)
    assert note is not None
    assert site_urls.INSTALL_AND_UPGRADE_URL in note
