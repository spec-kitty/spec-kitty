"""kernel.content_digest: the one ``sha256:<hex>`` bytes digest."""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.content_digest import sha256_digest
from specify_cli.skills.manifest import compute_content_hash

pytestmark = pytest.mark.fast

EMPTY = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_digest_is_prefixed_and_known() -> None:
    assert sha256_digest(b"") == EMPTY


def test_manifest_content_hash_delegates_to_the_kernel_digest(tmp_path: Path) -> None:
    target = tmp_path / "f"
    target.write_bytes(b"a\r\nb")
    # Literal digest computed independently with hashlib.sha256(b"a\r\nb"): a format change in either helper fails here.
    assert compute_content_hash(target) == "sha256:18745f36a05e29072709042d6062ce54f1b08ff36c27ba80c39f81fb010c8ce2"
    assert compute_content_hash(target) == sha256_digest(b"a\r\nb")
