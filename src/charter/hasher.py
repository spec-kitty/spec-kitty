"""SHA-256 hasher for charter content."""

import hashlib
from pathlib import Path

from ruamel.yaml import YAML

from kernel.text_decode import normalize_newlines

__all__ = [
    "hash_content",
    "is_stale",
]


def hash_content(content: str) -> str:
    """Generate SHA-256 hash of charter content.

    Args:
        content: Charter markdown text

    Returns:
        Hash string in format "sha256:hexdigest"

    Normalization (FR-009 / C2-e): a leading BOM is dropped and line endings
    are canonicalised to ``\\n`` before hashing, so the staleness decision is
    BOM- and newline-agnostic. The two charter read surfaces normalise content
    DIFFERENTLY — ``charter sync`` reads via the encoding chokepoint
    (``read_bytes().decode()``, which strips the BOM and preserves ``\\r\\n``)
    while ``charter status`` / the freshness computer read via ``read_text``
    (which keeps the BOM as ``\\ufeff`` but collapses ``\\r\\n`` to ``\\n`` via
    universal-newline translation). Without this normalization a CRLF/BOM
    charter produces divergent hashes, so ``sync`` reports ``noop`` while
    ``status``/freshness report ``stale`` (the C2-e "noop-despite-stale"
    drift). Canonicalising here is the single ``hash_content`` seam every
    surface routes through, so they agree regardless of how they decoded.
    """
    # Drop a leading BOM (``read_text`` keeps it, the chokepoint strips it),
    # normalize line endings (CRLF/CR -> LF) via the shared kernel primitive
    # (one newline rule, DIRECTIVE_044), then strip outer whitespace so
    # the hash is stable across the two divergent decoding read surfaces.
    normalized = normalize_newlines(content.lstrip("\ufeff")).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
    return f"sha256:{digest}"


def hash_charter(charter_path: Path) -> str:
    """Compute SHA-256 hash of charter file.

    Args:
        charter_path: Path to charter.md file

    Returns:
        Hash string in format "sha256:hexdigest"
    """
    content = charter_path.read_text("utf-8")
    return hash_content(content)


def is_stale(charter_path: Path | None, metadata_path: Path, content: str | None = None) -> tuple[bool, str, str]:
    """Check if charter has changed since last sync.

    Args:
        charter_path: Path to charter.md (None if using content directly)
        metadata_path: Path to metadata.yaml
        content: Optional pre-read content (avoids TOCTOU race condition)

    Returns:
        Tuple of (is_stale, current_hash, stored_hash)
        - is_stale: True if charter needs re-extraction
        - current_hash: Hash of current charter content
        - stored_hash: Hash from metadata.yaml (empty string if no metadata)
    """
    if content is not None:
        current_hash = hash_content(content)
    elif charter_path is not None:
        current_hash = hash_charter(charter_path)
    else:
        raise ValueError("Either charter_path or content must be provided")

    if not metadata_path.exists():
        return True, current_hash, ""

    yaml = YAML()
    metadata = yaml.load(metadata_path)
    stored_hash = metadata.get("charter_hash", "") if metadata else ""

    return current_hash != stored_hash, current_hash, stored_hash
