"""Single authority for the web addresses Spec Kitty owns (#6468).

Every first-party URL the CLI prints or the shipped schemas carry is built from
:data:`OWNED_DOMAIN`, so a link can never again point at a domain nobody
registered. User-facing documentation links start at :data:`DOCS_BASE_URL`;
schema ``$id``\\ s (``scripts/generate_schemas.py`` and the hand-written schema
files) start at ``https://<OWNED_DOMAIN>/schemas``.

A docs page is named by its path under ``docs/`` in this repository, without
the ``.md`` suffix; ``tests/kernel/test_site_urls.py`` resolves every page named
here against the ``docs/`` tree, so a moved guide reds there instead of printing
a dead link. ``tests/architectural/test_first_party_hosts_are_owned.py`` fails
on any Spec Kitty-branded host under ``src/``, ``scripts/`` or ``packs/`` that is
not :data:`OWNED_DOMAIN` or one of its subdomains.

Layer rule: ``kernel`` imports nothing upward, so every layer can read these.
"""

from __future__ import annotations

__all__ = [
    "DOCS_BASE_URL",
    "INSTALL_AND_UPGRADE_PAGE",
    "INSTALL_AND_UPGRADE_URL",
    "OWNED_DOMAIN",
    "docs_url",
]

#: The one registrable domain Spec Kitty owns for its branded hosts.
OWNED_DOMAIN = "spec-kitty.ai"

#: The published documentation site (``docs/CNAME``).
DOCS_BASE_URL = f"https://docs.{OWNED_DOMAIN}"

#: Install and upgrade guide: ``docs/guides/how-to/installation/install-and-upgrade.md``.
INSTALL_AND_UPGRADE_PAGE = "guides/how-to/installation/install-and-upgrade"


def docs_url(page: str) -> str:
    """Return the published URL of the docs page at ``docs/<page>.md``."""
    return f"{DOCS_BASE_URL}/{page.strip('/')}"


INSTALL_AND_UPGRADE_URL = docs_url(INSTALL_AND_UPGRADE_PAGE)
