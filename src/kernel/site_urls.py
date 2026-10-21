"""Single authority for the web addresses Spec Kitty owns (#6468).

Every first-party URL the CLI prints or the shipped schemas carry is built from
:data:`OWNED_DOMAIN`, so a link can never again point at a domain nobody
registered: user-facing documentation links (``specify_cli.docs_links``) start
at :data:`DOCS_BASE_URL`, and schema ``$id``\\ s (``scripts/generate_schemas.py``
and the hand-written schema files) start at ``https://<OWNED_DOMAIN>/schemas``.

``tests/architectural/test_first_party_hosts_are_owned.py`` fails on any
Spec Kitty-branded host under ``src/``, ``scripts/`` or ``packs/`` that is not
:data:`OWNED_DOMAIN` or one of its subdomains.

Layer rule: ``kernel`` imports nothing upward, so every layer can read these.
"""

from __future__ import annotations

__all__ = ["DOCS_BASE_URL"]

#: The one registrable domain Spec Kitty owns for its branded hosts.
OWNED_DOMAIN = "spec-kitty.ai"

#: The published documentation site (``docs/CNAME``).
DOCS_BASE_URL = f"https://docs.{OWNED_DOMAIN}"
