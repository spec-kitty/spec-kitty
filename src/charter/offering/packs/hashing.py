"""The sanctioned raw SHA-256 owners for charter pack and synthesis manifests.

Both the charter ``SynthesisManifest`` (``charter.activation.synthesizer.manifest``)
and the unified ``PackManifest`` (:mod:`charter.offering.packs.pack_manifest`) hash
through these two functions, so no second manifest hasher exists (RR-SF2 / T005).
They live in the offering tier so the pack model can use them without importing
``charter.activation``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from charter.offering.yaml_utils import canonical_yaml


def hash_manifest_payload(data: Mapping[str, Any], *, exclude_keys: frozenset[str]) -> str:
    """Single canonical manifest hasher — SHA-256 of ``canonical_yaml(payload)``.

    The **one** manifest-hashing primitive, shared by both the charter
    ``SynthesisManifest`` (via ``compute_manifest_hash``) and the unified
    ``PackManifest``. No second hasher is ever introduced (RR-SF2 / T005).

    Every key in ``exclude_keys`` is dropped before serialization so callers
    can omit self / provenance fields (``manifest_hash``, and the volatile
    ``generated_at`` / ``generated_by`` for the pack manifest) from the digest.
    """
    filtered = {k: v for k, v in data.items() if k not in exclude_keys}
    return hashlib.sha256(canonical_yaml(filtered)).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def hash_content_bytes(raw: bytes) -> str:
    """SHA-256 hex digest of raw artifact bytes (single sanctioned hasher).

    Callers are responsible for any normalization (e.g. LF line-ending
    normalization for cross-platform-stable ``content_hash`` values) before
    passing bytes here, so this stays a thin, auditable owner of the raw SHA.
    """
    return hashlib.sha256(raw).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


__all__ = ["hash_content_bytes", "hash_manifest_payload"]
