"""Owner of the ``sha256:<hex>`` provenance format used by the skills manifest.

The skills manifest ``content_hash`` and the pack-skill ``source_hash`` share this
one format and implementation. It is not the repository's only SHA-256 use (other
modules hash for their own purposes) and it is *not* the charter freshness hash
(``charter.hasher.hash_content`` normalises and strips text); it digests the exact
bytes it is given.
"""

from __future__ import annotations

import hashlib

__all__ = ["sha256_digest"]

_DIGEST_PREFIX = "sha256:"


def sha256_digest(data: bytes) -> str:
    """Return ``sha256:<hex>`` over *data* (exact bytes, no normalisation)."""
    digest = hashlib.sha256(data)  # noqa: TID251 - sanctioned owner of the sha256:<hex> provenance format; hash_content would normalize and strip
    return f"{_DIGEST_PREFIX}{digest.hexdigest()}"
