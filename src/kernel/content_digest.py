"""The one raw-bytes SHA-256 digest owner (``sha256:<hex>`` format).

Provenance checksums (skills manifest ``content_hash``, pack-skill
``source_hash``) share this single format and implementation. This is *not*
the charter freshness hash (``charter.hasher.hash_content`` normalises and
strips text); it digests the exact bytes it is given.
"""

from __future__ import annotations

import hashlib

__all__ = ["sha256_digest"]

_DIGEST_PREFIX = "sha256:"


def sha256_digest(data: bytes) -> str:
    """Return ``sha256:<hex>`` over *data* (exact bytes, no normalisation)."""
    digest = hashlib.sha256(data)  # noqa: TID251 - the single sanctioned raw-bytes SHA-256 owner; hash_content would normalize and strip
    return f"{_DIGEST_PREFIX}{digest.hexdigest()}"
