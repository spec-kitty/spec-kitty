"""kernel.content_digest: the one ``sha256:<hex>`` bytes digest."""

from __future__ import annotations

from pathlib import Path

from kernel.content_digest import sha256_digest
from specify_cli.skills.manifest import compute_content_hash

EMPTY = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_digest_is_prefixed_and_known() -> None:
    assert sha256_digest(b"") == EMPTY


def test_manifest_content_hash_delegates_to_the_kernel_digest(tmp_path: Path) -> None:
    target = tmp_path / "f"
    target.write_bytes(b"a\r\nb")
    assert compute_content_hash(target) == sha256_digest(b"a\r\nb")
