"""The CLI's documentation links resolve to a real page on a domain Spec Kitty owns (#6468)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest

from specify_cli import docs_links
from specify_cli.compat._detect.install_method import InstallMethod
from specify_cli.compat.remediation import RemediationIntent, _manual_note
from specify_cli.compat.upgrade_hint import build_upgrade_hint

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_docs_base_is_the_published_site() -> None:
    """The base is the host named by ``docs/CNAME``, the site GitHub Pages serves."""
    cname = (_REPO_ROOT / "docs" / "CNAME").read_text(encoding="utf-8").strip()
    assert urlsplit(docs_links.DOCS_BASE_URL) == ("https", cname, "", "", "")


def test_install_and_upgrade_page_exists() -> None:
    assert (_REPO_ROOT / "docs" / f"{docs_links.INSTALL_AND_UPGRADE_PAGE}.md").is_file()


@pytest.mark.parametrize("page", ["guides/x", "/guides/x", "guides/x/"])
def test_docs_url_joins_one_slash(page: str) -> None:
    assert docs_links.docs_url(page) == f"{docs_links.DOCS_BASE_URL}/guides/x"


def test_unknown_install_hint_links_the_install_guide() -> None:
    note = build_upgrade_hint(InstallMethod.UNKNOWN).note
    assert note is not None
    assert docs_links.INSTALL_AND_UPGRADE_URL in note


def test_unknown_upgrade_remediation_links_the_install_guide() -> None:
    """Both call sites print the same link, so they cannot drift apart again."""
    note = _manual_note("unknown", RemediationIntent.UPGRADE)
    assert note is not None
    assert docs_links.INSTALL_AND_UPGRADE_URL in note
