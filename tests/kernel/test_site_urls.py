"""Every shipped first-party address is built from the one owned domain (#6468)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest

from kernel import site_urls
from kernel.site_urls import DOCS_BASE_URL, OWNED_DOMAIN

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_docs_base_is_the_owned_docs_site() -> None:
    cname = (_REPO_ROOT / "docs" / "CNAME").read_text(encoding="utf-8").strip()
    assert urlsplit(DOCS_BASE_URL) == ("https", cname, "", "", "")
    assert cname.endswith("." + OWNED_DOMAIN)


def test_install_and_upgrade_page_exists() -> None:
    assert (_REPO_ROOT / "docs" / f"{site_urls.INSTALL_AND_UPGRADE_PAGE}.md").is_file()


def test_docs_url_joins_one_slash() -> None:
    assert site_urls.docs_url("/guides/x/") == f"{DOCS_BASE_URL}/guides/x"
