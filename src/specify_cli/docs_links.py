"""Links to the published Spec Kitty documentation that the CLI prints.

Every documentation URL the CLI shows a user is built here, from one base, so
two call sites cannot drift to different paths and no message points at a host
Spec Kitty does not own (#6468: the old links named a domain nobody had
registered).

A page is named by its path under ``docs/`` in this repository, without the
``.md`` suffix. ``tests/specify_cli/test_docs_links.py`` resolves every page
named here against the ``docs/`` tree, so a moved guide reds there instead of
printing a dead link.
"""

from __future__ import annotations

from kernel.site_urls import DOCS_BASE_URL

__all__ = ["INSTALL_AND_UPGRADE_URL"]

#: Install and upgrade guide: ``docs/guides/how-to/installation/install-and-upgrade.md``.
INSTALL_AND_UPGRADE_PAGE = "guides/how-to/installation/install-and-upgrade"


def docs_url(page: str) -> str:
    """Return the published URL of the docs page at ``docs/<page>.md``."""
    return f"{DOCS_BASE_URL}/{page.strip('/')}"


INSTALL_AND_UPGRADE_URL = docs_url(INSTALL_AND_UPGRADE_PAGE)
